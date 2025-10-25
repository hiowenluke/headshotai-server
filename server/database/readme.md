
1. 安装 PostgreSQL 和 DBeaver CE

1.1 注意：
- 数据库密码，不要带特殊字符 @#+:!，不然命令行执行用户身份验证会出错。
- 不需要继续安装 Stack Builder。
- 不要用 PostgreSQL 自带的管理工具 pgAdmin 4（运行卡顿），要改用开源的 DBeaver CE。

1.2 创建数据库 headshot_ai_dev

在 DBeaver CE 中，连接 PostgreSQL，用户 postgres，然后在用户 postgres 下，手动创建数据库 headshot_ai_dev。


2. 安装 psql 

```
brew install postgresql
```

注意：
- 如果命令行密码正确、但连不上 PostgresSQL，则是密码有不支持的特殊字符（例如 @#+:!）。按照如下方式修改
```
psql -U postgres
ALTER USER postgres WITH PASSWORD '新密码';
quit
```


3.	安装依赖
```
pip install -r requirements-postgres.txt
```

4.	初始化表：
```
python3 init_db.py --db headshot_ai_dev --user <your_user> --password <pwd>
```
（或）使用完整 DSN：
```
python3 init_db.py --dsn postgresql://user:pwd@localhost:5432/headshot_ai_dev
```

验证：
```
psql headshot_ai_dev -c \"\\dt\"
```

应看到 users / products / services / coin_topups / coin_spendings 五张表。

如需给现有数据库补充最新的 products/services 结构，可执行：
```
psql headshot_ai_dev -f server/database/123.sql
```
脚本支持重复执行，会自动补齐缺失列与数据。

## 独立测试 users 表插入

提供脚本：
* `server/database/user_insert.py` 单次 upsert 函数。
* `server/database/test_user_insert.py` 端到端：加载 .env -> 测试连接 -> 连续执行两次插入。

使用示例：
```bash
python server/database/test_user_insert.py --email test_user@example.com --sub 1234567890abcdef --name Hello --picture https://ex.com/p.png
```

输出示例阶段：
1. load_env
2. dsn
3. connect
4. insert (attempt 1)
5. insert (attempt 2) —— 第二次应 ok 且 user_id 不变，实现幂等。


5. 后续如何创建生产环境下的正式数据库？

到时候问 ChatGPT

