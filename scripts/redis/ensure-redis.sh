#!/bin/bash
# 确保 Redis 运行（用于开发环境）

if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is already running"
    exit 0
fi

echo "🔄 Redis is not running, starting..."
bash scripts/start-redis.sh

# 验证启动成功
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis started successfully"
    exit 0
else
    echo "❌ Failed to start Redis"
    echo ""
    echo "Please start Redis manually:"
    echo "  npm run redis:start"
    echo ""
    echo "Or install Redis if not installed:"
    echo "  brew install redis"
    exit 1
fi
