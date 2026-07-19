"""
user.py 是数据库database/finderos.db中users表的仓储对象
user.py主要实现与数据库表有关的操作：新增/修改/删除/查询等
采用Repository模式：把SQL+数据访问集中到一个类里，controller只调用方法
"""

import hashlib
import secrets
import sqlite3
import datetime

from app.models.db import get_connection

# 暴力破解防护配置
MAX_FAILED_ATTEMPTS = 5         # 连续失败次数阈值
LOCK_DURATION_MINUTES = 15      # 锁定时长（分钟）

def _hash_password(password:str,salt:bytes) -> str:
	#将明文相间+salt计算为稳定的hash
	k = hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),salt,100_000)
	return k.hex()

class UserRepository:
	#用户数据访问类（面向Controller提供方法）
	# @staticmethod 修饰可以保持方法的简洁，目的是不引入依赖注入，不维护链接池
	@staticmethod
	def create_user(username:str,password:str, role_id=1) -> bool:
		salt = secrets.token_bytes(16)
		password_hash = _hash_password(password,salt)
		try:
			with get_connection() as conn:
				conn.execute(
					"insert into users (username,password_hash,salt,role_id) values (?,?,?,?)",
					(username,password_hash,salt.hex(),role_id)
				)
				#问号的作用是参数占位符，用来代替语句中动态填入的值，避免出现注入问题，允许自动转换转义，隔离参数
			return True
		except sqlite3.IntegrityError:
			return False

	@staticmethod
	def get_user_by_username(username:str):
		with get_connection() as conn:
			row = conn.execute(
				"select * from users where username=?", 
				(username,)
			).fetchone()
		return row
	
	@staticmethod
	def get_user_by_id(user_id):
		"""根据ID获取用户"""
		with get_connection() as conn:
			row = conn.execute(
				"SELECT u.*, r.name as role_name FROM users u LEFT JOIN roles r ON u.role_id = r.id WHERE u.id = ?",
				(user_id,)
			).fetchone()
		return row

	@staticmethod
	def verify_user(username:str,password:str) -> tuple:
		"""
		验证用户凭证，返回 (valid: bool, reason: str)
		reason 可能为：'ok' | 'not_found' | 'locked' | 'wrong_password'
		调用方应统一返回"用户名或密码不正确"，不区分具体原因。
		"""
		row = UserRepository.get_user_by_username(username)
		if not row:
			return (False, "not_found")

		# 检查用户是否被禁用
		if "is_disabled" in row and row["is_disabled"] == 1:
			return (False, "not_found")  # 对外不暴露禁用状态

		# 检查账户是否被锁定
		lock_until = row["lock_until"] if "lock_until" in row.keys() else None
		if lock_until:
			try:
				lock_time = datetime.datetime.strptime(lock_until, "%Y-%m-%d %H:%M:%S")
				if lock_time > datetime.datetime.now():
					return (False, "locked")
			except (ValueError, TypeError):
				pass  # 格式异常时忽略锁定

		salt = bytes.fromhex(row["salt"])
		password_match = _hash_password(password, salt) == row["password_hash"]

		if password_match:
			# 登录成功：重置失败计数
			UserRepository._reset_failed_attempts(username)
			return (True, "ok")
		else:
			# 登录失败：递增失败计数并检查是否需锁定
			UserRepository._record_failed_attempt(username)
			return (False, "wrong_password")

	@staticmethod
	def _record_failed_attempt(username: str):
		"""记录一次失败尝试，超过阈值则锁定账户"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE users SET failed_attempts = COALESCE(failed_attempts, 0) + 1 WHERE username = ?",
				(username,)
			)
			row = conn.execute(
				"SELECT failed_attempts FROM users WHERE username = ?",
				(username,)
			).fetchone()
			if row and row["failed_attempts"] >= MAX_FAILED_ATTEMPTS:
				lock_until = (datetime.datetime.now() + datetime.timedelta(minutes=LOCK_DURATION_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
				conn.execute(
					"UPDATE users SET lock_until = ? WHERE username = ?",
					(lock_until, username)
				)

	@staticmethod
	def _reset_failed_attempts(username: str):
		"""重置失败计数和锁定状态"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE users SET failed_attempts = 0, lock_until = NULL WHERE username = ?",
				(username,)
			)
	
	@staticmethod
	def get_all_users(page=1, page_size=20, search_keyword=None):
		"""获取所有用户（带分页和搜索）"""
		offset = (page - 1) * page_size
		
		with get_connection() as conn:
			query = "SELECT u.*, r.name as role_name FROM users u LEFT JOIN roles r ON u.role_id = r.id"
			params = []
			
			if search_keyword:
				query += " WHERE u.username LIKE ?"
				params.append(f"%{search_keyword}%")
			
			query += " ORDER BY u.id DESC LIMIT ? OFFSET ?"
			params.extend([page_size, offset])
			
			rows = conn.execute(query, params).fetchall()
			
			# 获取总数
			count_query = "SELECT COUNT(*) as total FROM users"
			count_params = []
			if search_keyword:
				count_query += " WHERE username LIKE ?"
				count_params.append(f"%{search_keyword}%")
			
			total = conn.execute(count_query, count_params).fetchone()["total"]
			
			return {"items": rows, "total": total, "page": page, "page_size": page_size}
	
	@staticmethod
	def update_user(user_id, username=None, password=None, role_id=None):
		"""更新用户"""
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
					params.append(user_id)
					
					conn.execute(
						f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
						params
					)
				return True
		except sqlite3.IntegrityError:
			return False
	
	@staticmethod
	def delete_user(user_id):
		"""删除用户"""
		with get_connection() as conn:
			conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
		return True
	
	@staticmethod
	def toggle_user_disabled(user_id, is_disabled):
		"""启用/禁用用户"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE users SET is_disabled = ?, updated_at = datetime('now','localtime') WHERE id = ?",
				(is_disabled, user_id)
			)
		return True


