#!/usr/bin/env python3
"""手动完成充值 - 用于测试环境"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server.database import payments as payment_store

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/manual_complete_topup.py <session_id>")
        print("\nExample:")
        print("  python scripts/manual_complete_topup.py cs_test_a1zi9WcaVy9ufaUV5Zf0Gq4OLYRq7igYQ3i6GqDURbjV5S7zzP9YbW0f2y")
        sys.exit(1)
    
    session_id = sys.argv[1]
    
    print(f"正在完成充值: {session_id}")
    result = payment_store.complete_topup(session_id, provider='stripe')
    
    if result:
        print(f"✓ 充值完成!")
        print(f"  用户 ID: {result['user_id']}")
        print(f"  充值金币: {result['coins_total']}")
        print(f"  新余额: {result['new_balance']}")
    else:
        print("✗ 充值失败 - 可能已经完成或记录不存在")
        sys.exit(1)

if __name__ == '__main__':
    main()
