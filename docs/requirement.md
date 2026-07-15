# DataFinderAgentOS 项目需求跟踪

## 项目概述

DataFinderAgentOS 是一款政务智能瞭望与智能问数系统，基于 Tornado Web 框架开发，是一个 B/S 结构的数据智能采集和数据智能问数系统，分为用户侧（前台）和管理侧（后台）两个部分。

## 当前状态

### 已实现功能
1. **用户认证系统**
   - 用户登录（LoginHandler）
   - 用户登出（LogoutHandler）
   - 密码安全存储（salt + pbkdf2_hmac 哈希）
   - 基于 Cookie 的会话管理

2. **基础页面**
   - 登录页面（login.html）
   - 首页（index.html，需要认证）
   - 基础模板（base.html）

3. **数据层**
   - SQLite3 数据库初始化
   - users 表结构
   - UserRepository 仓储类

4. **管理侧后台系统（v0.1 发布）
   - **用户管理**：用户/管理员的增删改查、禁用、搜索、分页
   - **角色管理**：角色的增删改查、系统角色保护、功能权限分配（Layui树形联动）
   - **功能管理**：功能模块管理、启用禁用、二级功能结构
   - **菜单管理**：菜单排序、可见性配置
   - 完整的数据库表结构（roles、functions、role_functions、menus、admins（更新）、users（更新）
   - **仓储层**：RoleRepository、FunctionRepository、MenuRepository
   - **控制器**：UserManageHandler、RoleManageHandler、FunctionManageHandler、MenuManageHandler
   - **模板层**：admin/user.html、admin/role.html、admin/function.html、admin/menu.html

5. **任务3：瞭望管理系统（v0.1 新增）
   - **瞭望中心**：垂直布局三个区域（A区搜索采集、B区瞭源选择、C区采集结果），橱窗模式显示，1行3列，1页12条
   - **瞭源管理**：采集源管理，支持添加/删除/修改/分页，百度新闻默认数据源预置
   - **瞭望采集**：基于 RequestHeaders 模拟请求，BeautifulSoup 解析百度新闻
   - **数据仓库**：已并入瞭望中心，C区结果允许全选/多选并保存到数据仓库，支持查看、删除、分页、搜索、深度采集
   - **仓储层**：DataSourceRepository、CollectedDataRepository、DataWarehouseRepository
   - **控制器**：DataSourceManageHandler、WatchManageHandler、DataWarehouseManageHandler
   - **模板层**：admin/data_source.html、admin/watch.html、admin/data_warehouse.html
   - **数据库表**：data_sources、collected_data、data_warehouse（初始化时自动创建百度新闻数据源）

6. **任务4：模型引擎（v0.1 新增）
   - **模型管理**：支持 OPENAI API 范式的模型接入和管理（新增、删除、修改、查询）
   - **列表展示**：炫酷沉浸式风格，橱窗列表式（1行2列，1页6条），可视化 Token 统计
   - **模型配置**：支持设置系统提示词、top_p、上下文大小、最大 token、温度等
   - **模型分类**：支持文本、图像、音频、视频、多模态、嵌入等多种主流类型
   - **模型调用**：支持设置默认模型供业务调用
   - **模型对话**：使用 SSE (Server-Sent Events) 协议实现流式对话测试
   - **仓储层**：AiModelRepository
   - **控制器**：AiModelManageHandler、AiModelChatHandler
   - **模板层**：admin/ai_model.html
   - **数据库表**：ai_models

7. **任务3.2：数据仓库（v0.1 新增）**
   - **归属调整**：数据仓库已从“数据管理”菜单并入“瞭望中心”，作为瞭望中心的子功能
   - **瞭望中心集成**：C区结果允许全选/多选，并提供“保存到数据仓库”功能
   - **数据仓库管理**：列表显示通过瞭望采集保存的数据，支持查看、删除、分页、搜索
   - **数据存储策略**：基于 url 唯一性，同数据再次保存时更新，不同则新增（INSERT OR REPLACE）
   - **深度采集标识**：列表中有“是/否”标识，并预留了悬浮窗任务面板及查看面板
   - **仓储层**：DataWarehouseRepository
   - **控制器**：DataWarehouseManageHandler
   - **模板层**：admin/data_warehouse.html
   - **数据库表**：data_warehouse

8. **任务5：数字员工（v0.1 新增）**
   - **员工类型**：支持 LLM 员工和 API 员工两种类型
   - **LLM 员工**：支持选择模型、配置 System Prompt、上传 `.nd` 文件补充 Prompt、启用技能和网页抓取功能（Crawl4ai）
   - **API 员工**：支持配置 API URL、请求方法（GET/POST/PUT/DELETE）、请求头（JSON）和请求参数（JSON）
   - **数据卡片**：API 类型员工支持配置 `card_type`（weather/json/table/html），前台 @ 调用时自动渲染对应数据卡片
   - **.nd 文件管理**：LLM 类型员工新增/编辑时支持上传一个或多个 `.nd` 文件，文件按员工 ID 独立存储在 `data/dgUser/{employee_id}/`，前台 @ 调用时自动将文件内容补充到 System Prompt
   - **管理功能**：完整的增删改查、分页、搜索、启用/禁用状态管理
   - **详情查看**：支持查看数字员工完整配置信息及已上传的 `.nd` 文件列表
   - **API 预览**：支持对 API 类型员工进行数据预览测试
   - **使用场景**：支持 @xxx 调度数字员工参与任务，如深度采集任务指派"采集专员"、天气查询等
   - **仓储层**：DigitalEmployeeRepository
   - **控制器**：DigitalEmployeeManageHandler（包含 get_detail、preview_api 接口）
   - **模板层**：admin/digital_employee.html
   - **数据库表**：digital_employees

