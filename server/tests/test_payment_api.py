import os
import sys
import time
from types import SimpleNamespace

import pytest
import stripe  # type: ignore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(BASE_DIR)
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from app import app  # noqa: E402
from auth.session_manager import SessionManager  # noqa: E402
from api.payment import SESSION_COOKIE  # noqa: E402


@pytest.fixture()
def client():  # type: ignore
    app.testing = True
    with app.test_client() as c:
        yield c


def _create_session(client, *, sub='user_sub', email='user@example.com'):
    session_id = 'sess-test-123'
    exp = int(time.time()) + 3600
    SessionManager.save_session(session_id, {
        'sub': sub,
        'email': email,
        'exp': exp,
        'ts': time.time()
    }, exp)
    client.set_cookie(SESSION_COOKIE, session_id, domain='localhost', path='/')
    return session_id


def _cleanup_session(session_id, client):
    SessionManager.delete_session(session_id)
    client.delete_cookie(SESSION_COOKIE, domain='localhost', path='/')


def test_create_checkout_session_requires_auth(client, monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_dummy')

    resp = client.post('/api/payment/create-checkout-session', json={'price_usd': 10, 'coins': 100})
    assert resp.status_code == 401


def test_create_checkout_session_success(client, monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_dummy')

    created_kwargs = {}

    def fake_create(**kwargs):
        created_kwargs.update(kwargs)
        return SimpleNamespace(id='cs_test_123', url='https://stripe.test/checkout/cs_test_123')

    monkeypatch.setattr(stripe.checkout.Session, 'create', fake_create)

    recorded_payload = {}

    def fake_record_checkout_session(**kwargs):
        recorded_payload.update(kwargs)
        return True

    monkeypatch.setattr('api.payment.payment_store.record_checkout_session', fake_record_checkout_session)

    def fake_get_user(identifier):
        if identifier in ('user_sub', 'user@example.com'):
            return {
                'id': 'user-uuid',
                'email': 'user@example.com',
                'coin_balance': 200
            }
        return None

    monkeypatch.setattr('api.payment.get_user', fake_get_user)

    session_id = _create_session(client)

    resp = client.post('/api/payment/create-checkout-session', json={'price_usd': 19.99, 'coins': 200, 'bonus': 20, 'origin': 'https://frontend.test'})
    try:
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['session_id'] == 'cs_test_123'
        assert payload['checkout_url'].startswith('https://stripe.test/checkout')

        assert created_kwargs['client_reference_id'] == 'user-uuid'
        assert created_kwargs['line_items'][0]['price_data']['unit_amount'] == 1999
        assert created_kwargs['line_items'][0]['price_data']['currency'] == 'usd'
        assert created_kwargs['metadata']['coins'] == '200'

        assert recorded_payload['user_id'] == 'user-uuid'
        assert recorded_payload['coins_purchased'] == 200
        assert recorded_payload['coins_bonus'] == 20
        assert recorded_payload['amount_cents'] == 1999
    finally:
        _cleanup_session(session_id, client)


def test_payment_status_completed(client, monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_dummy')

    def fake_get_user(identifier):
        if identifier == 'user_sub':
            return {
                'id': 'user-uuid',
                'email': 'user@example.com',
                'coin_balance': 150
            }
        if identifier == 'user@example.com':
            return {
                'id': 'user-uuid',
                'email': 'user@example.com',
                'coin_balance': 300
            }
        return None

    monkeypatch.setattr('api.payment.get_user', fake_get_user)

    def fake_get_topup_by_session(session_id, provider='stripe'):
        return {
            'user_id': 'user-uuid',
            'amount_cents': 4999,
            'coins_purchased': 400,
            'coins_bonus': 80,
            'coins_total': 480,
            'status': 'completed'
        }

    monkeypatch.setattr('api.payment.payment_store.get_topup_by_session', fake_get_topup_by_session)

    session_id = _create_session(client)

    try:
        resp = client.get('/api/payment/status/cs_test_123')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['status'] == 'completed'
        assert payload['coins_total'] == 480
        assert payload['coins_added'] == 480
        assert payload['new_balance'] == 300
    finally:
        _cleanup_session(session_id, client)


def test_payment_status_forbidden(client, monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_dummy')

    def fake_get_user(identifier):
        if identifier in ('user_sub', 'user@example.com'):
            return {
                'id': 'user-uuid',
                'email': 'user@example.com',
                'coin_balance': 100
            }
        return None

    monkeypatch.setattr('api.payment.get_user', fake_get_user)

    def fake_get_topup_by_session(session_id, provider='stripe'):
        return {
            'user_id': 'other-user',
            'amount_cents': 1000,
            'coins_purchased': 100,
            'coins_bonus': 0,
            'coins_total': 100,
            'status': 'pending'
        }

    monkeypatch.setattr('api.payment.payment_store.get_topup_by_session', fake_get_topup_by_session)

    session_id = _create_session(client)
    try:
        resp = client.get('/api/payment/status/cs_forbidden')
        assert resp.status_code == 403
    finally:
        _cleanup_session(session_id, client)


def test_webhook_completed_event(client, monkeypatch):
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_test')

    captured = {}

    def fake_construct_event(payload, sig_header, secret):  # noqa: D401
        return {
            'type': 'checkout.session.completed',
            'data': {'object': {'id': 'cs_test_123', 'amount_total': 1999}}
        }

    monkeypatch.setattr(stripe.Webhook, 'construct_event', fake_construct_event)

    def fake_complete_topup(session_id, provider='stripe', amount_cents=None):
        captured['session_id'] = session_id
        captured['amount_cents'] = amount_cents
        return {'user_id': 'user-uuid', 'coins_total': 100, 'new_balance': 500}

    monkeypatch.setattr('api.payment.payment_store.complete_topup', fake_complete_topup)

    resp = client.post('/api/payment/webhook', data=b'{}', headers={'Stripe-Signature': 'sig_test'})
    assert resp.status_code == 200
    assert captured['session_id'] == 'cs_test_123'
    assert captured['amount_cents'] == 1999


def test_webhook_missing_signature(client, monkeypatch):
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_test')

    resp = client.post('/api/payment/webhook', data=b'{}')
    assert resp.status_code == 400