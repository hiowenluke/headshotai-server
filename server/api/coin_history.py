"""Coin history API endpoints - 金币历史记录接口"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify

from auth.session_manager import SessionManager
from database.db import get_user, get_conn

bp = Blueprint('coin_history_api', __name__)

SESSION_COOKIE = os.environ.get('SESSION_COOKIE_NAME', 'app_session')


def _get_authenticated_session() -> Optional[Dict[str, Any]]:
    """获取已认证的 session"""
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
    """加载当前用户"""
    ident = session_data.get('sub') or session_data.get('email')
    if not ident:
        return None

    user = get_user(str(ident))
    if not user:
        email = session_data.get('email')
        if email:
            user = get_user(str(email))
    return user


@bp.route('/api/coins/topup-history', methods=['GET'])
def get_topup_history():
    """获取充值历史
    
    Query Parameters:
        limit: 返回记录数量，默认 20，最大 100
        offset: 偏移量，默认 0
        status: 过滤状态 (pending/completed/expired/canceled)，可选
    
    Returns:
        {
            "items": [
                {
                    "id": "uuid",
                    "created_at": "2025-10-26T12:00:00Z",
                    "amount_usd": 99.99,
                    "coins_purchased": 1000,
                    "coins_bonus": 200,
                    "coins_total": 1200,
                    "status": "completed",
                    "payment_provider": "stripe",
                    "payment_tx_id": "cs_xxx"
                }
            ],
            "total": 10,
            "limit": 20,
            "offset": 0
        }
    """
    session_data = _get_authenticated_session()
    if not session_data:
        return jsonify({'error': 'not_authenticated'}), 401

    user = _load_current_user(session_data)
    if not user:
        return jsonify({'error': 'user_not_found'}), 404

    # 获取查询参数
    try:
        limit = min(int(request.args.get('limit', 20)), 100)
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return jsonify({'error': 'invalid_parameters'}), 400
    
    status_filter = request.args.get('status')
    
    conn = get_conn()
    if not conn:
        return jsonify({'error': 'database_unavailable'}), 503

    user_id = str(user['id'])
    
    # 构建查询
    where_clause = 'WHERE user_id = %s'
    params = [user_id]
    
    if status_filter:
        where_clause += ' AND status = %s'
        params.append(status_filter)
    
    # 查询总数
    count_sql = f'SELECT COUNT(*) FROM coin_topups {where_clause}'
    
    # 查询数据
    data_sql = f'''
        SELECT 
            id, created_at, amount_cents, coins_purchased, coins_bonus, 
            coins_total, status, payment_provider, payment_tx_id
        FROM coin_topups
        {where_clause}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    '''
    
    try:
        with conn.cursor() as cur:
            # 获取总数
            cur.execute(count_sql, params)
            total = cur.fetchone()[0]
            
            # 获取数据
            cur.execute(data_sql, params + [limit, offset])
            rows = cur.fetchall()
            
            items = []
            for row in rows:
                items.append({
                    'id': str(row[0]),
                    'created_at': row[1].isoformat() if row[1] else None,
                    'amount_usd': float(row[2]) / 100 if row[2] else 0,  # 转换为美元
                    'coins_purchased': int(row[3]) if row[3] else 0,
                    'coins_bonus': int(row[4]) if row[4] else 0,
                    'coins_total': int(row[5]) if row[5] else 0,
                    'status': row[6],
                    'payment_provider': row[7],
                    'payment_tx_id': row[8]
                })
            
            return jsonify({
                'items': items,
                'total': total,
                'limit': limit,
                'offset': offset
            })
    
    except Exception as e:
        import logging
        logging.exception('Failed to fetch topup history')
        return jsonify({'error': 'database_error'}), 500


@bp.route('/api/coins/spending-history', methods=['GET'])
def get_spending_history():
    """获取消费历史
    
    Query Parameters:
        limit: 返回记录数量，默认 20，最大 100
        offset: 偏移量，默认 0
    
    Returns:
        {
            "items": [
                {
                    "id": "uuid",
                    "created_at": "2025-10-26T12:00:00Z",
                    "service_name": "AI Headshot Generation",
                    "service_quantity": 1,
                    "coin_unit_price": 100,
                    "coins_spent": 100,
                    "product_name": "Headshot AI"
                }
            ],
            "total": 50,
            "limit": 20,
            "offset": 0
        }
    """
    session_data = _get_authenticated_session()
    if not session_data:
        return jsonify({'error': 'not_authenticated'}), 401

    user = _load_current_user(session_data)
    if not user:
        return jsonify({'error': 'user_not_found'}), 404

    # 获取查询参数
    try:
        limit = min(int(request.args.get('limit', 20)), 100)
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return jsonify({'error': 'invalid_parameters'}), 400
    
    conn = get_conn()
    if not conn:
        return jsonify({'error': 'database_unavailable'}), 503

    user_id = str(user['id'])
    
    # 查询总数
    count_sql = 'SELECT COUNT(*) FROM coin_spendings WHERE user_id = %s'
    
    # 查询数据（关联 services 和 products 表获取名称）
    data_sql = '''
        SELECT 
            cs.id, cs.created_at, cs.service_quantity, cs.coin_unit_price, 
            cs.coins_spent, s.name as service_name, p.name as product_name
        FROM coin_spendings cs
        LEFT JOIN services s ON cs.service_id = s.id
        LEFT JOIN products p ON cs.product_id = p.id
        WHERE cs.user_id = %s
        ORDER BY cs.created_at DESC
        LIMIT %s OFFSET %s
    '''
    
    try:
        with conn.cursor() as cur:
            # 获取总数
            cur.execute(count_sql, [user_id])
            total = cur.fetchone()[0]
            
            # 获取数据
            cur.execute(data_sql, [user_id, limit, offset])
            rows = cur.fetchall()
            
            items = []
            for row in rows:
                items.append({
                    'id': str(row[0]),
                    'created_at': row[1].isoformat() if row[1] else None,
                    'service_quantity': int(row[2]) if row[2] else 0,
                    'coin_unit_price': int(row[3]) if row[3] else 0,
                    'coins_spent': int(row[4]) if row[4] else 0,
                    'service_name': row[5] or 'Unknown Service',
                    'product_name': row[6] or 'Unknown Product'
                })
            
            return jsonify({
                'items': items,
                'total': total,
                'limit': limit,
                'offset': offset
            })
    
    except Exception as e:
        import logging
        logging.exception('Failed to fetch spending history')
        return jsonify({'error': 'database_error'}), 500


@bp.route('/api/coins/summary', methods=['GET'])
def get_coin_summary():
    """获取金币统计摘要
    
    Returns:
        {
            "current_balance": 1200,
            "total_purchased": 5000,
            "total_bonus": 1000,
            "total_spent": 4800,
            "total_topups": 5,
            "total_spendings": 48
        }
    """
    session_data = _get_authenticated_session()
    if not session_data:
        return jsonify({'error': 'not_authenticated'}), 401

    user = _load_current_user(session_data)
    if not user:
        return jsonify({'error': 'user_not_found'}), 404

    conn = get_conn()
    if not conn:
        return jsonify({'error': 'database_unavailable'}), 503

    user_id = str(user['id'])
    
    sql = '''
        SELECT 
            (SELECT COALESCE(coin_balance, 0) FROM users WHERE id = %s) as current_balance,
            (SELECT COALESCE(SUM(coins_purchased), 0) FROM coin_topups WHERE user_id = %s AND status = 'completed') as total_purchased,
            (SELECT COALESCE(SUM(coins_bonus), 0) FROM coin_topups WHERE user_id = %s AND status = 'completed') as total_bonus,
            (SELECT COALESCE(SUM(coins_spent), 0) FROM coin_spendings WHERE user_id = %s) as total_spent,
            (SELECT COUNT(*) FROM coin_topups WHERE user_id = %s AND status = 'completed') as total_topups,
            (SELECT COUNT(*) FROM coin_spendings WHERE user_id = %s) as total_spendings
    '''
    
    try:
        with conn.cursor() as cur:
            cur.execute(sql, [user_id] * 6)
            row = cur.fetchone()
            
            return jsonify({
                'current_balance': int(row[0]) if row[0] else 0,
                'total_purchased': int(row[1]) if row[1] else 0,
                'total_bonus': int(row[2]) if row[2] else 0,
                'total_spent': int(row[3]) if row[3] else 0,
                'total_topups': int(row[4]) if row[4] else 0,
                'total_spendings': int(row[5]) if row[5] else 0
            })
    
    except Exception as e:
        import logging
        logging.exception('Failed to fetch coin summary')
        return jsonify({'error': 'database_error'}), 500
