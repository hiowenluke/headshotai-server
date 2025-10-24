"""Database helpers for coin top-ups processed via Stripe payments."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from . import db as core_db

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = 'stripe'


def _open_transaction_connection():
    """Open a dedicated transactional connection when possible.

    The shared connection in ``core_db`` runs in autocommit mode. For operations
    that should be atomic (e.g. crediting coins exactly once) we prefer to work
    on a short-lived transactional connection. If creating such a connection
    fails we gracefully fall back to the shared autocommit connection.
    """

    dsn = getattr(core_db, '_dsn_cache', None) or getattr(core_db, '_build_dsn', lambda: None)()
    if not dsn:
        return None
    try:
        import psycopg  # type: ignore

        return psycopg.connect(dsn, autocommit=False)
    except Exception as exc:  # pragma: no cover - defensive logging path
        logger.warning('payments: failed to open transactional connection: %s', exc)
        return None


def record_checkout_session(
    *,
    user_id: str,
    session_id: str,
    amount_cents: int,
    coins_purchased: int,
    coins_bonus: int,
    provider: str = DEFAULT_PROVIDER,
    status: str = 'pending'
) -> bool:
    """Insert or update a ``coin_topups`` record for a Stripe checkout session.

    Returns ``True`` when a database row exists afterwards, ``False`` if the
    database connection is unavailable or the insert/update fails.
    """

    conn = core_db.get_conn()
    if not conn:
        logger.error('payments: database connection not available while recording session')
        return False

    coins_total = coins_purchased + coins_bonus

    sql = (
        """
        INSERT INTO coin_topups (
            user_id, amount_cents, coins_purchased, coins_bonus, coins_total,
            payment_provider, payment_tx_id, status
        )
        VALUES (%(user_id)s, %(amount_cents)s, %(coins_purchased)s, %(coins_bonus)s,
                %(coins_total)s, %(provider)s, %(session_id)s, %(status)s)
        ON CONFLICT (payment_provider, payment_tx_id)
        DO UPDATE SET
            amount_cents = EXCLUDED.amount_cents,
            coins_purchased = EXCLUDED.coins_purchased,
            coins_bonus = EXCLUDED.coins_bonus,
            coins_total = EXCLUDED.coins_total,
            status = EXCLUDED.status
        RETURNING id
        """
    )

    params = {
        'user_id': user_id,
        'amount_cents': amount_cents,
        'coins_purchased': coins_purchased,
        'coins_bonus': coins_bonus,
        'coins_total': coins_total,
        'provider': provider,
        'session_id': session_id,
        'status': status
    }

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cur.fetchone()
        return True
    except Exception:
        logger.exception('payments: failed to record checkout session')
        return False


def get_topup_by_session(
    session_id: str,
    *,
    provider: str = DEFAULT_PROVIDER
) -> Optional[Dict[str, Any]]:
    """Fetch a ``coin_topups`` record by provider/session id."""

    conn = core_db.get_conn()
    if not conn:
        return None

    sql = (
        """
        SELECT
            user_id,
            amount_cents,
            coins_purchased,
            coins_bonus,
            coins_total,
            status,
            payment_provider,
            payment_tx_id,
            created_at
        FROM coin_topups
        WHERE payment_provider = %(provider)s AND payment_tx_id = %(session_id)s
        """
    )

    try:
        with conn.cursor() as cur:
            cur.execute(sql, {'provider': provider, 'session_id': session_id})
            row = cur.fetchone()
            if not row:
                return None
    except Exception:
        logger.exception('payments: failed to load top-up record')
        return None

    return {
        'user_id': row[0],
        'amount_cents': int(row[1]) if row[1] is not None else None,
        'coins_purchased': int(row[2]) if row[2] is not None else None,
        'coins_bonus': int(row[3]) if row[3] is not None else None,
        'coins_total': int(row[4]) if row[4] is not None else None,
        'status': row[5],
        'payment_provider': row[6],
        'payment_tx_id': row[7],
        'created_at': row[8]
    }


def update_topup_status(
    session_id: str,
    status: str,
    *,
    provider: str = DEFAULT_PROVIDER,
    amount_cents: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Update the status of a top-up if it hasn't been completed yet."""

    conn = core_db.get_conn()
    if not conn:
        return None

    sql = (
        """
        UPDATE coin_topups
        SET status = %(status)s,
            amount_cents = COALESCE(%(amount_cents)s, amount_cents)
        WHERE payment_provider = %(provider)s AND payment_tx_id = %(session_id)s
          AND status <> 'completed'
        RETURNING user_id, coins_total, status
        """
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    'status': status,
                    'amount_cents': amount_cents,
                    'provider': provider,
                    'session_id': session_id
                }
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                'user_id': row[0],
                'coins_total': int(row[1]) if row[1] is not None else None,
                'status': row[2]
            }
    except Exception:
        logger.exception('payments: failed to update top-up status')
        return None


def complete_topup(
    session_id: str,
    *,
    provider: str = DEFAULT_PROVIDER,
    amount_cents: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Mark a top-up as completed and credit coins to the user.

    Returns a dictionary containing ``user_id``, ``coins_total`` and the user's
    new balance when the operation succeeds. Returns ``None`` if the record does
    not exist, was already completed, or if the database interaction fails.
    """

    tx_conn = _open_transaction_connection()
    conn = tx_conn or core_db.get_conn()
    if not conn:
        return None

    update_sql = (
        """
        UPDATE coin_topups
        SET status = 'completed',
            amount_cents = COALESCE(%(amount_cents)s, amount_cents)
        WHERE payment_provider = %(provider)s AND payment_tx_id = %(session_id)s
          AND status <> 'completed'
        RETURNING user_id, coins_total
        """
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                update_sql,
                {
                    'amount_cents': amount_cents,
                    'provider': provider,
                    'session_id': session_id
                }
            )
            row = cur.fetchone()
            if not row:
                if tx_conn:
                    tx_conn.commit()
                return None

            user_id, coins_total = row
            coins_total_int = int(coins_total) if coins_total is not None else 0

            cur.execute(
                "UPDATE users SET coin_balance = coin_balance + %s WHERE id = %s RETURNING coin_balance",
                (coins_total_int, user_id)
            )
            balance_row = cur.fetchone()
            new_balance = int(balance_row[0]) if balance_row and balance_row[0] is not None else None

        if tx_conn:
            tx_conn.commit()

        return {
            'user_id': user_id,
            'coins_total': coins_total_int,
            'new_balance': new_balance
        }
    except Exception:
        if tx_conn:
            try:
                tx_conn.rollback()
            except Exception:  # pragma: no cover - cleanup path
                pass
        logger.exception('payments: failed to complete top-up')
        return None
    finally:
        if tx_conn:
            try:
                tx_conn.close()
            except Exception:  # pragma: no cover - defensive cleanup
                pass
