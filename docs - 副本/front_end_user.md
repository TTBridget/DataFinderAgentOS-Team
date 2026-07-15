# 用户侧-前台用户系统技术文档

## 概述

用户侧-前台用户系统是 DataFinderAgentOS 中面向终端用户的交互入口，采用 ChatGPT / 豆包风格的沉浸式对话界面，提供用户注册、登录、智能问答、数字员工调度、会话管理等功能。

## 功能特性

### 1. 用户认证

- **登录**：已注册用户使用用户名和密码登录，验证通过后设置安全 Cookie
- **注册**：新用户填写用户名、密码、确认密码，字段与后台用户管理保持一致
- **自动登录**：注册成功后自动写入登录态并跳转至首页
- **登出**：清除 Cookie 会话并返回登录页

### 2. 对话主页布局

页面采用左右分区设计：

- **A 区（LOGO 区）**：系统 LOGO + 标题“智能瞭望与问数”
- **B 区（模型切换区）**：下拉选择当前使用的 AI 模型，默认选中后台模型引擎的默认模型
- **C 区（任务列表区）**：历史会话列表，根据首条用户消息自动生成标题，点击可查看历史记录
- **D 区（对话区）**：聊天气泡形式，左侧 AI 消息，右侧用户消息
- **E 区（输入区）**：多行输入框 + 发送按钮，支持 Enter 发送、Shift+Enter 换行

### 3. 模型切换

- 页面初始化时通过 `/api/models` 加载后台模型引擎中所有可用模型
- 默认使用后台设置的默认模型服务
- 切换模型后，新消息将使用所选模型
- 加载历史会话时，模型选择区会自动同步为该会话最后使用的模型

### 4. 会话管理

- **自动创建**：发送首条消息时自动创建新会话，标题取自首条消息前 20 个字符
- **历史查看**：点击左侧任务列表标题加载完整历史消息
- **删除会话**：悬停（桌面端）或长按/常驻（移动端）显示删除按钮
- **新建会话**：点击“新对话”清空当前会话并回到空状态

### 5. SSE 流式对话

- 使用 Server-Sent Events 与后端 `/api/chat` 建立流式连接
- AI 回复以打字效果逐字呈现
- 支持 `[DONE]` 和 `done` 事件标识回复结束
- 错误时显示友好提示并自动重置输入状态
- **响应元信息**：每条 AI 消息下方显示本次响应的耗时（秒）和 Token 估算数量，便于用户感知模型性能

### 6. AI 意图识别与数据库问数

系统在非 `@数字员工` 场景下会自动识别用户意图，并调度正确的处理路径：

- **chat**：普通闲聊/问答，直接走大模型对话
- **database_query**：用户希望查询、统计数据（如“数据仓库有多少条数据”）
- **chart_request**：用户希望看到可视化图表（如“用柱状图展示各来源数据量”）
- **employee_call**：用户通过 `@员工名` 调用数字员工

识别方式采用“规则兜底 + LLM 判定”的混合策略：先匹配常见关键词，若无法确定则调用后台配置的 LLM 进行意图分类。

当意图为 `database_query` 或 `chart_request` 时，系统会：

1. 根据用户问题生成安全的 SQLite SELECT 语句
2. 通过白名单表限制、SQL 语法校验、只读执行环境等多重防护执行查询
3. 将查询结果以表格文本形式返回（**不暴露真实 SQL**）
4. 若意图为 `chart_request`，再生成 Echarts 图表配置并推送图表事件，前端自动渲染柱状图/折线图/饼图

**安全限制**：

- 仅允许查询白名单中的只读表（data_warehouse、deep_collected_data、collected_data、ai_models、digital_employees）
- 禁止执行 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE 等写入操作
- 禁止多语句和未授权表访问
- 不接收用户直接输入 SQL，避免 SQL 注入
- 不接收用户提示词注入，意图识别和 SQL 生成都由系统控制

### 7. 数据报表（Echarts）可视化

当意图识别为 `chart_request` 时，服务端会根据查询结果生成图表配置，并通过 SSE 推送 `type=chart` 事件。前端基于 Echarts 5.x 动态渲染：

- **bar（柱状图）**：适用于分类数值比较，如各来源数据量统计
- **line（折线图）**：适用于时间序列趋势展示
- **pie（饼图）**：适用于占比/分类汇总展示

图表与文本回复一起展示在 AI 消息气泡内，支持窗口自适应缩放。

### 8. @ 数字员工调度

- 在输入框中输入 `@` 激活数字员工选择菜单
- 菜单列出后台已启用的数字员工，**显示与交互均使用后台配置的员工名称**
- 支持方向键选择、Enter 确认、Esc 关闭
- 发送消息后，后端解析 `@员工名` 指令并调用对应员工
- **模型优先级**：优先使用数字员工自身配置的模型；若未配置，则回退到系统默认模型
- 支持 LLM 类型员工（System Prompt + 模型）和 API 类型员工（HTTP 接口调用）
- **典型员工**：
  - `@采集专员`：调用 crawl4ai 进行网页深度采集
  - `@天气`：调用 wttr.in API 查询指定城市天气（如 `@天气 北京`），天气描述已翻译为中文