9. **任务6：用户侧-前台用户系统（v0.1 新增，已扩展）**
   - **用户登录注册**：前台用户注册、登录、登出，字段与后台用户管理一致，注册后自动登录
   - **ChatGPT 风格主页**：左右布局（A 区 LOGO + B 区模型切换 + C 区任务列表；D 区对话区 + E 区输入区），浅色系、扁平化、响应式设计
   - **模型切换**：默认使用后台模型引擎默认模型，支持切换其他可用模型
   - **对话会话**：根据首条消息自动生成任务标题，支持新建、切换、删除、置顶、重命名会话及历史记录查看
   - **SSE 流式对话**：基于 Server-Sent Events 实现 AI 回复的实时打字效果；用户侧模型请求严格遵循 OpenAI API 范式（`/chat/completions` + `stream=true` + 解析 `delta.content`）
   - **响应元信息展示**：每条 AI 消息下方显示响应时间（秒）和 Token 估算数量
   - **AI 意图识别**：支持 `chat`/`database_query`/`chart_request`/`employee_call` 四种意图，采用规则兜底 + LLM 判定的混合策略；`database_query` 进一步细分为统计、趋势、排名、来源、关联、内容检索、事实查询、概览等二级意图
   - **数据库问数**：用户可直接通过自然语言查询后台采集数据（优先 `data_warehouse`，深度采集结合 `deep_collected_data`，原始采集 fallback 到 `collected_data`）；系统生成安全 SQL 并返回结果，不暴露真实 SQL，不接收用户输入 SQL
   - **智能分析解读**：对查询结果进行自然语言分析，简单结果优先本地格式化（减少 LLM 调用），复杂分析走模型生成结论
   - **数据报表可视化**：当意图为 `chart_request` 时，基于 Echarts 动态渲染柱状图/折线图/饼图/散点图
   - **@ 数字员工**：输入 `@` 可调出后台启用的数字员工（显示与交互均使用员工名称），默认已启用 @天气、@随机音乐、@新闻、@文案写作助手、@小智、@采集专员；优先使用员工配置的模型，否则回退到系统默认模型
   - **数据卡片渲染**：API 类型数字员工若配置了 `card_type`，前台将自动渲染对应卡片（weather/music/news/json/table/html），例如 `@天气 北京` 渲染中文天气卡片、`@随机音乐` 渲染红色音乐卡片、`@新闻` 渲染浅色新闻卡片
   - **/ 快捷功能**：输入 `/` 激活快捷指令菜单（help、new、clear、weather 等示例）
   - **对话导出 PDF**：对话区右上角提供导出按钮，可将当前会话导出为 PDF 文件
   - **暂停与编辑重发**：AI 生成过程中可暂停；用户可编辑已发送消息并重新发送，AI 基于新内容重新思考回复
   - **仓储层**：ChatSessionRepository、ChatMessageRepository
   - **控制器**：auth.py（LoginHandler/RegisterHandler/LogoutHandler）、chat.py（ChatHandler/ChatSessionHandler/ChatMessageHandler/ChatResendHandler/ChatExportHandler/ModelListHandler/EmployeeListHandler）、home.py（IndexHandler）
   - **服务层**：intent_engine.py（意图识别、SQL 生成、图表配置生成）
   - **模板层**：login.html、register.html、index.html
   - **数据库表**：chat_sessions（含 `is_pinned`）、chat_messages（含 `is_edited`、`response_time`、`token_count`）

10. **任务6.5：数智大屏（v0.1 新增）**
    - **核心数字展示**：仓库总数、数据源总数、用户总数、深度采集条数，数据来源于系统真实数据库（data_warehouse、data_sources、users、admins 表）
    - **3D 地球可视化**：使用 ECharts-GL 渲染交互式 3D 地球，展示全球数据节点及连线动画
    - **关键词云**：根据数据仓库中 keyword 字段的频率统计生成词云，使用 ECharts-Wordcloud 插件
    - **采集趋势与预测**：按日期统计数据仓库更新量，展示采集趋势曲线，并基于最近 7 天均值预测下一天数据量
    - **数据源分布**：环形图展示各数据源在数据仓库中的数据占比
    - **数据仓库状态**：柱状图展示已深度采集与未深度采集的数据量对比
    - **数字员工统计**：仪表盘展示数字员工启用率，以及各类型员工分布
    - **数据更新规则**：页面加载时立即请求数据，之后每隔 30 秒自动刷新；数字采用平滑动画过渡，避免闪烁
    - **加载状态**：数据返回前显示 shimmer 加载占位效果，不显示 0 或空白
    - **企业风格设计**：深色主题、渐变背景、毛玻璃效果、响应式布局
    - **控制器**：DashboardHandler、DashboardDataHandler（`app/controllers/dashboard.py`）
    - **模板层**：`app/templates/admin/dashboard.html`（独立页面，不继承 base.html）
    - **路由配置**：`/admin/dashboard`、`/admin/dashboard/data?action=xxx`

