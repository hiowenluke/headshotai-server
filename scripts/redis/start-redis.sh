#!/bin/bash
# 启动 Redis 服务器（用于开发环境）

echo "Starting Redis server..."

# 检查 Redis 是否已经在运行
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is already running"
    exit 0
fi

# 启动 Redis
redis-server --daemonize yes --port 6379 --bind 127.0.0.1

# 等待 Redis 启动
sleep 1

# 检查是否启动成功
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis started successfully"
else
    echo "❌ Failed to start Redis"
    exit 1
fi
