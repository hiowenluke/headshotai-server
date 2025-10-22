#!/bin/bash
# 停止 Redis 服务器

echo "Stopping Redis server..."

# 检查 Redis 是否在运行
if ! redis-cli ping > /dev/null 2>&1; then
    echo "Redis is not running"
    exit 0
fi

# 停止 Redis
redis-cli shutdown

# 等待 Redis 停止
sleep 1

# 检查是否停止成功
if redis-cli ping > /dev/null 2>&1; then
    echo "❌ Failed to stop Redis"
    exit 1
else
    echo "✅ Redis stopped successfully"
fi
