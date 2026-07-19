# 数字员工模块技术文档

## 概述

数字员工模块是 DataFinderAgentOS 系统的核心功能之一，支持两种类型的数字化员工能力实现：
1. **LLM 类型**：基于大语言模型或 LLM + Crawl4ai 实现的数字化员工
2. **API 类型**：通过 HTTP/HTTPS API 接口实现的数字化员工

## 功能特性

### LLM 类型数字员工
- 基于模型引擎中的默认模型或手动指派的模型服务
- 支持 System Prompt 配置
- 支持上传一个或多个 `.nd` 文件，文件内容会在对话时自动补充到 System Prompt 中
- `.nd` 文件存储在 `data/dgUser/{employee_id}/` 目录下，每个数字员工拥有独立目录
- 支持 Skill 技能增强（可选）
- 支持 Crawl4ai 网页抓取组件（可选）
- 通过 @xxx 调度数字化员工参与或执行任务

### API 类型数字员工
- 通过 HTTP/HTTPS API 实现接口能力服务
- 支持多种请求方法：GET、POST、PUT、DELETE
- 支持自定义请求头（JSON 格式）
- 支持自定义请求参数（JSON 格式）
- 支持配置数据卡片类型 `card_type`，前台 @ 调用时自动渲染对应卡片
- 支持后台侧预览数据或卡片

## 工作场景

1. **深度采集任务**：如果指派了"采集专员"的数字化员工，则可以通过配置好的数字化员工实现自动获得指定数据
2. **天气查询**：用户在前台侧 @天气 成都，通过后台配置好的天气数字化员工实现天气卡片的渲染和数据呈现
3. **AI 问答任务**：通过 LLM 类型数字员工实现智能问答
4. **AI 智能问数**：通过数字员工内建 API 参与后台业务执行
5. **深度采集任务**：如果指派了"采集专员"的数字化员工，则可以通过配置好的数字化员工实现自动获得指定数据，并给出结果

## 默认数字员工

系统默认创建以下数字员工，并均在前台左侧"数字员工"工具栏提供快捷入口：

| 数字员工 | 类型 | 触发方式 | 说明 |
|---------|------|---------|------|
| 采集专员 | LLM | `@采集专员 <网页链接>` | 启用 crawl4ai 时自动提取 URL 进行瞭望采集并进一步深度采集，直接返回标题与正文 |
| 天气 | API | `@天气 城市名` | 调用 wttr.in 查询天气，渲染中文天气卡片 |
| 随机音乐 | API | `@随机音乐` | 内置 SoundHelix 示例曲库，返回可播放音乐卡片 |
| 新闻 | API | `@新闻` | 调用热点新闻接口，返回全国热点新闻卡片 |
| 文案写作助手 | LLM | `@文案写作助手 开始` | 按角色/约束/场景/模板流程交互写作 |
| 小智 | LLM | `@小智 你好` | 通用 AI 聊天助手 |

### 采集专员

系统默认创建一个名为"采集专员"的数字员工，用于深度采集任务：

| 属性 | 值 |
|------|-----|
| 名称 | 采集专员 |
| 类型 | LLM |
| 描述 | 负责深度采集任务的数字化员工，能够自动获取网页的详细内容 |
| 使用技能 | 否 |
| 使用 Crawl4ai | 是 |
| 排序 | 1 |

**System Prompt**：
```
你是一名专业的数据采集专员，负责从网页中提取详细内容。请按照以下步骤执行：1. 访问目标URL；2. 提取页面的完整正文内容；3. 提取页面中的关键数据和表格；4. 整理并返回结构化的数据。
```

**前台调用行为**：
1. 用户发送 `@采集专员 <网页链接>`（链接可夹杂在描述中，系统自动提取第一个 http/https URL）
2. 若未检测到 URL，助手会提示用户粘贴要采集的链接，不会调用模型引擎
3. 检测到 URL 后，先校验 URL 安全性（禁止内网/非 HTTP 协议），然后使用 crawl4ai 异步爬取页面
4. 爬取成功后：
   - 将结果作为"瞭望采集"数据保存到数据仓库
   - 创建并立即完成一条"深度采集"任务记录
   - 直接向用户返回标题、URL、正文字数与正文内容（前 3000 字符）
   - 同时推送一张采集结果数据卡片
