#!/usr/bin/env python3
"""
一次性清理脚本
用于处理当前存在的孤儿会话记录
在部署清理系统时运行一次
"""

import os
import sys
import logging
from datetime import datetime

from session_cleanup import SessionCleanup

# 设置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    print("=" * 60)
    print("Redis 会话清理系统 - 一次性清理")
    print("=" * 60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 首先运行模拟清理，显示将要执行的操作
    print("1. 运行模拟清理，分析当前状态...")
    print("-" * 40)
    
    dry_run_cleanup = SessionCleanup(dry_run=True)
    dry_run_cleanup.cleanup_orphaned_user_sessions()
    
    print(dry_run_cleanup.get_cleanup_report())
    
    # 如果发现需要清理的内容，询问用户确认
    if dry_run_cleanup.stats['orphaned_sessions_found'] > 0:
        print()
        print("⚠️  发现需要清理的孤儿会话记录")
        print(f"   - 孤儿会话数量: {dry_run_cleanup.stats['orphaned_sessions_found']}")
        print(f"   - 受影响的用户: {dry_run_cleanup.stats['user_sessions_checked']}")
        print()
        
        confirm = input("是否继续执行实际清理？(y/N): ").strip().lower()
        
        if confirm in ['y', 'yes']:
            print()
            print("2. 执行实际清理...")
            print("-" * 40)
            
            # 执行实际清理
            actual_cleanup = SessionCleanup(dry_run=False)
            actual_cleanup.cleanup_orphaned_user_sessions()
            
            print(actual_cleanup.get_cleanup_report())
            
            print()
            print("✅ 清理完成！")
            
            # 验证清理结果
            print()
            print("3. 验证清理结果...")
            print("-" * 40)
            
            verify_cleanup = SessionCleanup(dry_run=True)
            verify_cleanup.cleanup_orphaned_user_sessions()
            
            if verify_cleanup.stats['orphaned_sessions_found'] == 0:
                print("✅ 验证通过：没有发现剩余的孤儿会话")
            else:
                print(f"⚠️  仍有 {verify_cleanup.stats['orphaned_sessions_found']} 个孤儿会话")
                print("   建议重新运行清理脚本")
        else:
            print("❌ 用户取消，未执行清理")
    else:
        print("✅ 没有发现需要清理的孤儿会话记录")
        print("   数据一致性良好")
    
    print()
    print("=" * 60)
    print("一次性清理完成")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ 清理被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 清理过程中出现错误: {e}")
        logger.error(f"一次性清理失败: {e}")
        sys.exit(1)
