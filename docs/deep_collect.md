# 深度采集模块技术文档

## 概述

深度采集模块是数据仓库的核心功能之一，用于对已保存的数据进行深度内容提取和处理。通过调度数字员工（如"采集专员"），可以自动获取网页的完整内容，并将结果持久化到数据库中。

## 功能特性

### 深度采集任务面板
- 点击深度采集按钮后，弹出悬浮窗口
- 显示任务情况、进度、状态、步骤
- 显示调度的数字员工详细信息
- 显示执行日志（实时更新）
- 显示采集结果（标题、字数、内容预览）

### 深度数据查看
- 已深度采集的数据支持查看详细内容
- 展示采集员工、采集状态、采集时间
- 展示标题、字数统计、详细内容

### 批量采集
- 支持多选数据进行批量深度采集
- 支持对已采集过的数据进行更新采集

## 工作流程

```
用户点击深度采集 → 选择数字员工 → 启动采集任务 → 后台线程执行采集 → 更新任务状态/进度/步骤/日志 → 采集完成 → 保存结果数据
```

## 数据库设计

### deep_collected_data 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| warehouse_id | INTEGER | 关联数据仓库 ID |
| employee_id | INTEGER | 关联数字员工 ID |
| employee_name | TEXT | 数字员工名称 |
| status | TEXT | 任务状态：pending/running/completed/failed |
| progress | INTEGER | 采集进度（0-100） |
| steps | TEXT | 采集步骤（JSON 数组） |
| logs | TEXT | 执行日志（JSON 数组） |
| result_data | TEXT | 采集结果数据（JSON） |
| title | TEXT | 采集标题 |
| content | TEXT | 采集正文 |
| url | TEXT | 采集URL |
| word_count | INTEGER | 正文字数 |
| error_message | TEXT | 错误信息 |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

### result_data 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| title | STRING | 标题 |
| url | STRING | 原始 URL |
| content | STRING | 提取的详细内容 |
| word_count | INTEGER | 字数统计 |
| original_content | STRING | 原始摘要内容 |
| warning | STRING | 警告信息（可选） |

## 后端实现

### 仓储层

**文件路径**：app/models/data_warehouse.py

#### DataWarehouseRepository 类新增方法

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| create_deep_collect_task | 创建深度采集任务 | warehouse_id, employee_id, employee_name | 任务 ID |
| update_deep_collect_task | 更新深度采集任务 | task_id, **kwargs | True |
| get_deep_collect_task | 获取深度采集任务 | warehouse_id | dict 或 None |
| get_deep_collect_task_by_id | 根据任务ID获取任务 | task_id | dict 或 None |
| add_deep_collect_step | 添加采集步骤 | task_id, step_name, status | True |
| add_deep_collect_log | 添加执行日志 | task_id, message, level | True |
| batch_deep_collect | 批量创建采集任务 | warehouse_ids, employee_id, employee_name | 任务ID列表 |
| get_deep_collected_items | 获取已深度采集的数据 | page, per_page, search | 分页数据 |

### 控制器层

**文件路径**：app/controllers/admin.py

#### DataWarehouseManageHandler 新增接口

| action | 说明 | 所需参数 |
|--------|------|----------|
| get_deep_task | 获取深度采集任务 | id（warehouse_id） |
| start_deep_collect | 启动深度采集任务 | id（warehouse_id）, employee_id, employee_name |
| get_employees | 获取可用采集专员列表（仅返回启用、LLM 类型且启用网页抓取的员工） | 无 |
| batch_deep_collect | 批量深度采集 | ids（JSON数组）, employee_id, employee_name |

## 前端实现

**文件路径**：app/templates/admin/data_warehouse.html

### 页面结构

1. **数据列表区**：包含复选框、标题、来源、关键词、发布时间、深度采集状态、保存时间、操作按钮
2. **批量操作区**：批量深度采集按钮
3. **深度采集面板**：数字员工选择、采集任务状态、进度条、采集步骤、执行日志、采集结果
4. **深度数据查看面板**：采集详情展示

### 交互逻辑

1. **任务轮询**：采集任务启动后，每2秒轮询一次任务状态
2. **实时更新**：进度、步骤、日志实时更新显示
3. **批量选择**：支持全选/反选数据
4. **更新采集**：已采集数据支持再次采集更新