5. 爬取失败时，直接向用户返回具体错误原因，不再走模型引擎生成兜底回复

**前端入口**：前台左侧"数字员工"工具栏点击 `@采集专员` 后，输入框会预填入 `@采集专员 https://`，用户只需把链接补全即可发送。

### 文案写作助手

系统默认创建一个名为"文案写作助手"的 LLM 类型数字员工，用于前台交互递进式专业文案写作：

| 属性 | 值 |
|------|-----|
| 名称 | 文案写作助手 |
| 类型 | LLM |
| 描述 | 专家级论文/专业文案写作助手 |
| 使用技能 | 否 |
| 使用 Crawl4ai | 否 |
| 排序 | 3 |

**交互流程**：
1. 用户输入 `@文案写作助手 开始`，助手提示输入核心关键词
2. 用户输入关键词，助手生成 10 个备选主题（固定 Markdown 模板）
3. 用户选择主题编号，助手生成三种差异化风格大纲：
   - 风格一：专业报告风（完整一二级章节大纲）
   - 风格二：小红书种草风（仅一级小标题）
   - 风格三：普通叙事风（完整编写思路与内容框架）
4. 用户选择风格后，助手严格依据选定大纲逐章节生成详细正文
5. 每生成完一个章节，助手等待用户输入 `确认继续` 或修改意见，全程逐章交互、分步完成全文撰写

**提示文件**：初始化数据库时，系统会按以下优先级查找文案写作助手的提示文件目录：
1. `temp/WriteToolsAgent/Docs/`
2. `docs/prompts/WriteToolsAgent/`
3. `temp/`

找到后将 `role.md`、`constraint.md`、`scene.md`、`template.md` 按顺序复制到 `data/dgUser/{employee_id}/`，并作为该员工的 System Prompt 补充注入到每次 @ 调用的对话上下文中。建议将提示文件统一维护在 `docs/prompts/WriteToolsAgent/` 下。

**前端入口**：前台左侧"数字员工"工具栏提供 `@文案写作助手 开始` 快捷入口，点击后自动填入输入框。

### 天气

系统默认创建一个名为"天气"的 API 类型数字员工，用于前台天气查询：

| 属性 | 值 |
|------|-----|
| 名称 | 天气 |
| 类型 | API |
| 描述 | 查询指定城市天气，输入 @天气 北京 即可获取天气信息 |
| API URL | `https://wttr.in/{query}` |
| 请求方法 | GET |
| 请求头 | `{"User-Agent": "curl/7.68.0"}` |
| 请求参数 | `{"format": "j1", "lang": "zh"}` |
| 卡片类型 | `weather` |
| 排序 | 2 |

**说明**：`{query}` 占位符会在调用时被替换为用户输入的城市名（如"北京"）。若用户只输入 `@天气` 未指定城市，则默认查询北京。请求参数使用 `format=j1` 以获取 JSON 数据，供前台渲染天气卡片。

## 数据库设计

### digital_employees 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| name | TEXT | 员工名称（唯一） |
| description | TEXT | 描述 |
| type | TEXT | 员工类型：'llm' 或 'api' |
| model_id | INTEGER | 关联模型 ID（LLM 类型） |
| system_prompt | TEXT | 系统提示词（LLM 类型） |
| use_skills | INTEGER | 是否启用技能（0/1，LLM 类型） |
| use_crawl4ai | INTEGER | 是否启用网页抓取（0/1，LLM 类型） |
| api_url | TEXT | API 地址（API 类型） |
| api_method | TEXT | 请求方法（API 类型，默认 GET） |
| api_headers | TEXT | 请求头（JSON，API 类型） |
| api_params | TEXT | 请求参数（JSON，API 类型） |
| card_type | TEXT | 数据卡片类型：weather、json、table、html，NULL 表示纯文本 |
| is_enabled | INTEGER | 是否启用（0/1，默认 1） |
| sort_order | INTEGER | 排序（默认 0） |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

