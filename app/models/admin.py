"""
admin.py 是数据库database/finderos.db中admins表的仓储对象
admin.py主要实现与数据库表有关的操作：新增/修改/删除/查询等
采用Repository模式：把SQL+数据访问集中到一个类里，controller只调用方法
"""

import hashlib
import secrets
import sqlite3

from app.models.db import get_connection

def _hash_password(password:str,salt:bytes) -> str:
	#将明文相间+salt计算为稳定的hash
	k = hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),salt,100_000)
	return k.hex()

class AdminRepository:
	#管理员数据访问类（面向Controller提供方法）
	# @staticmethod 修饰可以保持方法的简洁，目的是不引入依赖注入，不维护链接池
	@staticmethod
	def create_admin(username:str,password:str,role_id=2) -> bool:
		salt = secrets.token_bytes(16)
		password_hash = _hash_password(password,salt)
		try:
			with get_connection() as conn:
				conn.execute(
					"insert into admins (username,password_hash,salt,role_id) values (?,?,?,?)",
					(username,password_hash,salt.hex(),role_id)
				)
			return True
		except sqlite3.IntegrityError:
			return False

	@staticmethod
	def get_admin_by_username(username:str):
		with get_connection() as conn:
			row = conn.execute(
				"select * from admins where username=?", 
				(username,)
			).fetchone()
		return row
	
	@staticmethod
	def get_admin_by_id(admin_id):
		"""根据ID获取管理员"""
		with get_connection() as conn:
			row = conn.execute(
				"SELECT a.*, r.name as role_name FROM admins a LEFT JOIN roles r ON a.role_id = r.id WHERE a.id = ?",
				(admin_id,)
			).fetchone()
		return row

	@staticmethod
	def verify_admin(username:str,password:str) -> bool:
		row = AdminRepository.get_admin_by_username(username)
		#先看用户名是否存在，如果用户名不存在，则后面验证没有必要
		if not row:
			return False
		# 检查管理员是否被禁用（添加兼容性处理）
		if "is_disabled" in row and row["is_disabled"] == 1:
			return False
		salt = bytes.fromhex(row["salt"])
		return _hash_password(password,salt) == row["password_hash"]
	
	@staticmethod
	def get_all_admins(page=1, page_size=20, search_keyword=None):
		"""获取所有管理员（带分页和搜索）"""
		offset = (page - 1) * page_size
		
		with get_connection() as conn:
			query = "SELECT a.*, r.name as role_name FROM admins a LEFT JOIN roles r ON a.role_id = r.id"
			params = []
			
			if search_keyword:
				query += " WHERE a.username LIKE ?"
				params.append(f"%{search_keyword}%")
			
			query += " ORDER BY a.id DESC LIMIT ? OFFSET ?"
			params.extend([page_size, offset])
			
			rows = conn.execute(query, params).fetchall()
			
			# 获取总数
			count_query = "SELECT COUNT(*) as total FROM admins"
			count_params = []
			if search_keyword:
				count_query += " WHERE username LIKE ?"
				count_params.append(f"%{search_keyword}%")
			
			total = conn.execute(count_query, count_params).fetchone()["total"]
			
			return {"items": rows, "total": total, "page": page, "page_size": page_size}
	
	@staticmethod
	def update_admin(admin_id, username=None, password=None, role_id=None):
		"""更新管理员"""
		try:
			with get_connection() as conn:
				updates = []
				params = []
				
				if username is not None:
					updates.append("username = ?")
					params.append(username)
				
				if password is not None:
					salt = secrets.token_bytes(16)
					password_hash = _hash_password(password, salt)
					updates.append("password_hash = ?")
					updates.append("salt = ?")
					params.extend([password_hash, salt.hex()])
				
				if role_id is not None:
					updates.append("role_id = ?")
					params.append(role_id)
				
				if updates:
					updates.append("updated_at = datetime('now','localtime')")
					params.append(admin_id)
					
					conn.execute(
						f"UPDATE admins SET {', '.join(updates)} WHERE id = ?",
						params
					)
				return True
		except sqlite3.IntegrityError:
			return False
	
	@staticmethod
	def delete_admin(admin_id):
		"""删除管理员"""
		with get_connection() as conn:
			conn.execute("DELETE FROM admins WHERE id = ?", (admin_id,))
		return True
	
	@staticmethod
	def toggle_admin_disabled(admin_id, is_disabled):
		"""启用/禁用管理员"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE admins SET is_disabled = ?, updated_at = datetime('now','localtime') WHERE id = ?",
				(is_disabled, admin_id)
			)
		return True

