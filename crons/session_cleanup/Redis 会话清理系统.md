# Redis 会话清理系统

这个系统用于维护 Redis 中会话数据的一致性，自动清理孤儿会话记录和过期会话。

## 问题背景

在使用 Redis 存储用户会话时，可能出现以下数据不一致的情况：
- `appauth:usess:<email>` 中存储了会话ID列表
- 但对应的 `appauth:sess:<id>` 会话数据已经不存在
- 这导致了"孤儿"会话记录，浪费存储空间并可能影响数据准确性

## 解决方案

### 1. 自动清理机制

代码中增强了以下功能：
- **实时清理**：在会话操作时自动清理相关的孤儿记录
- **惰性清理**：在获取用户会话列表时检查并清理无效会话
- **强化删除**：删除会话时同时清理所有相关索引

### 2. 清理工具

#### `session_cleanup.py` - 主要清理工具
```bash
# 清理孤儿会话记录（默认，安全操作）
python3 crons/session_cleanup/session_cleanup.py

# 查看要清理的内容（模拟运行）
python3 crons/session_cleanup/session_cleanup.py --dry-run

# 同时清理孤儿会话和超过30天的过期会话（慎用）
python3 crons/session_cleanup/session_cleanup.py --include-expired

# 同时清理孤儿会话和超过7天的过期会话（慎用）
python3 crons/session_cleanup/session_cleanup.py --include-expired --max-age-days 7
```

#### `initial_cleanup.py` - 一次性清理
```bash
# 交互式清理现有的孤儿记录
python3 crons/session_cleanup/initial_cleanup.py
```

#### `scheduled_cleanup.py` - 定期清理任务
```bash
# 定期清理任务（适合 cron 调用）
python3 crons/session_cleanup/scheduled_cleanup.py
```

## 部署步骤

### 1. 立即清理现有问题
```bash
cd crons/session_cleanup
python3 initial_cleanup.py
```

### 2. 设置定期清理任务
```bash
# 编辑 crontab
crontab -e

# 添加以下行（调整路径为你的实际路径）：
# 每天凌晨2点清理孤儿会话（安全操作）
0 2 * * * /usr/bin/python3 /path/to/project/crons/session_cleanup/scheduled_cleanup.py

# 如果需要同时清理过期会话，设置环境变量
# 每天凌晨2点完整清理（包括过期会话）
0 2 * * * CLEANUP_INCLUDE_EXPIRED=1 /usr/bin/python3 /path/to/project/crons/session_cleanup/scheduled_cleanup.py

# 每6小时检查孤儿会话
0 */6 * * * /usr/bin/python3 /path/to/project/crons/session_cleanup/session_cleanup.py
```

### 3. 环境变量配置
确保设置了以下环境变量：
```bash
export REDIS_URL="redis://localhost:6379/0"
export REDIS_PREFIX="appauth"

# 可选：启用过期会话清理（默认只清理孤儿会话）
export CLEANUP_INCLUDE_EXPIRED=1
export CLEANUP_MAX_AGE_DAYS=30
```

## 监控和维护

### 查看清理日志
```bash
# 查看定期清理日志
tail -f crons/session_cleanup/session_cleanup.log

# 查看系统日志中的清理信息
grep "session.*cleanup" /var/log/syslog
```

### 手动检查数据一致性
```bash
# 快速检查是否有孤儿记录（默认操作）
python3 crons/session_cleanup/session_cleanup.py --dry-run

# 检查孤儿记录和过期会话
python3 crons/session_cleanup/session_cleanup.py --dry-run --include-expired
```

### 应急清理
如果发现大量孤儿记录：
```bash
# 立即清理所有孤儿记录（默认操作）
python3 crons/session_cleanup/session_cleanup.py

# 清理孤儿记录和超过3天的过期会话
python3 crons/session_cleanup/session_cleanup.py --include-expired --max-age-days 3
```

## 清理统计说明

清理报告包含以下统计信息：
- **检查的用户会话键**：扫描的 `appauth:usess:*` 键数量
- **检查的总会话数**：所有会话ID的总数
- **发现的有效会话**：实际存在的会话数
- **发现的孤儿会话**：引用但不存在的会话数
- **移除的孤儿会话**：实际清理的孤儿会话数
- **删除的空用户会话键**：完全清空的用户会话索引

## 安全注意事项

1. **备份**：在首次运行前备份 Redis 数据
2. **测试**：先在测试环境验证清理逻辑
3. **监控**：密切关注清理后的系统行为
4. **回滚**：准备回滚方案以防出现问题

## 性能影响

- 清理操作设计为轻量级，不会显著影响系统性能
- 定期清理在低峰时段（凌晨）运行
- 实时清理只影响正在操作的用户会话
- 如有性能担忧，可以调整清理频率

## 故障排除

### 常见问题

1. **Redis 连接失败**
   - 检查 `REDIS_URL` 环境变量
   - 确认 Redis 服务运行状态

2. **权限错误**
   - 确保脚本有执行权限：`chmod +x *.py`
   - 检查 Redis 访问权限

3. **清理效果不明显**
   - 运行 `--dry-run` 查看详细分析
   - 检查是否有新的孤儿记录产生

### 获取帮助
```bash
python3 crons/session_cleanup/session_cleanup.py --help
```
