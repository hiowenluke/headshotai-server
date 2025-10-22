#!/usr/bin/env python3
"""Standalone test runner for inserting a user into the users table.

Usage:
  python server/database/debug/test_user_insert.py --email test@example.com --sub 12345 \
      [--provider google] [--name NAME] [--picture URL] [--ip 127.0.0.1]

Process:
  1. Load .env (if present) into environment (supports simple ${VAR} expansion of already-defined vars).
  2. Print key DB env vars.
  3. Attempt direct connection (shows server version) like debug_conn.py.
    4. Run insertion (single or twice for idempotency check) directly calling db.upsert_user.
  5. Output JSON lines for each step.

Exit codes:
  0 success, 2 connection failure, 3 insertion failure.
"""
from __future__ import annotations
import os, re, json, sys, time, traceback
from typing import Dict

script_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(script_dir,'..','..','..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from server.database.debug.common import load_env, build_dsn, connect

def main(argv):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--email', required=True)
    parser.add_argument('--sub', required=True)
    parser.add_argument('--provider', default='google')
    parser.add_argument('--name')
    parser.add_argument('--picture')
    parser.add_argument('--ip', default='127.0.0.1')
    parser.add_argument('--env', default='.env', help='Path to .env file (default .env)')
    parser.add_argument('--single', action='store_true', help='Only run one insertion attempt (skip idempotency second run)')
    args = parser.parse_args(argv)

    loaded = load_env(args.env)
    print(json.dumps({'stage':'load_env','loaded_keys':sorted(list(loaded.keys()))}))

    dsn = build_dsn()
    print(json.dumps({'stage':'dsn','dsn_present':bool(dsn)}))
    if not dsn:
        print(json.dumps({'stage':'fatal','error':'no_dsn_env'}))
        return 2

    if not connect(dsn):
        return 2

    # Ensure project root on sys.path
    script_dir = os.path.abspath(os.path.dirname(__file__))
    # script_dir = server/database/debug -> project_root = repo root (three levels up)
    project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    # Import db module once
    try:
        import importlib
        db = importlib.import_module('server.database.db')  # type: ignore
    except Exception as e_db:
        print(json.dumps({'stage':'import_db','ok':False,'error':str(e_db)}))
        return 3

    def do_upsert(email: str, sub: str, provider: str, name: str|None, picture: str|None, ip: str|None):
        res = db.upsert_user(sub=sub, provider=provider, email=email, name=name, picture=picture, ip=ip)
        if isinstance(res, tuple):
            ok, is_new = res
        else:
            ok, is_new = (bool(res), None)
        user = db.get_user(email)
        uid = user['id'] if user else None
        err = None if ok else 'upsert_user returned False'
        return ok, is_new, uid, err

    attempts = (1,) if args.single else (1,2)
    for idx in attempts:
        ok, is_new, uid, err = do_upsert(
            email=args.email,
            sub=args.sub,
            provider=args.provider,
            name=args.name,
            picture=args.picture,
            ip=args.ip
        )
        if uid is not None:
            try:
                # psycopg may return uuid.UUID instance; cast to str for JSON
                uid_str = str(uid)
            except Exception:
                uid_str = f"{uid}"
        else:
            uid_str = None
        print(json.dumps({'stage':'insert','attempt':idx,'ok':ok,'is_new':is_new,'user_id':uid_str,'error':err}))
        if not ok and idx == 1:
            # abort second attempt if first already fails fatally
            break
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