## 后端实现

### 仓储层

**文件路径**：app/models/digital_employee.py

#### 数字员工文件工具函数

**文件路径**：app/models/digital_employee.py

| 函数 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| save_employee_nd_files | 保存上传的 `.nd` 文件到 `data/dgUser/{emp_id}/` | emp_id, file_list | 成功保存的文件名列表 |
| read_employee_nd_contents | 读取员工目录下所有 `.nd` 文件内容并拼接 | emp_id | 拼接后的字符串 |
| list_employee_nd_files | 列出员工目录下的 `.nd` 文件 | emp_id | 文件名列表 |
| delete_employee_dir | 删除员工文件目录（删除员工时调用） | emp_id | None |

#### DigitalEmployeeRepository 类

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| get_all | 获取数字员工列表（分页、搜索） | page, per_page, search_keyword | {"items": [], "total": int, "page": int, "per_page": int} |
| get_by_id | 根据 ID 获取数字员工 | emp_id | dict 或 None |
| create | 创建数字员工 | name, description, emp_type, model_id, system_prompt, use_skills, use_crawl4ai, api_url, api_method, api_headers, api_params, card_type, is_enabled, sort_order | 新记录 ID 或 None |
| update | 更新数字员工 | emp_id, 各字段可选参数 | True 或 False |
| delete | 删除数字员工及其文件目录 | emp_id | True |
| toggle_enabled | 启用/禁用数字员工 | emp_id, is_enabled | True |

### 控制器层

**文件路径**：app/controllers/admin.py

#### DigitalEmployeeManageHandler 类

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | /admin/digital | 渲染数字员工管理页面，支持分页和搜索 |
| POST | /admin/digital | 处理各类操作请求 |

#### POST 请求 action 参数

| action | 说明 | 所需参数 |
|--------|------|----------|
| add | 新增数字员工 | name, type, description, 及对应类型的配置参数 |
| edit | 编辑数字员工 | id, 及需要更新的字段 |
| delete | 删除数字员工 | id |
| toggle | 启用/禁用 | id, is_enabled |
| get_detail | 获取员工详情 | id |
| preview_api | 预览 API 数据 | id |

## 前端实现

**文件路径**：app/templates/admin/digital_employee.html

### 页面结构

1. **搜索区域**：支持按名称或描述搜索
2. **列表区域**：展示数字员工列表，包含 ID、名称、类型、描述、排序、状态、操作
3. **操作按钮**：新增、编辑、详情、预览（仅 API 类型）、启用/禁用、删除
4. **弹窗表单**：新增/编辑数字员工的表单，根据类型动态显示不同字段
5. **详情弹窗**：展示数字员工完整配置信息
6. **API 预览弹窗**：测试 API 类型员工的数据响应

### 类型切换

- 选择 LLM 类型时，显示模型选择、System Prompt、技能增强选项
- 选择 API 类型时，显示 API URL、请求方法、请求头、请求参数配置

## API 接口说明

### 获取数字员工列表

```
GET /admin/digital?page=1&search=xxx
```

### 新增数字员工

```
POST /admin/digital
Content-Type: multipart/form-data

action=add
name=xxx
type=llm|api
description=xxx
model_id=1 (LLM类型)
system_prompt=xxx (LLM类型)
nd_files[]=@xxx.nd (LLM类型，支持多个 .nd 文件)
use_skills=1 (LLM类型)
use_crawl4ai=1 (LLM类型)
api_url=xxx (API类型)
api_method=GET|POST|PUT|DELETE (API类型)
api_headers={"Content-Type": "application/json"} (API类型)
api_params={"key": "value"} (API类型)
card_type=weather|json|table|html (API类型，可选)
sort_order=0
```

**说明**：新增 LLM 类型数字员工时，可上传一个或多个 `.nd` 文件。文件保存到 `data/dgUser/{employee_id}/`，前台 @ 调用该员工时会自动将文件内容补充到 System Prompt。

### 编辑数字员工