## 需求跟踪

### 用户侧-前台功能需求
| 功能模块 | 子功能 | 状态 | 优先级 | 说明 |
|---------|-------|------|--------|------|
| 用户认证 | 用户登录 | 已完成 | 高 | 已实现基本登录功能 |
| 用户认证 | 用户注册 | 已完成 | 高 | 注册字段与后台用户管理一致，注册成功后自动登录 |
| 智能问数 | 用户对话 | 已完成 | 高 | 通过 SSE 流式对话与 AI 交互，类似 ChatGPT 的智能应用 |
| 智能问数 | AI 意图识别 | 已完成 | 高 | 支持 chat/database_query/chart_request/employee_call 四种意图 |
| 智能问数 | 数据统计分析 | 已完成 | 高 | 通过自然语言查询后台采集数据，支持统计/趋势/排名/来源/关联/内容检索等多场景，安全 SQL 执行，不暴露真实 SQL |
| 智能问数 | 智能分析解读 | 已完成 | 高 | 对查询结果进行自然语言分析，简单结果本地格式化，复杂结果由模型生成结论 |
| 智能问数 | 图形图像报表 | 已完成 | 高 | 基于 Echarts 动态渲染柱状图/折线图/饼图/散点图，按意图调度生成 |
| 数字员工 | 员工调度 | 已完成 | 高 | 输入 `@` 可调出后台启用的数字员工，支持任意已配置员工（如 @采集专员） |
| 数字员工 | @天气 | 已完成 | 中 | 默认配置 API 类型"天气"员工，调用 wttr.in 查询天气，前端输入 @天气 城市名 即可调用，渲染中文天气卡片 |
| 数字员工 | @随机音乐 | 已完成 | 中 | 默认 API 类型"随机音乐"员工，返回红色系音乐卡片，支持在线播放/暂停/换一首 |
| 数字员工 | @新闻 | 已完成 | 中 | 默认 API 类型"新闻"员工，调用 vvhan 热点新闻接口返回 10 条全国热点新闻，浅色卡片展示 |
| 数字员工 | @文案写作助手 | 已完成 | 中 | 默认 LLM 类型"文案写作助手"员工，引入 temp/WriteToolsAgent/Docs 提示文件，严格按角色/约束/场景/模板流程交互写作 |
| 数字员工 | @小智 | 已完成 | 中 | 默认 LLM 类型"小智"员工，支持通用 AI 聊天对话 |
| 数字员工 | @采集专员 | 已完成 | 中 | 默认 LLM 类型"采集专员"员工，支持 @采集专员 进行深度采集任务，可生成表格/报表呈现 |
| 报表功能 | 报表呈现 | 已完成 | 中 | 前台"报表呈现"入口 + chart_request 意图自动生成 Echarts 图表 |
| 报表功能 | 报表查看 | 待开发 | 中 | 查看生成的报表 |
| 历史记录 | 任务列表 | 已完成 | 中 | 左侧"历史任务"列表支持新建/切换/删除/置顶/重命名会话 |
| 历史记录 | 对话历史 | 已完成 | 中 | 左侧任务列表点击可查看历史对话记录 |
| 报告导出 | 对话导出 PDF | 已完成 | 中 | 对话区右上角"导出"按钮，将当前会话内容导出为 PDF 文件并保存 |
| 对话交互 | 暂停生成 | 已完成 | 中 | AI 生成过程中可随时点击"暂停生成"按钮停止当前输出 |
| 对话交互 | 编辑重发 | 已完成 | 中 | 用户可编辑已发送的用户消息并重新发送，AI 基于新内容重新思考回复 |
| 其他 | 用户登出 | 已完成 | 中 | 已实现登出功能 |
| 其他 | 模型切换 | 已完成 | 高 | 左侧模型下拉框实时切换当前会话使用的模型 |
| 其他 | 首页展示 | 已完成 | 高 | ChatGPT 风格主页，支持响应式侧边栏（默认折叠/点击展开/栏目记忆）、模型切换、会话管理和快捷输入 |

### 管理侧-后台功能需求
| 功能模块 | 状态 | 优先级 | 说明 |
|---------|------|--------|------|
| 用户管理 | 已完成 | 高 | 用户/管理员的增删改查、禁用、搜索、分页 |
| 角色管理 | 已完成 | 高 | 角色的增删改查、系统角色保护、功能权限分配（Layui树形联动） |
| 功能管理 | 已完成 | 高 | 系统功能模块的管理、二级功能结构、启用禁用 |
| 菜单管理 | 已完成 | 高 | 菜单排序、可见性配置 |
| 瞭望中心 | 已完成 | 高 | A/B/C垂直布局，数据采集，结果橱窗展示。C区支持多选并保存至数据仓库 |
| 瞭源管理 | 已完成 | 高 | 采集源管理，RequestHeaders配置，百度新闻数据源预置 |
| 数据仓库 | 已完成 | 高 | 保存并管理瞭望采集到的数据，支持列表/搜索/删除/深度采集（含任务面板、进度、步骤、日志、结果）、批量采集、更新采集 |
| 数字员工 | 已完成 | 高 | 支持两种员工类型（LLM 和 API），完整的管理功能及预留扩展 |
| 模型引擎 | 已完成 | 高 | AI 模型引擎的管理和配置，支持OpenAI API范式、SSE流式对话测试 |
| 数智大屏 | 已完成 | 高 | 采集数据及系统运营的数据化呈现，包含3D地球、词云、采集趋势预测、数据源分布、仓库状态、数字员工统计等可视化图表 |

