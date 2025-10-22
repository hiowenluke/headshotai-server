"""Images (legacy demo /api/images) blueprint."""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
import json

bp = Blueprint('images_api', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(BASE_DIR)
with open(os.path.join(SERVER_DIR, 'config.json'), 'r') as f:
    cfg = json.load(f)

TOTAL = cfg.get('total_images', 100)
PER_PAGE_DEFAULT = cfg.get('per_page', 10)
IMAGES_DIR = os.path.join(SERVER_DIR, '..', 'store', 'images', 'demo', 'home')

from services.files import list_files_for_category  # after BASE_DIR defined

@bp.get('/api/images')
def images():
    try:
        page = int(request.args.get('page', '0'))
        per_page = int(request.args.get('per_page', str(PER_PAGE_DEFAULT)))
    except ValueError:
        page = 0
        per_page = PER_PAGE_DEFAULT

    category = request.args.get('category')
    files = list_files_for_category(category)
    if len(files) == 0:
        return jsonify({'images': [], 'page': page, 'per_page': per_page, 'total': 0})

    imgs = []
    for i in range(TOTAL):
        fname = files[i % len(files)]
        url = f"/{fname.replace(os.sep, '/') }"
        imgs.append(url)

    start = page * per_page
    end = start + per_page
    result = imgs[start:end]
    return jsonify({'images': result, 'page': page, 'per_page': per_page, 'total': TOTAL})
