# Google 登录集成方案

## 目录
1. Google Cloud 项目与 OAuth 配置
2. 凭据安全提供方式
3. 后端授权码交换流程（含 PKCE 可选）
4. 用户与会话关联 & 通知前端
5. 前端交互与弹窗实现
6. 登录后返回来源页面逻辑（含侧边菜单特殊处理）
7. 安全要点清单
8. 部署与测试用例
9. 需要准备 / 提供的企业账号信息
10. 下一步可交付代码清单

---
## 1. Google Cloud 项目与 OAuth 配置
- 在 Google Cloud Console 创建/选择一个项目。
- 启用所需 API（基础 OpenID 不需要额外启用；若取头像/更多资料可启用 People API）。
- 配置 OAuth 同意屏幕：
  - 用户类型：External（对公众）
  - 填写应用名称、支持邮箱、隐私政策 URL、服务条款 URL。
  - Scopes：`openid email profile`（最小化权限）。
  - 验证前如需真实外部用户，添加测试用户。
- 创建 OAuth 2.0 Client（类型：Web application）：
  - Authorized JavaScript origins：
    - 开发：`http://localhost:5173`
    - 生产：`https://yourdomain.com`
  - Authorized redirect URIs：
    - 开发：`http://localhost:5173/api/auth/google/callback`
    - 生产：`https://yourdomain.com/api/auth/google/callback`
- 获得 `client_id` 与 `client_secret`。

## 2. 凭据安全提供方式
后端（Python 服务）：使用环境变量或部署平台 Secret：
```
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_secret
GOOGLE_REDIRECT_URI=https://yourdomain.com/api/auth/google/callback
```
前端只需要（可选）`VITE_GOOGLE_CLIENT_ID`；也可以完全由后端生成授权 URL，前端不直接使用 client_id。
> 不要把 secret 写入版本库 (config.json / 源码)。

## 3. 后端授权码交换流程
推荐“授权码 +（可选 PKCE）”流程。

### /api/auth/google/start
1. 生成随机 `state`（CSRF 防护）。
2. 可选：生成 `code_verifier` 与 `code_challenge` (S256)。
3. 保存 `state`(+ `code_verifier`) 到：短期内存 / Redis / HttpOnly cookie。
4. 构造授权 URL：
```
https://accounts.google.com/o/oauth2/v2/auth?
  client_id=...&redirect_uri=...&response_type=code&
  scope=openid%20email%20profile&state=...&prompt=select_account&
  code_challenge=...&code_challenge_method=S256
```
5. 返回：
   - 方式 A：后端直接 302 重定向。
   - 方式 B：返回 JSON `{ url }` 供前端 popup 打开。

### /api/auth/google/callback
1. 校验 `state`。
2. 若 query 有 `error`（如 access_denied）→ 记录并返回失败页面（postMessage 通知）。
3. POST 交换 token：`https://oauth2.googleapis.com/token`
```
code=...&client_id=...&client_secret=...&redirect_uri=...&grant_type=authorization_code&code_verifier=...
```
4. 验证 `id_token`（签名 & aud / exp / iss）。
5. 解析字段：`sub` (Google 唯一 ID), `email`, `name`, `picture`。
6. `get_or_create` 本地用户：按 `google_sub=sub` / email 匹配。
7. 建立会话：生成 session_id 或自签 JWT；放入 HttpOnly+Secure+SameSite=Lax cookie。
8. 返回一个极简 HTML：
```html
<script>
  window.opener && window.opener.postMessage({
    type:'auth:success', provider:'google'
  }, window.location.origin);
  window.close();
</script>
```
失败时：`type:'auth:failure', reason`。

## 4. 用户与会话关联 & 通知前端
- 会话层：`session_id` ↔ 用户 ID（存储在服务端或 Redis）。
- 前端加载时可调用 `/api/auth/session` 返回当前用户信息（惰性同步）。
- 登录完成后 popup 通过 `postMessage` 主窗口 → 更新全局 store (`isLoggedIn=true`, `user` 对象)。

## 5. 前端交互与弹窗
按钮逻辑（`signIn('google')`）：
1. `fetch('/api/auth/google/start')`（若返回 JSON）→ `const w = window.open(url, 'google_auth', 'width=520,height=640');`
2. 监听：
```js
function onMsg(e){
  if(e.origin!==location.origin) return;
  if(e.data?.type==='auth:success'){ /* setUser; close modal */ }
  if(e.data?.type==='auth:failure'){ /* show error */ }
}
window.addEventListener('message', onMsg);
```
3. 轮询 popup 关闭（无结果）→ 取消状态。

## 6. 登录后返回来源页面
- 记录来源：打开 Auth 前 `authOrigin = router.currentRoute.value.fullPath`；保存 `authFrom`（例如 side-menu）。
- 成功后：
  - 如果 `authFrom==='side-menu'`：不跳路由（菜单已关闭，主界面即目标）。
  - 否则 `router.push(authOrigin)`（避免留在 /auth 模态状态）。
- 若使用事件触发 `open-auth`，可以 detail 带 `{ from: 'side-menu' }`。

## 7. 安全要点
| 要点 | 说明 |
|------|------|
| state | 必须校验；不匹配拒绝 |
| PKCE | 减少授权码被截获风险（推荐） |
| Scopes 最小化 | 仅 `openid email profile` |
| HttpOnly Cookie | 前端无法 JS 读取，减 XSS 令牌泄露 |
| SameSite=Lax | 降低 CSRF 风险 |
| id_token 验证 | aud/iss/exp/签名 必须验证 |
| 速率限制 | 交换 token 与用户创建加限流 |
| 错误处理 | Google 取消、网络、token 失效各自分支 |

## 8. 部署与测试用例
| 用例 | 预期 |
|------|------|
| 正常登录 | 收到 success 消息，用户状态更新 |
| 用户取消 | 收到 failure(reason=access_denied) |
| state 篡改 | 后端 400 拒绝 |
| 二次登录 | 返回同一用户，无重复创建 |
| 侧边菜单入口 | 登录后不改变当前 route |
| 过期 id_token | 后端拒绝并提示重新登录 |

## 9. 需要准备的企业账号信息
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- Redirect URI（开发 & 生产）
- （可选）组织限制策略（仅公司域用户）
- （可选）Logo / 品牌名 / 支持邮箱 / 隐私政策 & ToS URL

## 10. 下一步可交付代码（若需要我继续）
- `server/auth_google.py`：实现 `/api/auth/google/start` & `/api/auth/google/callback`
- Session 管理（内存 / Redis）示例
- 前端：
  - 在 `AuthModal.vue` 中完善 `signIn('google')`
  - 全局状态 `user` / `isLoggedIn`
  - postMessage 监听封装 util
- 错误与 Loading UI

> 告诉我“生成后端与前端示例代码”即可继续落地。

---
**速览流程图**
```
[User Click Google]
      |
      v
 /api/auth/google/start  ---> 生成 state+PKCE+URL ----> 返回 URL
      |                                      \
      v                                       打开 Google 授权页
  (Popup Window) <--- code --- Google Accounts --- 用户授权
      | callback
      v
 /api/auth/google/callback -> 验证 state -> 交换 token -> 验证 id_token -> 用户入库/会话
      |
   postMessage success
      |
 Main Window 更新状态 -> 关闭 AuthModal / 返回来源
```