## 瞭望管理系统说明

### 功能说明

1. **瞭望管理（/admin/watch）
   - **A区**：搜索区，输入关键词，点击采集按钮发起数据采集
   - **B区**：瞭源列表，支持多选，默认勾选所有可用的瞭源
   - **C区**：采集结果，橱窗模式，1行3列，1页12条，显示标题、来源、时间、摘要和原文链接

2. **瞭源管理（/admin/data_source）
   - 管理采集源，包含名称、描述、Base URL、路径模板、Headers（JSON）、状态、排序
   - 默认预置百度新闻数据源
   - 路径模板支持 {keyword}（关键词）、{page}（分页步长）占位符
   - Headers 配置模拟真实浏览器请求

3. **百度新闻数据源配置
   - Base URL: `https://www.baidu.com`
   - 路径模板: `/s?rtt=1&bsst=1&cl=2&tn=news&rsv_dl=ns_pc&word={keyword}&pn={page}`
   - 分页步长: `page*10`（0: 第一页，10: 第二页，20: 第三页...）

### 技术实现
- **网络请求**：requests 库
- **HTML解析**：BeautifulSoup4 + lxml
- **数据库**：SQLite3（data_sources、collected_data 表）
- **分页**：每页 20 条（瞭源管理），每页 12 条（采集结果）
- **前端**：Layui 框架（卡片、分页、表单、弹窗组件）

## 任务 6.4 智能问数验证用例

### 验证场景

| 问题示例 | 预期意图 | 预期分析/结果 | 验证状态 |
|---------|---------|--------------|---------|
| 数据仓库里有多少条数据？ | statistical_query | 返回总数并给出统计结论 | 已通过 |
| 按来源统计各有多少条数据？ | source_query | 按来源分组统计并展示分布 | 已通过 |
| 深度采集的数据有多少条？ | statistical_query | 返回 deep_collected_data 总数 | 已通过 |
| 数据按日期分布的趋势如何？ | trend_query | 按日期分组统计趋势 | 已通过 |
| 来源数量排名前3的是哪些？ | ranking_query | 返回 Top3 来源及数量 | 已通过 |
| 每个关键词下各来源的分布情况？ | source_query / correlation_query | 多字段交叉分组统计 | 已通过 |
| 标题包含高温的数据有哪些？ | content_query | 返回标题、URL、来源等精简字段 | 已通过 |
| 深度采集文章的平均字数是多少？ | statistical_query | 返回 AVG(word_count) 并格式化 | 已通过 |
| 用柱状图展示各来源的数据量 | chart_request | 生成柱状图 Echarts 配置并渲染 | 已通过 |

### 关键优化点

1. **意图细分**：`database_query` 下支持 `statistical_query`、`trend_query`、`ranking_query`、`source_query`、`correlation_query`、`content_query`、`fact_query`、`overview_query` 八种二级意图
2. **规则优先**：通过关键词规则快速分类，减少不必要的 LLM 调用，降低响应延迟
3. **Schema 缓存**：`data_query.py` 中缓存 enriched schema，避免每次查询重复生成
4. **结果本地格式化**：单值查询和两列分布查询优先本地格式化，确保数据准确且减少 LLM 开销
5. **安全 SQL**：仅允许 SELECT，禁止写操作、DDL 和多语句，只查询白名单表
6. **数据范围**：优先 `data_warehouse`，深度采集内容 `JOIN deep_collected_data`，原始采集 fallback 到 `collected_data`

## 前台界面与交互验证

### 侧边栏交互

| 验证项 | 预期行为 | 验证结果 |
|--------|---------|---------|
| 登录后默认状态 | 桌面端侧边栏默认折叠（64px），移动端默认隐藏 | 通过 |
| 点击展开/收起 | 桌面端点击切换按钮展开/折叠侧边栏；移动端点击左上角汉堡按钮从左侧弹出/收回 | 通过 |
| 栏目记忆展开 | 点击功能菜单项后，该项所在的分类栏目保持 `expanded` 状态 | 通过 |
| 移动端完全收起 | 前台与后台移动端侧边栏收起时均设置 `transform: translateX(-110%)` + `visibility: hidden` + `pointer-events: none`，彻底移出可视区域且不接收事件，不影响右侧主内容 | 通过 |
| 移动端不阻挡内容 | 移动端侧边栏收起后仅保留左上角按钮，不占用页面空间；展开时以抽屉+遮罩形式呈现，不影响底层内容滚动 | 通过 |
| 后台移动端适配 | 后台 `layui-side` 在移动端可完全收起，`layui-body` 内容占满全宽，栅格列在窄屏下自动占满一行 | 通过 |
| 后台侧边栏完整菜单 | 后台移动端侧边栏从 `top: 64px` 开始并支持纵向滚动，可完整显示系统管理、瞭望中心、智能应用三个父栏目 | 通过 |
| 内容居中显示 | 移动端主内容区移除侧边栏占位后，前后台内容均居中或占满显示，不再被挤压到右侧 | 通过 |
| 侧栏覆盖不影响内容 | 移动端侧边栏展开时以抽屉形式覆盖在主内容上方，主内容本身不被推挤，仍可正常显示 | 通过 |

