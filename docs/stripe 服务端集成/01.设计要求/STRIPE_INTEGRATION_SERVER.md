# 🔧 Stripe 支付集成 - 服务端实现指南

## 📋 概述

本文档描述如何在 Flask 后端实现 Stripe 支付集成，配合前端完成金币购买功能。

---

## 🛠️ 服务端需要实现的功能

### 1. 安装依赖

```bash
pip install stripe
```

### 2. 配置 Stripe API Key

在服务端配置文件中添加：

```python
# config.py 或 .env
STRIPE_SECRET_KEY = "sk_test_..."  # 测试环境
STRIPE_PUBLISHABLE_KEY = "pk_test_..."  # 前端可能需要
STRIPE_WEBHOOK_SECRET = "whsec_..."  # Webhook 签名验证
```

---

## 📡 API 端点实现

### 1. 创建 Checkout Session

**端点**: `POST /api/payment/create-checkout-session`

**请求体**:
```json
{
  "price_usd": 99.99,
  "coins": 1000,
  "bonus": 200,
  "success_url": "https://yourapp.com/payment/success?session_id={CHECKOUT_SESSION_ID}",
  "cancel_url": "https://yourapp.com/payment/cancel"
}
```

**Python 实现示例**:

```python
import stripe
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

payment_bp = Blueprint('payment', __name__)
stripe.api_key = app.config['STRIPE_SECRET_KEY']

@payment_bp.route('/api/payment/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """创建 Stripe Checkout Session"""
    try:
        data = request.get_json()
        
        # 验证请求参数
        price_usd = float(data.get('price_usd'))
        coins = int(data.get('coins'))
        bonus = int(data.get('bonus', 0))
        success_url = data.get('success_url')
        cancel_url = data.get('cancel_url')
        
        # 创建 Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'{coins} Coins',
                        'description': f'Get {coins} coins' + (f' + {bonus} bonus coins' if bonus > 0 else ''),
                        'images': ['https://yourapp.com/coin-icon.png'],  # 可选
                    },
                    'unit_amount': int(price_usd * 100),  # Stripe 使用分为单位
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(current_user.id),  # 用于关联用户
            metadata={
                'user_id': str(current_user.id),
                'coins': str(coins),
                'bonus': str(bonus),
                'total_coins': str(coins + bonus)
            }
        )
        
        # 保存 Session 信息到数据库（可选，用于后续查询）
        save_payment_session(
            session_id=session.id,
            user_id=current_user.id,
            amount_usd=price_usd,
            coins=coins,
            bonus=bonus,
            status='pending'
        )
        
        return jsonify({
            'session_id': session.id,
            'checkout_url': session.url
        }), 200
        
    except Exception as e:
        app.logger.error(f'Failed to create checkout session: {e}')
        return jsonify({'error': 'Failed to create checkout session'}), 500


def save_payment_session(session_id, user_id, amount_usd, coins, bonus, status):
    """保存支付会话到数据库"""
    # 实现数据库保存逻辑
    # 示例表结构：
    # payment_sessions:
    #   - id (primary key)
    #   - session_id (Stripe Session ID)
    #   - user_id
    #   - amount_usd
    #   - coins
    #   - bonus
    #   - status (pending/completed/failed/cancelled)
    #   - created_at
    #   - updated_at
    pass
```

---

### 2. 查询支付状态

**端点**: `GET /api/payment/status/<session_id>`

**Python 实现示例**:

```python
@payment_bp.route('/api/payment/status/<session_id>', methods=['GET'])
@login_required
def get_payment_status(session_id):
    """查询支付状态"""
    try:
        # 从数据库查询支付记录
        payment = get_payment_by_session_id(session_id)
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        # 验证用户权限
        if payment.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        return jsonify({
            'status': payment.status,
            'session_id': session_id,
            'coins_added': payment.coins + payment.bonus if payment.status == 'completed' else None,
            'new_balance': current_user.coin_balance if payment.status == 'completed' else None
        }), 200
        
    except Exception as e:
        app.logger.error(f'Failed to get payment status: {e}')
        return jsonify({'error': 'Failed to get payment status'}), 500


def get_payment_by_session_id(session_id):
    """从数据库获取支付记录"""
    # 实现数据库查询逻辑
    pass
```

