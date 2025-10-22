"""File listing helpers for demo images.
Isolated from Flask app for easier unit testing.
"""
from __future__ import annotations
import os
from typing import List, Optional

# 缩略图 240x300，大图 520x650
# 都放在同一个目录下，方便前端按需加载：
#   列表只加载缩略图，点击后加载大图
THUMBNAIL_WIDTH = "demo"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Move two levels up to reach project root relative to this file (services/)
SERVER_DIR = os.path.dirname(BASE_DIR)
PUBLIC_DEMO_HOME = os.path.join(SERVER_DIR, '..', 'public', 'images', THUMBNAIL_WIDTH, 'home')
PUBLIC_DEMO_FACES = os.path.join(SERVER_DIR, '..', 'public', 'images', THUMBNAIL_WIDTH, 'faces')

__all__ = [
    'PUBLIC_DEMO_HOME', 'PUBLIC_DEMO_FACES',
    'list_files_for_category', 'list_demo_faces'
]

def list_files_for_category(category: Optional[str] = None) -> List[str]:
    """List thumbnail home image relative paths.

    If category is provided and exists as a subfolder of <THUMBNAIL_WIDTH>/home, returns
    images inside that subfolder. Supports nested categories like 'Studio/Dark'.
    Otherwise returns images directly under home.
    Returned paths are relative like 'images/<THUMBNAIL_WIDTH>/home/<...>'.
    """
    base_dir = PUBLIC_DEMO_HOME
    if category:
        # Support nested categories like 'Studio/Dark'
        cat_path = category.replace('/', os.sep)
        cat_dir = os.path.join(base_dir, cat_path)
        
        if os.path.isdir(cat_dir):
            files = []
            # Recursively collect all image files
            for root, dirs, filenames in os.walk(cat_dir):
                for filename in filenames:
                    if (
                        not filename.startswith('.')
                        and _is_image_file(filename)
                        and not _is_large_variant(filename)
                    ):
                        # Calculate relative path from cat_dir
                        rel_path = os.path.relpath(os.path.join(root, filename), cat_dir)
                        files.append(rel_path)
            
            files.sort()
            # Build full relative paths
            return [os.path.join('images', THUMBNAIL_WIDTH, 'home', cat_path, f).replace(os.sep, '/') for f in files]
    
    # Fallback: list files directly under home
    files: List[str] = []
    if os.path.isdir(base_dir):
        for entry in os.listdir(base_dir):
            p = os.path.join(base_dir, entry)
            if (
                os.path.isfile(p)
                and not entry.startswith('.')
                and _is_image_file(entry)
                and not _is_large_variant(entry)
            ):
                files.append(entry)
    
    files.sort()
    return [os.path.join('images', THUMBNAIL_WIDTH, 'home', f).replace(os.sep, '/') for f in files]

def _is_image_file(filename: str) -> bool:
    """Check if file is an image based on extension."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
    return any(filename.lower().endswith(ext) for ext in image_extensions)


def _is_large_variant(filename: str) -> bool:
    """Return True if filename denotes a large-sized variant we should skip."""
    name, _ = os.path.splitext(filename)
    return name.lower().endswith('_l')

def list_demo_faces(gender: str, ethnicity: str, limit: int) -> List[str]:
    """List demo face image URLs based on gender/ethnicity subdirectories."""
    gender_dir = os.path.join(PUBLIC_DEMO_FACES, gender)
    eth_dir = os.path.join(gender_dir, ethnicity) if os.path.isdir(gender_dir) else None
    base_dir = eth_dir if (eth_dir and os.path.isdir(eth_dir)) else None
    if not base_dir:
        return []
    files = [
        f for f in os.listdir(base_dir)
        if (
            os.path.isfile(os.path.join(base_dir, f))
            and not f.startswith('.')
            and not _is_large_variant(f)
        )
    ]
    files.sort()
    return [f"/images/{THUMBNAIL_WIDTH}/faces/{gender}/{ethnicity}/{f}" for f in files[:limit]]
