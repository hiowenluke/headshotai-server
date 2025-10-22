"""
Facebook OAuth 认证模块 - 示例
展示如何复用独立的会话和状态管理器
"""
import os
import time
import secrets
from typing import Dict, Optional, Any
from urllib.parse import urlencode
import requests
from flask import Blueprint, request, make_response

# 导入复用的管理器模块
from server.auth.session_manager import SessionManager
from server.auth.state_manager import StateManager
from server.auth.session_settings import (
    SESSION_COOKIE,
    SESSION_MIN_SECONDS,
    SESSION_TTL_DEFAULT,
    SESSION_COOKIE_SECURE,
    select_cookie_domain,
)

# 数据库导入（复用Google认证的导入逻辑）
try:
    from server.database.db import upsert_user, get_user
except ImportError:
    def upsert_user(*args, **kwargs): return False, False
    def get_user(*args, **kwargs): return None

bp = Blueprint('auth_facebook', __name__)

# ===== Facebook OAuth 配置 =====
FACEBOOK_AUTH_URL = 'https://www.facebook.com/v18.0/dialog/oauth'
FACEBOOK_TOKEN_URL = 'https://graph.facebook.com/v18.0/oauth/access_token'
FACEBOOK_USER_URL = 'https://graph.facebook.com/v18.0/me'

FB_CLIENT_ID = os.environ.get('FACEBOOK_CLIENT_ID', '')
FB_CLIENT_SECRET = os.environ.get('FACEBOOK_CLIENT_SECRET', '')
FB_REDIRECT_URI = os.environ.get('FACEBOOK_REDIRECT_URI', 'http://localhost:5173/api/auth/facebook/callback')
FB_SCOPES = ['email', 'public_profile']

# ===== Helper Functions =====

def _generate_state() -> str:
    """生成OAuth状态码"""
    return secrets.token_urlsafe(24)

# ===== Routes =====

@bp.route('/api/auth/facebook/start')
def start():
    """启动Facebook OAuth流程"""
    if not FB_CLIENT_ID or not FB_CLIENT_SECRET:
        return {'error': 'facebook auth not configured'}, 500
    
    # 清理过期状态和会话
    StateManager.clean_expired()
    SessionManager.clean_sessions()
    
    state = _generate_state()
    # Facebook不使用PKCE，所以code_verifier设为空
    StateManager.save_state(state, FB_REDIRECT_URI, '', 'facebook')
    
    params = {
        'client_id': FB_CLIENT_ID,
        'redirect_uri': FB_REDIRECT_URI,
        'response_type': 'code',
        'scope': ','.join(FB_SCOPES),
        'state': state
    }
    
    return {'url': f"{FACEBOOK_AUTH_URL}?{urlencode(params)}"}

