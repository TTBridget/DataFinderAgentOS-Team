## 1. 总结
- **漏洞类型**：SSRF (CWE-918)
- **标记位置**：`app/controllers/admin.py:1096`
- **漏洞描述**：`DigitalEmployeeManageHandler` 中的 `preview_api` 操作从数据库获取存储的员工记录，并向该记录中存储的 `api_url` 发起 HTTP 请求。`api_url` 值由经过身份验证的管理员在创建或编辑员工时提供，且未经验证即持久化存储，随后直接传递给 `requests` 库，未进行任何 URL 白名单、IP 黑名单或重定向限制。

## 2. 分析逻辑

### 步骤 1：检查标记的汇聚点（sink）`app/controllers/admin.py:1096`
```python
class DigitalEmployeeManageHandler(AdminBaseHandler):
    ...
    elif action == "preview_api":
        emp_id = int(self.get_body_argument("id", 0))
        employee = DigitalEmployeeRepository.get_by_id(emp_id)
        ...
        api_url = employee["api_url"]
        api_method = employee["api_method"] or "GET"
        api_headers = employee["api_headers"]
        api_params = employee["api_params"]
        ...
        if api_method.upper() == "GET":
            response = requests.get(api_url, headers=headers, params=params, timeout=10)
        elif api_method.upper() == "POST":
            response = requests.post(api_url, headers=headers, json=params, timeout=10)
        elif api_method.upper() == "PUT":
            response = requests.put(api_url, headers=headers, json=params, timeout=10)
        elif api_method.upper() == "DELETE":
            response = requests.delete(api_url, headers=headers, params=params, timeout=10)
```
该汇聚点直接调用了 `requests.get/post/put/delete(...)`，目标 URL 完全来自数据库记录（`employee["api_url"]`）。未进行白名单检查、IP 验证，也未禁用重定向（`allow_redirects` 默认为 `True`）。

### 步骤 2：通过员工创建/更新流程追溯 `api_url` 的来源
```python
# app/controllers/admin.py:989-1021 (add action)
elif action == "add":
    ...
    api_url = self.get_body_argument("api_url", None)
    ...
    emp_id = DigitalEmployeeRepository.create(
        ...
        api_url=api_url,
        ...
    )

# app/controllers/admin.py:1031-1065 (edit action)
elif action == "edit":
    ...
    api_url = self.get_body_argument("api_url", None)
    ...
    success = DigitalEmployeeRepository.update(
        ...
        api_url=api_url,
        ...
    )
```
`api_url` 直接来自 HTTP 请求体（`self.get_body_argument("api_url", None)`），未经任何修改即传递给存储库。中间没有任何验证、清理或白名单检查。

### 步骤 3：检查存储库和数据库层的验证情况
```python
# app/models/digital_employee.py:150-169 (create)
@staticmethod
def create(..., api_url=None, ...):
    ...
    conn.execute(
        """
        INSERT INTO digital_employees 
        (... , api_url, ...)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (... , api_url, ...)
    )

# app/models/digital_employee.py:171-236 (update)
@staticmethod
def update(..., api_url=None, ...):
    ...
    if api_url is not None:
        updates.append("api_url = ?")
        params.append(api_url)
    ...
```

```sql
-- app/models/db.py:376
api_url TEXT,
```
存储库和数据库模式均未对 `api_url` 进行任何验证。该列是一个无限制的 `TEXT` 字段，存储库直接将原始值插入其中。

### 步骤 4：检查端点的身份认证与访问控制
```python
# app/controllers/admin.py:964
class DigitalEmployeeManageHandler(AdminBaseHandler):
    ...
    @tornado.web.authenticated
    def post(self):
        ...
```
```python
# app/controllers/base.py:22-27
class AdminBaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        username = self.get_secure_cookie("admin_username")
        if not username:
            return None
        return username.decode("utf-8")
```
端点要求管理员身份验证（`@tornado.web.authenticated` + `AdminBaseHandler`）。虽然这限定了攻击面仅限于经过身份验证的管理员，但核心 SSRF 漏洞依然存在：能够以管理员身份认证的用户可以存储恶意 URL，并强制服务器向任意内部或外部目标发起请求。

