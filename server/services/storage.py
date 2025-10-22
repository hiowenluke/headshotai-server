"""Storage abstraction (local or S3) extracted from former image_api (now app.py).
Provides simple save + URL helpers with lazy S3 client init.
"""
from __future__ import annotations
import os
import time
from typing import Optional

try:
    import boto3  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None  # type: ignore

S3_CLIENT = None

__all__ = [
    'save_file', 'build_file_name'
]

def _ensure_local_dirs(upload_dir: str):
    os.makedirs(upload_dir, exist_ok=True)

def build_file_name(ext: str = '.webp') -> str:
    return f"{int(time.time()*1000)}{ext}"

def _init_s3():
    global S3_CLIENT
    if S3_CLIENT is None and boto3:
        S3_CLIENT = boto3.client('s3')
    return S3_CLIENT

def save_file(data: bytes, *, storage_mode: str, upload_dir: str, s3_bucket: Optional[str] = None,
              user_id: Optional[str] = None, category: Optional[str] = None,
              ext: str = '.webp', file_name: Optional[str] = None) -> str:
    """Save file either locally or to S3.

    Returns a public-ish URL path (for local) or S3 object key.
    """
    file_name = file_name or build_file_name(ext)
    if storage_mode == 's3':
        client = _init_s3()
        if not client:
            raise RuntimeError('boto3 not available for s3 storage mode')
        key = file_name
        extra = {'ContentType': 'image/webp'} if file_name.endswith('.webp') else {}
        params = dict(Bucket=s3_bucket, Key=key, Body=data, **({'ContentType': extra['ContentType']} if extra else {}))  # type: ignore
        client.put_object(**params)
        return key
    # local
    # Local path: upload_dir/<user>/<category>/file
    user_dir = os.path.join(upload_dir, user_id) if user_id else upload_dir
    if category:
        user_dir = os.path.join(user_dir, category)
    _ensure_local_dirs(user_dir)
    path = os.path.join(user_dir, file_name)
    with open(path, 'wb') as f:
        f.write(data)
    rel = os.path.relpath(path, os.path.join(os.path.dirname(upload_dir)))
    # Normalize to forward slashes for URLs
    return '/' + rel.replace('\\', '/')
