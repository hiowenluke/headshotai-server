#!/usr/bin/env bash
# 启动 Stripe webhook 转发（用于本地测试）

set -euo pipefail

echo "=========================================="
echo "Stripe Webhook 本地测试"
echo "=========================================="
echo ""

# 检查 Stripe CLI 是否安装
if ! command -v stripe &> /dev/null; then
    echo "❌ Stripe CLI 未安装"
    echo ""
    echo "请先安装 Stripe CLI:"
    echo "  brew install stripe/stripe-cli/stripe"
    echo ""
    exit 1
fi

echo "✓ Stripe CLI 已安装: $(stripe --version)"
echo ""

# 检查是否已登录
if ! stripe config --list &> /dev/null; then
    echo "⚠️  请先登录 Stripe:"
    echo "  stripe login"
    echo ""
    exit 1
fi

echo "✓ Stripe 账户已登录"
echo ""

# 获取后端端口
PORT=${PORT:-5010}

echo "=========================================="
echo "开始转发 Webhook 事件"
echo "=========================================="
echo ""
echo "目标端点: http://localhost:${PORT}/api/payment/webhook"
echo ""
echo "⚠️  重要提示："
echo "1. 复制下方显示的 webhook signing secret"
echo "2. 更新 .env 文件中的 STRIPE_WEBHOOK_SECRET"
echo "3. 重启后端服务"
echo ""
echo "按 Ctrl+C 停止转发"
echo ""
echo "=========================================="
echo ""

# 开始转发
stripe listen --forward-to "http://localhost:${PORT}/api/payment/webhook"
