# 金币历史 API 快速开始

## API 端点总览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/coins/topup-history` | GET | 获取充值历史 |
| `/api/coins/spending-history` | GET | 获取消费历史 |
| `/api/coins/summary` | GET | 获取金币统计摘要 |

## 快速示例

### 1. 获取充值历史

```typescript
// 获取最近 20 条充值记录
const response = await axios.get('/api/coins/topup-history', {
  params: { limit: 20, offset: 0 },
  withCredentials: true
})

console.log(response.data)
// {
//   items: [...],
//   total: 5,
//   limit: 20,
//   offset: 0
// }
```

### 2. 获取消费历史

```typescript
// 获取最近 20 条消费记录
const response = await axios.get('/api/coins/spending-history', {
  params: { limit: 20, offset: 0 },
  withCredentials: true
})

console.log(response.data)
// {
//   items: [...],
//   total: 48,
//   limit: 20,
//   offset: 0
// }
```

### 3. 获取统计摘要

```typescript
// 获取金币统计信息
const response = await axios.get('/api/coins/summary', {
  withCredentials: true
})

console.log(response.data)
// {
//   current_balance: 1200,
//   total_purchased: 5000,
//   total_bonus: 1000,
//   total_spent: 4800,
//   total_topups: 5,
//   total_spendings: 48
// }
```

## 重要提示

1. **认证要求**：所有 API 都需要用户登录，使用 `withCredentials: true` 携带 Cookie
2. **分页**：使用 `limit` 和 `offset` 参数实现分页
3. **时间格式**：API 返回 ISO 8601 格式，需要在客户端格式化

## 完整文档

详细的 API 文档、TypeScript 类型定义和 Vue/React 示例，请查看：
- [COIN_HISTORY_API.md](./COIN_HISTORY_API.md)
