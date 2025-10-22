#!/usr/bin/env python3
"""
Redis 会话清理工具
清理孤儿会话记录，确保数据一致性
"""

import os
import json
import time
import logging
from typing import List, Dict, Set, Optional
from datetime import datetime, timedelta

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Redis 配置
REDIS_URL = os.environ.get('REDIS_URL') or os.environ.get('REDIS_URI') or ''
REDIS_PREFIX = os.environ.get('REDIS_PREFIX', 'appauth')

_redis = None
if REDIS_URL:
    try:
        import redis  # type: ignore
        _redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        _redis.ping()
        logger.info(f"Connected to Redis: {REDIS_URL}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        _redis = None
else:
    logger.error("REDIS_URL not configured")
    exit(1)

def _rkey(kind: str, ident: str) -> str:
    """生成 Redis 键名"""
    return f"{REDIS_PREFIX}:{kind}:{ident}"

class SessionCleanup:
    def __init__(self, dry_run: bool = False):
        """
        初始化清理器
        :param dry_run: 如果为 True，只报告要清理的内容，不实际执行
        """
        self.dry_run = dry_run
        self.stats = {
            'user_sessions_checked': 0,
            'user_sessions_cleaned': 0,
            'orphaned_sessions_found': 0,
            'orphaned_sessions_removed': 0,
            'empty_user_sessions_removed': 0,
            'total_sessions_checked': 0,
            'valid_sessions_found': 0
        }
    
    def cleanup_orphaned_user_sessions(self) -> Dict[str, int]:
        """
        清理孤儿用户会话记录
        检查所有 appauth:usess:* 键，移除指向不存在会话的记录
        """
        logger.info("开始清理孤儿用户会话记录...")
        
        if not _redis:
            logger.error("Redis 连接不可用")
            return self.stats
        
        # 获取所有用户会话键
        user_session_pattern = _rkey('usess', '*')
        user_session_keys = _redis.keys(user_session_pattern)
        
        logger.info(f"找到 {len(user_session_keys)} 个用户会话键")
        
        for user_key in user_session_keys:
            self.stats['user_sessions_checked'] += 1
            user_email = user_key.replace(f"{REDIS_PREFIX}:usess:", "")
            
            logger.info(f"检查用户: {user_email}")
            
            # 获取该用户的所有会话ID（使用ZSET的所有成员）
            try:
                session_ids = _redis.zrange(user_key, 0, -1)
                if not session_ids:
                    logger.info(f"  用户 {user_email} 没有会话记录")
                    continue
                
                logger.info(f"  用户 {user_email} 有 {len(session_ids)} 个会话记录")
                self.stats['total_sessions_checked'] += len(session_ids)
                
                # 检查每个会话是否存在
                valid_sessions = []
                orphaned_sessions = []
                
                for session_id in session_ids:
                    session_key = _rkey('sess', session_id)
                    if _redis.exists(session_key):
                        valid_sessions.append(session_id)
                        self.stats['valid_sessions_found'] += 1
                    else:
                        orphaned_sessions.append(session_id)
                        self.stats['orphaned_sessions_found'] += 1
                
                logger.info(f"  有效会话: {len(valid_sessions)}, 孤儿会话: {len(orphaned_sessions)}")
                
                # 如果有孤儿会话，清理它们
                if orphaned_sessions:
                    if not self.dry_run:
                        # 从 ZSET 中移除孤儿会话
                        _redis.zrem(user_key, *orphaned_sessions)
                        self.stats['orphaned_sessions_removed'] += len(orphaned_sessions)
                        logger.info(f"  已移除 {len(orphaned_sessions)} 个孤儿会话")
                    else:
                        logger.info(f"  [DRY RUN] 将移除 {len(orphaned_sessions)} 个孤儿会话: {orphaned_sessions}")
                
                # 如果所有会话都是孤儿，删除整个用户会话键
                if not valid_sessions:
                    if not self.dry_run:
                        _redis.delete(user_key)
                        self.stats['empty_user_sessions_removed'] += 1
                        logger.info(f"  已删除空的用户会话键: {user_key}")
                    else:
                        logger.info(f"  [DRY RUN] 将删除空的用户会话键: {user_key}")
                    self.stats['user_sessions_cleaned'] += 1
                elif orphaned_sessions:
                    self.stats['user_sessions_cleaned'] += 1
                    
            except Exception as e:
                logger.error(f"处理用户 {user_email} 时出错: {e}")
        
        return self.stats
    
    def cleanup_expired_sessions(self, max_age_days: int = 30) -> Dict[str, int]:
        """
        清理过期的会话记录
        :param max_age_days: 超过多少天的会话被认为是过期的
        """
        logger.info(f"开始清理超过 {max_age_days} 天的过期会话...")
        
        if not _redis:
            logger.error("Redis 连接不可用")
            return self.stats
        
        cutoff_timestamp = time.time() - (max_age_days * 24 * 3600)
        expired_sessions = []
        
        # 获取所有会话键
        session_pattern = _rkey('sess', '*')
        session_keys = _redis.keys(session_pattern)
        
        logger.info(f"检查 {len(session_keys)} 个会话记录")
        
        for session_key in session_keys:
            try:
                session_data = _redis.get(session_key)
                if session_data:
                    session_json = json.loads(session_data)
                    session_ts = session_json.get('ts', 0)
                    
                    if session_ts < cutoff_timestamp:
                        session_id = session_key.replace(f"{REDIS_PREFIX}:sess:", "")
                        expired_sessions.append(session_id)
            except Exception as e:
                logger.error(f"检查会话 {session_key} 时出错: {e}")
        
        if expired_sessions:
            logger.info(f"找到 {len(expired_sessions)} 个过期会话")
            
            if not self.dry_run:
                # 删除过期会话
                for session_id in expired_sessions:
                    session_key = _rkey('sess', session_id)
                    _redis.delete(session_key)
                
                logger.info(f"已删除 {len(expired_sessions)} 个过期会话")
                
                # 清理用户会话索引中的过期会话引用
                self.cleanup_orphaned_user_sessions()
            else:
                logger.info(f"[DRY RUN] 将删除 {len(expired_sessions)} 个过期会话")
        else:
            logger.info("没有找到需要清理的过期会话")
        
        return self.stats
    
    def get_cleanup_report(self) -> str:
        """生成清理报告"""
        report = f"""
=== 会话清理报告 ===
模式: {'DRY RUN (模拟)' if self.dry_run else '实际执行'}
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

检查统计:
- 检查的用户会话键: {self.stats['user_sessions_checked']}
- 检查的总会话数: {self.stats['total_sessions_checked']}
- 发现的有效会话: {self.stats['valid_sessions_found']}
- 发现的孤儿会话: {self.stats['orphaned_sessions_found']}

清理统计:
- 清理的用户会话键: {self.stats['user_sessions_cleaned']}
- 移除的孤儿会话: {self.stats['orphaned_sessions_removed']}
- 删除的空用户会话键: {self.stats['empty_user_sessions_removed']}

数据一致性: {self.get_consistency_status()}
"""
        return report
    
    def get_consistency_status(self) -> str:
        """获取数据一致性状态"""
        if self.stats['orphaned_sessions_found'] == 0:
            return "✅ 良好"
        elif self.stats['orphaned_sessions_removed'] >= self.stats['orphaned_sessions_found']:
            return "✅ 已修复"
        else:
            return "⚠️ 需要修复"

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Redis 会话清理工具')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行，不实际执行清理')
    parser.add_argument('--max-age-days', type=int, default=30, help='清理超过指定天数的过期会话')
    parser.add_argument('--include-expired', action='store_true', help='同时清理过期会话（默认只清理孤儿会话）')
    
    args = parser.parse_args()
    
    if not _redis:
        logger.error("无法连接到 Redis，退出")
        exit(1)
    
    cleanup = SessionCleanup(dry_run=args.dry_run)
    
    try:
        # 默认只清理孤儿会话记录（安全操作）
        logger.info("清理孤儿会话记录")
        cleanup.cleanup_orphaned_user_sessions()
        
        # 如果指定了 --include-expired，则同时清理过期会话
        if args.include_expired:
            logger.info(f"清理超过 {args.max_age_days} 天的过期会话")
            cleanup.cleanup_expired_sessions(args.max_age_days)
        
        # 输出报告
        print(cleanup.get_cleanup_report())
        
    except KeyboardInterrupt:
        logger.info("清理被用户中断")
    except Exception as e:
        logger.error(f"清理过程中出现错误: {e}")
        exit(1)

if __name__ == '__main__':
    main()
