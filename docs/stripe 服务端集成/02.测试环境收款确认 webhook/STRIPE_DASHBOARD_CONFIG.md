# Stripe Dashboard Webhook 配置指南

## 快速配置（仅信用卡支付）

如果你只使用信用卡支付，按以下步骤配置：

### 1. 进入 Webhook 配置页面

1. 登录 [Stripe Dashboard](https://dashboard.stripe.com/)
2. 点击 **Developers** → **Webhooks**
3. 点击 **Add endpoint** 按钮

### 2. 配置端点 URL

**测试环境**：
- 使用 Stripe CLI 转发（见下方说明）
- 或使用 ngrok 等内网穿透工具

**生产环境**：
```
https://your-domain.com/api/payment/webhook
```

### 3. 选择事件

点击 **Select events** 按钮，然后：

#### 推荐配置：6 个事件（完整监控）

**Checkout Session 事件**（搜索 `checkout.session`）：
- ✅ `checkout.session.completed`
- ✅ `checkout.session.expired`
- ✅ `checkout.session.async_payment_succeeded`
- ✅ `checkout.session.async_payment_failed`

**Payment Intent 事件**（搜索 `payment_intent`）：
- ✅ `payment_intent.succeeded`
- ✅ `payment_intent.payment_failed`

#### 最小配置：2 个事件（仅信用卡）

如果只使用信用卡支付，最少配置：
- ✅ `checkout.session.completed`
- ✅ `checkout.session.expired`

### 4. 保存配置

1. 点击 **Add endpoint** 保存
2. 复制显示的 **Signing secret**（格式：`whsec_xxx`）
3. 将 secret 添加到 `.env` 文件：
   ```bash
   STRIPE_WEBHOOK_SECRET=whsec_xxx
   ```

## 完整配置（支持异步支付）

如果你需要支持银行转账等异步支付方式，额外添加：
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`

**注意**：如果搜索不到这些事件，说明你的账户没有启用异步支付功能，这是正常的。

## 事件说明

### Checkout Session 事件

#### checkout.session.completed ⭐⭐⭐⭐⭐
- **触发时机**：用户完成支付，Session 状态变为 `complete`
- **处理逻辑**：增加用户金币余额
- **重要性**：必须配置，主要的支付成功事件

#### checkout.session.expired ⭐⭐⭐⭐
- **触发时机**：Session 过期（默认 24 小时未完成支付）
- **处理逻辑**：标记充值记录为 `expired`
- **重要性**：推荐配置，清理过期订单

#### checkout.session.async_payment_succeeded ⭐⭐⭐⭐
- **触发时机**：异步支付成功（如银行转账确认）
- **处理逻辑**：增加用户金币余额
- **重要性**：推荐配置，支持异步支付方式

#### checkout.session.async_payment_failed ⭐⭐⭐⭐
- **触发时机**：异步支付失败
- **处理逻辑**：标记充值记录为 `expired`
- **重要性**：推荐配置，处理异步支付失败

### Payment Intent 事件

#### payment_intent.succeeded ⭐⭐⭐
- **触发时机**：底层支付成功（通常在 checkout.session.completed 之前或同时）
- **处理逻辑**：记录日志，避免重复处理
- **重要性**：推荐配置，提供额外的支付确认
- **说明**：主要用于监控和日志，实际充值由 checkout.session.completed 处理

#### payment_intent.payment_failed ⭐⭐⭐
- **触发时机**：底层支付失败
- **处理逻辑**：记录日志
- **重要性**：推荐配置，监控支付失败原因

## 测试环境配置

### 使用 Stripe CLI（推荐）

1. **安装 Stripe CLI**
   ```bash
   brew install stripe/stripe-cli/stripe
   ```

2. **登录**
   ```bash
   stripe login
   ```

3. **转发 Webhook**
   ```bash
   stripe listen --forward-to http://localhost:5010/api/payment/webhook
   ```

4. **复制 Webhook Secret**
   Stripe CLI 会显示类似这样的输出：
   ```
   > Ready! Your webhook signing secret is whsec_xxx (^C to quit)
   ```
   
   将这个 secret 添加到 `.env` 文件：
   ```bash
   STRIPE_WEBHOOK_SECRET=whsec_xxx
   ```

5. **重启后端服务**
   ```bash
   ./run_server
   ```

### 测试 Webhook

在另一个终端窗口中触发测试事件：
```bash
# 测试支付完成
stripe trigger checkout.session.completed

# 测试 Session 过期
stripe trigger checkout.session.expired
```

## 常见问题

### Q: 为什么我在 Dashboard 看不到 async_payment 事件？

A: 这可能是因为：
1. 你的账户没有启用异步支付方式（如 ACH、SEPA）
2. 需要在搜索框中输入完整的事件名称才能找到

建议直接在搜索框中输入 `checkout.session.async` 来查找这些事件。

### Q: 我应该配置 payment_intent 事件吗？

A: **推荐配置**。虽然 Checkout Session 事件已经足够处理支付流程，但配置 Payment Intent 事件可以：
- 提供额外的支付状态确认
- 获取更详细的支付失败原因
- 在某些边缘情况下提供保障
- 便于调试和监控

当前代码会记录这些事件的日志，但主要的充值逻辑由 Checkout Session 事件处理，避免重复充值。

### Q: 配置了 6 个事件会不会重复充值？

A: **不会**。代码已经做了幂等性处理：
- `checkout.session.completed` 会完成充值
- `payment_intent.succeeded` 只记录日志，不会重复充值
- 数据库中使用 `payment_tx_id` 作为唯一标识，防止重复处理

### Q: Webhook 签名验证失败怎么办？

A: 检查以下几点：
1. `.env` 文件中的 `STRIPE_WEBHOOK_SECRET` 是否正确
2. 测试环境使用 Stripe CLI 的 secret，生产环境使用 Dashboard 的 secret
3. 重启后端服务以加载新的环境变量

### Q: 如何验证 Webhook 是否正常工作？

A: 
1. 在 Stripe Dashboard 的 Webhooks 页面查看事件日志
2. 查看后端服务日志
3. 使用 Stripe CLI 触发测试事件
4. 完成一次真实的测试支付

## 生产环境检查清单

- [ ] 在 Stripe Dashboard 配置了 Webhook 端点
- [ ] 选择了正确的事件（至少 `checkout.session.completed`）
- [ ] 复制了 Webhook signing secret 到生产环境配置
- [ ] 使用 HTTPS（Stripe 要求）
- [ ] 测试了完整的支付流程
- [ ] 配置了日志监控和告警
- [ ] 验证了幂等性处理（防止重复充值）

## 参考资料

- [Stripe Webhooks 文档](https://stripe.com/docs/webhooks)
- [Checkout Session 事件](https://stripe.com/docs/api/events/types#event_types-checkout.session.completed)
- [Stripe CLI 文档](https://stripe.com/docs/stripe-cli)
