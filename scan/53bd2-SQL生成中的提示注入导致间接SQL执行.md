## 1. 总结
- **漏洞类型**：SQL 注入 (CWE-89)
- **标记位置**：`app/services/intent_engine.py:372-412`
- **漏洞描述**：`generate_sql` 函数通过 Python 字符串格式化将用户输入直接嵌入 LLM 提示词中。攻击者可执行提示词注入，影响 LLM 生成包含经过巧妙混淆语法的 SQL，从而绕过 `execute_readonly_sql` 中基于正则表达式的验证，导致未授权的 SQL 语句执行。

## 2. 分析逻辑

### 步骤 1：检查标记的汇聚点 `app/services/intent_engine.py:372`
阅读 `generate_sql` 函数：
```python
async def generate_sql(question, model, query_type="statistical_query"):
    if not model:
        return None, "未配置模型，无法生成 SQL"
    try:
        schema = _get_cached_enriched_schema()
        prompt = SQL_PROMPT.format(
            schema=schema,
            question=question,
            query_type=query_type
        )
        content = await _call_llm(...)
        ...
        return content, None
```
`question` 参数通过 `str.format()` 直接插入到 LLM 提示词中，未对提示词注入进行任何消毒或分隔处理。LLM 的输出（`content`）随后作为 SQL 字符串返回。这是间接注入路径的前半部分。

### 步骤 2：追踪从 HTTP 入口点到汇聚点的数据流
阅读 `app/controllers/chat.py` 以追溯 `question` 的来源：
```python
class ChatHandler(BaseHandler):
    @tornado.web.authenticated
    async def get(self):
        ...
        message = self.get_argument("message", "").strip()       # 第265行
        ...
        original_message = message                                  # 第294行
        ...
        if intent in ("database_query", "chart_request"):
            query_result = await execute_database_query(original_message, model)  # 第394行
```
`message` 是直接的 HTTP 查询参数（`self.get_argument`）。它仅经过 `.strip()` 处理后就作为 `original_message` 传给 `execute_database_query`，后者再调用 `generate_sql(question, model, query_type)`。用户可控的输入未经任何消毒直接到达 LLM 提示词。

### 步骤 3：检查 SQL 执行与验证
阅读 `app/models/data_query.py:248-275`：
```python
def execute_readonly_sql(sql):
    _validate_sql(sql)
    with get_connection() as conn:
        try:
            conn.execute("PRAGMA query_only = ON")
        except Exception:
            pass
        cursor = conn.execute(sql)   # 原始 SQL 字符串直接执行
```
来自 LLM 的 SQL 字符串直接传入 `conn.execute(sql)`，完全未使用参数化。唯一的防护是 `_validate_sql` 的正则检查以及尽力而为的 `PRAGMA query_only = ON`。

### 步骤 4：分析正则验证的绕过方式
阅读 `app/models/data_query.py:195-245`：
```python
def _validate_sql(sql):
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        raise DataQueryError("只允许执行 SELECT 查询")

    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", ...]
    for word in forbidden:
        if re.search(r'\b' + word + r'\b', sql_upper):
            raise DataQueryError(...)

    if ";" in sql:
        raise DataQueryError("禁止执行多条 SQL 语句")

    for table in re.findall(r'(?:FROM|JOIN)\s+(?:\(\s*)?(\w+)', sql_upper):
        if table.upper() in sql_keywords:
            continue
        if table.lower() not in allowed_lower:
            raise DataQueryError(f"不允许访问表: {table}")
```
表名白名单的正则 `r'(?:FROM|JOIN)\s+(?:\(\s*)?(\w+)'` 仅捕获未加引号的标识符（`\w+`）。在 SQLite 中，表名可以使用双引号（`"table_name"`）、方括号（`[table_name]`）或反引号（`` `table_name` ``）来引用。由于正则无法匹配带引号的标识符，攻击者可以通过提示词注入让 LLM 生成类似以下查询来完全绕过表名白名单：
```sql
SELECT * FROM "sqlite_master"
```
该查询以 `SELECT` 开头，不含禁止的关键词，没有分号，并且正则 `re.findall(r'(?:FROM|JOIN)\s+(?:\(\s*)?(\w+)', ...)` 根本不会匹配 `"sqlite_master"`，因此表名检查被静默绕过。同样的绕过方式也适用于数据库中的任何表。

