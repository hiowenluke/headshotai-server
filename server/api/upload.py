"""Upload related routes blueprint."""
from flask import Blueprint, jsonify, request, send_from_directory
import os
import time
from werkzeug.utils import secure_filename
from services.storage import save_file, build_file_name
from auth.session_manager import SessionManager
from settings import UPLOAD_ROOT, STORAGE_MODE, S3_BUCKET, S3_REGION

bp = Blueprint('upload_api', __name__)

ALLOWED_CATEGORIES = {
    'faces': 'faces',
    'backdrops': 'backdrops',
    'outfits': 'outfits',
    'poses': 'poses',
    'hairstyles': 'hairstyles'
}

DEFAULT_UPLOAD_CATEGORY = 'faces'

SESSION_COOKIE = os.environ.get('SESSION_COOKIE_NAME', 'app_session')
RECENT_FACES_LIMIT = 4

def _enumerate_face_files(user: str) -> list[tuple[float, str]]:
    if STORAGE_MODE != 'local':
        # TODO: add S3 support when remote storage listing is available
        return []

    faces_dir = os.path.join(UPLOAD_ROOT, user, 'faces')
    if not os.path.isdir(faces_dir):
        return []

    files: list[tuple[float, str]] = []
    for entry in os.listdir(faces_dir):
        path = os.path.join(faces_dir, entry)
        if not os.path.isfile(path):
            continue
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        files.append((mtime, entry))

    files.sort(key=lambda item: item[0], reverse=True)
    return files

def _face_created_timestamp(entry: str, mtime: float) -> int:
    name, _ = os.path.splitext(entry)
    try:
        ts = int(name)
        if ts > 10**12:  # already in milliseconds
            return ts
        return ts * 1000
    except ValueError:
        return int(mtime * 1000)

def list_recent_faces_for_user(user_ident: str | None) -> list[str]:
    if not user_ident:
        return []

    user = _sanitize_user(user_ident)
    files = _enumerate_face_files(user)
    if not files:
        return []

    recent = [f"/upload/{user}/faces/{entry}" for _, entry in files[:RECENT_FACES_LIMIT]]
    return recent

def list_all_faces_for_user(user_ident: str | None) -> list[dict[str, object]]:
    if not user_ident:
        return []

    user = _sanitize_user(user_ident)
    files = _enumerate_face_files(user)
    faces: list[dict[str, object]] = []
    for mtime, entry in files:
        created_at = _face_created_timestamp(entry, mtime)
        faces.append({
            'url': f"/upload/{user}/faces/{entry}",
            'created_at': created_at
        })
    return faces


os.makedirs(UPLOAD_ROOT, exist_ok=True)

def _sanitize_user(user):
    if not user:
        return 'user1'
    user = secure_filename(user)
    return user or 'user1'

def _sanitize_category(cat):
    if not cat:
        return 'faces'
    cat = cat.lower().strip()
    if cat not in ALLOWED_CATEGORIES:
        return 'faces'
    return cat

def _get_authenticated_session():
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

@bp.route('/api/upload', methods=['POST', 'OPTIONS'])
def upload():
    if request.method == 'OPTIONS':
        return jsonify({'ok': True})
    f = request.files.get('file')
    if not f:
        return jsonify({'success': False, 'error': 'missing file'}), 400

    session = _get_authenticated_session()
    user = _sanitize_user(request.form.get('user'))
    category = DEFAULT_UPLOAD_CATEGORY

    filename = build_file_name('.webp')
    try:
        f.stream.seek(0)
        data = f.read()
        key_or_path = save_file(
            data,
            storage_mode=STORAGE_MODE,
            upload_dir=UPLOAD_ROOT,
            s3_bucket=S3_BUCKET,
            user_id=user,
            category=category,
            ext='.webp',
            file_name=filename
        )
        if STORAGE_MODE == 's3':
            url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{key_or_path}"
        else:
            url = key_or_path
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    return jsonify({'success': True, 'url': url, 'user': user, 'category': category, 'storage': STORAGE_MODE})

@bp.get('/upload/<user>/<category>/<path:filename>')
def serve_uploaded_generic(user, category, filename):
    if STORAGE_MODE == 's3':
        return jsonify({'error': 'Direct serving disabled in S3 mode'}), 404
    user = _sanitize_user(user)
    category = _sanitize_category(category)
    local_dir = os.path.join(UPLOAD_ROOT, user, category)
    os.makedirs(local_dir, exist_ok=True)
    return send_from_directory(local_dir, filename)

@bp.get('/upload/faces/<path:filename>')
def serve_uploaded_legacy(filename):
    if STORAGE_MODE == 's3':
        return jsonify({'error': 'Legacy route disabled in S3 mode'}), 404
    local_dir = os.path.join(UPLOAD_ROOT, 'user1', 'faces')
    os.makedirs(local_dir, exist_ok=True)
    return send_from_directory(local_dir, filename)

@bp.get('/api/upload/faces/recent')
def recent_faces():
    session = _get_authenticated_session()
    if not session:
        return jsonify({'error': 'not_authenticated'}), 401

    user_ident = session.get('sub') or session.get('email')
    faces = list_recent_faces_for_user(user_ident)
    return jsonify({'faces': faces})

@bp.get('/api/upload/faces/all')
def all_faces():
    session = _get_authenticated_session()
    if not session:
        return jsonify({'error': 'not_authenticated'}), 401

    user_ident = session.get('sub') or session.get('email')
    faces = list_all_faces_for_user(user_ident)
    return jsonify({'faces': faces})
