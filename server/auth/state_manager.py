"""
OAuth状态管理模块 - 独立的状态存储操作
支持多种OAuth提供商复用
"""
import os
import json
import time
import threading
from typing import Dict, Optional, Tuple, Any

# Redis配置
REDIS_URL = os.environ.get('REDIS_URL') or os.environ.get('REDIS_URI') or ''
REDIS_PREFIX = os.environ.get('REDIS_PREFIX', 'appauth')
STATE_TTL = 600

# Redis连接（复用session_manager的连接逻辑）
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
_state_store: Dict[str, Dict[str, Any]] = {}
_code_verifiers: Dict[str, str] = {}
_lock = threading.Lock()

def _rkey(kind: str, ident: str) -> str:
    """生成Redis键名"""
    return f"{REDIS_PREFIX}:{kind}:{ident}"

def _debug_log(msg: str):
    """调试日志"""
    if os.environ.get('AUTH_DEBUG','0') in ('1','true','yes'):
        try:
            print(f"[STATE_MANAGER] {msg}")
        except Exception:
            pass

class StateManager:
    """OAuth状态管理器"""
    
    @staticmethod
    def save_state(state: str, redirect_uri: str, code_verifier: str, provider: str = 'google'):
        """保存OAuth状态"""
        exp_ts = int(time.time() + STATE_TTL)
        state_data = {
            'redirect_uri': redirect_uri, 
            'exp': exp_ts,
            'provider': provider
        }
        
        if _redis:
            pipe = _redis.pipeline()
            pipe.set(_rkey('state', state), json.dumps(state_data), ex=STATE_TTL)
            pipe.set(_rkey('codev', state), code_verifier, ex=STATE_TTL)
            pipe.execute()
        else:
            with _lock:
                _state_store[state] = state_data
                _code_verifiers[state] = code_verifier
        
        _debug_log(f"save_state state={state[:8]}... provider={provider} redirect_uri={redirect_uri}")

    @staticmethod
    def pop_state(state: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """获取并删除OAuth状态"""
        if _redis:
            pipe = _redis.pipeline()
            pipe.get(_rkey('state', state))
            pipe.get(_rkey('codev', state))
            pipe.delete(_rkey('state', state))
            pipe.delete(_rkey('codev', state))
            res = pipe.execute()
            meta_raw, verifier = res[0], res[1]
            meta = json.loads(meta_raw) if meta_raw else None
        else:
            with _lock:
                meta = _state_store.pop(state, None)
                verifier = _code_verifiers.pop(state, None)
        
        _debug_log(f"pop_state state={state[:8]}... found={bool(meta)} verifier={bool(verifier)}")
        return meta, verifier

    @staticmethod
    def clean_expired():
        """清理过期状态（内存模式下使用）"""
        if _redis: 
            return  # Redis模式下由TTL自动处理
        
        now = time.time()
        with _lock:
            obsolete = [s for s, meta in _state_store.items() if meta.get('exp', 0) < now]
            for s in obsolete:
                _state_store.pop(s, None)
                _code_verifiers.pop(s, None)
        
        if obsolete:
            _debug_log(f"clean_expired removed {len(obsolete)} expired states")

    @staticmethod
    def is_redis_enabled() -> bool:
        """检查Redis是否可用"""
        return bool(_redis)

    @staticmethod
    def get_debug_info() -> Dict[str, Any]:
        """获取调试信息"""
        return {
            'redis_url_configured': bool(REDIS_URL),
            'redis_connected': bool(_redis),
            'state_store_memory': len(_state_store) if not _redis else 'redis',
            'code_verifiers_memory': len(_code_verifiers) if not _redis else 'redis',
            'state_ttl': STATE_TTL
        }
