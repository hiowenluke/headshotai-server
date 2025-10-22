import os, json, time, base64, hashlib, secrets, threading
from typing import Dict, Optional, List, Any
from urllib.parse import urlencode
import requests
from google.oauth2 import id_token as google_id_token  # type: ignore
from google.auth.transport import requests as google_requests  # type: ignore
from flask import Blueprint, request, make_response

# 导入独立的管理器模块
try:
    from server.auth.session_manager import SessionManager
    from server.auth.state_manager import StateManager
except ImportError:
    # 如果导入失败，尝试添加项目根路径
    import pathlib, sys as _sys
    proj_root = pathlib.Path(__file__).resolve().parents[3]
    if str(proj_root) not in _sys.path:
        _sys.path.insert(0, str(proj_root))
    from server.auth.session_manager import SessionManager
    from server.auth.state_manager import StateManager
_DB_IMPORT_ERROR = None
_DB_IMPORT_IMPL = 'real'
try:
    # Primary import path
    from server.database.db import upsert_user, get_user  # type: ignore
except Exception as e1:  # pragma: no cover
    _DB_IMPORT_ERROR = f"primary:{e1}"
    # Attempt to add project root then retry (root = parent of 'server')
    try:
        import pathlib, sys as _sys
        proj_root = pathlib.Path(__file__).resolve().parents[3]  # .../root/server/auth/google
        if str(proj_root) not in _sys.path:
            _sys.path.insert(0, str(proj_root))
    except Exception as _ep:  # pragma: no cover
        _DB_IMPORT_ERROR += f"; add_path_fail:{_ep}"
    try:
        from server.database.db import upsert_user, get_user  # type: ignore
        _DB_IMPORT_ERROR += '; recovered_after_path_insert'
    except Exception as e2:  # pragma: no cover
        _DB_IMPORT_IMPL = 'stub'
        _DB_IMPORT_ERROR = f"primary:{e1}; secondary:{e2}"
        def upsert_user(*args, **kwargs):  # type: ignore
            if os.environ.get('AUTH_DEBUG','0') in ('1','true','yes'):
                try:
                    print('[AUTH][DB_STUB] upsert_user called (db import failed)')
                    if os.environ.get('AUTH_DEBUG_VERBOSE') in ('1','true','yes') and _DB_IMPORT_ERROR:
                        print('[AUTH][DB_IMPORT_ERROR]', _DB_IMPORT_ERROR)
                except Exception: pass
            return False
        def get_user(*args, **kwargs):  # type: ignore
            return None
if os.environ.get('AUTH_DEBUG','0') in ('1','true','yes'):
    try:
        if _DB_IMPORT_IMPL == 'stub':
            print(f"[AUTH][DB_IMPORT_FAIL] using stub functions error={_DB_IMPORT_ERROR}")
        else:
            print('[AUTH][DB_IMPORT_OK] real db functions loaded')
    except Exception:
        pass

# ===== 会话配置 =====
from server.auth.session_settings import (
    SESSION_COOKIE,
    SESSION_MIN_SECONDS,
    SESSION_TTL_DEFAULT,
    SESSION_COOKIE_SECURE,
    SESSION_COOKIE_DOMAIN_RAW,
    SESSION_COOKIE_DOMAINS,
    select_cookie_domain,
)

bp = Blueprint('auth_google', __name__)

# ===== Google OAuth 配置 =====
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'

CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5173/api/auth/google/callback')
REDIRECT_URIS_RAW = os.environ.get('GOOGLE_REDIRECT_URIS', '').strip()
if REDIRECT_URIS_RAW:
    _redirect_uri_list: List[str] = [u.strip() for u in REDIRECT_URIS_RAW.split(',') if u.strip()]
else:
    _redirect_uri_list = [REDIRECT_URI]
SCOPES = ['openid', 'email', 'profile']