## API 接口说明

### 获取深度采集任务

```
POST /admin/data_warehouse
Content-Type: application/x-www-form-urlencoded

action=get_deep_task
id=1
```

### 启动深度采集任务

```
POST /admin/data_warehouse
Content-Type: application/x-www-form-urlencoded

action=start_deep_collect
id=1
employee_id=1
employee_name=采集专员
```

### 获取可用数字员工

```
POST /admin/data_warehouse
Content-Type: application/x-www-form-urlencoded

action=get_employees
```

### 批量深度采集

```
POST /admin/data_warehouse
Content-Type: application/x-www-form-urlencoded

action=batch_deep_collect
ids=[1,2,3]
employee_id=1
employee_name=采集专员
```

## 使用场景

### 场景0：前台 @采集专员 深度采集

1. 用户在前台对话输入框中发送 `@采集专员 帮我采集这篇新闻：https://example.com/article`
2. 后端自动从消息中提取 URL，使用 crawl4ai 异步爬取目标网页
3. 将原始采集结果保存到 `data_warehouse`（瞭望采集）
4. 进一步创建 `deep_collected_data` 深度采集任务，记录采集步骤、日志、标题、正文、URL、字数
5. 更新 `data_warehouse.is_deep_collected = 1`
6. 向前台推送采集结果表格卡片，展示仓库 ID、标题、URL、正文字数、状态
7. 将采集正文作为上下文注入模型，供后续问答、表格或报表生成使用

### 场景1：单条数据深度采集

1. 在数据仓库列表中，找到需要深度采集的数据
2. 点击"深度采集"按钮
3. 在弹出的面板中选择数字员工（如"采集专员"）
4. 点击"开始采集"按钮
5. 实时查看采集进度、步骤和日志
6. 采集完成后查看采集结果

### 场景2：批量数据深度采集

1. 在数据仓库列表中，勾选多个需要深度采集的数据
2. 点击"批量深度采集"按钮
3. 在弹出的面板中选择数字员工
4. 点击"开始批量采集"按钮
5. 等待采集完成（可刷新页面查看状态）

### 场景3：更新采集

1. 在数据仓库列表中，找到已深度采集的数据
2. 点击"更新采集"按钮
3. 重新执行深度采集流程，更新数据

## 技术实现细节

### 后台线程执行

深度采集任务使用 threading.Thread 在后台执行，避免阻塞主线程：

```python
import threading
threading.Thread(target=run_collect, daemon=True).start()
```

### 采集步骤

1. 初始化采集任务（进度 10%）
2. 调度采集专员（进度 20%）
3. 执行网页内容提取（进度 50%）
4. 整理结构化数据（进度 80%）
5. 采集完成（进度 100%）

### 网页内容提取

使用 crawl4ai 组件进行网页内容深度采集：

- 通过 `AsyncWebCrawler` 异步爬取目标 URL
- 使用 `PruningContentFilter` 过滤无关内容
- 生成 Markdown 格式正文，保留完整标题和正文
- 内容最多保留 8000 字符
- 爬取失败时自动回退到原始摘要内容

### 环境依赖

深度采集依赖 crawl4ai 组件，请在项目的 Python 虚拟环境中安装：

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate    # Linux/macOS
pip install -r requirements.txt
```

`requirements.txt` 中已包含 `crawl4ai`。当前项目虚拟环境中已验证的版本：

| 组件 | 版本 | 说明 |
|------|------|------|
| crawl4ai | 0.9.1 | 网页爬取核心库 |
| playwright | 1.61.0 | 浏览器自动化驱动 |
| Chromium | 已安装 | Playwright 浏览器 |

安装完成后，可通过以下命令验证：

```bash
venv\Scripts\python.exe -c "import crawl4ai; print(crawl4ai.__version__)"
venv\Scripts\python.exe -m playwright install chromium
```

首次运行 crawl4ai 时，组件会自动下载所需的浏览器驱动（Playwright/Chromium）。

### 错误处理

- 网页访问失败时，使用原始摘要内容
- 记录警告日志
- 任务状态标记为 failed 时记录错误信息