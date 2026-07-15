## 1. 总结
- **漏洞类型**：SQL 注入（CWE-89）
- **标记位置**：`app/models/data_query.py:239`
- **漏洞描述**：`data_query.py` 中的 `_validate_sql` 函数使用正则表达式 `r'(?:FROM|JOIN)\s+(?:\(\s*)?(\w+)'` 提取表名以进行白名单验证。该正则仅捕获 `FROM` 或 `JOIN` 后紧跟的第一个单词，未能检测旧式逗号分隔 `FROM` 子句中的其他表（例如 `SELECT * FROM data_warehouse, admins`）。能够通过提示注入影响 LLM 生成 SQL 的攻击者可以绕过表白名单，对未在白名单中的敏感表（如 `users`、`admins`、`roles`、`chat_messages` 等）执行 `SELECT` 查询。

## 2. 分析逻辑

### 步骤 1：检查 `app/models/data_query.py:239` 处的标记点
`_validate_sql` 函数对大写化后的 SQL 字符串使用正则 `r'(?:FROM|JOIN)\s+(?:\(\s*)?(\w+)'` 配合 `re.findall` 提取表名以进行白名单验证。该正则仅匹配 `FROM` 或 `JOIN` 后紧跟的一个单词。

```python
# app/models/data_query.py:239
for table in re.findall(r'(?:FROM|JOIN)\s+(?:\(\s*)?(\w+)', sql_upper):
    if table.upper() in sql_keywords:
        continue
    if table.lower() not in allowed_lower:
        raise DataQueryError(f"不允许访问表: {table}")
```

对于诸如 `SELECT * FROM data_warehouse, admins` 的查询，正则仅捕获 `data_warehouse`（在白名单中），但**不会**捕获 `admins`（不在白名单中）。结果验证静默通过，查询得以执行。

### 步骤 2：追踪 SQL 执行路径
验证后的 SQL 被传递给 `execute_readonly_sql`，后者通过原始的 `sqlite3` 连接执行，且无任何参数化：

```python
# app/models/data_query.py:248-261
def execute_readonly_sql(sql):
    _validate_sql(sql)
    with get_connection() as conn:
        try:
            conn.execute("PRAGMA query_only = ON")
        except Exception:
            pass
        cursor = conn.execute(sql)   # <-- raw SQL execution
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
```

`conn.execute(sql)` 使用单个字符串参数，是原始的 SQL 执行。`PRAGMA query_only = ON` 仅阻止写操作（INSERT/UPDATE/DELETE），但**不能**阻止对敏感表的未授权 `SELECT` 语句。

### 步骤 3：追踪数据源回到用户输入
沿调用链向上追溯：

1. `app/controllers/chat.py:265` 直接从 HTTP 请求接收用户输入：
```python
message = self.get_argument("message", "").strip()
```

2. `app/controllers/chat.py:294` 将其存储为 `original_message`。

3. `app/controllers/chat.py:392-394` 当检测到的意图为 `database_query` 或 `chart_request` 时，将用户消息传递给数据库查询引擎：
```python
if intent in ("database_query", "chart_request"):
    try:
        query_result = await execute_database_query(original_message, model)
```

4. `app/services/intent_engine.py:460` 调用 `generate_sql(question, model, query_type)`，该方法将 `question`（原始用户消息）发送给 LLM，并附带包含数据库模式的提示。

5. `app/services/intent_engine.py:466` 执行 LLM 生成的 SQL：
```python
rows = execute_readonly_sql(sql)
```

因此，用户消息是一个不受控的入口点，可以影响生成的 SQL。基于 LLM 的 SQL 生成中，提示注入技术已有充分记录，且应用程序在将用户消息包含到 LLM 提示中之前未对其进行清理。

### 步骤 4：验证敏感未授权表的存在
数据库文件（`database/finderos.db`）在 `app/models/db.py:17` 中定义。`app/models/db.py` 中的模式初始化创建了许多**不在** `ALLOWED_TABLES` 白名单中的敏感表：

```python
# app/models/db.py:93-171
CREATE TABLE IF NOT EXISTS users(...)
CREATE TABLE IF NOT EXISTS roles(...)
CREATE TABLE IF NOT EXISTS functions(...)
CREATE TABLE IF NOT EXISTS role_functions(...)
CREATE TABLE IF NOT EXISTS menus(...)
CREATE TABLE IF NOT EXISTS admins(...)
CREATE TABLE IF NOT EXISTS chat_sessions(...)
CREATE TABLE IF NOT EXISTS chat_messages(...)
```

