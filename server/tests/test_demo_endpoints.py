import json
import os
import sys
import pytest
from flask.testing import FlaskClient

# Ensure server package importable when running tests from server/ directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(BASE_DIR)
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from app import app  # noqa: E402

@pytest.fixture(scope='module')
def client():  # type: ignore
    app.testing = True
    with app.test_client() as c:
        yield c

def test_demo_faces_default(client: FlaskClient):
    rv = client.get('/api/demo_faces')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'faces' in data
    assert data['gender'] == 'Female'
    assert data['ethnicity'] == 'White'


def test_demo_home_pagination(client: FlaskClient):
    rv1 = client.get('/api/demo_home?per_page=3&page=1')
    assert rv1.status_code == 200
    d1 = rv1.get_json()
    assert d1['page'] == 1
    assert len(d1['images']) <= 3

    rv2 = client.get('/api/demo_home?per_page=3&page=2')
    assert rv2.status_code == 200
    d2 = rv2.get_json()
    # pages can be empty if not enough demo files; just validate schema
    assert d2['page'] == 2
    assert 'has_more' in d2


def test_prices(client):
    rv = client.get('/api/prices')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'prices' in data
    assert 'eta_seconds' in data


def test_recharge_rules(client):
    rv = client.get('/api/recharge_rules')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'rules' in data
    assert 'currency' in data


def test_images_legacy(client):
    rv = client.get('/api/images?page=0&per_page=2')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'images' in data
    assert 'total' in data

def test_health(client):
    rv = client.get('/api/health')
    assert rv.status_code == 200
    data = rv.get_json()
    assert data.get('status') == 'ok'
