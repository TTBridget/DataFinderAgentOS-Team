## 1. 总结

- **漏洞类型**：敏感数据泄露（信息泄露）
- **CWE**：CWE-312（敏感信息的明文存储）
- **标记位置**：`app/templates/admin/ai_model.html:370`
- **漏洞描述**：`ai_model.html` 模板通过 `json_encode(dict(model))` 将完整的 AI 模型对象（包含明文 `api_key`）嵌入前端。JavaScript 函数 `openEditModal()` 随后读取 `model.api_key` 并填充编辑表单。这会将敏感的第三方 API 凭证暴露给浏览器 DOM 中任何经过身份验证的管理员用户。此外，一个独立的 API 端点（`/api/models`）向任何经过身份验证的用户返回相同的未过滤模型数据，扩大了暴露面。

## 2. 分析逻辑

### 步骤 1：检查标记位置 `app/templates/admin/ai_model.html:370`

读取标记行附近的模板：

```html
<!-- app/templates/admin/ai_model.html:370 -->
<button class="btn-ghost" onclick='openEditModal({{ json_encode(dict(model)) }})'>
    <i class="layui-icon layui-icon-edit"></i> 设置
</button>
```

`model` 变量是来自 `models` 循环的 SQLite 行对象。`dict(model)` 将其转换为普通 Python 字典，`json_encode(...)` 将其序列化为 JSON 字符串，并直接插入 HTML 属性中。由于仓库查询使用了 `SELECT *`，字典中包含了 `api_key` 字段及其完整的明文值（例如 `sk-...`）。

**结论**：该位置是凭证确实暴露到客户端 HTML/JavaScript 的源头。

### 步骤 2：回溯数据源到后端处理器

读取 `app/controllers/admin.py:545-562`：

```python
class AiModelManageHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        search = self.get_argument("search", "")
        model_type = self.get_argument("model_type", "")
        result = AiModelRepository.get_all(page, 6, search, model_type)
        self.render("admin/ai_model.html", title="模型引擎",
                    models=result["items"],
                    ...)
```

处理器将 `result["items"]` 直接传递给模板，渲染前未进行字段过滤或掩码处理。

读取 `app/models/ai_model.py:8-32`：

```python
class AiModelRepository:
    @staticmethod
    def get_all(page=1, per_page=6, search="", model_type=""):
        # ...
        sql = f"SELECT * FROM ai_models {where_sql} ORDER BY is_default DESC, id DESC LIMIT ? OFFSET ?"
        rows = conn.execute(sql, params + [per_page, offset]).fetchall()
        return {"items": rows, "total": total}
```

仓库使用了 `SELECT *`，获取了包括明文 `api_key` 在内的所有列。行工厂是 `sqlite3.Row`，因此 `dict(row)` 保留了所有列。

**结论**：数据源是返回未掩码 API 密钥的原始数据库查询，中间层未过滤掉敏感字段。

### 步骤 3：检查是否存在清理函数、验证器或字段过滤器

搜索了整个代码库中可能在数据到达模板或 API 响应之前对 `api_key` 进行掩码或重新处理的函数，未找到此类函数。

搜索了类似 `mask`、`redact`、`api_key[:`、`api_key.replace`、`api_key[-4:]` 或 AI 模型的 DTO 类等模式，未找到。

**结论**：从数据库到前端的路径上没有清理函数或字段过滤器。

### 步骤 4：检查使用暴露密钥的 JavaScript 消费者

读取 `app/templates/admin/ai_model.html:598-607`：

```javascript
function openEditModal(modelStr){
    var $ = layui.jquery;
    var model = typeof modelStr === 'string' ? JSON.parse(modelStr) : modelStr;
    $('#action').val('edit');
    $('#modelId').val(model.id);
    $('#name').val(model.name);
    $('#provider').val(model.provider);
    $('#api_key').val(model.api_key);   // <-- 读取明文密钥
    $('#base_url').val(model.base_url);
    ...
}
```

JavaScript 显式读取 `model.api_key` 并将其写入 DOM 输入字段中。这意味着纯文本密钥同时存在于 HTML 源码和实时 DOM 中，任何 XSS 负载或浏览器扩展都可以访问。

**结论**：暴露的数据被客户端代码主动使用，确认此次泄露是功能性的且有意为之（尽管不安全）。

### 步骤 5：检查额外的暴露面（API 端点）

在调查调用者时，发现了 `app/controllers/chat.py:112-125`：

```python
class ModelListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        default_model = AiModelRepository.get_default_model()
        result = AiModelRepository.get_all(1, 1000, "")
        models = []
        for m in result["items"]:
            model_dict = dict(m)
            model_dict["is_default"] = bool(default_model and model_dict["id"] == default_model["id"])
            models.append(model_dict)
        self.write({"code": 0, "data": models})
```

该端点映射到 `app.py:39` 中的 `/api/models`。它仅受 `BaseHandler`（普通用户身份验证）保护，而非 `AdminBaseHandler`。它向**任何**经过身份验证的用户返回**相同**的 `dict(m)` 数据，包括 `api_key`——而不仅仅是管理员。

**结论**：存在第二个更广泛的暴露面，普通经过身份验证的用户通过简单的 GET 请求即可获取所有纯文本 API 密钥。

### 步骤 6：检查数据库静态存储加密

读取 `app/models/db.py:438-458`（`ai_models` 表的模式定义）：

