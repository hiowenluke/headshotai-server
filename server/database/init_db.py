#!/usr/bin/env python3
"""Initialize PostgreSQL schema for headshot-ai (development).

Usage:
  python3 server/init_db.py \
    --dsn postgresql://user:pass@localhost:5432/headshot_ai_dev

Or provide components:
  python3 server/init_db.py --host localhost --port 5432 --db headshot_ai_dev --user myu --password secret

Environment alternative (overrides flags if set):
  DB_DSN=postgresql://user:pass@localhost:5432/headshot_ai_dev python3 server/init_db.py

Idempotent: safe to run multiple times.
"""
import argparse
import os
import sys
import psycopg2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_PATH = os.path.join(BASE_DIR, 'db_init.sql')

def load_sql() -> str:
    with open(SQL_PATH, 'r', encoding='utf-8') as f:
        return f.read()

def parse_args():
    ap = argparse.ArgumentParser(description='Initialize PostgreSQL schema')
    ap.add_argument('--dsn', help='Full DSN, e.g. postgresql://user:pass@host:5432/db')
    ap.add_argument('--host', default='localhost')
    ap.add_argument('--port', type=int, default=5432)
    ap.add_argument('--db', '--database', dest='database', default='headshot_ai_dev')
    ap.add_argument('--user', default='postgres')
    ap.add_argument('--password', default='')
    return ap.parse_args()

def build_dsn(a) -> str:
    if a.dsn:
        return a.dsn
    pwd = f":{a.password}" if a.password else ''
    return f"postgresql://{a.user}{pwd}@{a.host}:{a.port}/{a.database}"

def main():
    dsn = os.environ.get('DB_DSN')
    args = parse_args()
    if not dsn:
        dsn = build_dsn(args)
    sql = load_sql()
    print(f"[INIT-DB] Connecting: {dsn}")
    try:
        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print('[INIT-DB] Schema applied successfully.')
    except Exception as e:
        print('[INIT-DB] ERROR:', e, file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
