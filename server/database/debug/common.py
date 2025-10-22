"""Shared helpers for database debug scripts.

Provides:
  load_env(path='.env') -> dict of parsed key/values (first found) with ${VAR} expansion.
  build_dsn() -> best-effort PostgreSQL DSN string or None.
  debug_connect(dsn) -> bool, prints JSON diagnostic line.

Output lines are JSON to stay consistent with other debug tools.
"""
from __future__ import annotations
import os, re, json, time, traceback
from typing import Dict, Optional

_ENV_LOADED = False
_ENV_CACHE: Dict[str,str] = {}

def load_env(path: str = '.env') -> Dict[str,str]:
    """Load environment variables from a .env file once.

    Search order:
      1. repo_root/.env (three levels up from this file)
      2. explicit provided path
      3. CWD/.env
    First existing file is parsed; variables do not overwrite existing os.environ.
    Supports basic ${VAR} expansion referencing earlier keys or existing env.
    Emits a JSON line with stage=env_loaded when loaded.
    """
    global _ENV_LOADED, _ENV_CACHE
    if _ENV_LOADED:
        return _ENV_CACHE
    script_dir = os.path.abspath(os.path.dirname(__file__))
    candidates = [
        os.path.abspath(os.path.join(script_dir, '..','..','..','.env')),
        os.path.abspath(path),
        os.path.abspath(os.path.join(os.getcwd(), '.env')),
    ]
    seen = set()
    line_re = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$')
    for p in candidates:
        if p in seen: continue
        seen.add(p)
        if not os.path.isfile(p):
            continue
        try:
            tmp: Dict[str,str] = {}
            with open(p,'r',encoding='utf-8') as f:
                for raw in f:
                    line = raw.rstrip('\n')
                    s = line.strip()
                    if not s or s.startswith('#'): continue
                    m = line_re.match(s)
                    if not m: continue
                    k,v = m.group(1), m.group(2)
                    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                        v = v[1:-1]
                    def repl(mo):
                        name = mo.group(1)
                        return tmp.get(name, os.environ.get(name,''))
                    v = re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', repl, v)
                    tmp[k]=v
            for k,v in tmp.items():
                os.environ.setdefault(k,v)
            _ENV_CACHE = tmp
            print(json.dumps({'stage':'env_loaded','file':p,'keys':sorted(tmp.keys())}))
            _ENV_LOADED = True
            return _ENV_CACHE
        except Exception as e:  # pragma: no cover
            print(json.dumps({'stage':'env_load_error','file':p,'error':str(e)}))
    _ENV_LOADED = True
    _ENV_CACHE = {}
    return _ENV_CACHE

def build_dsn() -> Optional[str]:
    dsn = (os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL') or os.environ.get('PG_DSN'))
    if dsn:
        return dsn
    host = os.environ.get('PGHOST')
    if not host:
        return None
    user = os.environ.get('PGUSER','postgres')
    password = os.environ.get('PGPASSWORD','')
    db = os.environ.get('PGDATABASE','postgres')
    port = os.environ.get('PGPORT','5432')
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"

def connect(dsn: str) -> bool:
    """Attempt a connection; print JSON with success metadata."""
    try:
        import psycopg
    except Exception as e:
        print(json.dumps({'stage':'import_psycopg','ok':False,'error':str(e)}))
        return False
    try:
        t0 = time.time()
        conn = psycopg.connect(dsn, autocommit=True)
        dt = (time.time()-t0)*1000
        with conn.cursor() as cur:
            cur.execute('select version(), current_database()')
            row = cur.fetchone()
        print(json.dumps({'stage':'connect','ok':True,'ms':round(dt,1),'version':row[0],'database':row[1]}))
        return True
    except Exception as e:
        print(json.dumps({'stage':'connect','ok':False,'error':str(e)}))
        if os.environ.get('DB_DEBUG'): traceback.print_exc()
        return False
