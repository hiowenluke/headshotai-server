#!/usr/bin/env python3
"""Clear a user's login sessions (Redis) by email (and optionally legacy sub index).

Usage:
  python scripts/user_clear_login_state.py user@example.com [--legacy-sub SUB] [--dry-run] [--force]

Behavior:
  * Loads .env (best-effort) for REDIS_URL / REDIS_URI / REDIS_PREFIX.
  * Finds Redis ZSET index <prefix>:usess:<email_lower> (new scheme) and removes it plus all referenced session keys <prefix>:sess:<sid>.
  * Optionally also clears legacy index <prefix>:usess:<sub> if --legacy-sub provided.
  * Provides JSON summary lines for automation.
"""
from __future__ import annotations
import os, re, sys, argparse, json
from typing import Optional, Dict, Any

try:
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None  # type: ignore

_ENV_LOADED = False

def _load_env_dotenv():
    global _ENV_LOADED
    if _ENV_LOADED: return
    path = '.env'
    if not os.path.isfile(path): return
    try:
        import re as _re
        with open(path, 'r', encoding='utf-8') as f:
            for raw in f:
                line = raw.rstrip('\n')
                if not line or line.lstrip().startswith('#'): continue
                m = _re.match(r'([A-Za-z_][A-Za-z0-9_]*)=(.*)', line)
                if not m: continue
                k, v = m.group(1), m.group(2)
                if k in os.environ: continue
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                for _ in range(8):
                    nv = _re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', lambda mm: os.environ.get(mm.group(1), ''), v)
                    if nv == v: break
                    v = nv
                os.environ[k] = v
        _ENV_LOADED = True
    except Exception as e:  # pragma: no cover
        print(json.dumps({'stage':'warn','msg':f'parse_env_failed:{e}'}))

def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() == 'yes'
    except EOFError:
        return False

def _redis_connect(url: Optional[str]):
    if not url or not redis:
        return None
    try:
        r = redis.Redis.from_url(url, decode_responses=True)
        r.ping()
        return r
    except Exception as e:  # pragma: no cover
        print(json.dumps({'stage':'warn','msg':f'redis_connect_failed:{e}'}))
        return None

def clear_user_login_state(email: str, legacy_sub: Optional[str]=None, dry_run: bool=False, force: bool=False) -> Dict[str, Any]:
    _load_env_dotenv()
    email_l = email.lower().strip()
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email_l):
        raise SystemExit('invalid email format')
    prefix = os.environ.get('REDIS_PREFIX','appauth')
    rurl = os.environ.get('REDIS_URL') or os.environ.get('REDIS_URI')
    rcli = _redis_connect(rurl)
    if not rcli:
        return {
            'email': email_l,
            'redis_connected': False,
            'index_deleted': False,
            'sessions_deleted': 0,
            'legacy_index_deleted': False,
            'legacy_sessions_deleted': 0,
        }
    if not force and not dry_run:
        # Isolated confirmation (caller may have confirmed already – they can pass force to skip)
        if not _confirm(f'确认清理该用户的所有 Redis 登录状态 email={email_l}? (yes/NO): '):
            return {'cancelled': True, 'email': email_l}

    index_key = f"{prefix}:usess:{email_l}"
    members = []
    sessions_deleted = 0
    missing_sessions = 0
    index_deleted = False
    if rcli.exists(index_key):
        try:
            members = rcli.zrange(index_key, 0, -1) or []
        except Exception:  # pragma: no cover
            members = []
        if not dry_run:
            try: rcli.delete(index_key); index_deleted = True
            except Exception: index_deleted = False
        for sid in members:
            sk = f"{prefix}:sess:{sid}"
            if rcli.exists(sk):
                if not dry_run:
                    try: rcli.delete(sk); sessions_deleted += 1
                    except Exception: pass
            else:
                missing_sessions += 1
    legacy_index_deleted = False
    legacy_sessions_deleted = 0
    if legacy_sub:
        legacy_key = f"{prefix}:usess:{legacy_sub}"
        if rcli.exists(legacy_key):
            try:
                legacy_members = rcli.zrange(legacy_key, 0, -1) or []
            except Exception:
                legacy_members = []
            if not dry_run:
                try: rcli.delete(legacy_key); legacy_index_deleted = True
                except Exception: legacy_index_deleted = False
            for sid in legacy_members:
                sk = f"{prefix}:sess:{sid}"
                if rcli.exists(sk):
                    if not dry_run:
                        try: rcli.delete(sk); legacy_sessions_deleted += 1
                        except Exception: pass
    return {
        'email': email_l,
        'redis_connected': True,
        'index_key': index_key,
        'index_member_count': len(members),
        'index_deleted': index_deleted,
        'sessions_deleted': sessions_deleted,
        'missing_sessions': missing_sessions,
        'legacy_index_deleted': legacy_index_deleted,
        'legacy_sessions_deleted': legacy_sessions_deleted,
        'dry_run': dry_run,
    }

def _main():
    ap = argparse.ArgumentParser(description='Clear user login sessions (Redis) by email.')
    ap.add_argument('email')
    ap.add_argument('--legacy-sub', help='also clear legacy usess:<sub> index')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()
    res = clear_user_login_state(args.email, args.legacy_sub, args.dry_run, args.force)
    print(json.dumps({'stage':'done', **res}, ensure_ascii=False))

if __name__ == '__main__':
    _main()