### 前台功能入口完整性

| 功能 | 入口位置 | 验证结果 |
|------|---------|---------|
| 登录/注册 | `/login`、`/register` 独立页面，注册成功后自动登录 | 通过 |
| 智能问数 | 侧边栏 AI 应用 > 智能问数 / 输入框直接提问 | 通过 |
| AI 问答 | 侧边栏 AI 应用 > AI 问答 | 通过 |
| @文案编写 | 侧边栏 数字员工 > 文案编写 / 输入框 `@` 菜单 | 通过 |
| @天气 | 侧边栏 数字员工 > 天气查询 / 输入框 `@` 菜单 | 通过 |
| @采集专员 | 侧边栏 数字员工 > 采集专员 / 输入框 `@` 菜单 | 通过 |
| 报表呈现 | 侧边栏 AI 应用 > 报表呈现 / 输入框请求生成可视化报告 | 通过 |
| 任务列表 | 侧边栏 历史任务 区域，支持切换/删除会话 | 通过 |
| 模型切换 | 侧边栏 当前模型 下拉框 | 通过 |

### 修复记录

- 修复移动端侧边栏展开时，内部 `sidebar-toggle` 与左上角 `mobile-menu-btn` 重叠的问题：在 `@media (max-width: 768px)` 中隐藏内部切换按钮，仅保留左上角统一入口。
- 修复移动端侧边栏收起不彻底的问题：在 `@media (max-width: 768px)` 中关闭侧边栏时设置 `transform: translateX(-110%)`、`visibility: hidden`、`pointer-events: none`，确保完全移出可视区域且不拦截右侧内容事件；开启时恢复可见和事件接收。
- 完成后台移动端侧边栏适配：`app/templates/admin/base.html` 新增左上角汉堡按钮、遮罩层和 `toggleSidebar`/`closeSidebar` 逻辑；移动端 `layui-side` 完全收起，`layui-body` 占满全宽，栅格列自动换行占满，表格区域支持横向滚动，避免内容被挤压到右侧。
- 修复前台移动端侧边栏占位问题：`app/templates/index.html` 中 `.sidebar.collapsed` 在 `@media (max-width: 768px)` 下明确保持 `position: fixed`，避免 collapsed 覆盖规则意外将其改为 static 而占用文档流，导致主内容被挤到右侧。
- 修复后台移动端侧边栏菜单显示不全问题：将移动端 `layui-side` 起始位置从 `top: 0` 调整为 `top: 64px`，并添加 `overflow-y: auto` 与 `-webkit-overflow-scrolling: touch`，确保系统管理、瞭望中心、智能应用三个父栏目完整可见。

### Markdown 渲染

| 验证项 | 预期行为 | 验证结果 |
|--------|---------|---------|
| AI 文本消息 | 普通文本正常显示，无异常间距 | 通过 |
| Markdown 标题 | `#`、`##` 等渲染为对应层级标题 | 通过 |
| 粗体/斜体/行内代码 | `**粗体**`、`*斜体*`、`` `code` `` 渲染为对应样式 | 通过 |
| 列表 | 无序列表渲染为项目符号列表 | 通过 |
| 代码块 |  fenced code block 渲染为带背景代码块 | 通过 |
| 引用 | `>` 渲染为左侧带色引用块 | 通过 |
| 表格 | Markdown 表格渲染为带边框表格 | 通过 |
| 原始 HTML 过滤 | 消息中的 `<script>` 等原始 HTML 被转义，不执行 | 通过 |
| 流式消息 | SSE 流式输出的 AI 内容实时按 Markdown 渲染 | 通过 |

## 后台管理菜单交互

| 验证项 | 预期行为 | 验证结果 |
|--------|---------|---------|
| 默认状态 | 后台首页未命中任何子菜单时，各父栏目均收起 | 通过 |
| 点击智能应用子功能 | 跳转后"智能应用"栏目保持展开，子功能高亮 | 通过 |
| 点击系统管理子功能 | 跳转后"系统管理"栏目保持展开，其他栏目收起 | 通过 |
| 栏目互斥 | 仅当前所在栏目自动展开，避免多个栏目同时展开造成拥挤 | 通过 |

## 移动端适配修复记录

针对手机端（`max-width: 768px`）前后台界面进行的响应式修复：

