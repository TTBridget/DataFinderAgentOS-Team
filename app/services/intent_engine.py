"""
intent_engine.py - AI 对话意图识别与工具调度引擎（增强版）
支持：
1. 意图识别（chat / database_query / chart_request / employee_call）
2. 查询意图细分（统计、分析、趋势、排名、关联、内容检索等）
3. 安全 SQL 生成（用于数据库问数）
4. 查询结果 AI 分析解读（不暴露 SQL）
5. 图表配置生成（用于 Echarts 渲染）
"""
import json
import re
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

from app.models.data_query import execute_readonly_sql, _get_cached_enriched_schema, DataQueryError
from app.utils.security import validate_llm_base_url


INTENT_PROMPT = """你是一名意图识别专家。请分析用户输入，判断其意图，并输出 JSON 结果。

可选意图：
- chat：普通闲聊、问答、不需要查询数据库或生成图表
- database_query：用户想从数据库中查询数据、统计、分析、挖掘、检索
- chart_request：用户希望看到图表、可视化、报表、趋势图、柱状图、饼图等
- employee_call：用户明确 @ 某个数字员工（如 @天气、@采集专员）

输出格式（仅 JSON，不要其他文字）：
{{
  "intent": "database_query|chart_request|chat|employee_call",
  "confidence": 0.9,
  "reason": "简短理由"
}}

注意：
- 如果用户要求“统计”“查询”“有多少”“排名”“趋势”“按...分组”“分析”“来源”“关键词”“关联”“分布”，优先 database_query
- 如果用户提到“图表”“报表”“可视化”“饼图”“柱状图”“折线图”“趋势图”“统计图”，优先 chart_request
- chart_request 通常也包含 database_query，intent 应选 chart_request
- 如果用户消息以 @ 开头，intent 固定为 employee_call
"""


QUERY_TYPE_PROMPT = """你是一名数据分析意图分类专家。请根据用户问题，判断其属于哪种数据查询/分析类型，并输出 JSON。

可选类型：
- fact_query：查询具体某条/某几条数据详情
- statistical_query：统计总数、平均值、极值、占比、分布等
- trend_query：按时间趋势分析
- ranking_query：排名、Top N
- source_query：来源分析、来源分布、信源统计
- correlation_query：关联挖掘、交叉分析、关系发现
- content_query：内容检索、关键词搜索、文本查找
- overview_query：整体概览、综合汇总

输出格式（仅 JSON）：
{{
  "query_type": "类型",
  "confidence": 0.9,
  "reason": "简短理由",
  "suggested_approach": "建议的分析思路"
}}

用户问题：{question}
"""


SQL_PROMPT = """你是一名资深数据分析师兼 SQLite SQL 专家。请根据用户问题、数据库 schema 与样例数据，生成一条安全的 SQLite SELECT 查询语句。

【数据库 Schema】
{schema}

【用户问题】
{question}

【查询类型】
{query_type}

【要求】
1. 只生成 SELECT 语句，禁止 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/EXEC/PRAGMA/ATTACH/TRUNCATE
2. 禁止多语句，不要包含分号
3. 只查询上面列出的白名单表
4. 优先使用 data_warehouse 表进行查询；涉及深度采集内容时 JOIN deep_collected_data；原始采集 fallback 到 collected_data
5. 允许并鼓励使用 JOIN、GROUP BY、ORDER BY、HAVING、LIMIT、聚合函数（COUNT/SUM/AVG/MAX/MIN）、子查询、窗口函数等进行分析
6. 根据查询类型选择合适的 SQL 模式：
   - 统计：使用聚合函数 + GROUP BY
   - 趋势：按 DATE(created_at) 或 publish_time 分组
   - 排名：ORDER BY + LIMIT
   - 来源分析：GROUP BY source_name
   - 关联挖掘：多字段 GROUP BY 或 JOIN
   - 内容检索：title LIKE '%关键词%' OR content LIKE '%关键词%'，优先选择 id, title, url, source_name, publish_time 等关键字段，避免返回过长 content
7. 不要添加任何解释，只输出 SQL 字符串（不要 Markdown 代码块）
8. 如果问题无法通过数据库查询回答，请输出：__NOT_QUERY__

请生成 SQL：
"""


