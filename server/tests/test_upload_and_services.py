import io
import os
import sys
import tempfile
import time
import shutil
import pytest

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(BASE_DIR)
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from app import app  # noqa: E402
from services import files as files_service  # noqa: E402
from services import storage as storage_service  # noqa: E402
from auth.session_manager import SessionManager  # noqa: E402
from api.upload import SESSION_COOKIE, UPLOAD_ROOT  # noqa: E402

THUMBNAIL_WIDTH = "demo"  # keep in sync with services/files.py

@pytest.fixture(scope='module')
def client():  # type: ignore
    app.testing = True
    with app.test_client() as c:
        yield c

# ---------------- Upload route tests ----------------

def test_upload_success(client):
    data = {
        'user': 'test_user',
        'category': 'faces',
        'file': (io.BytesIO(b'GIF89a'), 'dummy.webp')
    }
    rv = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert rv.status_code == 200
    j = rv.get_json()
    assert j['success'] is True
    assert j['user'] == 'test_user'
    assert j['category'] == 'faces'
    assert j['url'].startswith('/upload/') or j['url'].startswith('http')


def test_upload_missing_file(client):
    data = {
        'user': 'abc',
        'category': 'faces'
    }
    rv = client.post('/api/upload', data=data)
    assert rv.status_code == 400
    j = rv.get_json()
    assert j['success'] is False
    assert 'missing file' in j['error']


def test_upload_invalid_category_fallback(client):
    data = {
        'user': 'u2',
        'category': 'NOT_EXISTING_CAT',
        'file': (io.BytesIO(b'123456'), 'a.webp')
    }
    rv = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert rv.status_code == 200
    j = rv.get_json()
    # Category should fallback to faces per sanitizer
    assert j['category'] == 'faces'


def test_recent_faces_requires_auth(client):
    rv = client.get('/api/upload/faces/recent')
    assert rv.status_code == 401


def test_recent_faces_returns_latest_entries(client):
    session_id = 'sess_recent_01'
    exp = int(time.time()) + 3600
    SessionManager.save_session(session_id, {
        'sub': 'recent_user',
        'email': 'recent@example.com',
        'exp': exp,
        'ts': time.time()
    }, exp)

    client.set_cookie('localhost', SESSION_COOKIE, session_id)

    user_dir = os.path.join(UPLOAD_ROOT, 'recent_user', 'faces')
    shutil.rmtree(os.path.join(UPLOAD_ROOT, 'recent_user'), ignore_errors=True)
    os.makedirs(user_dir, exist_ok=True)

    for idx in range(5):
        fname = f'{1000 + idx}.webp'
        path = os.path.join(user_dir, fname)
        with open(path, 'wb') as f:
            f.write(b'data')
        ts = time.time() + idx
        os.utime(path, (ts, ts))

    rv = client.get('/api/upload/faces/recent')
    assert rv.status_code == 200
    payload = rv.get_json()
    assert isinstance(payload, dict)
    faces = payload.get('faces') or []
    assert len(faces) == 4
    assert faces[0].endswith('1004.webp')
    assert faces[-1].endswith('1001.webp')

    SessionManager.delete_session(session_id)
    client.delete_cookie('localhost', SESSION_COOKIE)
    shutil.rmtree(os.path.join(UPLOAD_ROOT, 'recent_user'), ignore_errors=True)

# ---------------- services.files tests ----------------

def test_list_files_for_category_returns_list():
    result = files_service.list_files_for_category()
    assert isinstance(result, list)
    # elements (if any) are relative paths under images/<THUMBNAIL_WIDTH>/home
    if result:
        assert result[0].startswith(f'images/{THUMBNAIL_WIDTH}/home/')


def test_list_demo_faces_limit():
    faces = files_service.list_demo_faces('Female', 'White', 3)
    assert len(faces) <= 3
    if faces:
        assert faces[0].startswith(f'/images/{THUMBNAIL_WIDTH}/faces/')

# ---------------- services.storage tests ----------------

def test_storage_save_file_local():
    with tempfile.TemporaryDirectory() as tmp:
        data = b'abcdefg'
        path = storage_service.save_file(
            data,
            storage_mode='local',
            upload_dir=tmp,
            user_id='uu1',
            category='faces',
            ext='.webp'
        )
        # Returned path should be /<rel>
        assert path.startswith('/')
        # File should exist physically
        # reconstruct absolute: parent of upload_dir + rel without leading '/'
        abs_parent = os.path.dirname(tmp)
        abs_path = os.path.join(abs_parent, path.lstrip('/'))
        assert os.path.exists(abs_path)
