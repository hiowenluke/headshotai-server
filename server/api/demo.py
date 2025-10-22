"""Demo listing related API blueprint (home images & demo faces)."""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from services.files import list_files_for_category, list_demo_faces
import os

bp = Blueprint('demo_api', __name__)

# 获取 server 目录路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(BASE_DIR)

@bp.get('/api/demo_faces')
def api_demo_faces():
    gender = request.args.get('gender', 'Female')
    ethnicity = request.args.get('ethnicity', 'White')
    try:
        limit = int(request.args.get('limit', '4'))
    except ValueError:
        limit = 4
    faces = list_demo_faces(gender, ethnicity, limit)
    return jsonify({'faces': faces, 'gender': gender, 'ethnicity': ethnicity, 'count': len(faces)})

@bp.get('/api/demo_home')
def api_demo_home():
    category = request.args.get('category')
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get('per_page', '10'))
    except ValueError:
        per_page = 10

    gender = request.args.get('gender')
    ethnicity = request.args.get('ethnicity')
    age = request.args.get('age')
    body_size = request.args.get('body_size')

    imgs_all = list_files_for_category(category)
    total = len(imgs_all)
    start = (page - 1) * per_page
    end = start + per_page
    page_imgs = imgs_all[start:end]
    out = [f"/{p}" if not p.startswith('/') else p for p in page_imgs]
    return jsonify({
        'images': out,
        'category': category,
        'page': page,
        'per_page': per_page,
        'total': total,
        'has_more': end < total,
        'preferences': {
            'gender': gender,
            'ethnicity': ethnicity,
            'age': age,
            'body_size': body_size
        }
    })

@bp.get('/api/demo_options')
def api_demo_options():
    """API for options pages (backdrops, poses, outfits, hairstyles)."""
    option_type = request.args.get('type')  # 'backdrops', 'poses', 'outfits', 'hairstyles'
    category = request.args.get('category')
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get('per_page', '50'))
    except ValueError:
        per_page = 50

    # 构建基础路径
    base_path = os.path.join(SERVER_DIR, '..', 'public', 'images', 'demo', 'options', option_type or 'backdrops')
    
    # 如果 category 为 '*' 或 'all'，返回所有分类的图片
    if category in ('*', 'all', None, ''):
        all_files = []
        
        # 遍历所有子目录
        if os.path.isdir(base_path):
            for cat_name in os.listdir(base_path):
                cat_dir = os.path.join(base_path, cat_name)
                
                # 跳过隐藏文件和非目录
                if cat_name.startswith('.') or not os.path.isdir(cat_dir):
                    continue
                
                # 遍历该分类下的所有文件
                for filename in os.listdir(cat_dir):
                    filepath = os.path.join(cat_dir, filename)
                    if (
                        os.path.isfile(filepath)
                        and not filename.startswith('.')
                        and _is_image_file(filename)
                        and not _is_large_variant(filename)
                    ):
                        # 构建完整的相对路径
                        rel_path = f"/images/demo/options/{option_type}/{cat_name}/{filename}".replace(os.sep, '/')
                        all_files.append(rel_path)
        
        all_files.sort()
        
        # 分页
        total = len(all_files)
        start = (page - 1) * per_page
        end = start + per_page
        page_files = all_files[start:end]
        
        return jsonify({
            'images': page_files,
            'type': option_type,
            'category': category or 'all',
            'page': page,
            'per_page': per_page,
            'total': total,
            'has_more': end < total
        })
    
    # 如果指定了具体的 category，返回该分类的图片
    if category:
        # 支持嵌套分类如 'Studio/Dark'
        cat_path = category.replace('/', os.sep)
        cat_dir = os.path.join(base_path, cat_path)
        
        if os.path.isdir(cat_dir):
            files = []
            for filename in os.listdir(cat_dir):
                filepath = os.path.join(cat_dir, filename)
                if (
                    os.path.isfile(filepath)
                    and not filename.startswith('.')
                    and _is_image_file(filename)
                    and not _is_large_variant(filename)
                ):
                    files.append(filename)
            
            files.sort()
            # 分页
            total = len(files)
            start = (page - 1) * per_page
            end = start + per_page
            page_files = files[start:end]
            
            # 构建完整的相对路径
            out = [f"/images/demo/options/{option_type}/{cat_path}/{f}".replace(os.sep, '/') for f in page_files]
            
            return jsonify({
                'images': out,
                'type': option_type,
                'category': category,
                'page': page,
                'per_page': per_page,
                'total': total,
                'has_more': end < total
            })
    
    return jsonify({
        'images': [],
        'type': option_type,
        'category': category,
        'page': page,
        'per_page': per_page,
        'total': 0,
        'has_more': False
    })

def _is_image_file(filename: str) -> bool:
    """Check if file is an image based on extension."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
    return any(filename.lower().endswith(ext) for ext in image_extensions)

def _is_large_variant(filename: str) -> bool:
    """Return True if filename denotes a large-sized variant we should skip."""
    name, _ = os.path.splitext(filename)
    return name.lower().endswith('_l')