ANALYZE_PROMPT = """你是一名数据分析师。请根据用户问题与查询结果，生成一段自然语言的分析结论。

【用户问题】
{question}

【查询结果】
{result}

【要求】
1. 用中文回答，语言流畅、专业
2. 直接给出数据洞察和结论，不要列出原始 SQL
3. 如果结果是空数据，请说明“未查询到相关数据”
4. 如果是统计/排名/分布，请概括关键发现（如最多、最少、占比、趋势等）
5. 如果是内容检索，请总结检索到的关键信息
6. 控制在 200 字以内，重点突出
"""


CHART_PROMPT = """你是一名数据可视化专家。用户希望根据以下查询结果生成 Echarts 图表配置。

查询结果（JSON，最多 5 条示例）：
{sample}

总条数：{count}

用户原问题：{question}

请输出 JSON 配置，指定图表类型和数据映射：
{{
  "type": "bar|line|pie|scatter",
  "title": "图表标题",
  "x_axis": "用于 X 轴的字段名",
  "y_axis": "用于 Y 轴的字段名",
  "series_name": "数据系列名称",
  "reason": "选择该图表类型的理由"
}}

注意：
- 如果数据只有一列适合作为类别、一列适合作为数值，使用 bar
- 如果数据包含时间序列，使用 line
- 如果数据是占比/分类汇总，使用 pie
- 如果数据适合观察相关性，使用 scatter
- 只输出 JSON，不要其他文字
"""


def detect_employee_mention(message, employees):
	"""
	检测消息是否 @ 了数字员工
	employees 列表元素需包含 name 字段
	"""
	if not message or not message.startswith("@"):
		return None
	match = re.match(r"@([^\s]+)", message)
	if not match:
		return None
	name = match.group(1)
	for emp in employees:
		if emp.get("name") == name:
			return emp
	return None


async def _call_llm(base_url, api_key, model_name, messages, temperature=0.1, max_tokens=512):
	"""调用 LLM 进行意图识别或配置生成"""
	if not validate_llm_base_url(base_url):
		raise ValueError("模型 Base URL 不合法或存在 SSRF 风险")

	client = AsyncHTTPClient()

	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {api_key or ''}"
	}

	payload = {
		"model": model_name,
		"messages": messages,
		"temperature": temperature,
		"top_p": 1.0,
		"max_tokens": max_tokens,
		"stream": False
	}

	url = base_url or ""
	if not url.endswith("/"):
		url += "/"
	url += "chat/completions"

	request = HTTPRequest(
		url=url,
		method="POST",
		headers=headers,
		body=json.dumps(payload),
		request_timeout=30,
		follow_redirects=False
	)

	response = await client.fetch(request)
	response_text = response.body.decode("utf-8", errors="replace")
	data = json.loads(response_text)

	if "choices" in data and len(data["choices"]) > 0:
		return data["choices"][0]["message"]["content"]
	return None


def _extract_json(text):
	"""从文本中提取 JSON 对象"""
	if not text:
		return None
	match = re.search(r'\{.*\}', text, re.DOTALL)
	if match:
		try:
			return json.loads(match.group(0))
		except json.JSONDecodeError:
			return None
	return None


