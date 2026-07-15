# DataFinderAgentOS 测试用例规范

## 测试用例编写规范

### 测试文件命名规范
- 测试文件必须以 `test_` 前缀开头，如 `test_user_models.py`
- 测试文件放置在 `test/` 目录下

### 测试文件模板

```python
# test_example.py
import os
import sys
import time

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

if project_root not in sys.path:
	sys.path.insert(0, project_root)

# 导入需要测试的模块
from app.models.example import ExampleRepository
from app.models.db import init_db

# 初始化数据库
init_db()

def test_example():
	"""示例测试函数"""
	# 测试代码
	print("测试1：", ExampleRepository.method())

if __name__ == "__main__":
	test_example()
```

## 测试类型

### 1. 功能测试

功能测试验证功能是否按照预期工作。

#### 示例：用户模块功能测试

参考已有的 [test_user_models.py](file:///c:/Users/Wu/Desktop/shixun/day5/DataFinderAgentOS/test/test_user_models.py)

```python
import os
import sys
import time

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

if project_root not in sys.path:
	sys.path.insert(0, project_root)

from app.models.db import init_db
from app.models.user import UserRepository

init_db()

username = f"test_user_{int(time.time())}"
password = "test123456"

print("=== 用户模块测试 ===")
print("1. 测试创建用户：", UserRepository.create_user(username, password))  # 期望 True
print("2. 测试重复创建用户：", UserRepository.create_user(username, password))  # 期望 False
print("3. 测试正确密码验证：", UserRepository.verify_user(username, password))  # 期望 True
print("4. 测试错误密码验证：", UserRepository.verify_user(username, "wrongpass"))  # 期望 False
print("5. 测试不存在用户验证：", UserRepository.verify_user("notexist", password))  # 期望 False
```

### 2. 安全性测试

| 测试项 | 测试方法 | 预期结果 |
|--------|----------|----------|
| SQL 注入防护 | 传入包含 SQL 特殊字符的参数 | 不会发生注入，正常处理 |
| XSS 防护 | 传入包含 HTML/JS 标签的输入 | 输出被正确转义 |
| 密码存储 | 检查数据库中的密码字段 | 只存储哈希值，不存储明文 |
| 会话管理 | 测试 Cookie 安全性 | 使用 secure_cookie 机制 |

### 3. 边界条件测试

| 测试场景 | 输入 | 预期行为 |
|----------|------|----------|
| 空值输入 | username/password 为空 | 正确提示输入 |
| 超长输入 | 超过数据库字段限制 | 正确处理或提示 |
| 特殊字符输入 | 包含特殊字符的输入 | 正确转义处理 |

## 测试执行

### 运行单个测试文件

使用虚拟环境运行测试：

```powershell
# 激活虚拟环境
.\venv\Scripts\activate

# 运行测试
python test\test_user_models.py
```

## 测试用例清单

### 已完成测试
- [x] 用户模块基础功能测试
- [x] 用户注册/登录/登出功能验证
- [x] ChatGPT 风格前台主页渲染与交互验证
- [x] SSE 流式对话功能验证
- [x] @ 数字员工调度功能验证
- [x] @ 天气数字员工查询城市天气验证
- [x] API 类型数字员工数据卡片渲染验证（weather/json/table/html）
- [x] LLM 类型数字员工上传 `.nd` 文件补充 Prompt 验证
- [x] `.nd` 文件按员工独立目录存储在 `data/dgUser/{employee_id}/` 验证
- [x] 删除数字员工时同步清理其 `.nd` 文件目录验证
- [x] / 快捷指令菜单功能验证
- [x] 会话创建、切换、删除及历史记录加载验证
- [x] AI 意图识别功能验证（chat/database_query/chart_request/employee_call）
- [x] 数据库问数功能验证（自然语言查询返回安全 SQL 执行结果，不暴露 SQL）
- [x] Echarts 图表渲染验证（柱状图、饼图按 chart_request 意图调度生成）
- [x] 响应时间和 Token 数量展示验证
- [x] @天气中文天气描述验证
- [x] 用户侧模型请求 OpenAI API 范式 + SSE 流式响应验证

### 待开发测试
- [ ] 用户认证 Controller 单元测试
- [ ] 页面渲染自动化测试
- [ ] 安全性测试
- [ ] 边界条件测试