ALLOWED_EMAIL_DOMAIN = os.environ.get('GOOGLE_ALLOWED_EMAIL_DOMAIN', '').lower().strip()
ALLOWED_EMAILS_RAW = os.environ.get('GOOGLE_ALLOWED_EMAILS', '').strip()
ALLOWED_EMAILS = {e.lower().strip() for e in ALLOWED_EMAILS_RAW.split(',')} if ALLOWED_EMAILS_RAW else set()
PROMPT = os.environ.get('GOOGLE_OAUTH_PROMPT', 'select_account')
ID_TOKEN_LEEWAY = int(os.environ.get('ID_TOKEN_LEEWAY','60'))
VERIFY_AUD = os.environ.get('GOOGLE_VERIFY_AUD','1') not in ('0','false','no')

# ===== Helpers =====

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip('=')

def _gen_state() -> str:
    return _b64url(os.urandom(24))

def _gen_code_verifier() -> str:
    return _b64url(os.urandom(32))

def _code_challenge(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode()).digest())

def _clean_expired():
    """清理过期状态（委托给StateManager）"""
    StateManager.clean_expired()

def _clean_sessions():
    """清理过期会话（委托给SessionManager）"""
    SessionManager.clean_sessions()

# ===== Redis wrappers =====

def _save_state(state: str, redirect_uri: str, code_verifier: str):
    """保存OAuth状态（委托给StateManager）"""
    StateManager.save_state(state, redirect_uri, code_verifier, 'google')

def _pop_state(state: str):
    """获取并删除OAuth状态（委托给StateManager）"""
    return StateManager.pop_state(state)

def _save_session(session_id: str, data: Dict[str, Any], exp: int):
    """保存会话（委托给SessionManager）"""
    SessionManager.save_session(session_id, data, exp)

def _get_session(session_id: str):
    """获取会话（委托给SessionManager）"""
    return SessionManager.get_session(session_id)

def _refresh_session_if_needed(session_id: str, data: Dict[str, Any]):
    """会话续期（委托给SessionManager）"""
    return SessionManager.refresh_session_if_needed(session_id, data)

def _del_session(session_id: str):
    """删除会话（委托给SessionManager）"""
    SessionManager.delete_session(session_id)

def _user_index_id(email: Optional[str], sub: Optional[str]) -> Optional[str]:
    """生成用户索引ID（委托给SessionManager）"""
    return SessionManager._user_index_id(email, sub)

def _add_session_to_user(email: Optional[str], sub: Optional[str], session_id: str, ts: float):
    """添加会话到用户索引（委托给SessionManager）"""
    SessionManager.add_session_to_user(email, sub, session_id, ts)

def _list_user_sessions(email: Optional[str], sub: Optional[str]):
    """列出用户会话（委托给SessionManager）"""
    return SessionManager.list_user_sessions(email, sub)

# ===== Redirect URI selection =====

