"""
会话管理模块 - 独立的Redis/内存会话操作
支持多种OAuth提供商复用
"""
import os
import json
import time
import threading
import secrets
from typing import Dict, Optional, List, Any

# Redis配置
REDIS_URL = os.environ.get('REDIS_URL') or os.environ.get('REDIS_URI') or ''
REDIS_PREFIX = os.environ.get('REDIS_PREFIX', 'appauth')
MAX_USER_SESSIONS = int(os.environ.get('MAX_USER_SESSIONS', '0') or '0')  # 0 = unlimited
SESSION_LIST_RETURN_LIMIT = int(os.environ.get('SESSION_LIST_LIMIT', '20') or '20')

# 会话配置
SESSION_TTL_DEFAULT = 3600
SESSION_SLIDING_ENABLED = os.environ.get('SESSION_SLIDING','1').lower() in ('1','true','yes')
SESSION_SLIDING_SECONDS = int(os.environ.get('SESSION_SLIDING_SECONDS','3600') or '3600')
SESSION_ABSOLUTE_SECONDS = int(os.environ.get('SESSION_ABSOLUTE_SECONDS','0') or '0')

# Redis连接
_redis = None
if REDIS_URL:
    try:
        import redis  # type: ignore
        _redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        try: 
            _redis.ping()
        except Exception: 
            _redis = None
    except Exception:
        _redis = None

# 内存存储fallback
_session_store: Dict[str, Dict] = {}
_user_sessions: Dict[str, List[str]] = {}  # per-user session id list (memory mode)
_lock = threading.Lock()

def _rkey(kind: str, ident: str) -> str:
    """生成Redis键名"""
    return f"{REDIS_PREFIX}:{kind}:{ident}"

def _debug_log(msg: str):
    """调试日志"""
    if os.environ.get('AUTH_DEBUG','0') in ('1','true','yes'):
        try:
            print(f"[SESSION_MANAGER] {msg}")
        except Exception:
            pass

