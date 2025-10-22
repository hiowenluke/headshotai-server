"""Session-oriented auth routes shared across identity providers."""
from __future__ import annotations

import time

from flask import Blueprint, request, make_response

from api.upload import list_recent_faces_for_user, list_all_faces_for_user
from server.auth.session_manager import SessionManager
from server.auth.session_settings import (
    SESSION_COOKIE,
    SESSION_COOKIE_SECURE,
    select_cookie_domain,
)

bp = Blueprint('auth_session', __name__)


@bp.route('/api/auth/session')
def session_info():
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return {'authenticated': False}
    data = SessionManager.get_session(sid)
    if not data:
        return {'authenticated': False}
    if data.get('exp') and data['exp'] < time.time():
        SessionManager.delete_session(sid)
        return {'authenticated': False}

    new_exp = SessionManager.refresh_session_if_needed(sid, data)
    user_ident = data.get('sub') or data.get('email')
    recent_faces = list_recent_faces_for_user(user_ident)
    include_faces = request.args.get('faces') or request.args.get('include')
    faces_all = list_all_faces_for_user(user_ident) if include_faces == 'all' else None

    resp_body = {
        'authenticated': True,
        'user': data,
        'recent_faces': recent_faces,
    }
    if faces_all is not None:
        resp_body['faces_all'] = faces_all

    resp = make_response(resp_body)
    if new_exp:
        cookie_max = max(0, new_exp - int(time.time()))
        cookie_kwargs = dict(
            httponly=True,
            secure=SESSION_COOKIE_SECURE,
            samesite='None' if SESSION_COOKIE_SECURE else 'Lax',
            max_age=cookie_max,
            path='/',
        )
        chosen_domain = select_cookie_domain(request.host)
        if chosen_domain:
            cookie_kwargs['domain'] = chosen_domain
        resp.set_cookie(SESSION_COOKIE, sid, **cookie_kwargs)
    return resp


@bp.route('/api/auth/sessions')
def sessions_list():
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return {'authenticated': False}, 401
    current = SessionManager.get_session(sid)
    if not current:
        return {'authenticated': False}, 401
    sub = current.get('sub')
    if not sub:
        return {'authenticated': False}, 401
    sessions = SessionManager.list_user_sessions(current.get('email'), sub)
    return {'authenticated': True, 'current': sid, 'sessions': sessions}


@bp.route('/api/auth/logout_session', methods=['POST'])
def logout_session():
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return {'success': False, 'error': 'not_authenticated'}, 401
    cur = SessionManager.get_session(sid)
    if not cur:
        return {'success': False, 'error': 'not_authenticated'}, 401
    sub = cur.get('sub')
    body = request.get_json(silent=True) or {}
    target = body.get('session_id')
    if not target:
        return {'success': False, 'error': 'missing_session_id'}, 400
    tdata = SessionManager.get_session(target)
    if not tdata or tdata.get('sub') != sub:
        return {'success': False, 'error': 'not_found'}, 404
    SessionManager.delete_session(target)
    return {'success': True, 'deleted': target, 'current': (target == sid)}


@bp.route('/api/auth/logout_all', methods=['POST'])
def logout_all():
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return {'success': False, 'error': 'not_authenticated'}, 401
    cur = SessionManager.get_session(sid)
    if not cur:
        return {'success': False, 'error': 'not_authenticated'}, 401
    sub = cur.get('sub')
    sessions = SessionManager.list_user_sessions(cur.get('email'), sub)
    for item in sessions:
        SessionManager.delete_session(item['session_id'])
    resp = make_response({'success': True, 'cleared': len(sessions)})
    resp.delete_cookie(SESSION_COOKIE, path='/')
    return resp


@bp.route('/api/auth/logout', methods=['POST'])
def logout():
    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        SessionManager.delete_session(sid)
    resp = make_response({'success': True})
    resp.delete_cookie(SESSION_COOKIE, path='/')
    return resp
