"""
api_interface.py - 接口管理数据访问层
管理可被数字员工引用的 API 接口定义
"""

import sqlite3
from app.models.db import get_connection


class ApiInterfaceRepository:
	"""接口管理仓储"""

	@staticmethod
	def get_all(page=1, per_page=20, search_keyword=None):
		"""获取所有接口，带分页和搜索"""
		offset = (page - 1) * per_page
		with get_connection() as conn:
			query = "SELECT * FROM api_interfaces"
			count_query = "SELECT COUNT(*) as total FROM api_interfaces"
			params = []
			count_params = []

			if search_keyword:
				where_clause = " WHERE name LIKE ? OR description LIKE ?"
				query += where_clause
				count_query += where_clause
				params.extend([f"%{search_keyword}%", f"%{search_keyword}%"])
				count_params.extend([f"%{search_keyword}%", f"%{search_keyword}%"])

			query += " ORDER BY sort_order ASC, id DESC LIMIT ? OFFSET ?"
			params.extend([per_page, offset])

			rows = conn.execute(query, params).fetchall()
			total = conn.execute(count_query, count_params).fetchone()["total"]
			return {"items": rows, "total": total, "page": page, "per_page": per_page}

	@staticmethod
	def get_by_id(interface_id):
		"""根据ID获取接口"""
		with get_connection() as conn:
			return conn.execute(
				"SELECT * FROM api_interfaces WHERE id = ?",
				(interface_id,)
			).fetchone()

	@staticmethod
	def get_enabled():
		"""获取所有已启用的接口"""
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT * FROM api_interfaces WHERE is_enabled = 1 ORDER BY sort_order ASC, id DESC"
			).fetchall()
			return rows

	@staticmethod
	def create(name, description, api_url, api_method="GET", api_headers=None,
			   api_params=None, api_body=None, response_type="json",
			   card_type=None, is_enabled=1, sort_order=0):
		"""创建接口"""
		try:
			with get_connection() as conn:
				cursor = conn.execute(
					"""
					INSERT INTO api_interfaces
					(name, description, api_url, api_method, api_headers, api_params, api_body,
					 response_type, card_type, is_enabled, sort_order)
					VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
					""",
					(name, description, api_url, api_method, api_headers, api_params, api_body,
					 response_type, card_type, is_enabled, sort_order)
				)
				return cursor.lastrowid
		except sqlite3.IntegrityError:
			return None

	@staticmethod
	def update(interface_id, name=None, description=None, api_url=None, api_method=None,
			   api_headers=None, api_params=None, api_body=None, response_type=None,
			   card_type=None, is_enabled=None, sort_order=None):
		"""更新接口"""
		try:
			with get_connection() as conn:
				updates = []
				params = []

				if name is not None:
					updates.append("name = ?")
					params.append(name)
				if description is not None:
					updates.append("description = ?")
					params.append(description)
				if api_url is not None:
					updates.append("api_url = ?")
					params.append(api_url)
				if api_method is not None:
					updates.append("api_method = ?")
					params.append(api_method)
				if api_headers is not None:
					updates.append("api_headers = ?")
					params.append(api_headers)
				if api_params is not None:
					updates.append("api_params = ?")
					params.append(api_params)
				if api_body is not None:
					updates.append("api_body = ?")
					params.append(api_body)
				if response_type is not None:
					updates.append("response_type = ?")
					params.append(response_type)
				if card_type is not None:
					updates.append("card_type = ?")
					params.append(card_type)
				if is_enabled is not None:
					updates.append("is_enabled = ?")
					params.append(is_enabled)
				if sort_order is not None:
					updates.append("sort_order = ?")
					params.append(sort_order)

				if updates:
					updates.append("updated_at = datetime('now','localtime')")
					params.append(interface_id)
					conn.execute(
						f"UPDATE api_interfaces SET {', '.join(updates)} WHERE id = ?",
						params
					)
				return True
		except sqlite3.IntegrityError:
			return False

	@staticmethod
	def delete(interface_id):
		"""删除接口"""
		with get_connection() as conn:
			conn.execute("DELETE FROM api_interfaces WHERE id = ?", (interface_id,))
		return True

	@staticmethod
	def toggle_enabled(interface_id, is_enabled):
		"""启用/禁用接口"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE api_interfaces SET is_enabled = ?, updated_at = datetime('now','localtime') WHERE id = ?",
				(is_enabled, interface_id)
			)
		return True
