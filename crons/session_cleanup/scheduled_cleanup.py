#!/usr/bin/env python3
"""
定期会话清理任务
可以通过 cron 或其他调度器定期运行
"""

import os
import sys
import time
import logging
from datetime import datetime

from session_cleanup import SessionCleanup

# 设置日志
log_file = os.path.join(os.path.dirname(__file__), 'session_cleanup.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_scheduled_cleanup():
    """运行定期清理任务"""
    logger.info("=== 开始定期会话清理任务 ===")
    
    try:
        # 创建清理器实例
        cleanup = SessionCleanup(dry_run=False)
        
        # 默认只执行安全的孤儿会话清理
        logger.info("执行孤儿会话清理...")
        cleanup.cleanup_orphaned_user_sessions()
        
        # 如果设置了环境变量，才执行过期会话清理
        include_expired = os.environ.get('CLEANUP_INCLUDE_EXPIRED', '0').lower() in ('1', 'true', 'yes')
        if include_expired:
            max_age_days = int(os.environ.get('CLEANUP_MAX_AGE_DAYS', '30'))
            logger.info(f"执行过期会话清理（超过 {max_age_days} 天）...")
            cleanup.cleanup_expired_sessions(max_age_days=max_age_days)
        else:
            logger.info("跳过过期会话清理（未启用 CLEANUP_INCLUDE_EXPIRED）")
        
        # 生成并记录报告
        report = cleanup.get_cleanup_report()
        logger.info("清理完成，生成报告:")
        for line in report.strip().split('\n'):
            logger.info(line)
        
        # 如果发现了问题并修复，发送通知（可选）
        if cleanup.stats['orphaned_sessions_found'] > 0:
            logger.warning(f"发现并清理了 {cleanup.stats['orphaned_sessions_found']} 个孤儿会话")
        
        logger.info("=== 定期会话清理任务完成 ===")
        
    except Exception as e:
        logger.error(f"定期清理任务失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    run_scheduled_cleanup()
