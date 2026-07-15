"""
data_query.py - 安全的数据库查询执行器（增强版）
用于 AI 对话中的智能问数能力

能力范围：
1. 支持对后台采集数据（data_warehouse / deep_collected_data / collected_data）进行只读查询
2. 支持复杂分析 SQL：JOIN、GROUP BY、ORDER BY、聚合函数、子查询、窗口函数
3. 提供表结构、样例数据、统计信息，帮助 LLM 生成更精准的 SQL
4. 严格的安全校验：仅允许 SELECT，禁止任何写操作与多语句
"""
import sqlite3
import re
import json
import sqlparse
from sqlparse.sql import Identifier, IdentifierList
from sqlparse.tokens import Keyword, DML
from app.models.db import get_connection


# 允许查询的表白名单（只读）
# 每个表包含：字段列表、字段描述、数据示例、业务说明
ALLOWED_TABLES = {
    "data_warehouse": {
        "description": "数据仓库：存储从瞭望采集模块整合后的核心数据条目，是智能问数的首选数据源。包含标题、正文、URL、发布时间、来源、关键词、是否经过深度采集等字段。",
        "columns": {
            "id": {"type": "INTEGER", "description": "数据主键"},
            "source_id": {"type": "INTEGER", "description": "关联的数据源 ID"},
            "title": {"type": "TEXT", "description": "数据标题，可用于关键词检索、主题分析"},
            "url": {"type": "TEXT", "description": "数据原始链接"},
            "content": {"type": "TEXT", "description": "数据正文/摘要内容"},
            "publish_time": {"type": "TEXT", "description": "发布时间，原始格式如 '23分钟前'、'1小时前'、'2026-07-14'"},
            "source_name": {"type": "TEXT", "description": "来源名称，如 '中国发展改革'、'封面新闻'"},
            "keyword": {"type": "TEXT", "description": "采集关键词，如 '四川'、'成都'"},
            "is_deep_collected": {"type": "INTEGER", "description": "是否经过深度采集：1=是，0=否"},
            "created_at": {"type": "TEXT", "description": "入库时间"},
            "updated_at": {"type": "TEXT", "description": "更新时间"},
        }
    },
    "deep_collected_data": {
        "description": "深度采集结果：存储数字员工通过 Crawl4ai 对 data_warehouse 中目标 URL 进行深度采集后的完整正文、字数、状态、执行日志等。适用于内容深度分析、字数统计、采集任务质量分析。",
        "columns": {
            "id": {"type": "INTEGER", "description": "深度采集任务主键"},
            "warehouse_id": {"type": "INTEGER", "description": "关联的数据仓库条目 ID，可与 data_warehouse.id 关联"},
            "employee_id": {"type": "INTEGER", "description": "执行采集的数字员工 ID"},
            "employee_name": {"type": "TEXT", "description": "执行采集的数字员工名称"},
            "status": {"type": "TEXT", "description": "任务状态：pending/running/completed/failed"},
            "progress": {"type": "INTEGER", "description": "任务进度 0-100"},
            "title": {"type": "TEXT", "description": "深度采集后提取的标题"},
            "content": {"type": "TEXT", "description": "深度采集后的完整正文内容"},
            "url": {"type": "TEXT", "description": "采集目标 URL"},
            "word_count": {"type": "INTEGER", "description": "正文字数"},
            "created_at": {"type": "TEXT", "description": "创建时间"},
            "updated_at": {"type": "TEXT", "description": "更新时间"},
        }
    },
    "collected_data": {
        "description": "原始采集结果：存储从各数据源直接采集到的原始条目，是 data_warehouse 的源头数据。",
        "columns": {
            "id": {"type": "INTEGER", "description": "采集主键"},
            "source_id": {"type": "INTEGER", "description": "数据源 ID"},
            "title": {"type": "TEXT", "description": "标题"},
            "url": {"type": "TEXT", "description": "链接"},
            "content": {"type": "TEXT", "description": "摘要内容"},
            "publish_time": {"type": "TEXT", "description": "发布时间"},
            "source_name": {"type": "TEXT", "description": "来源名称"},
            "keyword": {"type": "TEXT", "description": "采集关键词"},
            "created_at": {"type": "TEXT", "description": "采集时间"},
        }
    },
    "digital_employees": {
        "description": "数字员工：系统中配置的数字化员工信息，包含 LLM 类型和 API 类型。",
        "columns": {
            "id": {"type": "INTEGER", "description": "员工 ID"},
            "name": {"type": "TEXT", "description": "员工名称，如 '采集专员'、'天气'"},
            "description": {"type": "TEXT", "description": "描述"},
            "type": {"type": "TEXT", "description": "类型：llm 或 api"},
            "model_id": {"type": "INTEGER", "description": "关联模型 ID"},
            "is_enabled": {"type": "INTEGER", "description": "是否启用：1=启用，0=禁用"},
            "sort_order": {"type": "INTEGER", "description": "排序"},
            "created_at": {"type": "TEXT", "description": "创建时间"},
        }
    },
    "ai_models": {
        "description": "模型引擎：系统中配置的大模型服务信息。",
        "columns": {
            "id": {"type": "INTEGER", "description": "模型 ID"},
            "name": {"type": "TEXT", "description": "模型名称"},
            "provider": {"type": "TEXT", "description": "提供商"},
            "base_url": {"type": "TEXT", "description": "API 基础地址"},
            "is_default": {"type": "INTEGER", "description": "是否默认"},
            "is_enabled": {"type": "INTEGER", "description": "是否启用"},
            "total_tokens": {"type": "INTEGER", "description": "累计使用 Token"},
            "created_at": {"type": "TEXT", "description": "创建时间"},
        }
    }
}