async def recognize_intent(message, model, employees=None):
	"""
	识别用户意图
	返回: {"intent": "chat|database_query|chart_request|employee_call", ...}
	"""
	# 优先处理 @ 员工
	if employees:
		emp = detect_employee_mention(message, employees)
		if emp:
			return {"intent": "employee_call", "employee": emp, "confidence": 1.0}

	# 规则兜底
	lower_msg = message.lower()
	chart_keywords = ["图表", "报表", "可视化", "饼图", "柱状图", "折线图", "趋势图", "统计图"]
	query_keywords = ["统计", "查询", "有多少", "排名", "趋势", "按", "分组", "汇总", "总数", "平均",
					 "分析", "来源", "关键词", "关联", "分布", "占比", "Top", "多少条", "检索"]

	if any(k in lower_msg for k in chart_keywords):
		return {"intent": "chart_request", "confidence": 0.8}
	if any(k in lower_msg for k in query_keywords):
		return {"intent": "database_query", "confidence": 0.8}

	# 如果配置了模型，使用 LLM 判断
	if model:
		try:
			content = await _call_llm(
				model["base_url"], model["api_key"], model["name"],
				[
					{"role": "system", "content": INTENT_PROMPT},
					{"role": "user", "content": message}
				]
			)
			result = _extract_json(content)
			if result:
				return {
					"intent": result.get("intent", "chat"),
					"confidence": result.get("confidence", 0.5),
					"reason": result.get("reason", "")
				}
		except Exception:
			pass

	return {"intent": "chat", "confidence": 1.0}


def classify_query_type_rule(question):
	"""
	基于规则判断数据库查询的细分类型（减少一次 LLM 调用，降低延迟）
	返回: {"query_type": "...", "confidence": ..., "reason": ..., "suggested_approach": "..."}
	"""
	q = question.lower()

	# 图表请求已在更高层识别，这里不处理
	if any(k in q for k in ["趋势", "走势", "随着时间", "按时间", "时间分布", "日", "月", "年"]):
		return {"query_type": "trend_query", "confidence": 0.85, "reason": "包含时间/趋势关键词", "suggested_approach": "按时间字段分组统计"}
	if any(k in q for k in ["排名", "top", "第几", "最多", "最少", "最大", "最小", "前"]):
		return {"query_type": "ranking_query", "confidence": 0.85, "reason": "包含排名/极值关键词", "suggested_approach": "ORDER BY + LIMIT"}
	if any(k in q for k in ["来源", "信源", "媒体", "出处", "站点"]):
		return {"query_type": "source_query", "confidence": 0.85, "reason": "包含来源分析关键词", "suggested_approach": "GROUP BY source_name"}
	if any(k in q for k in ["关联", "关系", "交叉", "对比", "相关性", "共同", "共现", "图谱"]):
		return {"query_type": "correlation_query", "confidence": 0.8, "reason": "包含关联/关系关键词", "suggested_approach": "多字段 GROUP BY 或 JOIN"}
	if any(k in q for k in ["检索", "搜索", "包含", "查找", "含有", "关键词", "标题"]):
		return {"query_type": "content_query", "confidence": 0.85, "reason": "包含内容检索关键词", "suggested_approach": "LIKE 模糊匹配"}
	if any(k in q for k in ["详情", "具体", "某条", "哪条", "内容是什么", "是什么"]):
		return {"query_type": "fact_query", "confidence": 0.75, "reason": "包含具体事实查询关键词", "suggested_approach": "精确条件查询"}
	if any(k in q for k in ["概览", "整体", "综合", "汇总", "总体", "情况"]):
		return {"query_type": "overview_query", "confidence": 0.75, "reason": "包含整体概览关键词", "suggested_approach": "多维度汇总统计"}
	if any(k in q for k in ["多少", "总数", "总量", "总计", "统计", "平均", "均值", "avg", "sum", "占比", "比例", "百分比"]):
		return {"query_type": "statistical_query", "confidence": 0.85, "reason": "包含统计/聚合关键词", "suggested_approach": "聚合函数 + GROUP BY"}

	# 默认统计
	return {"query_type": "statistical_query", "confidence": 0.7, "reason": "未命中特定类型关键词，默认统计分析", "suggested_approach": "聚合函数 + GROUP BY"}