---

### 3. Stripe Webhook 处理（重要！）

**端点**: `POST /api/payment/webhook`

这是最关键的部分，用于接收 Stripe 的支付完成通知。

**Python 实现示例**:

```python
@payment_bp.route('/api/payment/webhook', methods=['POST'])
def stripe_webhook():
    """处理 Stripe Webhook 事件"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        # 验证 Webhook 签名
        event = stripe.Webhook.construct_event(
            payload, sig_header, app.config['STRIPE_WEBHOOK_SECRET']
        )
    except ValueError as e:
        # 无效的 payload
        app.logger.error(f'Invalid webhook payload: {e}')
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        # 无效的签名
        app.logger.error(f'Invalid webhook signature: {e}')
        return jsonify({'error': 'Invalid signature'}), 400
    
    # 处理不同的事件类型
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session_completed(session)
    
    elif event['type'] == 'checkout.session.expired':
        session = event['data']['object']
        handle_checkout_session_expired(session)
    
    elif event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        handle_payment_intent_succeeded(payment_intent)
    
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        handle_payment_intent_failed(payment_intent)
    
    return jsonify({'status': 'success'}), 200


def handle_checkout_session_completed(session):
    """处理支付完成事件"""
    try:
        session_id = session['id']
        user_id = int(session['metadata']['user_id'])
        coins = int(session['metadata']['coins'])
        bonus = int(session['metadata']['bonus'])
        total_coins = coins + bonus
        
        app.logger.info(f'Payment completed for session {session_id}, user {user_id}')
        
        # 1. 更新支付记录状态
        update_payment_status(session_id, 'completed')
        
        # 2. 增加用户金币余额
        add_user_coins(user_id, total_coins)
        
        # 3. 记录交易历史
        create_transaction_record(
            user_id=user_id,
            type='purchase',
            coins=total_coins,
            amount_usd=session['amount_total'] / 100,  # 转换为美元
            session_id=session_id,
            description=f'Purchased {coins} coins + {bonus} bonus'
        )
        
        # 4. 发送通知（可选）
        send_purchase_notification(user_id, total_coins)
        
        app.logger.info(f'Successfully added {total_coins} coins to user {user_id}')
        
    except Exception as e:
        app.logger.error(f'Failed to handle checkout session completed: {e}')
        # 可以实现重试机制或者告警


def handle_checkout_session_expired(session):
    """处理支付会话过期"""
    session_id = session['id']
    update_payment_status(session_id, 'expired')
    app.logger.info(f'Checkout session expired: {session_id}')


def handle_payment_intent_succeeded(payment_intent):
    """处理支付成功"""
    app.logger.info(f'Payment intent succeeded: {payment_intent["id"]}')


def handle_payment_intent_failed(payment_intent):
    """处理支付失败"""
    app.logger.error(f'Payment intent failed: {payment_intent["id"]}')


def update_payment_status(session_id, status):
    """更新支付状态"""
    # 实现数据库更新逻辑
    pass


def add_user_coins(user_id, coins):
    """增加用户金币"""
    # 实现数据库更新逻辑
    # UPDATE users SET coin_balance = coin_balance + coins WHERE id = user_id
    pass


def create_transaction_record(user_id, type, coins, amount_usd, session_id, description):
    """创建交易记录"""
    # 实现数据库插入逻辑
    # 示例表结构：
    # transactions:
    #   - id
    #   - user_id
    #   - type (purchase/usage/refund)
    #   - coins
    #   - amount_usd
    #   - session_id
    #   - description
    #   - created_at
    pass


def send_purchase_notification(user_id, coins):
    """发送购买通知（可选）"""
    # 可以发送邮件、推送通知等
    pass
```

---

## 🔐 安全注意事项

### 1. Webhook 签名验证
**必须**验证 Stripe Webhook 的签名，防止伪造请求：

```python
event = stripe.Webhook.construct_event(
    payload, sig_header, STRIPE_WEBHOOK_SECRET
)
```

