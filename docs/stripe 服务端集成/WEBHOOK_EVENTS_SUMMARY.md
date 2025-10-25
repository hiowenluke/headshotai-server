# Stripe Webhook 事件配置总结

## 当前配置：6 个事件

你已经在 Stripe Dashboard 配置了以下 6 个 webhook 事件：

### ✅ Checkout Session 事件（4 个）

1. **checkout.session.completed**
   - 主要的支付成功事件
   - 触发充值逻辑，增加用户金币

2. **checkout.session.expired**
   - Session 过期事件
   - 标记订单为过期状态

3. **checkout.session.async_payment_succeeded**
   - 异步支付成功（如银行转账）
   - 触发充值逻辑，增加用户金币

4. **checkout.session.async_payment_failed**
   - 异步支付失败
   - 标记订单为过期状态

### ✅ Payment Intent 事件（2 个）

5. **payment_intent.succeeded**
   - 底层支付成功确认
   - 记录日志，不重复充值

6. **payment_intent.payment_failed**
   - 底层支付失败通知
   - 记录日志，用于监控

## 事件处理流程

### 信用卡支付（同步）

```
用户点击支付
    ↓
payment_intent.succeeded (记录日志)
    ↓
checkout.session.completed (增加金币) ✅
    ↓
充值完成
```

### 银行转账（异步）

```
用户发起转账
    ↓
checkout.session.completed (状态: pending)
    ↓
等待银行确认...
    ↓
payment_intent.succeeded (记录日志)
    ↓
checkout.session.async_payment_succeeded (增加金币) ✅
    ↓
充值完成
```

### 支付失败

```
用户支付失败
    ↓
payment_intent.payment_failed (记录日志)
    ↓
checkout.session.expired (标记过期) ✅
    ↓
订单关闭
```

## 代码处理逻辑

### server/api/payment.py

```python
@bp.route('/api/payment/webhook', methods=['POST'])
def stripe_webhook():
    # 验证签名
    event = stripe.Webhook.construct_event(payload, sig_header, secret)
    event_type = event.get('type')
    
    # Checkout Session 事件（主要处理）
    if event_type == 'checkout.session.completed':
        complete_topup()  # 增加金币
    
    elif event_type == 'checkout.session.async_payment_succeeded':
        complete_topup()  # 增加金币
    
    elif event_type == 'checkout.session.expired':
        update_status('expired')  # 标记过期
    
    elif event_type == 'checkout.session.async_payment_failed':
        update_status('expired')  # 标记过期
    
    # Payment Intent 事件（日志记录）
    elif event_type == 'payment_intent.succeeded':
        logger.info('payment succeeded')  # 仅记录
    
    elif event_type == 'payment_intent.payment_failed':
        logger.warning('payment failed')  # 仅记录
    
    return {'status': 'ok'}
```

## 幂等性保障

代码通过以下机制防止重复充值：

1. **数据库唯一约束**
   ```sql
   UNIQUE (payment_provider, payment_tx_id)
   ```

2. **状态检查**
   ```python
   # 只处理 status != 'completed' 的记录
   WHERE status <> 'completed'
   ```

3. **事务处理**
   ```python
   # 使用数据库事务确保原子性
   with transaction():
       update_status()
       add_coins()
   ```

## 测试验证

### 1. 使用 Stripe CLI 测试

```bash
# 测试支付成功
stripe trigger checkout.session.completed

# 测试支付失败
stripe trigger checkout.session.expired

# 测试异步支付
stripe trigger checkout.session.async_payment_succeeded
```

### 2. 查看日志

```bash
# 后端日志会显示：
[INFO] stripe: payment_intent.succeeded received: pi_xxx (handled by checkout.session.completed)
[INFO] stripe: top-up completed for session cs_xxx
```

### 3. 验证数据库

```sql
-- 查看充值记录
SELECT payment_tx_id, status, coins_total 
FROM coin_topups 
ORDER BY created_at DESC 
LIMIT 5;

-- 查看用户余额
SELECT email, coin_balance 
FROM users 
WHERE id = 'user_id';
```

## 监控建议

### 关键指标

1. **Webhook 成功率**
   - 目标：> 99%
   - 在 Stripe Dashboard → Webhooks 查看

2. **充值成功率**
   - 目标：> 95%
   - 监控 `checkout.session.completed` 事件

3. **支付失败率**
   - 监控 `payment_intent.payment_failed` 事件
   - 分析失败原因

### 告警设置

建议设置以下告警：
- Webhook 失败率 > 1%
- 充值处理失败（数据库错误）
- 支付失败率异常增高

## 常见问题排查

### 问题 1：充值成功但余额未更新

**排查步骤**：
1. 检查 webhook 是否收到 `checkout.session.completed` 事件
2. 查看后端日志是否有错误
3. 检查数据库中的充值记录状态
4. 验证 `complete_topup` 函数是否执行成功

### 问题 2：收到重复的 webhook 事件

**说明**：这是正常的，Stripe 可能会重试发送 webhook。

**解决方案**：代码已经实现了幂等性处理，重复事件不会导致重复充值。

### 问题 3：payment_intent 和 checkout.session 事件都触发了

**说明**：这是正常的，两种事件会同时触发。

**解决方案**：
- `checkout.session.completed` 会执行充值
- `payment_intent.succeeded` 只记录日志
- 不会重复充值

## 配置检查清单

- [x] 配置了 6 个 webhook 事件
- [x] 复制了 webhook signing secret 到 `.env`
- [x] 重启了后端服务
- [x] 测试了支付流程
- [x] 验证了充值成功
- [x] 检查了日志输出
- [ ] 配置了监控和告警（生产环境）

## 参考文档

- [STRIPE_WEBHOOK_SETUP.md](./STRIPE_WEBHOOK_SETUP.md) - Webhook 配置详细说明
- [STRIPE_DASHBOARD_CONFIG.md](./STRIPE_DASHBOARD_CONFIG.md) - Dashboard 配置指南
- [STRIPE_INTEGRATION_SERVER.md](./STRIPE_INTEGRATION_SERVER.md) - 服务端集成指南

## 更新日志

- 2025-10-26: 添加了 6 个 webhook 事件配置
- 2025-10-26: 更新了代码以处理 payment_intent 事件
- 2025-10-26: 添加了幂等性保障机制