async def classify_query_type(question, model):
	"""
	判断数据库查询的细分类型：优先规则，可选 LLM 兜底
	返回: {"query_type": "...", "confidence": ..., "reason": ..., "suggested_approach": "..."}
	"""
	# 优先使用规则分类，降低延迟
	rule_result = classify_query_type_rule(question)
	if rule_result["confidence"] >= 0.8:
		return rule_result

	# 置信度较低时，使用 LLM 兜底
	if not model:
		return rule_result

	try:
		content = await _call_llm(
			model["base_url"], model["api_key"], model["name"],
			[
				{"role": "system", "content": "你是一名数据分析意图分类专家。只输出 JSON。"},
				{"role": "user", "content": QUERY_TYPE_PROMPT.format(question=question)}
			],
			temperature=0.1,
			max_tokens=512
		)
		result = _extract_json(content)
		if result:
			return {
				"query_type": result.get("query_type", rule_result["query_type"]),
				"confidence": result.get("confidence", 0.5),
				"reason": result.get("reason", ""),
				"suggested_approach": result.get("suggested_approach", "")
			}
	except Exception:
		pass

	return rule_result


def _format_simple_analysis(question, rows, columns):
	"""对简单查询结果进行本地格式化，避免 LLM 调用"""
	if not rows:
		return None

	q = question.lower()

	# 单条单值：如 COUNT(*)、AVG(...)
	if len(rows) == 1 and len(columns) == 1:
		col = columns[0]
		val = rows[0].get(col)
		# 数值格式化
		if isinstance(val, float):
			val = round(val, 2)
		if any(k in q for k in ["多少", "count", "总数", "总量", "几", "数量"]):
			return f"经统计，查询结果为 {val}。"
		if any(k in q for k in ["平均", "均值", "avg", "average"]):
			return f"经计算，平均值为 {val}。"
		if any(k in q for k in ["最大", "最多", "max"]):
			return f"经查询，最大值为 {val}。"
		if any(k in q for k in ["最小", "最少", "min"]):
			return f"经查询，最小值为 {val}。"
		return f"查询结果为：{val}。"

	# 两列数据（类别+数值）：常见排名、分布、来源统计
	if len(rows) >= 1 and len(columns) == 2:
		cat_col, val_col = columns[0], columns[1]
		# 识别数值列
		try:
			total = sum(float(r.get(val_col, 0) or 0) for r in rows)
		except (TypeError, ValueError):
			total = None

		items = []
		for r in rows:
			cat = r.get(cat_col, "")
			val = r.get(val_col, "")
			if isinstance(val, float):
				val = round(val, 2)
			items.append(f"{cat}（{val}）")

		if total is not None and total > 0:
			if any(k in q for k in ["排名", "top", "第几", "最多", "最少", "最大", "最小", "前"]):
				return f"排名结果如下（共 {len(rows)} 项，合计 {round(total, 2)}）：" + "、".join(items) + "。"
			return f"统计结果如下（共 {len(rows)} 项，合计 {round(total, 2)}）：" + "、".join(items) + "。"

	return None


def _escape_prompt_input(text):
	"""对用户输入进行提示词注入防御转义"""
	if not text:
		return text
	# 将可能闭合标签的字符替换为不可闭合形式，破坏注入结构
	return str(text).replace("<", "＜").replace(">", "＞")


