"""
skill.py - 技能管理数据访问层
管理可被数字员工启用的技能增强
"""

import sqlite3
import json
from app.models.db import get_connection


class SkillRepository:
	"""技能管理仓储"""

	@staticmethod
	def get_all(page=1, per_page=20, search_keyword=None):
		"""获取所有技能，带分页和搜索"""
		offset = (page - 1) * per_page
		with get_connection() as conn:
			query = "SELECT * FROM skills"
			count_query = "SELECT COUNT(*) as total FROM skills"
			params = []
			count_params = []

			if search_keyword:
				where_clause = " WHERE name LIKE ? OR description LIKE ? OR code LIKE ?"
				query += where_clause
				count_query += where_clause
				params.extend([f"%{search_keyword}%", f"%{search_keyword}%", f"%{search_keyword}%"])
				count_params.extend([f"%{search_keyword}%", f"%{search_keyword}%", f"%{search_keyword}%"])

			query += " ORDER BY sort_order ASC, id DESC LIMIT ? OFFSET ?"
			params.extend([per_page, offset])

			rows = conn.execute(query, params).fetchall()
			total = conn.execute(count_query, count_params).fetchone()["total"]
			return {"items": rows, "total": total, "page": page, "per_page": per_page}

	@staticmethod
	def get_enabled():
		"""获取所有已启用的技能"""
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT * FROM skills WHERE is_enabled = 1 ORDER BY sort_order ASC, id DESC"
			).fetchall()
			return rows

	@staticmethod
	def get_by_id(skill_id):
		"""根据ID获取技能"""
		with get_connection() as conn:
			return conn.execute(
				"SELECT * FROM skills WHERE id = ?",
				(skill_id,)
			).fetchone()

	@staticmethod
	def get_by_code(code):
		"""根据编码获取技能"""
		with get_connection() as conn:
			return conn.execute(
				"SELECT * FROM skills WHERE code = ?",
				(code,)
			).fetchone()

	@staticmethod
	def create(name, code, description=None, config=None, is_enabled=1, sort_order=0):
		"""创建技能"""
		try:
			with get_connection() as conn:
				cursor = conn.execute(
					"""
					INSERT INTO skills (name, code, description, config, is_enabled, sort_order)
					VALUES (?, ?, ?, ?, ?, ?)
					""",
					(name, code, description, config, is_enabled, sort_order)
				)
				return cursor.lastrowid
		except sqlite3.IntegrityError:
			return None

	@staticmethod
	def update(skill_id, name=None, code=None, description=None, config=None,
			   is_enabled=None, sort_order=None):
		"""更新技能"""
		try:
			with get_connection() as conn:
				updates = []
				params = []

				if name is not None:
					updates.append("name = ?")
					params.append(name)
				if code is not None:
					updates.append("code = ?")
					params.append(code)
				if description is not None:
					updates.append("description = ?")
					params.append(description)
				if config is not None:
					updates.append("config = ?")
					params.append(config)
				if is_enabled is not None:
					updates.append("is_enabled = ?")
					params.append(is_enabled)
				if sort_order is not None:
					updates.append("sort_order = ?")
					params.append(sort_order)

				if updates:
					updates.append("updated_at = datetime('now','localtime')")
					params.append(skill_id)
					conn.execute(
						f"UPDATE skills SET {', '.join(updates)} WHERE id = ?",
						params
					)
				return True
		except sqlite3.IntegrityError:
			return False

	@staticmethod
	def delete(skill_id):
		"""删除技能"""
		with get_connection() as conn:
			conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
		return True

	@staticmethod
	def toggle_enabled(skill_id, is_enabled):
		"""启用/禁用技能"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE skills SET is_enabled = ?, updated_at = datetime('now','localtime') WHERE id = ?",
				(is_enabled, skill_id)
			)
		return True


class SkillEngine:
	"""技能执行引擎"""

	@staticmethod
	def apply_skills(system_prompt, skills=None, user_input=None):
		"""
		将启用的技能增强应用到系统提示词
		skills: 技能对象列表（通常为 SkillRepository.get_enabled() 的结果）
		返回增强后的系统提示词
		"""
		if not skills:
			return system_prompt or ""

		enhancements = []
		for skill in skills:
			if skill["code"] == "current_time":
				try:
					config = json.loads(skill["config"] or '{}')
					fmt = config.get("format", "%Y-%m-%d %H:%M:%S")
					from datetime import datetime
					current = datetime.now().strftime(fmt)
					enhancements.append(f"当前时间：{current}")
				except Exception:
					pass

		# 如果原提示词为空，直接返回增强内容
		if not system_prompt:
			return "\n".join(enhancements)

		# 否则追加到原提示词后面
		return system_prompt.strip() + "\n\n" + "\n".join(enhancements)