def _select_redirect_uri() -> str:
    origin = request.headers.get('Origin', '') or ''
    referer = request.headers.get('Referer', '') or ''  # fallback when Origin absent (same-origin GET often lacks Origin)
    req_host = request.headers.get('X-Forwarded-Host') or request.host or ''
    scheme = request.headers.get('X-Forwarded-Proto', request.scheme) or 'http'
    debug = os.environ.get('AUTH_DEBUG','0') in ('1','true','yes')
    def log(msg: str):
        if debug:
            try: print(f"[AUTH][REDIR] {msg}")
            except Exception: pass
    def norm(u: str) -> str: return u.rstrip('/')
    from urllib.parse import urlparse
    # Build candidate objects
    candidates: List[Dict[str, Any]] = []
    for raw in _redirect_uri_list:
        if '://' in raw:
            pr = None
            try: pr = urlparse(raw)
            except Exception: pass
            host = (pr.netloc if pr else '').lower()
            candidates.append({
                'raw': norm(raw),
                'type': 'full',
                'host': host,
                'scheme': pr.scheme if pr else 'https',
                'has_cb': raw.endswith('/api/auth/google/callback')
            })
        else:
            candidates.append({
                'raw': raw.lower(),
                'type': 'host',
                'host': raw.lower(),
                'scheme': scheme,
                'has_cb': False
            })
    origin_host = ''
    origin_scheme = scheme
    if origin:
        try:
            po = urlparse(origin)
            origin_host = (po.netloc or '').lower()
            if po.scheme: origin_scheme = po.scheme
        except Exception:
            pass
    referer_host = ''
    referer_scheme = scheme
    if referer:
        try:
            pr = urlparse(referer)
            referer_host = (pr.netloc or '').lower()
            if pr.scheme: referer_scheme = pr.scheme
        except Exception:
            pass
    req_host_l = req_host.lower()
    log(f"origin={origin} origin_host={origin_host} referer={referer} referer_host={referer_host} req_host={req_host_l} scheme={scheme} list={_redirect_uri_list}")

    def build(cb_candidate: Dict[str, Any], force_scheme: Optional[str]=None) -> str:
        if cb_candidate['type'] == 'full':
            if cb_candidate['has_cb']:
                return cb_candidate['raw']
            return f"{cb_candidate['raw']}/api/auth/google/callback"
        # host-only
        sc = force_scheme or cb_candidate['scheme'] or scheme
        return f"{sc}://{cb_candidate['host']}/api/auth/google/callback"

    # 1. Full URL host matches origin host
    if origin_host:
        for c in candidates:
            if c['host'] == origin_host and c['type'] == 'full':
                chosen = build(c)
                log(f"match: full origin_host -> {chosen}")
                return chosen
    # 2. Host-only matches origin host
    if origin_host:
        for c in candidates:
            if c['host'] == origin_host and c['type'] == 'host':
                chosen = build(c, force_scheme=origin_scheme)
                log(f"match: host origin_host -> {chosen}")
                return chosen
    # 2b. Full URL host matches referer host (when Origin missing)
    if not origin_host and referer_host:
        for c in candidates:
            if c['host'] == referer_host and c['type'] == 'full':
                chosen = build(c)
                log(f"match: full referer_host -> {chosen}")
                return chosen
    # 2c. Host-only matches referer host
    if not origin_host and referer_host:
        for c in candidates:
            if c['host'] == referer_host and c['type'] == 'host':
                chosen = build(c, force_scheme=referer_scheme)
                log(f"match: host referer_host -> {chosen}")
                return chosen
    # 3. Full matches request host
    for c in candidates:
        if c['host'] == req_host_l and c['type'] == 'full':
            chosen = build(c)
            log(f"match: full req_host -> {chosen}")
            return chosen
    # 4. Host-only matches request host
    for c in candidates:
        if c['host'] == req_host_l and c['type'] == 'host':
            chosen = build(c)
            log(f"match: host req_host -> {chosen}")
            return chosen
    # 5. Prefer first non-localhost candidate
    # Before jumping to non-localhost fallback, if request itself is localhost-ish (backend dev port)
    # and we have a localhost candidate, prefer that to keep same-site flow (ensures cookie usable by SPA).
    if req_host_l.startswith('127.') or req_host_l.startswith('localhost'):
        for c in candidates:
            if c['host'].startswith('localhost') or c['host'].startswith('127.'):
                chosen = build(c)
                log(f"heuristic localhost -> {chosen}")
                return chosen
    for c in candidates:
        if not c['host'].startswith('localhost') and not c['host'].startswith('127.'):
            chosen = build(c)
            log(f"fallback non-localhost -> {chosen}")
            return chosen
    # 6. Absolute fallback first candidate
    if candidates:
        chosen = build(candidates[0])
        log(f"fallback first -> {chosen}")
        return chosen
    # 7. Last resort
    default_cb = f"{scheme}://{req_host_l or 'localhost:5173'}/api/auth/google/callback"
    log(f"fallback default -> {default_cb}")
    return default_cb

