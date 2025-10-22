"""Pricing & recharge related routes blueprint."""
from __future__ import annotations
from flask import Blueprint, jsonify
import os, json

bp = Blueprint('pricing_api', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(BASE_DIR)
with open(os.path.join(SERVER_DIR, 'config.json'), 'r') as f:
    cfg = json.load(f)

RAW_PRICE_MAP = cfg.get('price_map', {})
PRICE_MAP = {k: (v.get('price') if isinstance(v, dict) else v) for k, v in RAW_PRICE_MAP.items()}
ETA_MAP = {k: (v.get('eta_seconds') if isinstance(v, dict) else None) for k, v in RAW_PRICE_MAP.items()}
RECHARGE_RULES = cfg.get('recharge_rules', [])
COIN_SYMBOL = cfg.get('coin_symbol', 'C')
RECHARGE_CURRENCY = cfg.get('recharge_currency', 'USD')

@bp.get('/api/prices')
def prices():
    return jsonify({'prices': PRICE_MAP, 'eta_seconds': ETA_MAP, 'version': 1})

@bp.get('/api/recharge_rules')
def recharge_rules():
    return jsonify({
        'rules': RECHARGE_RULES,
        'currency': RECHARGE_CURRENCY,
        'coin_symbol': COIN_SYMBOL,
        'version': 1
    })
