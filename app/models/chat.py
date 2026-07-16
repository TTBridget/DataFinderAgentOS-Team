"""
chat.py - 前台对话数据访问层
管理用户对话会话和消息记录
"""

from app.models.db import get_connection


class ChatSessionRepository:
	"""对话会话仓储"""

	@staticmethod
	def get_all_sessions(page=1, page_size=10, search_keyword=None, user_id=None):
		"""后台管理：获取所有会话列表（含消息数），支持搜索"""
		offset = (page - 1) * page_size
		with get_connection() as conn:
			query = """
				SELECT cs.*, u.username as username,
				       (SELECT COUNT(*) FROM chat_messages cm WHERE cm.session_id = cs.id) as message_count
				FROM chat_sessions cs
				LEFT JOIN users u ON cs.user_id = u.id
			"""
			count_query = "SELECT COUNT(*) as total FROM chat_sessions cs"
			params = []
			count_params = []

			conditions = []
			if user_id:
				conditions.append("cs.user_id = ?")
				params.append(user_id)
				count_params.append(user_id)

			if search_keyword:
				conditions.append("(cs.title LIKE ? OR u.username LIKE ?)")
				params.extend([f"%{search_keyword}%", f"%{search_keyword}%"])
				count_params.extend([f"%{search_keyword}%", f"%{search_keyword}%"])

			if conditions:
				where = " WHERE " + " AND ".join(conditions)
				query += where
				count_query += where

			query += " ORDER BY cs.updated_at DESC LIMIT ? OFFSET ?"
			params.extend([page_size, offset])

			rows = conn.execute(query, params).fetchall()
			total = conn.execute(count_query, count_params).fetchone()["total"]
			return {"items": rows, "total": total, "page": page, "page_size": page_size}

	@staticmethod
	def admin_delete(session_id):
		"""后台管理：删除会话及其消息（不校验用户归属）"""
		with get_connection() as conn:
			conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
			conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
			return True

	@staticmethod
	def create(user_id, title=None, model_id=None, employee_id=None):
		"""创建新会话"""
		with get_connection() as conn:
			cursor = conn.execute(
				"INSERT INTO chat_sessions (user_id, title, model_id, employee_id) VALUES (?, ?, ?, ?)",
				(user_id, title or "新对话", model_id, employee_id)
			)
			return cursor.lastrowid
	
	@staticmethod
	def get_by_id(session_id):
		"""根据ID获取会话"""
		with get_connection() as conn:
			return conn.execute(
				"SELECT * FROM chat_sessions WHERE id = ?",
				(session_id,)
			).fetchone()
	
	@staticmethod
	def get_user_sessions(user_id, page=1, page_size=50):
		"""获取用户的会话列表，置顶会话优先排在最前"""
		offset = (page - 1) * page_size
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY is_pinned DESC, updated_at DESC LIMIT ? OFFSET ?",
				(user_id, page_size, offset)
			).fetchall()
			
			total = conn.execute(
				"SELECT COUNT(*) as total FROM chat_sessions WHERE user_id = ?",
				(user_id,)
			).fetchone()["total"]
			
			return {"items": rows, "total": total, "page": page, "page_size": page_size}
	
	@staticmethod
	def update_pinned(session_id, user_id, is_pinned):
		"""更新会话置顶状态"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE chat_sessions SET is_pinned = ?, updated_at = datetime('now','localtime') WHERE id = ? AND user_id = ?",
				(1 if is_pinned else 0, session_id, user_id)
			)
			return True
	
	@staticmethod
	def update_title(session_id, title):
		"""更新会话标题"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE chat_sessions SET title = ?, updated_at = datetime('now','localtime') WHERE id = ?",
				(title, session_id)
			)
			return True
	
	@staticmethod
	def update_model(session_id, model_id):
		"""更新会话当前使用的模型"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE chat_sessions SET model_id = ?, updated_at = datetime('now','localtime') WHERE id = ?",
				(model_id, session_id)
			)
			return True
	
	@staticmethod
	def update_employee(session_id, employee_id):
		"""更新会话当前使用的数字员工"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE chat_sessions SET employee_id = ?, updated_at = datetime('now','localtime') WHERE id = ?",
				(employee_id, session_id)
			)
			return True
	
	@staticmethod
	def touch(session_id):
		"""更新会话更新时间"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE chat_sessions SET updated_at = datetime('now','localtime') WHERE id = ?",
				(session_id,)
			)
			return True
	
	@staticmethod
	def delete(session_id, user_id):
		"""删除会话及其消息"""
		with get_connection() as conn:
			# 先删除消息
			conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
			# 再删除会话，确保属于当前用户
			conn.execute(
				"DELETE FROM chat_sessions WHERE id = ? AND user_id = ?",
				(session_id, user_id)
			)
			return True


class ChatMessageRepository:
	"""对话消息仓储"""

	@staticmethod
	def get_all_messages(page=1, page_size=10, search_keyword=None, session_id=None, user_id=None):
		"""后台管理：获取所有对话消息，支持搜索"""
		offset = (page - 1) * page_size
		with get_connection() as conn:
			query = """
				SELECT cm.*, cs.title as session_title, u.username as username
				FROM chat_messages cm
				LEFT JOIN chat_sessions cs ON cm.session_id = cs.id
				LEFT JOIN users u ON cs.user_id = u.id
			"""
			count_query = "SELECT COUNT(*) as total FROM chat_messages cm"
			params = []
			count_params = []

			conditions = []
			if session_id:
				conditions.append("cm.session_id = ?")
				params.append(session_id)
				count_params.append(session_id)

			if user_id:
				conditions.append("cs.user_id = ?")
				params.append(user_id)
				count_params.append(user_id)

			if search_keyword:
				conditions.append("(cm.content LIKE ? OR cs.title LIKE ? OR u.username LIKE ?)")
				params.extend([f"%{search_keyword}%", f"%{search_keyword}%", f"%{search_keyword}%"])
				count_params.extend([f"%{search_keyword}%", f"%{search_keyword}%", f"%{search_keyword}%"])

			if conditions:
				where = " WHERE " + " AND ".join(conditions)
				query += where
				count_query += where

			query += " ORDER BY cm.created_at DESC, cm.id DESC LIMIT ? OFFSET ?"
			params.extend([page_size, offset])

			rows = conn.execute(query, params).fetchall()
			total = conn.execute(count_query, count_params).fetchone()["total"]
			return {"items": rows, "total": total, "page": page, "page_size": page_size}

	@staticmethod
	def admin_delete(message_id):
		"""后台管理：删除单条消息"""
		with get_connection() as conn:
			conn.execute("DELETE FROM chat_messages WHERE id = ?", (message_id,))
			return True

	@staticmethod
	def create(session_id, role, content, model_id=None, employee_id=None, response_time=None, token_count=None, card_type=None, card_data=None):
		"""创建消息"""
		with get_connection() as conn:
			cursor = conn.execute(
				"INSERT INTO chat_messages (session_id, role, content, model_id, employee_id, response_time, token_count, card_type, card_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
				(session_id, role, content, model_id, employee_id, response_time, token_count, card_type, card_data)
			)
			return cursor.lastrowid
	
	@staticmethod
	def get_session_messages(session_id, user_id=None):
		"""获取会话的所有消息，可选验证用户权限"""
		with get_connection() as conn:
			if user_id is not None:
				# 验证会话属于该用户
				session = conn.execute(
					"SELECT 1 FROM chat_sessions WHERE id = ? AND user_id = ?",
					(session_id, user_id)
				).fetchone()
				if not session:
					return []
			
			rows = conn.execute(
				"SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC, id ASC",
				(session_id,)
			).fetchall()
			return rows
	
	@staticmethod
	def update_content(message_id, content):
		"""更新消息内容（用于流式响应完成后更新完整内容）"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE chat_messages SET content = ? WHERE id = ?",
				(content, message_id)
			)
			return True
	
	@staticmethod
	def get_by_id(message_id):
		"""根据ID获取消息"""
		with get_connection() as conn:
			return conn.execute(
				"SELECT * FROM chat_messages WHERE id = ?",
				(message_id,)
			).fetchone()
	
	@staticmethod
	def update_content_and_mark_edited(message_id, content):
		"""更新用户消息内容并标记为已编辑"""
		with get_connection() as conn:
			conn.execute(
				"UPDATE chat_messages SET content = ?, is_edited = 1 WHERE id = ?",
				(content, message_id)
			)
			return True
	
	@staticmethod
	def truncate_after(message_id, session_id):
		"""删除指定消息之后的所有消息（用于编辑重发时清理旧回复）"""
		with get_connection() as conn:
			# 找到目标消息的创建时间
			msg = conn.execute(
				"SELECT created_at FROM chat_messages WHERE id = ? AND session_id = ?",
				(message_id, session_id)
			).fetchone()
			if not msg:
				return 0
			cursor = conn.execute(
				"DELETE FROM chat_messages WHERE session_id = ? AND (created_at > ? OR (created_at = ? AND id > ?))",
				(session_id, msg["created_at"], msg["created_at"], message_id)
			)
			return cursor.rowcount