# ===== Routes =====
@bp.route('/api/auth/google/start')
def start():
    if not CLIENT_ID or not CLIENT_SECRET:
        return { 'error': 'google auth not configured' }, 500
    _clean_expired(); _clean_sessions()
    state = _gen_state(); code_verifier = _gen_code_verifier(); challenge = _code_challenge(code_verifier)
    redirect_uri = _select_redirect_uri()
    _save_state(state, redirect_uri, code_verifier)
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'prompt': PROMPT
    }
    if ALLOWED_EMAIL_DOMAIN:
        params['hd'] = ALLOWED_EMAIL_DOMAIN
    return { 'url': f"{GOOGLE_AUTH_URL}?{urlencode(params)}" }

@bp.route('/api/auth/google/callback')
def callback():
    error = request.args.get('error')
    if error: return _popup_result(success=False, reason=error)
    code = request.args.get('code'); state = request.args.get('state')
    if not code or not state: return _popup_result(success=False, reason='missing_code_or_state')
    meta, verifier = _pop_state(state)
    if not meta or meta.get('exp', 0) < time.time() or not verifier:
        return _popup_result(success=False, reason='invalid_state')
    redirect_uri = meta.get('redirect_uri', REDIRECT_URI)
    data = {
        'code': code,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
        'code_verifier': verifier
    }
    try:
        token_res = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=10)
        token_json = token_res.json()
    except Exception as e:
        return _popup_result(success=False, reason=f'token_exchange_failed:{e}')
    id_token_str = token_json.get('id_token')
    if not id_token_str:
        return _popup_result(success=False, reason='missing_id_token')
    try:
        req = google_requests.Request()
        payload_json = google_id_token.verify_oauth2_token(
            id_token_str, req, CLIENT_ID if VERIFY_AUD else None, clock_skew_in_seconds=ID_TOKEN_LEEWAY
        )
    except Exception as e:
        return _popup_result(success=False, reason=f'id_token_verify_failed:{e}')

    sub = payload_json.get('sub'); email = (payload_json.get('email') or '').lower()
    name = payload_json.get('name'); picture = payload_json.get('picture')
    email_verified = payload_json.get('email_verified'); hd_claim = (payload_json.get('hd') or '').lower()
    if not sub: return _popup_result(success=False, reason='missing_sub')
    if ALLOWED_EMAIL_DOMAIN and hd_claim != ALLOWED_EMAIL_DOMAIN: return _popup_result(success=False, reason='forbidden_domain')
    if ALLOWED_EMAILS and email and email not in ALLOWED_EMAILS: return _popup_result(success=False, reason='email_not_allowed')
    if email and email_verified is False: return _popup_result(success=False, reason='email_not_verified')

    # 1) Google ID Token 自带 exp (通常 ~1h)。为了满足“离线很久回来仍然自动登录”的需求，
    #    我们允许通过 SESSION_MIN_SECONDS 设定一个初始最短生命周期：
    #    如果 id_token 给出的剩余时间 < SESSION_MIN_SECONDS，则采用 now + SESSION_MIN_SECONDS。
    #    这样即便用户离线超过 Google token 原本 1 小时，仍有本地会话（凭我们自己的服务器侧 session）保持。
    #    安全注意：如果设置很长（例如 30 天），应结合必要的登出 / 撤销策略与 HTTPS + HttpOnly。
    now_ts = time.time()
    id_token_exp = payload_json.get('exp')
    if id_token_exp:
        try:
            id_token_exp = int(id_token_exp)
        except Exception:
            id_token_exp = None
    if id_token_exp:
        exp = int(id_token_exp)
    else:
        exp = int(now_ts + SESSION_TTL_DEFAULT)
    if SESSION_MIN_SECONDS > 0:
        min_target = int(now_ts + SESSION_MIN_SECONDS)
        if exp < min_target:
            exp = min_target
    session_id = SessionManager.generate_session_id()
    ua = request.headers.get('User-Agent', '')[:400]
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
    session_payload = {
        'sub': sub, 'email': email, 'name': name, 'picture': picture,
        'provider': 'google', 'ts': time.time(), 'exp': exp, 'ua': ua, 'ip': ip
    }
    _add_session_to_user(email, sub, session_id, time.time())
    # Persist / update user record in Postgres (best effort)
    try:
        up_ok, is_new = upsert_user(sub, 'google', email, name, picture, ip)
        session_payload['is_new_user'] = bool(is_new)
        if os.environ.get('AUTH_DEBUG','0') in ('1','true','yes'):
            print(f"[AUTH][DB] upsert_user sub={sub} ok={up_ok} is_new={is_new}")
    except Exception as e:
        if os.environ.get('AUTH_DEBUG','0') in ('1','true','yes'):
            print(f"[AUTH][DB] upsert_user error {e}")
    # Save session after enriching payload (ensures is_new_user present)
    _save_session(session_id, session_payload, exp)

    resp = _popup_result(success=True)
    cookie_max = max(0, exp - int(time.time())) if exp else SESSION_TTL_DEFAULT
    # Optional cookie domain
    # 使用 SameSite=None 以支持跨域场景（特别是 iPhone Safari）
    # 注意：SameSite=None 必须配合 Secure=True 使用
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
    resp.set_cookie(SESSION_COOKIE, session_id, **cookie_kwargs)  # ensure cookie available to all API paths
    if os.environ.get('AUTH_DEBUG','0') in ('1','true','yes'):
        try:
            now_ts = int(time.time())
            print(f"[AUTH][COOKIE_SET] sid={session_id[:12]}.. domain={chosen_domain or '(host)'} max_age={cookie_max} now={now_ts} exp={exp} delta={exp-now_ts if exp else 'n/a'} secure={SESSION_COOKIE_SECURE} samesite={cookie_kwargs.get('samesite')}")
        except Exception as e:
            print(f"[AUTH][COOKIE_SET] Error logging: {e}")
    return resp

    chosen_domain = select_cookie_domain(request.host)