```sql
CREATE TABLE IF NOT EXISTS ai_models(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    api_key TEXT,          -- 存储为纯文本 TEXT
    base_url TEXT,
    ...
)
```

列类型为 `TEXT`，未加密、哈希或掩码。仓库在创建/更新操作中也以明文形式存储密钥（`app/models/ai_model.py:48-82`）。

**结论**：API 密钥在静态存储时为明文，加剧了暴露风险。

### 步骤 7：检查代码上下文（测试/演示/废弃代码）

- 标记的模板是用于生产模型管理的活动管理 UI。
- `app/controllers/admin.py` 在 `app.py:54` 中活跃路由到 `/admin/ai`。
- `temp_handlers.py` 存在但**未在任何地方导入**，是死代码。活动处理器位于 `app/controllers/admin.py`。

**结论**：这是面向生产环境的活跃代码，而非测试或演示代码。

### 步骤 8：检查框架/调试配置

读取 `app.py:17-26`：

```python
settings = dict(
    template_path=...,
    static_path=...,
    cookie_secret= "datafinderagentos-token",
    login_url="/",
    xsrf_cookies=True,
    debug=True,          # 调试模式已启用
    autoreload=True
)
```

`debug=True` 存在，表示 Tornado 在出错时会返回堆栈跟踪。虽然这是一个额外的信息泄露问题，但并不否定主要发现：API 密钥在正常操作中**故意**被渲染到模板中，而非仅仅在错误处理期间出现。

**结论**：凭证泄露是一个有意的数据流程问题，而非偶然的错误消息泄漏。

### 分析过程（决策树遍历）

使用**信息泄露**决策树：

1. **敏感信息是否暴露给未授权用户/客户端？**
   → **是**。明文的 `api_key` 被嵌入管理页面的 HTML 响应中（`app/templates/admin/ai_model.html:370`），同时也被返回在 JSON API 响应中（`/api/models`，`app/controllers/chat.py:125`）。引用了步骤 1、2、4 和 5 的证据。

2. **应用程序是否处于生产模式并具有适当的错误处理？**
   → **否**（`app.py:24` 中为 `debug=True`）。即使处于生产模式，此泄露也并非错误信息泄漏，而是有意的模板数据流。因此此分支不会导向「误报」。

3. **是否仅为服务器版本/技术信息的泄露？**
   → **否**。这是完整的纯文本 API 凭证。

4. **代码是否处于测试/演示/废弃/生成上下文？**
   → **否**。活动处理器位于 `app/controllers/admin.py` 并在 `app.py` 中路由。

→ **到达叶子节点：真实漏洞**

## 3. 结论

**真实漏洞**

**关键证据：**
- `app/templates/admin/ai_model.html:370` 执行 `openEditModal({{ json_encode(dict(model)) }})`，将包括明文 `api_key` 在内的整个模型行序列化到 HTML/JS 上下文中。
- `app/templates/admin/ai_model.html:607` 读取 `model.api_key` 并将其写入 DOM 输入字段 `#api_key`，确认了客户端代码主动使用暴露的秘密。
- `app/controllers/chat.py:125` 通过 `/api/models` API 端点向任何经过身份验证的用户返回相同的未过滤 `dict(m)` 数据，将暴露范围扩大到管理员之外。
- `app/models/ai_model.py:26` 使用 `SELECT *` 获取所有列，而 `app/models/db.py:445` 将密钥存储在纯 `TEXT` 列中，不进行加密或掩码处理。

## 4. 修复建议

1. **在列表/模板视图中掩码或省略 `api_key`。**
   - 在管理模板中，显式构建一个安全的字典，排除 `api_key`（或将其掩码，例如 `sk-...xxxx`）。只将安全字典传递给 `json_encode()`。
   - 示例：`json_encode({k: v for k, v in dict(model).items() if k != 'api_key'})` 或传递一个类似 `api_key_masked` 的掩码字段。

2. **创建专用、授权的端点来获取完整密钥。**
   - 提供一个单独的 API 端点（例如 `GET /admin/api/models/{id}/api_key`），**仅当**管理员明确请求编辑时才返回明文密钥。强制执行 `AdminBaseHandler` 和额外的授权检查（例如基于角色的权限）。

3. **修复面向普通用户的 `/api/models` 端点。**
   - 在 `app/controllers/chat.py:112` 中，**不要**向普通用户返回 `api_key`。在序列化响应之前，构建一个安全字段的白名单（如 `id`、`name`、`provider`、`model_type` 等）。

4. **对静态存储的 API 密钥进行加密。**
   - 将 `api_key` 加密存储到数据库中（例如，使用 AES-256-GCM 以及来自环境变量或密钥管理器的密钥）。仅在需要发起上游 API 调用的后端服务中解密（`app/controllers/chat.py:603`）。

5. **在生产环境中禁用调试模式。**
   - 在 `app.py` 中将 `debug=False` 设置为（或使其基于环境变量），防止向客户端返回堆栈跟踪。

6. **修复后重新检查。**
   - 验证 `grep -n 'api_key' app/templates/admin/ai_model.html` 不再显示密钥被序列化到模板中。
   - 验证 `grep -n 'api_key' app/controllers/chat.py` 不再显示密钥出现在面向普通用户的 API 响应中。
   - 验证专用的密钥检索端点需要管理员身份验证和授权。
