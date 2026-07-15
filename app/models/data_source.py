"""
data_source.py - 数据源/瞭源管理 Repository
"""
from .db import get_connection
import json


class DataSourceRepository:
	@staticmethod
	def get_all(page=1, per_page=20, search=""):
		offset = (page - 1) * per_page
		with get_connection() as conn:
			if search:
				sql = "SELECT * FROM data_sources WHERE name LIKE ? ORDER BY sort_order, id DESC LIMIT ? OFFSET ?"
				rows = conn.execute(sql, (f"%{search}%", per_page, offset)).fetchall()
				count_sql = "SELECT COUNT(*) as total FROM data_sources WHERE name LIKE ?"
				total = conn.execute(count_sql, (f"%{search}%",)).fetchone()["total"]
			else:
				sql = "SELECT * FROM data_sources ORDER BY sort_order, id DESC LIMIT ? OFFSET ?"
				rows = conn.execute(sql, (per_page, offset)).fetchall()
				count_sql = "SELECT COUNT(*) as total FROM data_sources"
				total = conn.execute(count_sql).fetchone()["total"]
			
			return {"items": rows, "total": total}
	
	@staticmethod
	def get_enabled():
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT * FROM data_sources WHERE is_enabled = 1 ORDER BY sort_order, id"
			).fetchall()
			return rows
	
	@staticmethod
	def get_by_id(id):
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM data_sources WHERE id = ?", (id,)).fetchone()
			return row
	
	@staticmethod
	def create(name, description, base_url, path_template, headers, is_enabled=1, sort_order=0):
		try:
			with get_connection() as conn:
				cursor = conn.execute(
					"""
					INSERT INTO data_sources (name, description, base_url, path_template, headers, is_enabled, sort_order)
					VALUES (?, ?, ?, ?, ?, ?, ?)
					""",
					(name, description, base_url, path_template, headers, is_enabled, sort_order)
				)
				return cursor.lastrowid
		except Exception as e:
			print(f"创建数据源错误: {e}")
			return None
	
	@staticmethod
	def update(id, name=None, description=None, base_url=None, path_template=None, headers=None, is_enabled=None, sort_order=None):
		with get_connection() as conn:
			set_clause = []
			params = []
			
			if name is not None:
				set_clause.append("name = ?")
				params.append(name)
			if description is not None:
				set_clause.append("description = ?")
				params.append(description)
			if base_url is not None:
				set_clause.append("base_url = ?")
				params.append(base_url)
			if path_template is not None:
				set_clause.append("path_template = ?")
				params.append(path_template)
			if headers is not None:
				set_clause.append("headers = ?")
				params.append(headers)
			if is_enabled is not None:
				set_clause.append("is_enabled = ?")
				params.append(is_enabled)
			if sort_order is not None:
				set_clause.append("sort_order = ?")
				params.append(sort_order)
			
			if not set_clause:
				return False
			
			set_clause.append("updated_at = datetime('now','localtime')")
			params.append(id)
			
			sql = f"UPDATE data_sources SET {', '.join(set_clause)} WHERE id = ?"
			conn.execute(sql, params)
			return True
	
	@staticmethod
	def delete(id):
		with get_connection() as conn:
			conn.execute("DELETE FROM data_sources WHERE id = ?", (id,))
			return True
