"""Stripe payment API endpoints."""
from __future__ import annotations

import os
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Optional, Tuple

import stripe  # type: ignore
from flask import Blueprint, current_app, jsonify, request

from auth.session_manager import SessionManager
from database.db import get_user
from database import payments as payment_store

bp = Blueprint('payment_api', __name__)

SESSION_COOKIE = os.environ.get('SESSION_COOKIE_NAME', 'app_session')


def _get_authenticated_session() -> Optional[Dict[str, Any]]:
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return None
    data = SessionManager.get_session(sid)
    if not data:
        return None
    exp = data.get('exp')
    if exp and exp < time.time():
        return None
    return data


def _load_current_user(session_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ident = session_data.get('sub') or session_data.get('email')
    if not ident:
        return None

    user = get_user(str(ident))
    if not user:
        email = session_data.get('email')
        if email:
            user = get_user(str(email))
    return user


def _stripe_secret_key() -> Optional[str]:
    return os.environ.get('STRIPE_SECRET_KEY')


def _ensure_stripe_ready() -> Optional[Tuple[Any, int]]:
    secret = _stripe_secret_key()
    if not secret:
        return jsonify({'error': 'stripe_not_configured'}), 503
    stripe.api_key = secret
    return None


def _parse_checkout_payload(data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[Any, int]]]:
    try:
        price = data.get('price_usd')
        price_decimal = Decimal(str(price))
    except (InvalidOperation, TypeError):
        return None, (jsonify({'error': 'invalid_price'}), 400)
    if price_decimal <= 0:
        return None, (jsonify({'error': 'invalid_price'}), 400)

    coins = data.get('coins')
    try:
        coins_int = int(coins)
    except (TypeError, ValueError):
        return None, (jsonify({'error': 'invalid_coins'}), 400)
    if coins_int <= 0:
        return None, (jsonify({'error': 'invalid_coins'}), 400)

    bonus = data.get('bonus', 0)
    try:
        bonus_int = int(bonus)
    except (TypeError, ValueError):
        return None, (jsonify({'error': 'invalid_bonus'}), 400)
    if bonus_int < 0:
        return None, (jsonify({'error': 'invalid_bonus'}), 400)

    currency = (data.get('currency') or 'usd').lower()
    if len(currency) != 3:
        return None, (jsonify({'error': 'invalid_currency'}), 400)

    amount_cents = int((price_decimal * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    origin = data.get('origin') or request.headers.get('Origin')
    if origin:
        origin = str(origin).rstrip('/')
    else:
        origin = (request.host_url or '').rstrip('/')
    if not origin or not (origin.startswith('http://') or origin.startswith('https://')):
        return None, (jsonify({'error': 'invalid_origin'}), 400)

    success_url = data.get('success_url') or f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = data.get('cancel_url') or f"{origin}/payment/cancel"
    if not (success_url.startswith('http://') or success_url.startswith('https://')):
        return None, (jsonify({'error': 'invalid_success_url'}), 400)
    if not (cancel_url.startswith('http://') or cancel_url.startswith('https://')):
        return None, (jsonify({'error': 'invalid_cancel_url'}), 400)

    plan_id = data.get('plan_id')

    return {
        'price_decimal': price_decimal,
        'amount_cents': amount_cents,
        'coins': coins_int,
        'bonus': bonus_int,
        'total_coins': coins_int + bonus_int,
        'currency': currency,
        'success_url': success_url,
        'cancel_url': cancel_url,
        'plan_id': plan_id
    }, None


@bp.route('/api/payment/create-checkout-session', methods=['POST', 'OPTIONS'])
def create_checkout_session():
    if request.method == 'OPTIONS':
        return jsonify({'ok': True})

    error_response = _ensure_stripe_ready()
    if error_response:
        response, status = error_response
        return response, status

    session_data = _get_authenticated_session()
    if not session_data:
        return jsonify({'error': 'not_authenticated'}), 401

    user = _load_current_user(session_data)
    if not user:
        return jsonify({'error': 'user_not_found'}), 404

    payload = request.get_json(silent=True) or {}
    parsed, parse_error = _parse_checkout_payload(payload)
    if parse_error:
        response, status = parse_error
        return response, status

    metadata = {
        'user_id': str(user['id']),
        'user_email': str(user.get('email') or ''),
        'coins': str(parsed['coins']),
        'bonus': str(parsed['bonus']),
        'total_coins': str(parsed['total_coins']),
        'price_usd': str(parsed['price_decimal']),
    }
    if parsed['plan_id']:
        metadata['plan_id'] = str(parsed['plan_id'])

    customer_email = session_data.get('email') or user.get('email')

    metadata_for_intent = dict(metadata)

    checkout_kwargs: Dict[str, Any] = {
        'payment_method_types': ['card'],
        'line_items': [{
            'price_data': {
                'currency': parsed['currency'],
                'product_data': {
                    'name': f"{parsed['coins']} Coins",
                    'description': (
                        f"{parsed['coins']} coins" + (f" + {parsed['bonus']} bonus" if parsed['bonus'] else '')
                    )
                },
                'unit_amount': parsed['amount_cents']
            },
            'quantity': 1
        }],
        'mode': 'payment',
        'success_url': parsed['success_url'],
        'cancel_url': parsed['cancel_url'],
        'client_reference_id': str(user['id']),
        'metadata': metadata,
        'payment_intent_data': {'metadata': metadata_for_intent}
    }
    if customer_email:
        checkout_kwargs['customer_email'] = customer_email

    try:
        checkout_session = stripe.checkout.Session.create(**checkout_kwargs)
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        current_app.logger.error('stripe: failed to create checkout session: %s', exc)
        return jsonify({'error': 'stripe_error'}), 502

    recorded = payment_store.record_checkout_session(
        user_id=str(user['id']),
        session_id=checkout_session.id,
        amount_cents=parsed['amount_cents'],
        coins_purchased=parsed['coins'],
        coins_bonus=parsed['bonus'],
        provider='stripe',
        status='pending'
    )

    if not recorded:
        current_app.logger.error('stripe: failed to persist checkout session %s', checkout_session.id)
        return jsonify({'error': 'session_persist_failed'}), 500

    return jsonify({
        'session_id': checkout_session.id,
        'checkout_url': checkout_session.url
    })


@bp.route('/api/payment/status/<session_id>', methods=['GET'])
def payment_status(session_id: str):
    session_data = _get_authenticated_session()
    if not session_data:
        return jsonify({'error': 'not_authenticated'}), 401

    user = _load_current_user(session_data)
    if not user:
        return jsonify({'error': 'user_not_found'}), 404

    topup = payment_store.get_topup_by_session(session_id, provider='stripe')
    if not topup:
        return jsonify({'error': 'not_found'}), 404

    if str(topup['user_id']) != str(user['id']):
        return jsonify({'error': 'forbidden'}), 403

    latest_user = get_user(str(user.get('email') or user.get('id')))
    new_balance = latest_user.get('coin_balance') if latest_user else user.get('coin_balance')

    response: Dict[str, Any] = {
        'status': topup['status'],
        'session_id': session_id,
        'coins_purchased': topup.get('coins_purchased'),
        'coins_bonus': topup.get('coins_bonus'),
        'coins_total': topup.get('coins_total'),
        'amount_cents': topup.get('amount_cents'),
        'currency': 'usd',
        'new_balance': new_balance
    }

    if topup['status'] == 'completed':
        response['coins_added'] = topup.get('coins_total')

    return jsonify(response)


@bp.route('/api/payment/webhook', methods=['POST'])
def stripe_webhook():
    secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    if not secret:
        current_app.logger.error('stripe: webhook secret not configured')
        return jsonify({'error': 'webhook_not_configured'}), 503

    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    if not sig_header:
        return jsonify({'error': 'missing_signature'}), 400

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except ValueError:
        return jsonify({'error': 'invalid_payload'}), 400
    except stripe.error.SignatureVerificationError:  # type: ignore[attr-defined]
        return jsonify({'error': 'invalid_signature'}), 400

    event_type = event.get('type')
    obj = event.get('data', {}).get('object', {})
    session_id = obj.get('id') if isinstance(obj, dict) else None
    amount_total = obj.get('amount_total') if isinstance(obj, dict) else None

    if event_type in {'checkout.session.completed', 'checkout.session.async_payment_succeeded'} and session_id:
        result = payment_store.complete_topup(session_id, provider='stripe', amount_cents=amount_total)
        if not result:
            current_app.logger.warning('stripe: top-up completion skipped or failed for session %s', session_id)
    elif event_type in {'checkout.session.expired', 'checkout.session.async_payment_failed'} and session_id:
        payment_store.update_topup_status(session_id, 'expired', provider='stripe', amount_cents=amount_total)
    elif event_type == 'checkout.session.canceled' and session_id:
        payment_store.update_topup_status(session_id, 'canceled', provider='stripe', amount_cents=amount_total)
    return jsonify({'status': 'ok'})