@bp.route('/api/auth/facebook/callback')
def callback():
    """处理Facebook OAuth回调"""
    error = request.args.get('error')
    if error:
        return _popup_result(success=False, reason=error)
    
    code = request.args.get('code')
    state = request.args.get('state')
    if not code or not state:
        return _popup_result(success=False, reason='missing_code_or_state')
    
    # 验证state
    meta, _ = StateManager.pop_state(state)
    if not meta or meta.get('exp', 0) < time.time():
        return _popup_result(success=False, reason='invalid_state')
    
    # 交换访问令牌
    token_data = {
        'client_id': FB_CLIENT_ID,
        'client_secret': FB_CLIENT_SECRET,
        'redirect_uri': meta.get('redirect_uri', FB_REDIRECT_URI),
        'code': code
    }
    
    try:
        token_response = requests.post(FACEBOOK_TOKEN_URL, data=token_data, timeout=10)
        token_json = token_response.json()
        access_token = token_json.get('access_token')
        
        if not access_token:
            return _popup_result(success=False, reason='no_access_token')
        
        # 获取用户信息
        user_response = requests.get(FACEBOOK_USER_URL, params={
            'access_token': access_token,
            'fields': 'id,name,email,picture'
        }, timeout=10)
        user_data = user_response.json()
        
    except Exception as e:
        return _popup_result(success=False, reason=f'facebook_api_error:{e}')
    
    # 提取用户信息
    fb_id = user_data.get('id')
    name = user_data.get('name')
    email = user_data.get('email')
    picture_data = user_data.get('picture', {})
    picture = picture_data.get('data', {}).get('url') if picture_data else None
    
    if not fb_id:
        return _popup_result(success=False, reason='missing_facebook_id')
    
    # 创建会话
    now_ts = time.time()
    exp = int(now_ts + SESSION_TTL_DEFAULT)
    if SESSION_MIN_SECONDS > 0:
        min_target = int(now_ts + SESSION_MIN_SECONDS)
        if exp < min_target:
            exp = min_target
    
    session_id = SessionManager.generate_session_id()
    ua = request.headers.get('User-Agent', '')[:400]
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
    
    session_payload = {
        'sub': fb_id,  # 使用Facebook ID作为subject
        'email': email,
        'name': name,
        'picture': picture,
        'provider': 'facebook',
        'ts': now_ts,
        'exp': exp,
        'ua': ua,
        'ip': ip
    }
    
    # 添加到用户会话索引
    SessionManager.add_session_to_user(email, fb_id, session_id, now_ts)
    
    # 保存用户到数据库
    try:
        up_ok, is_new = upsert_user(fb_id, 'facebook', email, name, picture, ip)
        session_payload['is_new_user'] = bool(is_new)
    except Exception:
        pass
    
    # 保存会话
    SessionManager.save_session(session_id, session_payload, exp)
    
    # 设置Cookie并返回
    resp = _popup_result(success=True)
    cookie_max = max(0, exp - int(time.time()))
    cookie_kwargs = dict(
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite='None' if SESSION_COOKIE_SECURE else 'Lax',
        max_age=cookie_max,
        path='/'
    )
    
    chosen_domain = select_cookie_domain(request.host)
    if chosen_domain:
        cookie_kwargs['domain'] = chosen_domain
    
    resp.set_cookie(SESSION_COOKIE, session_id, **cookie_kwargs)
    return resp

def _popup_result(success: bool, reason: Optional[str] = None):
    """生成弹窗结果页面"""
    html = ["<html><head><meta charset='utf-8'></head><body><script>"]
    
    if success:
        html.append("""
            (function(){
                try {
                    if(window.opener) {
                        window.opener.postMessage({type:'auth:success',provider:'facebook'}, window.location.origin);
                        window.close();
                    } else {
                        localStorage.setItem('auth:justLoggedIn','1');
                        var returnPath = localStorage.getItem('auth:returnPath');
                        localStorage.removeItem('auth:returnPath');
                        localStorage.removeItem('auth:isFullPageAuth');
                        setTimeout(function() {
                            if(returnPath && returnPath !== '/' && returnPath !== '') {
                                window.location.replace(returnPath);
                            } else {
                                window.location.replace('/home');
                            }
                        }, 100);
                    }
                } catch(e) {
                    console.error('Auth callback error:', e);
                    localStorage.setItem('auth:justLoggedIn','1');
                    setTimeout(function() {
                        window.location.replace('/home');
                    }, 100);
                }
            })();
        """)
    else:
        safe_reason = (reason or 'unknown').replace("'", "\\'")
        html.append(f"""
            (function(){{
                try {{
                    if(window.opener) {{
                        window.opener.postMessage({{type:'auth:failure',provider:'facebook',reason:'{safe_reason}'}}, window.location.origin);
                        window.close();
                    }} else {{
                        localStorage.setItem('auth:authFail','{safe_reason}');
                        var returnPath = localStorage.getItem('auth:returnPath');
                        localStorage.removeItem('auth:returnPath');
                        localStorage.removeItem('auth:isFullPageAuth');
                        setTimeout(function() {{
                            if(returnPath && returnPath !== '/' && returnPath !== '') {{
                                window.location.replace(returnPath);
                            }} else {{
                                window.location.replace('/home');
                            }}
                        }}, 100);
                    }}
                }} catch(e) {{
                    console.error('Auth error callback:', e);
                    localStorage.setItem('auth:authFail','{safe_reason}');
                    setTimeout(function() {{
                        window.location.replace('/home');
                    }}, 100);
                }}
            }})();
        """)
    
    html.append("</script></body></html>")
    return make_response('\n'.join(html))

# 注意：会话相关的路由可以复用Google认证的路由，
# 因为它们都使用相同的SessionManager
# 例如：/api/auth/session, /api/auth/logout 等