class DataQueryError(Exception):
	pass


# 缓存 enriched schema，减少重复生成
_enriched_schema_cache = None
_enriched_schema_time = 0
_SCHEMA_CACHE_TTL = 60  # 秒


def _get_cached_enriched_schema():
	"""获取缓存的 enriched schema，过期则重新生成"""
	global _enriched_schema_cache, _enriched_schema_time
	import time
	now = time.time()
	if _enriched_schema_cache is None or (now - _enriched_schema_time) > _SCHEMA_CACHE_TTL:
		_enriched_schema_cache = get_enriched_schema()
		_enriched_schema_time = now
	return _enriched_schema_cache


def get_table_samples(table_name, limit=3):
	"""获取指定表的样例数据"""
	if table_name not in ALLOWED_TABLES:
		return []
	try:
		with get_connection() as conn:
			rows = conn.execute(
				f"SELECT * FROM {table_name} LIMIT ?",
				(limit,)
			).fetchall()
			result = []
			for row in rows:
				d = dict(row)
				# 截断长文本字段，避免 prompt 过长
				for key in ["content", "logs", "steps", "result_data", "markdown", "metadata", "original_content", "images"]:
					if key in d and isinstance(d[key], str) and len(d[key]) > 200:
						d[key] = d[key][:200] + "..."
				result.append(d)
			return result
	except Exception:
		return []


def get_table_stats(table_name):
	"""获取指定表的基础统计信息"""
	if table_name not in ALLOWED_TABLES:
		return {}
	try:
		with get_connection() as conn:
			count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
			return {"total_rows": count}
	except Exception:
		return {"total_rows": 0}


def get_schema_description():
	"""获取可用于提示词的数据库 schema 描述（精简版）"""
	lines = []
	for table, info in ALLOWED_TABLES.items():
		stats = get_table_stats(table)
		lines.append(f"表名: {table}（{stats.get('total_rows', 0)} 条）- {info['description']}")
		for col, meta in info["columns"].items():
			lines.append(f"  - {col} ({meta['type']}): {meta['description']}")
	return "\n".join(lines)


