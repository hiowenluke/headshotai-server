import os, sys, json
script_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(script_dir,'..','..','..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from server.database.debug.common import load_env, build_dsn, connect

def main():
    load_env()
    info = {k: ('***redacted***' if 'PASSWORD' in k and os.environ.get(k) else os.environ.get(k))
            for k in ['DATABASE_URL','POSTGRES_URL','PG_DSN','PGHOST','PGUSER','PGPASSWORD','PGDATABASE','PGPORT']}
    print(json.dumps({'stage':'env','vars':info}))
    dsn = build_dsn()
    print(json.dumps({'stage':'dsn','value':bool(dsn)}))
    if not dsn:
        print(json.dumps({'stage':'fatal','error':'no_dsn'}))
        return 2
    ok = connect(dsn)
    return 0 if ok else 2

if __name__ == '__main__':
    sys.exit(main())