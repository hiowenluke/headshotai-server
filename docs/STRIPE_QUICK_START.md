# 🚀 Stripe 支付集成 - 快速开始指南

## 📋 概述

本指南帮助你快速完成 Stripe 支付集成，让用户可以购买金币。

---

## ✅ 客户端（已完成）

客户端的所有代码已经实现完毕，包括：

### 新增文件
1. `src/services/paymentService.ts` - 支付服务
2. `src/pages/payment/PaymentSuccessPage.vue` - 支付成功页面
3. `src/pages/payment/PaymentCancelPage.vue` - 支付取消页面

### 修改文件
1. `src/pages/userCenter/BuyCoinsPage.vue` - 添加支付逻辑
2. `src/App.vue` - 添加支付页面

---

## 🔧 服务端（需要实现）

### 第一步：安装依赖

```bash
pip install stripe
```

### 第二步：配置 Stripe

在服务端配置文件中添加：

```python
# config.py 或 .env
STRIPE_SECRET_KEY = "sk_test_..."  # 从 Stripe Dashboard 获取
STRIPE_WEBHOOK_SECRET = "whsec_..."  # 配置 Webhook 后获取
```

### 第三步：实现 3 个 API 端点

#### 1. 创建 Checkout Session

```python
@app.route('/api/payment/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    data = request.get_json()
    
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': f'{data["coins"]} Coins',
                },
                'unit_amount': int(data['price_usd'] * 100),
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=data['success_url'],
        cancel_url=data['cancel_url'],
        metadata={
            'user_id': str(current_user.id),
            'coins': str(data['coins']),
            'bonus': str(data['bonus'])
        }
    )
    
    return jsonify({
        'session_id': session.id,
        'checkout_url': session.url
    })
```

#### 2. 查询支付状态

```python
@app.route('/api/payment/status/<session_id>', methods=['GET'])
@login_required
def get_payment_status(session_id):
    # 从数据库查询支付记录
    payment = Payment.query.filter_by(session_id=session_id).first()
    
    return jsonify({
        'status': payment.status,
        'session_id': session_id,
        'coins_added': payment.coins if payment.status == 'completed' else None,
        'new_balance': current_user.coin_balance if payment.status == 'completed' else None
    })
```

#### 3. 处理 Webhook（最重要！）

```python
@app.route('/api/payment/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    event = stripe.Webhook.construct_event(
        payload, sig_header, STRIPE_WEBHOOK_SECRET
    )
    
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])
        coins = int(session['metadata']['coins'])
        bonus = int(session['metadata']['bonus'])
        
        # 增加用户金币
        user = User.query.get(user_id)
        user.coin_balance += (coins + bonus)
        db.session.commit()
    
    return jsonify({'status': 'success'})
```

### 第四步：配置 Stripe Dashboard

1. 登录 [Stripe Dashboard](https://dashboard.stripe.com/)
2. 进入 **Developers → Webhooks**
3. 点击 **Add endpoint**
4. 输入 URL: `https://yourapp.com/api/payment/webhook`
5. 选择事件: `checkout.session.completed`
6. 复制 **Signing secret** 到配置文件

---

## 🧪 测试流程

### 1. 启动服务

```bash
# 终端 1: 启动前端
cd headshotai-web
npm run dev

# 终端 2: 启动后端
cd ../server
./run_server

# 终端 3: 转发 Webhook（本地测试）
stripe listen --forward-to localhost:5000/api/payment/webhook
```

### 2. 测试支付

1. 打开浏览器访问 `http://localhost:5173`
2. 登录用户账号
3. 打开侧边菜单 → 点击 "Buy Coins"
4. 选择一个套餐
5. 点击 "Pay" 按钮
6. 使用测试卡号: `4242 4242 4242 4242`
7. 填写任意信息提交
8. 验证是否跳转到成功页面
9. 检查金币余额是否增加

---

## 📊 数据库表结构

### payment_sessions 表

```sql
CREATE TABLE payment_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    amount_usd DECIMAL(10, 2) NOT NULL,
    coins INTEGER NOT NULL,
    bonus INTEGER DEFAULT 0,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## 🐛 常见问题

### Q: 点击 Pay 按钮没反应？
**A:** 检查：
- 后端是否运行
- API 端点是否正确
- 浏览器控制台是否有错误

### Q: 支付成功但金币没增加？
**A:** 检查：
- Webhook 是否配置正确
- Webhook 处理逻辑是否正确
- Stripe Dashboard 中的 Webhook 日志

### Q: 本地测试 Webhook 不工作？
**A:** 使用 Stripe CLI：
```bash
stripe listen --forward-to localhost:5000/api/payment/webhook
```

---

## 📚 详细文档

- **客户端实现**: 查看 `STRIPE_INTEGRATION_CLIENT.md`
- **服务端实现**: 查看 `STRIPE_INTEGRATION_SERVER.md`
- **Stripe 官方文档**: https://stripe.com/docs

---

## ✅ 检查清单

### 客户端（已完成）
- [x] 支付服务
- [x] 支付成功页面
- [x] 支付取消页面
- [x] 购买页面集成

### 服务端（需要实现）
- [ ] 安装 stripe 包
- [ ] 配置 API Keys
- [ ] 实现创建 Session API
- [ ] 实现查询状态 API
- [ ] 实现 Webhook 处理
- [ ] 配置 Stripe Dashboard
- [ ] 创建数据库表
- [ ] 测试完整流程

---

## 🎉 完成后

支付功能上线后，用户就可以：
1. 在侧边菜单点击 "Buy Coins"
2. 选择套餐并支付
3. 使用 Stripe 安全支付
4. 自动获得金币

祝你集成顺利！🚀
