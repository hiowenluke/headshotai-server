# API 文档目录

## 金币系统 API

### 充值相关
- **支付 API** - 见 `../stripe 服务端集成/` 目录
  - 创建支付会话
  - 查询支付状态
  - Webhook 处理

### 历史记录 API
- **[金币历史 API](./COIN_HISTORY_API.md)** - 完整文档
  - 充值历史查询
  - 消费历史查询
  - 金币统计摘要
  - Vue 3 和 React 集成示例

- **[快速开始](./COIN_HISTORY_API_QUICK_START.md)** - 快速参考
  - API 端点总览
  - 基本使用示例

## 认证相关

所有 API 都需要用户登录认证，通过 Cookie 中的 `app_session` 传递。

### 认证流程
1. 用户通过 Google OAuth 登录
2. 服务端创建 session 并设置 Cookie
3. 客户端请求时自动携带 Cookie（需要 `withCredentials: true`）

## 其他 API

（待补充）

## 开发环境

- 后端地址：`http://localhost:5010`
- 前端地址：`http://localhost:5173`

## 更新日志

- 2025-10-26: 添加金币历史记录 API 文档
