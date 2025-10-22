#!/bin/bash
# 检查 Redis 状态

echo "Checking Redis status..."

if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is running"
    echo ""
    echo "Redis info:"
    redis-cli info server | grep -E "redis_version|uptime_in_seconds|tcp_port"
    echo ""
    echo "Connected clients:"
    redis-cli info clients | grep connected_clients
    echo ""
    echo "Memory usage:"
    redis-cli info memory | grep -E "used_memory_human|used_memory_peak_human"
else
    echo "❌ Redis is not running"
    echo ""
    echo "To start Redis, run:"
    echo "  bash scripts/start-redis.sh"
    exit 1
fi