def get_enriched_schema():
	"""获取增强版 schema 描述，包含表关系、样例数据、推荐查询场景"""
	parts = []
	parts.append("数据库表结构")

	for table, info in ALLOWED_TABLES.items():
		stats = get_table_stats(table)
		parts.append(f"\n表: {table}（{stats.get('total_rows', 0)} 条）- {info['description']}")
		cols = [f"{col}({meta['type']}):{meta['description']}" for col, meta in info["columns"].items()]
		parts.append("字段: " + "; ".join(cols))

	# 只为核心表提供样例，避免 prompt 过长
	parts.append("\n样例数据（data_warehouse）：")
	for sample in get_table_samples("data_warehouse", limit=1):
		parts.append(json.dumps(sample, ensure_ascii=False))

	parts.append("\n表关系：")
	parts.append("- deep_collected_data.warehouse_id = data_warehouse.id")
	parts.append("- collected_data 与 data_warehouse 可通过 url/title/source_id 关联")

	parts.append("\nSQL 模式示例：")
	parts.append("- 统计: SELECT COUNT(*) FROM data_warehouse WHERE ...")
	parts.append("- 来源分布: SELECT source_name, COUNT(*) cnt FROM data_warehouse GROUP BY source_name ORDER BY cnt DESC")
	parts.append("- 关键词分布: SELECT keyword, COUNT(*) cnt FROM data_warehouse GROUP BY keyword ORDER BY cnt DESC")
	parts.append("- 深度采集: SELECT dwd.title, dcd.word_count FROM deep_collected_data dcd JOIN data_warehouse dwd ON dcd.warehouse_id=dwd.id")
	parts.append("- 时间趋势: SELECT DATE(created_at) day, COUNT(*) FROM data_warehouse GROUP BY day ORDER BY day")
	parts.append("- 内容检索: SELECT title, source_name FROM data_warehouse WHERE title LIKE '%关键词%' OR content LIKE '%关键词%'")
	parts.append("- 关联交叉: SELECT source_name, keyword, COUNT(*) FROM data_warehouse GROUP BY source_name, keyword")

	return "\n".join(parts)


def _extract_table_names(parsed):
	"""从 sqlparse 解析结果中递归提取所有表名"""
	tables = set()
	from_seen = False
	for token in parsed.tokens:
		if from_seen:
			if isinstance(token, Identifier):
				tables.add(token.get_real_name())
			elif isinstance(token, IdentifierList):
				for identifier in token.get_identifiers():
					if isinstance(identifier, Identifier):
						tables.add(identifier.get_real_name())
			elif token.ttype is Keyword:
				from_seen = False
			elif token.is_group:
				tables.update(_extract_table_names(token))
		elif token.ttype is Keyword and token.value.upper() in ("FROM", "JOIN"):
			from_seen = True
		elif token.is_group:
			tables.update(_extract_table_names(token))
	return tables


def _validate_sql(sql):
	"""
	验证 SQL 安全性（基于 sqlparse AST）：
	1. 必须是 SELECT 语句
	2. 禁止任何写操作与 DDL
	3. 禁止多语句
	4. 只允许查询白名单表（FROM / JOIN 中出现的表，包括逗号分隔和引号标识符）
	5. 允许 JOIN、GROUP BY、ORDER BY、HAVING、LIMIT、聚合函数、子查询、窗口函数等只读分析
	"""
	if not sql or not sql.strip():
		raise DataQueryError("SQL 不能为空")

	# 禁止多语句
	if ";" in sql:
		raise DataQueryError("禁止执行多条 SQL 语句")

	parsed = sqlparse.parse(sql)
	if not parsed:
		raise DataQueryError("SQL 解析失败")

	if len(parsed) > 1:
		raise DataQueryError("禁止执行多条 SQL 语句")

	stmt = parsed[0]

	# 必须是 SELECT 语句
	first_token = None
	for token in stmt.tokens:
		if token.ttype is not None and not token.is_whitespace:
			first_token = token
			break
	if first_token is None or first_token.ttype is not DML or first_token.value.upper() != "SELECT":
		raise DataQueryError("只允许执行 SELECT 查询")

	# 禁止危险关键字（写操作与 DDL）
	forbidden = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "EXEC", "PRAGMA", "ATTACH",
				 "TRUNCATE", "REPLACE", "MERGE", "GRANT", "REVOKE"}
	for token in stmt.flatten():
		if token.ttype in (Keyword, DML) and token.value.upper() in forbidden:
			raise DataQueryError(f"SQL 中包含禁止关键字: {token.value}")

	# 只允许白名单表（不区分大小写）
	allowed_lower = {t.lower() for t in ALLOWED_TABLES}
	for table in _extract_table_names(stmt):
		if table and table.lower() not in allowed_lower:
			raise DataQueryError(f"不允许访问表: {table}")

	return True


def execute_readonly_sql(sql):
	"""
	执行只读 SQL 查询，返回字典列表
	"""
	_validate_sql(sql)

	with get_connection() as conn:
		# 设置只读模式（最佳 effort）
		try:
			conn.execute("PRAGMA query_only = ON")
		except Exception:
			pass

		cursor = conn.execute(sql)
		columns = [desc[0] for desc in cursor.description]
		rows = cursor.fetchall()

		result = []
		for row in rows:
			result.append({col: row[i] for i, col in enumerate(columns)})

		# 恢复
		try:
			conn.execute("PRAGMA query_only = OFF")
		except Exception:
			pass

		return result