| 修复项 | 涉及文件 | 修复措施 | 验证结果 |
|--------|---------|---------|---------|
| 前台数字员工栏目无法收起 | `app/templates/index.html` | 移动端 `.sidebar.collapsed .feature-category-content` 保持 `overflow: hidden` 并配合 `max-height` 过渡，恢复折叠/展开动画；栏目收起后不再与下方历史任务重叠 | 通过 |
| 后台侧栏点击父栏目自动收起 | `app/templates/admin/base.html` | 侧边栏点击事件仅对带 `data-url` 的子菜单链接触发 `closeSidebar()`，父栏目（系统管理/瞭望中心/智能应用）展开/收起时不再关闭侧栏 | 通过 |
| 后台顶部标题与菜单按钮重叠 | `app/templates/admin/base.html` | 头部改用 `display: flex; justify-content: space-between;`；移动端 `.layui-header` 增大 `padding-left` 至 72px，`.layui-logo` 设置 `flex: 1; min-width: 0; max-width: calc(100% - 80px); overflow: hidden`，标题文字自动截断省略；logo 图标缩小至 22px，避免与左上角菜单按钮重叠 | 通过 |
| 后台右上角用户操作显示不完整 | `app/templates/admin/base.html` | 右侧用户菜单 `<a>` 改为 `display: flex; align-items: center;` 并预留箭头空间；下拉菜单 `dl.layui-nav-child` 绝对定位 `right: 0` + `z-index: 200`，移动端完整显示个人信息/修改密码/退出登录 | 通过 |
| 管理页面按钮排版混乱 | `app/templates/admin/base.html`、`app/templates/admin/menu.html` | 在 `@media (max-width: 768px)` 中统一 `.layui-card-body > .layui-form-item` 为 `flex-wrap: wrap` + `gap: 8px`，搜索输入框占满一行，按钮自动换行并对齐；表格操作按钮增加间距；菜单管理卡片头部按钮支持换行 | 通过 |

覆盖页面：用户管理、功能管理、菜单管理、数据仓库、数字员工。

## 安全漏洞修复

参考 `scan/` 目录下的 26 份安全报告，对代码进行逐个排查并修复。核心修复点如下：

| 漏洞类型 | 涉及文件 | 修复措施 | 验证结果 |
|---------|---------|---------|---------|
| SSRF（LLM base_url / 数字员工 api_url） | `app/utils/security.py`、`app/controllers/chat.py`、`app/controllers/admin.py`、`app/services/intent_engine.py` | 新增 URL 白名单与私有 IP 过滤；所有出站 `HTTPRequest` 与 `requests` 调用设置 `follow_redirects=False` / `allow_redirects=False` | 通过 |
| SQL 注入（逗号连接、引号标识符绕过） | `app/models/data_query.py` | 使用 `sqlparse` 解析 AST，递归提取 `FROM`/`JOIN` 中的所有表名并校验白名单 | 通过 |
| 提示词注入 | `app/services/intent_engine.py` | 对用户输入进行 HTML 实体转义，破坏注入结构 | 通过 |
| IDOR（会话删除越权） | `app/controllers/chat.py`、`app/models/chat.py` | 删除前显式校验 `session["user_id"] == user_id` | 通过 |
| 信息泄露（api_key / 堆栈跟踪） | `app/controllers/chat.py`、`app/templates/admin/ai_model.html`、`app/controllers/base.py` | `/api/models` 移除 `api_key`；模板使用 `json_encode` 并排除 `api_key`；统一错误处理不暴露堆栈 | 通过 |
| 类型转换异常信息泄露 | `app/controllers/chat.py`、`app/controllers/admin.py` | 使用 `safe_int` / `safe_float` 替代裸 `int()` / `float()` | 通过 |
| 未受控线程创建（DoS） | `app/controllers/admin.py` | 深度采集改用 `ThreadPoolExecutor(max_workers=3)`，批量采集限制 50 条 | 通过 |
| XSS（模板 JS 上下文） | `app/templates/admin/ai_model.html`、`app/templates/admin/function.html`、`app/templates/admin/data_source.html` | 动态参数使用 `json_encode()` 转义 | 通过 |
| CSRF（GET 登出） | `app/controllers/auth.py`、`app/templates/index.html`、`app/templates/admin/base.html` | 移除 `LogoutHandler.get`；前后台均改用 POST + XSRF Token 表单登出 | 通过 |
| 硬编码凭据 | `app.py`、`config/config.py`、`app/models/db.py` | `COOKIE_SECRET` / `DEBUG` 从环境变量读取；默认管理员密码优先从 `ADMIN_INITIAL_PASSWORD` 读取，否则随机生成 | 通过 |

### 验证脚本

新增 `test_security.py`，覆盖以下关键检查：
- `safe_int` / `safe_float` 安全转换
- LLM base_url 与数字员工 api_url 的 SSRF 校验
- 私有/内部 IP 识别
- 基于 `sqlparse` 的 SQL 白名单校验（含逗号连接、引号标识符绕过用例）
- 提示词注入转义
- `cookie_secret`、`debug`、默认管理员密码不再硬编码
- `/api/models` 不泄露 `api_key`
- `GET /logout` 返回 405
- `/api/chat` 对无效/内网模型有基本防护

执行结果：

```text
============================================================
DataFinderAgentOS 安全修复自动化验证
============================================================
[PASS] safe_int / safe_float 安全转换
[PASS] LLM base_url SSRF 校验
[PASS] 数字员工 API URL SSRF 校验
[PASS] 私有/内部 IP 识别
[PASS] SQL 注入 AST 白名单校验
[PASS] 提示词注入转义
[PASS] cookie_secret 从环境变量读取
[PASS] debug 模式基于环境变量
[PASS] 默认管理员密码从环境变量/随机生成
[PASS] /api/models 响应不泄露 api_key
[PASS] GET /logout 被禁止（仅 POST 允许）
[PASS] /api/chat 对内网/无效模型有基本防护
============================================================
验证完成，未发现关键安全修复失效
============================================================
```

## 前台数字员工与交互增强

### 新增/完善的数字员工

