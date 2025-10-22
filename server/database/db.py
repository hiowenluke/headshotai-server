import os, threading, traceback
from typing import Optional, Dict, Any
from pathlib import Path

_conn_lock = threading.Lock()
_conn = None
_dsn_cache = None

BASE_DIR = Path(__file__).parent
SQL_DIR = BASE_DIR / 'sql'

def _db_debug() -> bool:
    return os.environ.get('DB_DEBUG') in ('1','true','TRUE','yes','on') or os.environ.get('AUTH_DB_DEBUG') in ('1','true','TRUE','yes','on')

def _dblog(*args):
    if _db_debug():
        try:
            print('[DB]', *args)
        except:
            pass
    # For very early diagnosis when user expects output but debug not triggering,
    # allow forcing a one-time environment echo (set DB_DEBUG_ECHO=1).
    elif os.environ.get('DB_DEBUG_ECHO') in ('1','true','yes'):
        try:
            print('[DB][ECHO]', *args)
        except:
            pass

def _load_sql(name: str) -> str:
    path = SQL_DIR / name
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

SQL_INSERT_USER = _load_sql('insert_user.sql')
SQL_SELECT_USER_ID_BY_EMAIL = _load_sql('select_user_id_by_email.sql')
SQL_INSERT_IDENTITY = _load_sql('insert_identity.sql')
SQL_SELECT_USER_BY_PROVIDER_SUB = _load_sql('select_user_by_provider_sub.sql')
SQL_SELECT_USER_BY_EMAIL = _load_sql('select_user_by_email.sql')

def _build_dsn() -> Optional[str]:
    dsn = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL') or os.environ.get('PG_DSN')
    if not dsn:
        host = os.environ.get('PGHOST')
        if not host: return None
        user = os.environ.get('PGUSER','postgres')
        password = os.environ.get('PGPASSWORD','')
        db = os.environ.get('PGDATABASE','postgres')
        port = os.environ.get('PGPORT','5432')
        dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return dsn

def get_conn():
    global _conn, _dsn_cache
    dsn = _build_dsn()
    if not dsn:
        return None
    with _conn_lock:
        if _conn is not None and _dsn_cache == dsn:
            return _conn
        try:
            import psycopg
            _conn = psycopg.connect(dsn, autocommit=True)
            _dsn_cache = dsn
            return _conn
        except Exception as e:
            try: print('[DB] connection failed', e)
            except: pass
            _conn = None
            return None

# Schema creation removed; run db_init.sql externally.

def _sanitize_username(candidate: str) -> str:
    import re
    candidate = candidate.lower()
    # keep alnum and underscore
    candidate = re.sub(r'[^a-z0-9_]+','', candidate)
    if not candidate:
        candidate = 'user'
    return candidate[:48]  # reserve room for suffix

def upsert_user(sub: str, provider: str, email: Optional[str], name: Optional[str], picture: Optional[str], ip: Optional[str] = None):
    """Upsert user & identity.
    Returns tuple (ok: bool, is_new: Optional[bool]) where is_new indicates whether user row was newly inserted.
    For backward compatibility callers expecting bool may treat truthy first element only.
    """
    debug = _db_debug()
    if not email:
        if debug: print('[DB][UPSERT] ok=False reason=missing_email sub', sub)
        return False
    conn = get_conn()
    if not conn:
        if debug: print('[DB][UPSERT] ok=False reason=no_connection sub', sub)
        return False
    try:
        with conn.cursor() as cur:
            base = _sanitize_username(email.split('@',1)[0])
            username = base
            user_id = None
            # 先判断是否已有该邮箱，避免依赖异常字符串来区分新老用户
            cur.execute(SQL_SELECT_USER_ID_BY_EMAIL, {'email': email})
            r_exist = cur.fetchone()
            inserted = False
            if r_exist:
                user_id = r_exist[0]
                # 单独执行更新 last_login 信息（与原 INSERT ON CONFLICT 行为等价）
                try:
                    cur.execute("UPDATE public.users SET last_login_at=now(), last_login_ip=%(ip)s, updated_at=now() WHERE id=%(id)s", {'ip': ip, 'id': user_id})
                except Exception as e_upd:
                    if debug: print('[DB][UPSERT][UPDATE_EXISTING] warn', e_upd)
            else:
                # 不存在再尝试插入（处理用户名冲突）
                for attempt in range(12):
                    try:
                        cur.execute(SQL_INSERT_USER, {'username': username,'email': email,'ip': ip})
                        user_id = cur.fetchone()[0]
                        inserted = True
                        break
                    except Exception as e_ins:
                        msg = str(e_ins)
                        if debug: print('[DB][UPSERT] attempt_fail', attempt, msg)
                        if 'users_username_key' in msg and attempt < 10:
                            username = f"{base}{attempt+1}"[:50]
                            continue
                        if 'users_email_key' in msg:
                            # 并发插入竞争：再查一次视为老用户
                            cur.execute(SQL_SELECT_USER_ID_BY_EMAIL, {'email': email})
                            r2 = cur.fetchone()
                            if r2:
                                user_id = r2[0]
                                inserted = False
                                break
                        raise
            if not user_id:
                cur.execute(SQL_SELECT_USER_ID_BY_EMAIL, {'email': email})
                r = cur.fetchone()
                if r: user_id = r[0]
            if not user_id:
                if debug: print('[DB][UPSERT] ok=False reason=no_user_id email', email)
                return False, None
            try:
                cur.execute(SQL_INSERT_IDENTITY, {
                    'user_id': user_id,'provider': provider,'provider_sub': sub,'name': name,'picture': picture
                })
            except Exception as e_ident:
                if debug: print('[DB][IDENT] ignore_fail', str(e_ident))
            if debug: print('[DB][UPSERT] ok=True email', email, 'id', user_id, 'is_new', inserted)
            return True, inserted
    except Exception as e:
        if debug:
            print('[DB][UPSERT] ok=False exception', repr(e))
            traceback.print_exc()
        return False, None

def get_user(sub_or_email: str) -> Optional[Dict[str, Any]]:
    """Fetch joined user + identity by provider_sub if looks like numeric/long, else by email."""
    conn = get_conn()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            # Try identity match (provider_sub)
            cur.execute(SQL_SELECT_USER_BY_PROVIDER_SUB, {'provider_sub': sub_or_email})
            r = cur.fetchone()
            if not r:
                # Fallback: email lookup
                cur.execute(SQL_SELECT_USER_BY_EMAIL, {'email': sub_or_email})
                r = cur.fetchone()
                if not r: return None
            return {
                'id': r[0], 'username': r[1], 'email': r[2], 'coin_balance': r[3],
                'last_login_at': r[4].isoformat() if r[4] else None,
                'last_login_ip': r[5],
                'created_at': r[6].isoformat() if r[6] else None,
                'updated_at': r[7].isoformat() if r[7] else None,
                'provider': r[8], 'provider_sub': r[9], 'name': r[10], 'picture': r[11]
            }
    except Exception as e:
        try: print('[DB] get_user failed', e)
        except: pass
        return None