- **数据卡片渲染**：API 类型员工若配置了 `card_type`，服务端会在 SSE 流中推送 `type=card` 事件，前端自动调用 `renderCard()` 渲染为对应卡片，与文本回复一起展示

### 9. / 快捷功能

- 输入 `/` 激活快捷指令菜单
- 内置示例指令：
  - `/help` - 查看帮助信息
  - `/new` - 开始新对话
  - `/clear` - 清空当前对话展示
  - `/weather` - 自动填入 `@天气 北京` 进行天气查询

### 10. 数据卡片渲染

当前台通过 `@xxx` 调用 API 类型数字员工，且该员工配置了 `card_type` 字段时，服务端会在 SSE 流中额外推送 `type=card` 事件，前端据此渲染数据卡片：

- **weather**：解析 wttr.in JSON 响应，渲染蓝色渐变天气卡片，包含城市、实时温度、天气图标、体感温度、湿度、风速、气压、能见度等，天气描述已翻译为中文
- **json**：将接口返回的 JSON 数据格式化展示
- **table**：将 JSON 数组渲染为 HTML 表格
- **html**：直接渲染接口返回的 HTML 片段
- **无/空**：不渲染卡片，仅展示文本回复

**实现文件**：`app/templates/index.html` 中定义了 `renderCard`、`renderWeatherCard`、`renderJsonCard`、`renderTableCard`、`appendCardToMessage`、`appendChartToMessage`、`initEChart` 等函数，并在 SSE `onmessage` 中监听 `type=card`、`type=chart`、`type=meta` 等事件。

## 数据库设计

### chat_sessions 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| user_id | INTEGER | 所属用户 ID |
| title | TEXT | 会话标题 |
| model_id | INTEGER | 当前使用的模型 ID |
| employee_id | INTEGER | 当前关联的数字员工 ID |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

### chat_messages 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| session_id | INTEGER | 所属会话 ID |
| role | TEXT | 消息角色：user / assistant |
| content | TEXT | 消息内容 |
| model_id | INTEGER | 生成该消息使用的模型 ID |
| employee_id | INTEGER | 生成该消息使用的数字员工 ID |
| response_time | REAL | 响应耗时（秒）|
| token_count | INTEGER | Token 估算数量 |
| created_at | TEXT | 创建时间 |

## 接口说明

| 接口 | 方法 | 说明 |
|------|------|------|
| `/login` | GET/POST | 用户登录 |
| `/register` | GET/POST | 用户注册 |
| `/logout` | GET/POST | 用户登出 |
| `/index` | GET | 前台首页（需登录） |
| `/api/models` | GET | 获取可用模型列表 |
| `/api/employees` | GET | 获取已启用的数字员工列表 |
| `/api/chat/sessions` | GET | 获取当前用户会话列表 |
| `/api/chat/sessions` | POST | 创建/更新/删除会话 |
| `/api/chat/messages` | GET | 获取指定会话的消息历史 |
| `/api/chat` | GET (SSE) | 流式对话接口 |

## 文件结构

| 文件 | 说明 |
|------|------|
| `app/controllers/auth.py` | 登录、注册、登出控制器 |
| `app/controllers/home.py` | 前台首页控制器 |
| `app/controllers/chat.py` | 对话、会话、模型、数字员工调度、意图识别、数据库问数、图表推送控制器 |
| `app/models/chat.py` | 对话会话与消息仓储 |
| `app/models/data_query.py` | 安全数据库查询执行器（白名单、只读、SQL 校验）|
| `app/services/intent_engine.py` | 意图识别、安全 SQL 生成、图表配置生成服务 |
| `app/templates/login.html` | 登录页面 |
| `app/templates/register.html` | 注册页面 |
| `app/templates/index.html` | 前台对话主页 |

## 设计约束

- 风格：浅色系、扁平化、企业化/政务行业风格、简约高级感
- 响应式：适配桌面端与移动端，移动端使用抽屉式侧边栏
- 沉浸式：页面占满视口，去除多余边距
- 安全：所有前台 API 均需登录认证，密码使用 PBKDF2 + Salt 哈希存储

## 使用说明

1. 访问 `http://localhost:10010/` 进入登录页
2. 若无账号，点击“立即注册”完成注册
3. 登录后进入首页，可直接输入消息与 AI 对话
4. 输入 `@` 调用数字员工，例如 `@采集专员 帮我采集这篇文章：https://example.com`、`@天气 北京`
5. 输入 `/` 查看快捷指令（如 `/weather` 快速查询天气）
6. 左侧任务列表可查看、切换、删除历史会话
7. 直接输入统计/查询类问题可与数据库对话，例如“数据仓库有多少条数据”
8. 输入图表类问题可自动生成可视化报表，例如“用柱状图展示各来源数据量”“用饼图展示各来源数据量”