`app/models/data_query.py:19-93` 中的 `ALLOWED_TABLES` 白名单仅允许：`data_warehouse`、`deep_collected_data`、`collected_data`、`digital_employees` 和 `ai_models`。`users` 和 `admins` 表包含密码哈希和盐值，是高价值目标。

### 步骤 5：检查路径上的清理或验证
- **正则验证**：`_validate_sql` 的正则是唯一的表级验证，对于逗号分隔的 `FROM` 子句明显存在缺陷。
- **无输入清理**：在 `app/services/intent_engine.py:382` 中，用户消息在传递给 LLM 调用之前未经过任何输入清理或长度限制。
- **无参数化查询**：`app/models/data_query.py:261` 处的 SQL 执行使用 `conn.execute(sql)` —— 原始执行，无参数化。
- **无二次授权**：`_validate_sql` 之后没有额外的授权检查来验证表访问权限。

### 步骤 6：检查代码上下文（测试/废弃代码）
该代码不在测试目录中。它是活跃的 `ChatHandler` SSE 端点（`app/controllers/chat.py:249`）的一部分，该端点带有 `@tornado.web.authenticated` 装饰器，并用于用户聊天交互。`execute_database_query` 函数直接从该活跃端点调用。

### 分析过程（决策树遍历）
- **Q1**：用户可控输入是否参与 SQL 字符串？→ **是**。来自 HTTP 请求的 `message` 参数被传递给 LLM，LLM 生成随后执行的 SQL。（`app/controllers/chat.py:265`，`app/services/intent_engine.py:460-466`）
- **Q2**：查询是否针对用户控制的部分进行了参数化（`?`、`:name`、`$1`、`#{}`）？→ **否**。SQL 通过 `conn.execute(sql)` 作为原始字符串执行。（`app/models/data_query.py:261`）
- **Q3**：数据路径上是否存在有效的输入验证（白名单、整数转换、枚举）？→ **否**。唯一的验证是有缺陷的正则 `_validate_sql`，可以通过逗号分隔的 `FROM` 语法绕过。（`app/models/data_query.py:239`）
- **Q4**：代码是否位于测试/演示/废弃/生成上下文中？→ **否**。它是生产代码中活跃的已认证 HTTP 端点。（`app/controllers/chat.py:249-394`）
- **Q5**：框架是否自动参数化且未被绕过？→ **否**。Python 的 `sqlite3` 不会自动参数化单参数 `execute()` 调用。（`app/models/data_query.py:261`）
- **→ 到达叶子节点**：`真实漏洞`

## 3. 结论
**真实漏洞**

**关键证据：**
- `app/models/data_query.py:239` 处的正则仅捕获 `FROM`/`JOIN` 后的第一个表，未能匹配逗号分隔的表（例如 `FROM data_warehouse, admins`）。
- 来自 `app/controllers/chat.py:265` 的用户可控 `message` 参数到达 LLM SQL 生成路径，并最终在 `app/models/data_query.py:261` 处执行原始 SQL。
- 数据库包含敏感但未列入白名单的表（`users`、`admins`、`roles`、`chat_messages` 等），这些表都存储在 `get_connection()` 访问的同一个 SQLite 文件中（`app/models/db.py:17`）。
- 该代码可从活跃的已认证 HTTP 端点（`app/controllers/chat.py:249`）访问，不是测试或废弃代码。
- `PRAGMA query_only = ON` 仅阻止写操作；不能通过逗号连接绕过方式阻止未授权读取。

## 4. 修复建议
- **使用合适的 SQL 解析器库替换基于正则的表提取**（例如 `sqlparse` 或 `sqlite3` 解析器），从 AST 中提取所有表引用，包括逗号分隔的表和嵌套子查询。在执行前对照 `ALLOWED_TABLES` 白名单验证每个表。
- **添加解析后验证步骤**，明确拒绝任何在 `FROM` 后包含逗号的 SQL，除非每个逗号分隔的标记都是白名单中的表名或别名。
- **考虑使用参数化查询封装器或只读 ORM** 作为执行层，但对于此特定问题，主要修复措施是健壮的基于 AST 的表验证。
- **修复后重新检查**：确保诸如 `SELECT * FROM data_warehouse, admins`、`SELECT * FROM data_warehouse JOIN admins ON ...` 和 `SELECT * FROM (SELECT * FROM data_warehouse), admins` 等查询都被新的验证器正确拒绝。