### 步骤 5：搜索代码中是否存在 URL 白名单、IP 验证或 SSRF 库的使用
在应用程序源代码中进行全局搜索，查找 `urlparse`、`urlsplit`、`validate.*url`、`whitelist`、`allowlist` 和 `ssrf`，在 Python 应用程序代码中未发现相关结果。项目中没有 URL 验证工具、IP 黑名单逻辑，也未导入任何 SSRF 保护库。

### 步骤 6：检查 `requests` 调用的重定向和协议控制
`app/controllers/admin.py:1133-1139` 中的 `requests` 调用未传递 `allow_redirects=False`，因此默认情况下客户端会跟随重定向。这意味着攻击者可以提供指向内部地址的重定向 URL（例如通过白名单域名上的开放重定向），进一步增加了风险。

### 分析过程
- Q1：用户可控输入是否影响服务端请求的 URL/主机？→ **是**。经过身份验证的管理员通过 `add`/`edit` 操作设置 `api_url`（步骤 2），`preview_api` 随后读取存储的值并将其传递给 `requests`（步骤 1）。
- Q2：目标主机名/URL 是否经过白名单验证？→ **否**。在创建、更新或预览流程中均不存在任何验证（步骤 3）。
- Q3：解析后的 IP 是否经过内部/私有范围的检查？→ **否**。未发现任何 IP 黑名单或 DNS 固定逻辑（步骤 5）。
- Q4：是否仅路径/查询部分用户可控而主机硬编码？→ **否**。包括协议和主机在内的完整 URL 均被存储和使用（步骤 1）。
- Q5：代码是否处于测试/演示/已废弃/生产环境下？→ **否**。这是实际生产环境的 admin 控制器代码（步骤 4）。
- → 到达叶节点：**真实漏洞**

## 3. 结论
**真实漏洞**

**关键证据：**
- `app/controllers/admin.py:1111` 直接从数据库记录中读取 `api_url`，且未经验证即传递给 `requests`。
- `app/controllers/admin.py:999` 和 `app/controllers/admin.py:1042` 在创建和更新员工时从请求体中接收 `api_url`，并直接存储，未进行任何 URL 验证。
- `app/models/digital_employee.py:203-205` 和 `app/models/db.py:376` 确认数据库层将 `api_url` 存储为无限制的 `TEXT` 字段，未添加任何约束。
- `requests` 的调用使用了默认的 `allow_redirects=True` 行为，且代码库中不存在任何 SSRF 保护库或 IP 黑名单。

## 4. 修复建议
- **在存储时对 `api_url` 进行验证和白名单检查**：在保存新员工或更新员工之前，使用 `urllib.parse.urlparse()` 解析 URL，并强制实施允许的主机名白名单（或严格的前缀白名单）。拒绝不匹配的 URL。
- **在请求时进行验证**：在 `preview_api` 中，调用 `requests` 之前，立即使用相同的白名单重新验证 `api_url`。不要仅依赖存储时的验证。
- **禁用重定向**：为 `preview_api` 中的所有 `requests` 调用传递 `allow_redirects=False`，以防止基于重定向的绕过。
- **限制协议**：确保解析出的 URL 协议仅为 `http` 或 `https`。拒绝 `file://`、`gopher://`、`dict://` 等。
- **阻止私有/内部 IP**：解析主机名，并确保得到的 IP 不在私有范围（`127.0.0.0/8`、`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`、`169.254.169.254/32` 等）内，再发起请求。使用 `ipaddress` 模块进行检查。
- **将相同的修复应用到 `chat.py`**：`app/controllers/chat.py:464-505` 在聊天中调用 API 类型员工时，通过 `AsyncHTTPClient` 执行了类似的存储型 SSRF；它也应获得相同的 URL/IP 验证和重定向控制。
- **考虑使用专门的 SSRF 保护库**（例如 `ssrf-req-filter` 或类似库），如果项目规模超出少数自定义检查的范围。