```
POST /admin/digital
Content-Type: application/x-www-form-urlencoded

action=edit
id=1
name=xxx (可选)
type=llm|api (可选)
...其他字段（可选）
```

### 删除数字员工

```
POST /admin/digital
Content-Type: application/x-www-form-urlencoded

action=delete
id=1
```

### 启用/禁用数字员工

```
POST /admin/digital
Content-Type: application/x-www-form-urlencoded

action=toggle
id=1
is_enabled=1|0
```

### 获取员工详情

```
POST /admin/digital
Content-Type: application/x-www-form-urlencoded

action=get_detail
id=1
```

### API 预览

```
POST /admin/digital
Content-Type: application/x-www-form-urlencoded

action=preview_api
id=1
```

## 使用示例

### 创建 LLM 类型数字员工

```
POST /admin/digital
action=add
name=智能助手
type=llm
description=通用AI智能助手
model_id=1
system_prompt=你是一个专业的智能助手，帮助用户解答问题。
use_skills=1
use_crawl4ai=0
sort_order=1
```

### 创建 API 类型数字员工

```
POST /admin/digital
action=add
name=天气
type=api
description=查询指定城市天气，输入 @天气 北京 即可获取天气信息
api_url=https://wttr.in/{query}
api_method=GET
api_headers={"User-Agent": "curl/7.68.0"}
api_params={"format": "j1", "lang": "zh"}
card_type=weather
sort_order=2
```

## 扩展说明

### 技能系统（预留）

LLM 类型数字员工支持启用技能系统，技能可以扩展员工的能力范围，如：
- 数据查询技能
- 文件处理技能
- 数学计算技能

### Crawl4ai 集成（已启用）

LLM 类型数字员工可启用 Crawl4ai 网页抓取组件，用于从网页中提取数据，增强数据采集能力。典型应用场景为深度采集任务中的"采集专员"：

- 通过 `AsyncWebCrawler` 异步爬取目标 URL
- 使用 `PruningContentFilter` 过滤无关内容
- 生成 Markdown 格式正文，保留完整标题和正文
- 内容最多保留 8000 字符
- 爬取失败时自动回退到原始摘要内容

**环境要求**：
- crawl4ai >= 0.9.1
- playwright >= 1.61.0
- Chromium 浏览器驱动已安装

**验证命令**：
```bash
venv\Scripts\python.exe -c "import crawl4ai; print(crawl4ai.__version__)"
venv\Scripts\python.exe -m playwright install chromium
```

### 卡片渲染（已启用）

API 类型员工支持通过 `card_type` 字段配置数据卡片类型，前台在 `@xxx` 调用时根据返回数据自动渲染对应卡片：

| 卡片类型 | 说明 | 数据源要求 | 前台渲染效果 |
|---------|------|-----------|-------------|
| weather | 天气卡片 | wttr.in 等返回 JSON 格式天气数据 | 蓝色渐变卡片，展示城市、温度、天气图标、体感、湿度、风速、气压 |
| music | 音乐卡片 | 内置曲库或 API 返回音乐 URL | 红色渐变卡片，展示歌名/歌手，支持播放/暂停/换一首 |
| news | 新闻卡片 | 热点新闻 API | 浅色卡片，展示全国热点新闻列表，标题可跳转 |
| json | JSON 数据卡片 | 任意 JSON 响应 | 格式化高亮 JSON 文本 |
| table | 表格卡片 | JSON 数组 | 自动提取表头并生成表格 |
| html | HTML 卡片 | HTML 文本 | 直接渲染 HTML 内容 |
| NULL / 空 | 纯文本 | 任意 | 以普通文本流形式展示 |

**历史记录卡片持久化**：前台对话生成卡片时，服务端将 `card_type` 与 `card_data` 一并保存到 `chat_messages` 表；用户重新加载历史会话时，前端读取这些字段并重新渲染卡片，确保 `@天气` 等卡片在历史记录中不会失效。

配置方式：在新增/编辑 API 类型数字员工时，选择“卡片类型”下拉框即可。若接口返回 JSON 但希望以纯文本展示，选择“无（纯文本）”。