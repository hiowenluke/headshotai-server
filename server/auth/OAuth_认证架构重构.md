# OAuth 认证架构重构

## 📁 文件结构

```
server/auth/
├── session_manager.py      # 会话管理器（Redis/内存）
├── state_manager.py        # OAuth状态管理器
├── google/
│   └── auth_google.py      # Google OAuth实现
└── facebook/
    └── auth_facebook.py    # Facebook OAuth实现（示例）
```

## 🏗️ 架构设计

### 1. 独立的管理器模块

#### SessionManager（会话管理器）
- **职责**：统一管理用户会话的CRUD操作
- **存储**：支持Redis和内存两种模式
- **功能**：
  - 保存/获取/删除会话
  - 会话续期（sliding session）
  - 用户会话索引管理
  - 会话数量限制
  - 过期清理

#### StateManager（状态管理器）
- **职责**：管理OAuth流程中的临时状态
- **存储**：支持Redis和内存两种模式
- **功能**：
  - 保存/获取OAuth state和code_verifier
  - 自动过期清理
  - 支持多Provider的状态管理

### 2. Provider特定模块

#### auth_google.py
- **职责**：Google OAuth的具体实现
- **依赖**：SessionManager + StateManager
- **功能**：Google特定的OAuth流程、用户信息解析

#### auth_facebook.py（示例）
- **职责**：Facebook OAuth的具体实现
- **依赖**：SessionManager + StateManager
- **功能**：Facebook特定的OAuth流程、用户信息解析

## 🔄 重构优势

### 1. 代码复用
- ✅ Redis操作逻辑在管理器中统一实现
- ✅ 会话生命周期管理可被多个Provider复用
- ✅ 状态管理逻辑可被多个Provider复用

### 2. 职责分离
- ✅ 业务逻辑专注于OAuth流程
- ✅ 数据存储逻辑独立在管理器中
- ✅ 配置管理更加清晰

### 3. 易于扩展
- ✅ 添加新的OAuth Provider只需实现Provider特定逻辑
- ✅ 会话和状态管理自动可用
- ✅ 统一的调试和监控接口

### 4. 维护性
- ✅ Redis相关Bug只需在一个地方修复
- ✅ 会话逻辑变更影响所有Provider
- ✅ 更容易进行单元测试

## 🚀 使用示例

### 添加新的OAuth Provider

```python
# 1. 创建新的Provider模块
from server.auth.session_manager import SessionManager
from server.auth.state_manager import StateManager

# 2. 实现OAuth流程
def start_oauth():
    state = generate_state()
    StateManager.save_state(state, redirect_uri, code_verifier, 'new_provider')
    # ... OAuth重定向逻辑

def oauth_callback():
    meta, verifier = StateManager.pop_state(state)
    # ... 验证和用户信息获取
    
    session_id = SessionManager.generate_session_id()
    SessionManager.save_session(session_id, user_data, exp)
    SessionManager.add_session_to_user(email, user_id, session_id, timestamp)
    # ... 设置Cookie
```

### 复用会话管理

```python
# 所有Provider都可以使用相同的会话路由
@bp.route('/api/auth/session')
def session_info():
    sess = SessionManager.get_session(session_id)
    new_exp = SessionManager.refresh_session_if_needed(session_id, sess)
    # ... 统一的会话处理逻辑

@bp.route('/api/auth/logout', methods=['POST'])
def logout():
    SessionManager.delete_session(session_id)
    # ... 统一的登出逻辑
```

## 🔧 配置

### 环境变量
```bash
# Redis配置（所有Provider共享）
REDIS_URL=redis://localhost:6379
REDIS_PREFIX=appauth
MAX_USER_SESSIONS=5
SESSION_LIST_LIMIT=20

# 会话配置
SESSION_SLIDING=1
SESSION_SLIDING_SECONDS=3600
SESSION_ABSOLUTE_SECONDS=86400
SESSION_MIN_SECONDS=3600

# Google特定
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Facebook特定
FACEBOOK_CLIENT_ID=your_facebook_client_id
FACEBOOK_CLIENT_SECRET=your_facebook_client_secret
```

## 🐛 调试

### 统一调试接口
```bash
curl http://localhost:5000/api/auth/_debug
```

返回包含所有管理器的调试信息：
- Redis连接状态
- 会话统计
- 状态存储统计
- Redis键样本

## 📈 性能优化

1. **Redis连接复用**：所有管理器共享Redis连接
2. **惰性清理**：只在必要时清理过期数据
3. **批量操作**：使用Redis pipeline减少网络开销
4. **配置优化**：支持滑动会话和绝对过期时间

## 🔐 安全考虑

1. **状态验证**：每个OAuth流程都有独立的状态验证
2. **会话隔离**：不同Provider的会话彼此独立
3. **过期管理**：自动清理过期的状态和会话
4. **Cookie安全**：支持Secure、HttpOnly、SameSite配置