### 步骤 5：验证 SAST 发现中关于注释/字符串字面量绕过的具体说法
SAST 描述称正则较弱，原因是“使用 SQL 注释绕过关键词过滤器，或在字符串字面量中嵌入破坏性命令”。然而，`app/models/data_query.py:216-218` 中的代码使用了：
```python
if re.search(r'\b' + word + r'\b', sql_upper):
```
该正则扫描**整个** SQL 字符串，包括注释和字符串字面量。它**不排除**这些部分。因此，嵌入在注释（`-- DELETE`）或字符串字面量（`'DELETE'`）中的关键词仍会被捕获。SAST 工具关于*绕过方式*的具体解释是**不准确的**；实际的绕过是通过**带引号的标识符**，正则从未匹配到它们。

### 步骤 6：检查代码上下文与可达性
端点 `ChatHandler.get()` 带有 `@tornado.web.authenticated` 装饰器，因此攻击需要已认证的用户。但是，任何已认证的用户都可以触发该漏洞。该代码是生产环境中的实际代码（`app/controllers/chat.py`），并非测试、演示或死代码。调用链完全可达：
`HTTP GET /chat?message=...` → `ChatHandler.get()` → `execute_database_query()` → `generate_sql()` → `_call_llm()` → `execute_readonly_sql()` → `conn.execute(sql)`。

### 步骤 7：检查框架与纵深防御保护
- `app/models/data_query.py:256` 中的 `PRAGMA query_only = ON` 被包装在一个裸的 `try/except: pass` 中，因此失败会被静默忽略。它只是纵深防御，不是可靠屏障。
- 在此路径中任何地方都没有使用参数化查询或预处理语句。
- 未设置提示词注入消毒器（例如，无分隔符转义，除 `.strip()` 外无输入长度限制）。

### 分析过程
- 问题 1：用户可控输入是否参与了 SQL 字符串的构建？→ **是**。来自 `self.get_argument` 的 `message` 流入 LLM 提示词，影响 LLM 生成的 SQL 并被执行（`app/controllers/chat.py:265` → `app/services/intent_engine.py:382` → `app/models/data_query.py:261`）。
- 问题 2：查询是否使用参数化？→ **否**。`conn.execute(sql)` 直接运行原始的 LLM 生成字符串，没有占位符（`app/models/data_query.py:261`）。
- 问题 3：数据路径上是否存在有效的输入验证？→ **否**。正则表达式表名白名单可以通过 SQLite 带引号的标识符（`"table_name"`、`[table_name]`、`` `table_name` ``）绕过，因为正则 `r'(?:FROM|JOIN)\s+(?:\(\s*)?(\w+)'` 只匹配未加引号的标识符（`app/models/data_query.py:239`）。
- 问题 4：代码是否处于测试/演示/死代码上下文中？→ **否**。它是生产环境中活跃的 `ChatHandler` 端点（`app/controllers/chat.py:249`）。
- 问题 5：框架是否自动进行参数化？→ **否**。应用程序使用原始的 `sqlite3.connect(...).execute(sql)` 执行动态构建的字符串（`app/models/data_query.py:261`）。
- → 结论：**真实漏洞**

## 3. 结论
**真实漏洞**

**关键证据：**
- 来自 `app/controllers/chat.py:265` 中 `self.get_argument("message", "")` 的用户输入在 `app/services/intent_engine.py:382` 处未经消毒即到达 LLM 提示词。
- LLM 生成的 SQL 在 `app/models/data_query.py:261` 处通过 `conn.execute(sql)` 直接执行，未使用参数化。
- `app/models/data_query.py:239` 处的表名白名单正则使用了 `\w+`，完全遗漏了 SQLite 的带引号标识符（`"..."`、`[...]`、`` `...` ``），使攻击者能够通过提示词注入绕过表名限制。
- `app/models/data_query.py:256` 处的 `PRAGMA query_only = ON` 是尽力而为的，失败时被静默忽略，因此不能可靠地阻止未授权的 SELECT 执行。

## 4. 修复建议
- **将基于正则的 SQL 验证器替换为真正的 SQL 解析器**（例如 `sqlparse`），生成 AST。验证 AST 以确保其是单个 `SELECT` 语句，并且每个表引用（包括带引号的标识符）都在允许的白名单中。
- **在将 `question` 嵌入 LLM 提示词之前添加提示词注入防御机制**。使用严格的分隔符或提示词注入防御框架（例如，将用户问题包裹在 XML 标签中，转义闭合标签，或应用专门的提示词注入防护）。
- **不要仅依赖 `PRAGMA query_only = ON`**。如果无法设置该 pragma，应将其作为硬错误处理。考虑以真正的只读模式打开 SQLite 连接（例如使用只读连接 URI 或单独的只读数据库副本）。
- **限制 LLM 使用定义良好的模式**，并使用 DTO（数据传输对象）绑定 LLM 输出，而不是直接执行原始 SQL 字符串。如果可能，使用 ORM 或查询构建器配合严格的白名单，而不是直接执行 LLM 的原始输出。
