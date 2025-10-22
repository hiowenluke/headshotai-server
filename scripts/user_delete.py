#!/usr/bin/env python3
"""Delete a user (by email) from Postgres and related Redis sessions.

Features:
  * Loads env vars (DATABASE_URL, REDIS_URL, REDIS_PREFIX) from process env; if missing, attempts to parse .env in current dir.
  * Confirms action unless --force.
  * Gathers counts (user_identities, coin_topups, coin_spendings) before deletion for summary.
  * Deletes user row (CASCADE handles dependent tables) after explicitly removing user_identities (optional but gives deterministic count removed).
  * Redis session index key format: <REDIS_PREFIX>:usess:<email_lower> (new scheme). Members are session IDs. Deletes index then each session key <REDIS_PREFIX>:sess:<sid>.
  * Optional --legacy-sub SUB allows also removing old index <REDIS_PREFIX>:usess:<sub> (backward compatibility).
  * Optional --dry-run performs no mutations.

Usage:
  python scripts/user_delete.py user@example.com
  python scripts/user_delete.py user@example.com --force
  python scripts/user_delete.py user@example.com --dry-run
  python scripts/user_delete.py user@example.com --legacy-sub 112233445566 --force

Requires: psycopg (v3), redis (python redis client). If redis unavailable, will skip session deletion.
"""
from __future__ import annotations
import os, sys, argparse, re, json
from typing import Optional

try:
    import psycopg
except ImportError:
    psycopg = None  # type: ignore
try:
    # Only for optional direct use; main Redis cleanup moved to user_clear_login_state
    from scripts.user_clear_login_state import clear_user_login_state  # type: ignore
except Exception:
    clear_user_login_state = None  # type: ignore

ENV_LOADED = False

def load_env_dotenv():
    global ENV_LOADED
    if ENV_LOADED:
        return
    path = '.env'
    if not os.path.isfile(path):
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for raw in f:
                line = raw.rstrip('\n')
                if not line or line.lstrip().startswith('#'):
                    continue
                m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)=(.*)', line)
                if not m:
                    continue
                k, v = m.group(1), m.group(2)
                if k in os.environ:  # do not override
                    continue
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                # simple ${VAR} expansion (iterative)
                for _ in range(10):
                    new_v = re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', lambda mm: os.environ.get(mm.group(1), ''), v)
                    if new_v == v:
                        break
                    v = new_v
                os.environ[k] = v
        ENV_LOADED = True
    except Exception as e:  # pragma: no cover
        print(f"[WARN] Failed to parse .env: {e}")


def confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() == 'yes'
    except EOFError:
        return False


def pg_connect(dsn: str):
    if not psycopg:
        print('[ERR] psycopg not installed. pip install psycopg[binary]')
        sys.exit(2)
    try:
        return psycopg.connect(dsn, autocommit=True)
    except Exception as e:
        print(f'[ERR] Failed to connect Postgres: {e}')
        sys.exit(2)



def delete_user(email: str, force: bool, dry_run: bool, legacy_sub: Optional[str]):
    load_env_dotenv()
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        print('[ERR] DATABASE_URL missing')
        sys.exit(1)
    # Redis handled by external clear script

    email_l = email.lower().strip()
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email_l):
        print('[ERR] Invalid email format')
        sys.exit(1)

    if not force and not dry_run:
        if not confirm(f'确认删除 email={email_l} 的用户及其会话? (yes/NO): '):
            print('已取消')
            return

    # Postgres section
    conn = pg_connect(dsn)
    user_id = None
    identities_count = topups = spendings = 0
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email=%s LIMIT 1", (email_l,))
        row = cur.fetchone()
        if not row:
            print(f"[PG] 未找到用户 email={email_l}")
        else:
            user_id = row[0]
            print(f"[PG] 用户 id={user_id}")
            cur.execute("SELECT count(*) FROM user_identities WHERE user_id=%s", (user_id,))
            identities_count = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM coin_topups WHERE user_id=%s", (user_id,))
            topups = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM coin_spendings WHERE user_id=%s", (user_id,))
            spendings = cur.fetchone()[0]
            print(f"[PG] user_identities={identities_count} coin_topups={topups} coin_spendings={spendings}")
            if dry_run:
                print('[PG] Dry-run 不执行删除')
            else:
                if identities_count:
                    cur.execute("DELETE FROM user_identities WHERE user_id=%s", (user_id,))
                cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
                print('[PG] 已删除用户及关联 (级联 / 手动)')

    redis_summary = None
    if clear_user_login_state:
        try:
            redis_summary = clear_user_login_state(email_l, legacy_sub, dry_run=dry_run, force=True)  # already confirmed above
            # Pretty print brief summary lines similar to old output
            if redis_summary.get('redis_connected'):
                print(f"[REDIS] index_members={redis_summary.get('index_member_count')} deleted={redis_summary.get('index_deleted')} sessions_deleted={redis_summary.get('sessions_deleted')} missing={redis_summary.get('missing_sessions')}")
                if legacy_sub:
                    print(f"[REDIS][LEGACY] index_deleted={redis_summary.get('legacy_index_deleted')} sessions_deleted={redis_summary.get('legacy_sessions_deleted')}")
            else:
                print('[REDIS] 未连接或未配置，跳过清理')
        except Exception as e:
            print(f"[REDIS] 清理异常: {e}")
    else:
        print('[REDIS] clear_user_login_state 不可用 (可能缺失脚本)')

    print('\n[SUMMARY]')
    print(f"email={email_l}")
    print(f"user_id={user_id or '(none)'}")
    print(f"identities_deleted={identities_count if not dry_run else 0} topups_before={topups} spendings_before={spendings}")
    if redis_summary:
        print(f"redis_index_deleted={redis_summary.get('index_deleted')} sessions_deleted={redis_summary.get('sessions_deleted')}")
        if legacy_sub:
            print(f"legacy_index_deleted={redis_summary.get('legacy_index_deleted')} legacy_sessions_deleted={redis_summary.get('legacy_sessions_deleted')}")
    else:
        print("redis_index_deleted=False sessions_deleted=0")
    if dry_run:
        print('[NOTE] Dry-run 模式未真正删除数据。')


def main():
    p = argparse.ArgumentParser(description='Delete user (email) from Postgres and Redis sessions.')
    p.add_argument('email', help='用户 email')
    p.add_argument('--force', action='store_true', help='跳过确认')
    p.add_argument('--dry-run', action='store_true', help='仅查看将删除的内容，不执行')
    p.add_argument('--legacy-sub', help='可选：旧的 sub 索引（appauth:usess:<sub>）也清理')
    args = p.parse_args()
    delete_user(args.email, args.force, args.dry_run, args.legacy_sub)

if __name__ == '__main__':
    main()