def _popup_result(success: bool, reason: Optional[str] = None):
    # Enhanced script: if opened as popup -> postMessage & close; if full page (fallback on mobile), store flag and redirect intelligently.
    # Safari 特殊处理：检测 Safari 并添加额外的兼容性处理
    user_agent = request.headers.get('User-Agent', '').lower()
    is_safari = 'safari' in user_agent and 'chrome' not in user_agent
    is_ios = any(x in user_agent for x in ['iphone', 'ipad', 'ipod'])
    
    html = ["<html><head><meta charset='utf-8'></head><body><script>"]
    html.append(
        "window.addEventListener('message', function(event){\n"
        "    try {\n"
        "        if(!event || !event.data) return;\n"
        "        if(event.data && event.data.type === 'auth:close-popup'){\n"
        "            try { window.close(); } catch(_) {}\n"
        "            setTimeout(function(){ window.location.replace('/home'); }, 200);\n"
        "        }\n"
        "    } catch(err) {\n"
        "        setTimeout(function(){ window.location.replace('/home'); }, 300);\n"
        "    }\n"
        "});"
    )
    
    if success:
        # Safari 成功处理
        safari_extra = ""
        if is_safari or is_ios:
            safari_extra = """
            // Safari 特殊处理
            localStorage.setItem('auth:safariAuth','1');
            localStorage.setItem('auth:showWelcome','1');
            // 强制触发存储事件
            try { window.dispatchEvent(new StorageEvent('storage', {key:'auth:justLoggedIn',newValue:'1'})); } catch(e) {}
            // 延迟处理确保存储完成
            setTimeout(function() {
                localStorage.setItem('auth:justLoggedIn','1');
            }, 100);
            """
        
        html.append(f"""
            (function(){{
                var isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
                var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
                
                try {{
                    if(window.opener) {{
                        window.opener.postMessage({{type:'auth:success',provider:'google'}}, window.location.origin);
                        window.close();
                    }} else {{
                        localStorage.setItem('auth:justLoggedIn','1');
                        {safari_extra}
                        
                        var returnPath = localStorage.getItem('auth:returnPath');
                        localStorage.removeItem('auth:returnPath');
                        localStorage.removeItem('auth:isFullPageAuth');
                        
                        // Safari 需要更长的延迟
                        var delay = (isSafari || isIOS) ? 300 : 100;
                        setTimeout(function() {{
                            if(returnPath && returnPath !== '/' && returnPath !== '') {{
                                window.location.replace(returnPath);
                            }} else {{
                                window.location.replace('/home');
                            }}
                        }}, delay);
                    }}
                }} catch(e) {{
                    console.error('Auth callback error:', e);
                    localStorage.setItem('auth:justLoggedIn','1');
                    {safari_extra}
                    setTimeout(function() {{
                        window.location.replace('/home');
                    }}, (isSafari || isIOS) ? 500 : 100);
                }}
            }})();
        """)
    else:
        safe_reason = (reason or 'unknown').replace("'", "\\'")
        html.append(f"""
            (function(){{
                var isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
                var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
                
                try {{
                    if(window.opener) {{
                        window.opener.postMessage({{type:'auth:failure',provider:'google',reason:'{safe_reason}'}}, window.location.origin);
                        window.close();
                    }} else {{
                        localStorage.setItem('auth:authFail','{safe_reason}');
                        var returnPath = localStorage.getItem('auth:returnPath');
                        localStorage.removeItem('auth:returnPath');
                        localStorage.removeItem('auth:isFullPageAuth');
                        
                        var delay = (isSafari || isIOS) ? 300 : 100;
                        setTimeout(function() {{
                            if(returnPath && returnPath !== '/' && returnPath !== '') {{
                                window.location.replace(returnPath);
                            }} else {{
                                window.location.replace('/home');
                            }}
                        }}, delay);
                    }}
                }} catch(e) {{
                    console.error('Auth error callback:', e);
                    localStorage.setItem('auth:authFail','{safe_reason}');
                    setTimeout(function() {{
                        window.location.replace('/home');
                    }}, (isSafari || isIOS) ? 500 : 100);
                }}
            }})();
        """)
    
    html.append("</script></body></html>")
    return make_response('\n'.join(html))