async def generate_sql(question, model, query_type="statistical_query"):
	"""
	根据用户问题生成安全 SQL
	返回: (sql_string, error_message)
	"""
	if not model:
		return None, "未配置模型，无法生成 SQL"

	try:
		schema = _get_cached_enriched_schema()
		prompt = SQL_PROMPT.format(
			schema=schema,
			question=_escape_prompt_input(question),
			query_type=_escape_prompt_input(query_type)
		)
		content = await _call_llm(
			model["base_url"], model["api_key"], model["name"],
			[
				{"role": "system", "content": "你是一名 SQLite SQL 专家。只输出 SQL 字符串，不解释。"},
				{"role": "user", "content": prompt}
			],
			temperature=0.0,
			max_tokens=2048
		)
		if not content:
			return None, "模型未返回 SQL"

		content = content.strip()
		# 去除 Markdown 代码块
		if content.startswith("```"):
			content = re.sub(r"^```\w*\n?", "", content)
			content = re.sub(r"\n?```$", "", content)
			content = content.strip()

		if content == "__NOT_QUERY__":
			return None, "当前问题无法通过数据库查询回答"

		return content, None
	except Exception as e:
		return None, f"生成 SQL 失败: {str(e)}"


async def analyze_result(question, rows, columns, model):
	"""
	对查询结果进行自然语言分析解读
	返回: 分析文本
	"""
	if not model or not rows:
		return None

	try:
		# 截断结果，避免 prompt 过长
		display_rows = rows[:20]
		result_text = json.dumps({
			"columns": columns,
			"row_count": len(rows),
			"rows": display_rows
		}, ensure_ascii=False, indent=2)

		prompt = ANALYZE_PROMPT.format(question=question, result=result_text)
		content = await _call_llm(
			model["base_url"], model["api_key"], model["name"],
			[
				{"role": "system", "content": "你是一名数据分析师。只输出分析结论，不暴露 SQL。"},
				{"role": "user", "content": prompt}
			],
			temperature=0.3,
			max_tokens=1024
		)
		return content.strip() if content else None
	except Exception:
		return None


async def execute_database_query(question, model):
	"""
	执行数据库问数（增强版）：
	1. 识别查询类型
	2. 生成 SQL
	3. 执行查询
	4. 对结果进行 AI 分析解读
	返回: {"sql": ..., "data": [...], "columns": [...], "analysis": "...", "query_type": "...", "error": ...}
	"""
	# 1. 识别查询类型
	query_type_info = await classify_query_type(question, model)
	query_type = query_type_info.get("query_type", "statistical_query")

	# 2. 生成 SQL
	sql, error = await generate_sql(question, model, query_type)
	if error:
		return {"sql": None, "data": [], "columns": [], "analysis": None, "query_type": query_type, "error": error}

	# 3. 执行查询
	try:
		rows = execute_readonly_sql(sql)
		columns = list(rows[0].keys()) if rows else []
	except DataQueryError as e:
		return {"sql": sql, "data": [], "columns": [], "analysis": None, "query_type": query_type, "error": str(e)}
	except Exception as e:
		return {"sql": sql, "data": [], "columns": [], "analysis": None, "query_type": query_type, "error": f"执行查询失败: {str(e)}"}

	# 4. 优先对简单结果进行本地格式化，减少 LLM 调用
	analysis = _format_simple_analysis(question, rows, columns)
	if not analysis:
		analysis = await analyze_result(question, rows, columns, model)

	return {
		"sql": sql,
		"data": rows,
		"columns": columns,
		"analysis": analysis,
		"query_type": query_type,
		"error": None
	}


async def generate_chart_config(question, query_result, model):
	"""
	根据查询结果生成图表配置
	返回: {"type": "bar|line|pie|scatter", "title": ..., ...}
	"""
	if not model or not query_result.get("data"):
		return None

	data = query_result["data"]
	sample = json.dumps(data[:5], ensure_ascii=False, indent=2)

	try:
		prompt = CHART_PROMPT.format(sample=sample, count=len(data), question=question)
		content = await _call_llm(
			model["base_url"], model["api_key"], model["name"],
			[
				{"role": "system", "content": "你是一名数据可视化专家。只输出 JSON 配置。"},
				{"role": "user", "content": prompt}
			],
			temperature=0.1,
			max_tokens=1024
		)
		if not content:
			return None

		return _extract_json(content)
	except Exception:
		return None
