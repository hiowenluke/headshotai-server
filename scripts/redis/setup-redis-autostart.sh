#!/bin/bash
# 配置 Redis 开机自启动（可选）

echo "Redis 开机自启动配置"
echo "===================="
echo ""
echo "选择配置方式："
echo "1) 使用 Homebrew Services（推荐，如果通过 Homebrew 安装）"
echo "2) 使用 LaunchAgent（适用于其他安装方式）"
echo "3) 不配置（手动启动）"
echo ""
read -p "请选择 [1-3]: " choice

case $choice in
    1)
        echo ""
        echo "使用 Homebrew Services..."
        if ! command -v brew &> /dev/null; then
            echo "❌ Homebrew 未安装"
            exit 1
        fi
        
        if ! brew list redis &> /dev/null; then
            echo "❌ Redis 未通过 Homebrew 安装"
            echo ""
            echo "请先安装 Redis："
            echo "  brew install redis"
            exit 1
        fi
        
        echo "启动 Redis 并设置开机自启动..."
        brew services start redis
        
        echo ""
        echo "✅ 配置完成！"
        echo ""
        echo "查看服务状态："
        echo "  brew services list"
        echo ""
        echo "停止自启动："
        echo "  brew services stop redis"
        ;;
        
    2)
        echo ""
        echo "使用 LaunchAgent..."
        
        # 检查 redis-server 路径
        REDIS_PATH=$(which redis-server)
        if [ -z "$REDIS_PATH" ]; then
            echo "❌ 找不到 redis-server"
            exit 1
        fi
        
        echo "Redis 路径: $REDIS_PATH"
        
        # 创建日志目录
        sudo mkdir -p /usr/local/var/log
        sudo chown $(whoami) /usr/local/var/log
        
        # 创建 LaunchAgent 目录
        mkdir -p ~/Library/LaunchAgents
        
        # 创建 plist 文件
        cat > ~/Library/LaunchAgents/com.redis.server.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.redis.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>$REDIS_PATH</string>
        <string>--port</string>
        <string>6379</string>
        <string>--bind</string>
        <string>127.0.0.1</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/usr/local/var/log/redis.log</string>
    <key>StandardErrorPath</key>
    <string>/usr/local/var/log/redis-error.log</string>
</dict>
</plist>
EOF
        
        # 加载 LaunchAgent
        launchctl load ~/Library/LaunchAgents/com.redis.server.plist
        
        # 启动服务
        launchctl start com.redis.server
        
        # 等待启动
        sleep 2
        
        # 验证
        if redis-cli ping > /dev/null 2>&1; then
            echo ""
            echo "✅ 配置完成！Redis 已启动"
            echo ""
            echo "查看日志："
            echo "  tail -f /usr/local/var/log/redis.log"
            echo ""
            echo "停止服务："
            echo "  launchctl stop com.redis.server"
            echo ""
            echo "取消自启动："
            echo "  launchctl unload ~/Library/LaunchAgents/com.redis.server.plist"
        else
            echo ""
            echo "❌ Redis 启动失败"
            echo ""
            echo "查看错误日志："
            echo "  cat /usr/local/var/log/redis-error.log"
        fi
        ;;
        
    3)
        echo ""
        echo "不配置开机自启动"
        echo ""
        echo "你可以使用以下命令手动启动 Redis："
        echo "  npm run redis:start"
        echo ""
        echo "或者在项目启动时自动启动（已配置）："
        echo "  npm run dev        # 前端（会自动启动 Redis）"
        echo "  ./run_server       # 后端（会自动启动 Redis）"
        ;;
        
    *)
        echo "无效的选择"
        exit 1
        ;;
esac