| 数字员工 | 类型 | 触发方式 | 功能说明 | 验证结果 |
|---------|------|---------|---------|---------|
| @天气 | API | `@天气 城市名` | 调用 wttr.in 获取实时天气，渲染中文天气卡片（城市、气温、体感、湿度、风速、气压、天气状况） | 通过 |
| @随机音乐 | API | `@随机音乐` | 内置 SoundHelix 示例曲库，返回红色系音乐卡片，展示歌名/歌手，支持播放/暂停/换一首 | 通过 |
| @新闻 | API | `@新闻` | 调用 vvhan 热点新闻接口，返回浅色新闻卡片，展示 10 条全国热点新闻标题及当前时间，标题可跳转 | 通过 |
| @文案写作助手 | LLM | `@文案写作助手 开始` | 引入 `temp/WriteToolsAgent/Docs` 中的 role/constraint/scene/template 提示文件，按顺序补充到 System Prompt；严格按"关键词->10 个备选主题->选择主题->三类大纲->选择风格->逐章交互写作"流程执行 | 通过 |
| @小智 | LLM | `@小智 你好` | 通用 AI 聊天助手，使用独立 System Prompt 进行自然对话 | 通过 |
| @采集专员 | LLM | `@采集专员 采集链接/描述` | 启用 crawl4ai 时自动提取 URL 进行深度采集，并将采集正文作为上下文供模型分析，可生成表格/报表 | 通过 |

### 数据卡片渲染

- 天气卡片：浅蓝色系，中文标签，图标随天气状况变化。
- 音乐卡片：红色系渐变背景，白色控制按钮，内置 `<audio>` 控件与自定义播放/暂停/换一首按钮。
- 新闻卡片：浅色系白底，带序号排名，前 3 条高亮，标题链接新窗口打开。
- 表格/JSON/HTML 卡片：针对 API 类型员工配置的 `card_type` 自动渲染，保持与后台配置一致。

### 对话导出功能

- 在对话区右上角增加"导出"按钮，点击后以 `GET /api/chat/export?session_id=xxx` 导出当前会话。
- 后端使用 `fpdf2` 生成 PDF，自动下载 Noto Sans CJK SC 中文字体，导出内容包含会话标题、导出时间、每条消息的角色/时间/内容（已做简单 Markdown 去标记处理）。
- 导出前校验会话归属，防止越权导出他人对话。

### 历史记录管理增强

- 置顶：会话列表支持置顶/取消置顶，置顶会话优先排在最前。
- 重命名：点击编辑图标可修改会话标题。
- 删除：保留原有删除功能，删除当前会话后自动清空对话区。

### 暂停与编辑重发

- 暂停生成：AI 回复流式输出时，消息下方显示"暂停生成"按钮，点击后立即关闭 EventSource 并停止输出。
- 编辑重发：用户消息 hover 显示"编辑"按钮，点击可修改内容；若当前正在生成，先自动暂停，再删除该消息之后的所有消息并触发重新生成。
- 数据库使用 `chat_messages.is_edited` 标记编辑状态，`chat_sessions.is_pinned` 记录置顶状态。

## 开发流程

1. **需求确认**：在开发前确认需求范围和验收标准
2. **代码实现**：遵循 constraint.md 中的约束进行开发
3. **测试验证**：编写测试用例并执行验证
4. **文档更新**：同步更新相关文档
5. **代码提交**：完成后提交代码（如需）

## 需求变更记录

本文件将记录每次需求的变更历史，包括变更时间、变更内容和变更原因。