@bp.route('/api/auth/_debug')
def auth_debug():
    sid = request.cookies.get(SESSION_COOKIE)
    sess = _get_session(sid) if sid else None
    
    # 获取管理器的调试信息
    session_debug = SessionManager.get_debug_info()
    state_debug = StateManager.get_debug_info()
    debug_keys = session_debug.get('redis_keys_sample')
    
    chosen_domain = select_cookie_domain(request.host)
    return {
        'db_import_impl': _DB_IMPORT_IMPL,
        'db_import_error': _DB_IMPORT_ERROR,
        'sid_present': bool(sid),
        'session_found': bool(sess),
        'cookie_domain_cfg': SESSION_COOKIE_DOMAIN_RAW or '(default host)',
        'cookie_domain_list': SESSION_COOKIE_DOMAINS,
        'cookie_domain_chosen': chosen_domain or '(host-only)',
        'host': request.host,
        'origin_hdr': request.headers.get('Origin'),
        'forwarded_host': request.headers.get('X-Forwarded-Host'),
        'forwarded_proto': request.headers.get('X-Forwarded-Proto'),
        'auth_debug_env': os.environ.get('AUTH_DEBUG'),
        'session_snapshot': {k: sess.get(k) for k in ('sub','email','exp','ts','ua','ip')} if sess else None,
        'redis_keys_sample': debug_keys,
        # 合并管理器的调试信息
        **session_debug,
        **state_debug
    }

@bp.route('/api/auth/db_user')
def auth_db_user():
    sub = request.args.get('sub') or request.args.get('id')
    if not sub:
        return { 'error': 'missing sub' }, 400
    try:
        row = get_user(sub)
        return { 'found': bool(row), 'user': row }
    except Exception as e:
        return { 'error': str(e) }, 500