class SessionManager:
    """会话管理器"""
    
    @staticmethod
    def save_session(session_id: str, data: Dict[str, Any], exp: int):
        """保存会话"""
        ttl = max(60, exp - int(time.time())) if exp else SESSION_TTL_DEFAULT
        if _redis:
            _redis.set(_rkey('sess', session_id), json.dumps(data), ex=ttl)
        else:
            with _lock:
                _session_store[session_id] = data
                sub = data.get('sub')
                if sub:
                    lst = _user_sessions.setdefault(sub, [])
                    lst.append(session_id)
                    SessionManager._enforce_max_sessions_memory(sub)
        
        _debug_log(f"save_session id={session_id} sub={data.get('sub')} exp={exp} ttl={ttl} redis={bool(_redis)}")

    @staticmethod
    def get_session(session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        if _redis:
            raw = _redis.get(_rkey('sess', session_id))
            if not raw: 
                return None
            try: 
                return json.loads(raw)
            except Exception: 
                return None
        else:
            with _lock:
                return _session_store.get(session_id)

    @staticmethod
    def delete_session(session_id: str):
        """删除会话"""
        if _redis:
            _redis.delete(_rkey('sess', session_id))
        else:
            with _lock:
                sess = _session_store.pop(session_id, None)
                if sess:
                    sub = sess.get('sub')
                    if sub and sub in _user_sessions:
                        _user_sessions[sub] = [s for s in _user_sessions[sub] if s != session_id]
                        if not _user_sessions[sub]: 
                            _user_sessions.pop(sub, None)

    @staticmethod
    def refresh_session_if_needed(session_id: str, data: Dict[str, Any]) -> Optional[int]:
        """Sliding 续期: 如果开启并且还未过期, 刷新 exp / TTL / cookie。
        策略: 剩余时间 < SESSION_SLIDING_SECONDS/2 时才写入，减少写放大。
        绝对上限: 若配置 SESSION_ABSOLUTE_SECONDS>0, exp 不会超过 ts+absolute。
        """
        if not SESSION_SLIDING_ENABLED:
            return None
        
        now = time.time()
        cur_exp = data.get('exp') or int(now + SESSION_TTL_DEFAULT)
        if cur_exp <= now:
            return None  # 已过期不续
        
        remaining = cur_exp - now
        # 计算新的候选 exp
        new_exp_candidate = int(now + SESSION_SLIDING_SECONDS)
        if SESSION_ABSOLUTE_SECONDS > 0:
            absolute_deadline = int(data.get('ts', now) + SESSION_ABSOLUTE_SECONDS)
            if new_exp_candidate > absolute_deadline:
                new_exp_candidate = absolute_deadline
        
        # 若剩余时间足够，跳过
        if remaining > SESSION_SLIDING_SECONDS / 2 and new_exp_candidate <= cur_exp:
            return None
        
        # 更新数据并重写存储
        data['exp'] = new_exp_candidate
        SessionManager.save_session(session_id, data, new_exp_candidate)
        return new_exp_candidate

    @staticmethod
    def _user_index_id(email: Optional[str], sub: Optional[str]) -> Optional[str]:
        """生成用户索引ID"""
        eid = (email or '').lower().strip()
        if eid:
            return eid
        return sub  # fallback

    @staticmethod
    def add_session_to_user(email: Optional[str], sub: Optional[str], session_id: str, ts: float):
        """将会话添加到用户索引"""
        idx = SessionManager._user_index_id(email, sub)
        if not idx:
            return
        
        if _redis:
            try:
                _redis.zadd(_rkey('usess', idx), { session_id: ts })
            except Exception:
                pass
            
            if MAX_USER_SESSIONS > 0:
                try:
                    over = _redis.zcard(_rkey('usess', idx)) - MAX_USER_SESSIONS
                    if over > 0:
                        old = _redis.zrange(_rkey('usess', idx), 0, over-1)
                        if old:
                            for sid in old:
                                SessionManager.delete_session(sid)
                            _redis.zrem(_rkey('usess', idx), *old)
                except Exception:
                    pass
        else:
            with _lock:
                lst = _user_sessions.setdefault(idx, [])
                lst.append(session_id)
            SessionManager._enforce_max_sessions_memory(idx)

    @staticmethod
    def _enforce_max_sessions_memory(idx: str):
        """强制执行内存模式下的最大会话数限制"""
        if MAX_USER_SESSIONS > 0:
            with _lock:
                lst = _user_sessions.get(idx, [])
                while len(lst) > MAX_USER_SESSIONS:
                    remove_id = lst.pop(0)
                    _session_store.pop(remove_id, None)

    @staticmethod
    def list_user_sessions(email: Optional[str], sub: Optional[str]) -> List[Dict[str, Any]]:
        """列出用户的所有会话"""
        now = time.time()
        idx = SessionManager._user_index_id(email, sub)
        if not idx:
            return []
        
        if _redis:
            try:
                # Primary (email) index
                def fetch_idx(i):
                    total = _redis.zcard(_rkey('usess', i))
                    if total == 0:
                        return []
                    start = max(0, total - SESSION_LIST_RETURN_LIMIT)
                    return list(reversed(_redis.zrange(_rkey('usess', i), start, -1)))
                
                sids = fetch_idx(idx)
                # Backward compatibility: if empty and sub differs from idx, try legacy sub index
                if not sids and sub and sub != idx:
                    legacy = fetch_idx(sub)
                    if legacy:
                        sids = legacy
                
                result = []
                stale: List[str] = []
                for sid in sids:
                    sess = SessionManager.get_session(sid)
                    if not sess:
                        stale.append(sid)
                        continue
                    exp = sess.get('exp')
                    result.append({
                        'session_id': sid,
                        'created_at': sess.get('ts'),
                        'expires_at': exp,
                        'expired': bool(exp and exp < now),
                        'ua': sess.get('ua'),
                        'ip': sess.get('ip'),
                        'provider': sess.get('provider', 'unknown')
                    })
                
                # 惰性清理：移除已失效的 session 索引，保持 ZSET 干净
                if stale:
                    try:
                        _redis.zrem(_rkey('usess', idx), *stale)
                        # 若清理后为空，删除整个 key（节省内存 & 便于观察）
                        if _redis.zcard(_rkey('usess', idx)) == 0:
                            _redis.delete(_rkey('usess', idx))
                    except Exception:
                        pass
                return result
            except Exception:
                return []
        else:
            with _lock:
                sids = list(_user_sessions.get(idx, []))[-SESSION_LIST_RETURN_LIMIT:]
            
            result = []
            for sid in reversed(sids):
                sess = SessionManager.get_session(sid)
                if not sess:
                    continue
                exp = sess.get('exp')
                result.append({
                    'session_id': sid,
                    'created_at': sess.get('ts'),
                    'expires_at': exp,
                    'expired': bool(exp and exp < now),
                    'ua': sess.get('ua'),
                    'ip': sess.get('ip'),
                    'provider': sess.get('provider', 'unknown')
                })
            return result

    @staticmethod
    def clean_sessions():
        """清理过期会话（内存模式下使用）"""
        if _redis: 
            return  # Redis模式下由TTL自动处理
        
        now = time.time()
        with _lock:
            expired = [sid for sid, data in _session_store.items() if data.get('exp') and data['exp'] < now]
            for sid in expired:
                _session_store.pop(sid, None)
                # 清理 user 索引
                for sub, lst in list(_user_sessions.items()):
                    if sid in lst:
                        lst[:] = [x for x in lst if x != sid]
                        if not lst: 
                            _user_sessions.pop(sub, None)

    @staticmethod
    def generate_session_id() -> str:
        """生成安全的会话ID"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def is_redis_enabled() -> bool:
        """检查Redis是否可用"""
        return bool(_redis)

    @staticmethod
    def get_debug_info() -> Dict[str, Any]:
        """获取调试信息"""
        debug_keys = None
        if os.environ.get('AUTH_DEBUG','0') in ('1','true','yes') and _redis:
            try:
                # Only fetch small key list for inspection
                all_keys = _redis.keys(_rkey('*','*'))  # pattern appauth:*:* typically small
                debug_keys = all_keys[:50]
            except Exception:
                debug_keys = 'error'
        
        return {
            'redis_url_configured': bool(REDIS_URL),
            'redis_connected': bool(_redis),
            'session_keys_memory': len(_session_store) if not _redis else 'redis',
            'user_sessions_memory': len(_user_sessions) if not _redis else 'redis',
            'redis_keys_sample': debug_keys,
            'max_user_sessions': MAX_USER_SESSIONS,
            'session_sliding_enabled': SESSION_SLIDING_ENABLED,
            'session_sliding_seconds': SESSION_SLIDING_SECONDS,
            'session_absolute_seconds': SESSION_ABSOLUTE_SECONDS
        }
