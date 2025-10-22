"""Centralized settings & environment detection.

Usage:
    from settings import ENV, IS_PROD, STORAGE_MODE, S3_BUCKET, S3_REGION, UPLOAD_ROOT
"""
from __future__ import annotations
import os
import json
from functools import lru_cache

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Environment / mode
ENV = os.getenv('APP_ENV') or os.getenv('ENV') or 'dev'
IS_PROD = ENV.lower() in ('prod', 'production')
IS_TEST = ENV.lower() in ('test', 'ci')

# Storage
STORAGE_MODE = os.getenv('STORAGE_MODE', 'local').lower()  # local | s3
S3_BUCKET = os.getenv('S3_BUCKET')
S3_REGION = os.getenv('S3_REGION', 'us-east-1')

# Upload root (served from front-end store directory for direct access)
UPLOAD_ROOT = os.path.join(BASE_DIR, '..', 'store', 'upload')
os.makedirs(UPLOAD_ROOT, exist_ok=True)

CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')

@lru_cache(maxsize=1)
def load_config() -> dict:
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

__all__ = [
    'ENV', 'IS_PROD', 'IS_TEST',
    'STORAGE_MODE', 'S3_BUCKET', 'S3_REGION',
    'UPLOAD_ROOT', 'load_config', 'BASE_DIR', 'PROJECT_ROOT'
]
