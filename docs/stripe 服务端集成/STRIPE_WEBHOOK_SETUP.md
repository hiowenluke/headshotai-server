# Stripe Webhook 本地测试配置

## 问题说明

在本地开发环境中，Stripe 无法直接访问你的服务器来发送 webhook 事件。这导致：
- 充值记录状态一直是 `pending`
- 用户余额不会自动更新
- 需要手动完成充值

## 解决方案：使用 Stripe CLI

### 1. 安装 Stripe CLI

```bash
# macOS (使用 Homebrew)
brew install stripe/stripe-cli/stripe

# 验证安装
stripe --version
```

### 2. 登录 Stripe 账户

```bash
stripe login
```

这会打开浏览器，让你授权 Stripe CLI 访问你的账户。
Please note: this key will expire after 90 days, at which point you'll need to re-authenticate.


### 3. 转发 Webhook 事件到本地服务器

```bash
stripe listen --forward-to http://localhost:5010/api/payment/webhook
```

这个命令会：
- 监听你的 Stripe 账户的所有事件
- 将事件转发到本地服务器的 webhook 端点
- 显示一个 webhook signing secret（类似 `whsec_xxx`）

### 4. 更新环境变量

将 Stripe CLI 显示的 webhook signing secret 复制到 `.env` 文件：

```bash
# 测试环境使用 Stripe CLI 的 webhook secret
STRIPE_WEBHOOK_SECRET=whsec_xxx  # 替换为 Stripe CLI 显示的值
```

重启后端服务以加载新的环境变量。

### 5. 测试 Webhook

在另一个终端窗口中触发测试事件：

```bash
# 测试 checkout.session.completed 事件
stripe trigger checkout.session.completed
```

你应该能在 Stripe CLI 的输出中看到事件被转发，并在后端日志中看到处理结果。

## 生产环境配置

在生产环境中，你需要：

1. 在 Stripe Dashboard 中配置 webhook 端点：
   - 进入 Developers → Webhooks → Add endpoint
   - URL: `https://your-domain.com/api/payment/webhook`
   - 点击 "Select events"
   - 搜索并选择以下事件：
   
   **Checkout Session 事件（主要）**：
     - ✅ `checkout.session.completed` **（必须，支付完成）**
     - ✅ `checkout.session.expired` **（推荐，Session 过期）**
     - ✅ `checkout.session.async_payment_succeeded` **（推荐，异步支付成功）**
     - ✅ `checkout.session.async_payment_failed` **（推荐，异步支付失败）**
   
   **Payment Intent 事件（额外保障）**：
     - ✅ `payment_intent.succeeded` **（推荐，支付成功的额外确认）**
     - ✅ `payment_intent.payment_failed` **（推荐，支付失败通知）**
   
   **说明**：
   - Checkout Session 事件是主要的处理流程
   - Payment Intent 事件提供额外的支付状态确认
   - 配置所有 6 个事件可以确保不会遗漏任何支付状态变化

2. 将生产环境的 webhook signing secret 配置到 `.env`：
   ```bash
   STRIPE_WEBHOOK_SECRET=whsec_prod_xxx
   ```

## 手动完成充值（临时方案）

如果不想配置 Stripe CLI，可以手动完成充值：

```bash
# 查看待处理的充值
psql $DATABASE_URL -c "SELECT payment_tx_id, coins_total, status FROM coin_topups WHERE status = 'pending' ORDER BY created_at DESC LIMIT 5;"

# 手动完成充值
python3 scripts/manual_complete_topup.py <session_id>
```

## Webhook 事件说明

### 推荐配置：6 个事件

当前配置了 6 个 webhook 事件，提供完整的支付状态监控：

#### Checkout Session 事件（主要处理流程）

1. **`checkout.session.completed`** ⭐⭐⭐⭐⭐
   - **触发时机**：用户完成支付，Session 状态变为 complete
   - **处理逻辑**：增加用户金币余额
   - **重要性**：必须配置，这是主要的支付成功事件

2. **`checkout.session.expired`** ⭐⭐⭐⭐
   - **触发时机**：Session 过期（默认 24 小时未完成支付）
   - **处理逻辑**：标记充值记录为 expired
   - **重要性**：推荐配置，用于清理过期订单

3. **`checkout.session.async_payment_succeeded`** ⭐⭐⭐⭐
   - **触发时机**：异步支付成功（如银行转账确认）
   - **处理逻辑**：增加用户金币余额
   - **重要性**：推荐配置，支持异步支付方式

4. **`checkout.session.async_payment_failed`** ⭐⭐⭐⭐
   - **触发时机**：异步支付失败
   - **处理逻辑**：标记充值记录为 expired
   - **重要性**：推荐配置，处理异步支付失败

#### Payment Intent 事件（额外保障）

5. **`payment_intent.succeeded`** ⭐⭐⭐
   - **触发时机**：底层支付成功（通常在 checkout.session.completed 之前或同时）
   - **处理逻辑**：记录日志，主要由 checkout.session.completed 处理
   - **重要性**：推荐配置，提供额外的支付确认
   - **说明**：避免重复处理，主要用于日志记录和监控

6. **`payment_intent.payment_failed`** ⭐⭐⭐
   - **触发时机**：底层支付失败
   - **处理逻辑**：记录日志
   - **重要性**：推荐配置，用于监控支付失败原因

### 事件关系说明

在 Checkout Session 模式下，事件触发顺序通常是：

**成功流程**：
```
payment_intent.succeeded → checkout.session.completed
```

**失败流程**：
```
payment_intent.payment_failed → checkout.session.expired
```

**异步支付流程**：
```
checkout.session.completed (pending) → payment_intent.succeeded → checkout.session.async_payment_succeeded
```

### 为什么同时配置两种事件？

1. **Checkout Session 事件**：提供完整的订单生命周期管理
2. **Payment Intent 事件**：提供底层支付状态的额外确认

虽然 Checkout Session 事件已经足够，但配置 Payment Intent 事件可以：
- 提供更详细的支付失败原因
- 在某些边缘情况下提供额外保障
- 便于调试和监控

### 最小配置 vs 完整配置

**最小配置**（仅信用卡支付）：
- `checkout.session.completed`
- `checkout.session.expired`

**完整配置**（推荐，当前配置）：
- `checkout.session.completed`
- `checkout.session.expired`
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `payment_intent.succeeded`
- `payment_intent.payment_failed`

## 常见问题

### Q: Stripe CLI 显示 "webhook signing secret" 在哪里？

A: 运行 `stripe listen --forward-to ...` 后，会显示类似这样的输出：
```
> Ready! Your webhook signing secret is whsec_xxx (^C to quit)
```

### Q: 如何查看 webhook 事件日志？

A: Stripe CLI 会实时显示所有转发的事件。你也可以在 Stripe Dashboard 的 Developers > Webhooks 中查看事件历史。

### Q: 测试环境和生产环境的 webhook secret 一样吗？

A: 不一样。测试环境使用 Stripe CLI 生成的 secret，生产环境使用 Stripe Dashboard 中配置的 secret。