### 变更记录
- 2026-07-14: 实现 API 类型数字员工的数据卡片渲染功能：后台配置 `card_type`（weather/json/table/html）后，前台通过 @xxx 调用时自动渲染对应卡片，默认天气员工配置为 weather 卡片并已验证
- 2026-07-14: 新增默认"天气"数字员工（API 类型，调用 wttr.in），支持在前端通过 @天气 城市名 查询天气；增强 API 类型员工 URL 占位符替换能力
- 2026-07-14: 调整后台菜单结构：删除“数据管理”菜单及“采集管理”功能，删除“可视化”菜单及“数智大屏”“舆情大屏”功能，将“数据仓库”并入“瞭望中心”
- 2026-07-14: 完成任务 6 用户侧-前台用户系统开发，实现用户注册/登录/登出、ChatGPT 风格对话主页、模型切换、会话管理、SSE 流式对话、@ 数字员工调度和 / 快捷指令菜单
- 2026-07-14: 检查并确认 crawl4ai 运行环境满足要求（crawl4ai 0.9.1、playwright 1.61.0、Chromium 已安装，example.com 爬取测试通过）
- 2026-07-14: 增强数字员工编辑弹窗的错误提示，显示具体 HTTP 状态码，便于定位请求失败原因
- 2026-07-14: 修复数字员工编辑/详情、搜索功能，修复数据仓库表头复选框可选中问题，深度采集接入 crawl4ai 组件并完善标题/正文/URL/字数持久化
- 2026-07-14: 优化瞭望采集和瞭源管理界面为高级商务风，修复 requests 处理 br/zstd 压缩格式导致百度新闻采集失败的问题
- 2026-07-14: 新增瞭望管理系统功能，实现瞭源管理、数据采集、结果展示
- 2026-07-14: 前台对话增加 AI 意图识别、数据库问数与 Echarts 图表渲染能力；支持 chat/database_query/chart_request/employee_call 四种意图，按意图调度生成图表，不暴露真实 SQL，不接收用户输入 SQL；修复 CHART_PROMPT 中 Python str.format 误解析 JSON 大括号导致图表配置生成失败的 Bug
- 2026-07-14: 前台 AI 消息下方显示响应时间（秒）和 Token 估算数量；天气反馈内容翻译为中文；用户侧 @数字员工 统一使用后台配置的名称进行交互和显示
- 2026-07-14: 确认用户侧模型请求严格遵循 OpenAI API 范式（`/chat/completions` + `stream=true` + 解析 `delta.content`），通过 SSE 向前端流式推送文本、卡片、图表和元信息事件
- 2026-07-14: 数字员工 LLM 类型新增/编辑时支持上传一个或多个 `.nd` 文件，文件内容在前台 @ 调用时自动补充到 System Prompt；文件按员工独立目录存储在 `data/dgUser/{employee_id}/`
- 2026-07-14: 完成任务 5.1 验证：通过前台对话 `@测试助手 你来自哪里？` 确认 `.nd` 文件内容（DataFinderAgentOS 数字员工中心 / .nd 文件补充 Prompt）已正确补充到 System Prompt 并生效；后台详情页正确展示已上传的 `test.nd` 文件
- 2026-07-15: 完成任务 6.4 智能问数增强：修复问数能力薄弱问题，支持按意图理解并分析后返回结果；优先查询后台采集数据（含深度采集）；覆盖统计、分析、趋势、排名、来源、关联、内容检索、报表呈现等场景；实现查询意图细分、schema 缓存、规则优先分类、安全 SQL 生成、结果本地格式化与 AI 分析解读、Echarts 图表配置自动生成；已验证统计、来源分布、深度采集平均字数、趋势、排名、关联交叉、内容检索、柱状图展示等用例
- 2026-07-15: 完成前台界面与交互验证：登录/注册/智能问数/AI 问答/@数字员工（文案编写/天气/采集专员）/报表呈现/任务列表/模型切换等功能入口均已完备；桌面端侧边栏默认折叠、点击展开、栏目记忆展开，移动端侧边栏仅保留左上角入口、点击从左侧弹出/收回且不影响主内容；修复移动端内部切换按钮与左上角菜单按钮重叠的问题
- 2026-07-15: 前台 AI 回复接入 Markdown 渲染：使用 marked.js 将 Markdown 语法（标题、粗体/斜体/代码、列表、代码块、引用、表格、链接等）转换为 HTML 展示；SSE 流式消息实时渲染；原始 HTML 自动转义避免 XSS
- 2026-07-15: 修复后台管理菜单交互：移除菜单栏目的硬编码展开状态，改为根据当前 URL 动态展开并高亮对应栏目；点击"智能应用"下子功能后，该栏目保持展开且子功能高亮
- 2026-07-15: 修复后台未登录跳转问题：`AdminBaseHandler` 改用重写 `get_login_url()` 方式，适配 Tornado 6.5.7，确保访问 `/admin/` 时跳转到 `/admin/login` 而非前台登录页
- 2026-07-15: 完成安全漏洞排查与修复：参考 scan/ 目录下 26 份安全报告，修复 SSRF、SQL 注入、提示词注入、IDOR、信息泄露、XSS、CSRF、DoS、硬编码凭据等类型漏洞；新增 `app/utils/security.py` 安全工具函数、`test_security.py` 自动化验证脚本；所有出站 HTTP 请求禁用重定向；`test_security.py` 验证全部通过
- 2026-07-15: 进一步优化后台移动端顶部标题与左上角菜单按钮的间距：将 `.layui-header` 移动端 `padding-left` 增大至 72px，`.layui-logo` 增加 `max-width: calc(100% - 80px)`，logo 图标缩小至 22px，确保标题与图标不再与侧栏切换按钮重叠；重启服务后验证通过
- 2026-07-15: 优化移动端侧边栏完全收起：关闭时 `transform: translateX(-110%)` + `visibility: hidden` + `pointer-events: none`，彻底避免影响右侧主内容显示与交互
- 2026-07-15: 完成前后台移动端侧边栏适配：前台 `index.html` 与后台 `admin/base.html` 均在移动端支持完全收起；后台 `layui-body` 占满全宽，栅格列自适应占满一行，内容居中显示不被挤压
- 2026-07-15: 修复前后台移动端侧边栏细节问题：前台 `.sidebar.collapsed` 在移动端保持 `position: fixed` 避免占位；后台 `layui-side` 从 `top: 64px` 开始并支持滚动，完整显示系统管理/瞭望中心/智能应用三个栏目
- 2026-07-15: 完成用户侧前台系统模块开发：补齐 @随机音乐、@新闻、@文案写作助手、@小智 四个默认数字员工；将 `temp/WriteToolsAgent/Docs` 中的 role/constraint/scene/template 按顺序补充到"文案写作助手"的 System Prompt；实现 AI 对话导出 PDF、历史记录置顶/重命名、消息暂停生成与编辑重发功能；完善 `chat_sessions`（增加 `is_pinned`）与 `chat_messages`（增加 `is_edited`、`response_time`、`token_count`）表结构
- 2026-07-15: 更新 `app/templates/index.html`：新增音乐/新闻卡片渲染、右上角导出按钮、会话置顶/重命名/删除交互、消息编辑按钮、暂停生成按钮；优化移动端侧边栏折叠逻辑