### 2. 幂等性处理
Webhook 可能会重复发送，需要确保处理是幂等的：

```python
def add_user_coins(user_id, coins, session_id):
    # 检查是否已经处理过这个 session
    if is_session_processed(session_id):
        app.logger.info(f'Session {session_id} already processed, skipping')
        return
    
    # 使用数据库事务确保原子性
    with db.transaction():
        # 增加金币
        user.coin_balance += coins
        # 标记 session 为已处理
        mark_session_processed(session_id)
```

### 3. 用户权限验证
确保用户只能查询自己的支付记录：

```python
if payment.user_id != current_user.id:
    return jsonify({'error': 'Unauthorized'}), 403
```

---

## 🗄️ 数据库表结构建议

### payment_sessions 表
```sql
CREATE TABLE payment_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    amount_usd DECIMAL(10, 2) NOT NULL,
    coins INTEGER NOT NULL,
    bonus INTEGER DEFAULT 0,
    status VARCHAR(50) NOT NULL,  -- pending/completed/failed/cancelled/expired
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_payment_sessions_user_id ON payment_sessions(user_id);
CREATE INDEX idx_payment_sessions_session_id ON payment_sessions(session_id);
```

### transactions 表
```sql
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    type VARCHAR(50) NOT NULL,  -- purchase/usage/refund
    coins INTEGER NOT NULL,
    amount_usd DECIMAL(10, 2),
    session_id VARCHAR(255),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);
```

---

## 🧪 测试

### 1. 使用 Stripe CLI 测试 Webhook

```bash
# 安装 Stripe CLI
brew install stripe/stripe-cli/stripe

# 登录
stripe login

# 转发 webhook 到本地
stripe listen --forward-to localhost:5000/api/payment/webhook

# 触发测试事件
stripe trigger checkout.session.completed
```

### 2. 测试卡号

Stripe 提供测试卡号：
- 成功: `4242 4242 4242 4242`
- 需要 3D 验证: `4000 0027 6000 3184`
- 失败: `4000 0000 0000 0002`

---

## 📝 配置 Stripe Dashboard

### 1. 设置 Webhook 端点

在 Stripe Dashboard 中：
1. 进入 Developers → Webhooks
2. 添加端点：`https://yourapp.com/api/payment/webhook`
3. 选择监听的事件：
   - `checkout.session.completed`
   - `checkout.session.expired`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
4. 复制 Webhook 签名密钥到配置文件

### 2. 获取 API Keys

1. 进入 Developers → API keys
2. 复制 Secret key (sk_test_...) 到服务端配置
3. 复制 Publishable key (pk_test_...) 如果前端需要

---

## 🚀 部署注意事项

### 1. 环境变量
确保生产环境使用正确的 API Key：
- 测试环境: `sk_test_...`
- 生产环境: `sk_live_...`

### 2. HTTPS
Stripe Webhook **必须**使用 HTTPS，本地测试可以使用 Stripe CLI。

### 3. 日志记录
记录所有支付相关操作，便于排查问题：
```python
app.logger.info(f'Payment session created: {session_id}')
app.logger.error(f'Payment failed: {error}')
```

### 4. 监控和告警
- 监控 Webhook 失败率
- 监控支付成功率
- 设置异常告警

---

## 📚 参考资料

- [Stripe Checkout 文档](https://stripe.com/docs/payments/checkout)
- [Stripe Webhooks 文档](https://stripe.com/docs/webhooks)
- [Stripe Python SDK](https://stripe.com/docs/api/python)
- [Stripe 测试卡号](https://stripe.com/docs/testing)

---

## ✅ 实现检查清单

- [ ] 安装 stripe Python 包
- [ ] 配置 Stripe API Keys
- [ ] 实现创建 Checkout Session API
- [ ] 实现查询支付状态 API
- [ ] 实现 Webhook 处理
- [ ] 实现 Webhook 签名验证
- [ ] 实现幂等性处理
- [ ] 创建数据库表
- [ ] 配置 Stripe Dashboard Webhook
- [ ] 测试完整支付流程
- [ ] 部署到生产环境
