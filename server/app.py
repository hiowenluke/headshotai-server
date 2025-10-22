#!/usr/bin/env python3
"""Application entrypoint (formerly image_api.py).

Registers blueprints and exposes `app` for WSGI/CLI usage.
"""
from flask import Flask, jsonify
import os
import json
from typing import Optional
from werkzeug.utils import secure_filename

from services.files import list_files_for_category  # type: ignore
from services.storage import build_file_name  # type: ignore
from api.demo import bp as demo_bp  # type: ignore
from api.pricing import bp as pricing_bp  # type: ignore
from api.upload import bp as upload_bp  # type: ignore
from api.images import bp as images_bp  # type: ignore
from api.debug import bp as debug_bp  # type: ignore
from api.new_user import bp as new_user_bp  # type: ignore
from settings import IS_PROD, load_config, STORAGE_MODE, S3_BUCKET, S3_REGION, UPLOAD_ROOT

app = Flask(__name__, static_folder='..')
try:  # pragma: no cover - optional blueprint
    from auth.google.auth_google import bp as google_bp  # type: ignore
    app.register_blueprint(google_bp)
    print('[INFO] Google auth blueprint loaded.')
except Exception as e:  # pragma: no cover
    import traceback, sys
    print('[WARN] Google auth blueprint not loaded:', e)
    traceback.print_exc()
    if os.environ.get('FORCE_GOOGLE_AUTH_IMPORT'):
        sys.exit(1)

try:
    from auth.session_routes import bp as session_bp  # type: ignore
    app.register_blueprint(session_bp)
    print('[INFO] Auth session blueprint loaded.')
except Exception as e:
    import traceback
    print('[WARN] Auth session blueprint not loaded:', e)
    traceback.print_exc()

 # _routes moved to debug blueprint

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cfg = load_config()

IMAGES_DIR = os.path.join(BASE_DIR, '..', 'public', 'images', 'demo', 'home')  # legacy reference
DEMO_FACES_DIR = os.path.join(BASE_DIR, '..', 'public', 'images', 'demo', 'faces')  # legacy reference

RAW_PRICE_MAP = cfg.get('price_map', {})
PRICE_MAP = {k: (v.get('price') if isinstance(v, dict) else v) for k,v in RAW_PRICE_MAP.items()}
ETA_MAP = {k: (v.get('eta_seconds') if isinstance(v, dict) else None) for k,v in RAW_PRICE_MAP.items()}
RECHARGE_RULES = cfg.get('recharge_rules', [])
COIN_SYMBOL = cfg.get('coin_symbol', 'C')
RECHARGE_CURRENCY = cfg.get('recharge_currency', 'USD')

ALLOWED_CATEGORIES = {
    'faces': 'faces',
    'backdrops': 'backdrops',
    'outfits': 'outfits',
    'poses': 'poses',
    'hairstyles': 'hairstyles'
}

 # UPLOAD_ROOT now from settings

def _sanitize_user(user: Optional[str]) -> str:
    if not user:
        return 'user1'
    user = secure_filename(user)
    return user or 'user1'

def _sanitize_category(cat: Optional[str]) -> str:
    if not cat:
        return 'faces'
    cat = cat.lower().strip()
    return cat if cat in ALLOWED_CATEGORIES else 'faces'

def _file_url(user: str, category: str, fname: str) -> str:  # retained for legacy uses
    if STORAGE_MODE == 's3':
        return f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{fname}"
    return f"/upload/{user}/{category}/{fname}"

# Register blueprints
app.register_blueprint(pricing_bp)
app.register_blueprint(demo_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(images_bp)
app.register_blueprint(new_user_bp)
if not IS_PROD:
    app.register_blueprint(debug_bp)

# 静态图片服务路由
@app.route('/images/<path:filename>')
def serve_static_images(filename):
    """Serve static images from public/images directory"""
    from flask import send_from_directory
    import os
    images_dir = os.path.join(BASE_DIR, '..', 'public', 'images')
    return send_from_directory(images_dir, filename)

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

def create_app():  # factory for tests / WSGI
    return app

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run API server')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug)
