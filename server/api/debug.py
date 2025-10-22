"""Debug / developer-only routes blueprint."""
from __future__ import annotations
from flask import Blueprint, jsonify, current_app
from settings import IS_PROD

bp = Blueprint('debug_api', __name__)

@bp.get('/api/_routes')
def list_routes():  # debug helper
    if IS_PROD:
        return jsonify({'error': 'disabled in production'}), 404
    out = []
    for r in current_app.url_map.iter_rules():
        if r.rule.startswith('/api'):
            out.append({
                'rule': r.rule,
                'methods': sorted(m for m in r.methods if m not in ('HEAD','OPTIONS')),
                'endpoint': r.endpoint
            })
    out.sort(key=lambda x: x['rule'])
    return jsonify({'routes': out, 'count': len(out)})

@bp.get('/api/health')
def health():
    return jsonify({'status': 'ok'})
