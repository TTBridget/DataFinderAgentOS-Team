import tornado.web
import time
from collections import defaultdict

from app.controllers.base import BaseHandler
from app.models.user import UserRepository


class LoginHandler(BaseHandler):
	
	# 基于 IP 的内存速率限制：每个 IP 每分钟最多 10 次 POST 请求（用户侧相对宽松）
	_RATE_LIMIT_WINDOW = 60
	_RATE_LIMIT_MAX = 10
	_rate_limit_records = defaultdict(list)
	
	@classmethod
	def _check_rate_limit(cls, ip: str) -> bool:
		"""检查 IP 是否超过速率限制，返回 True 表示允许请求"""
		now = time.time()
		records = cls._rate_limit_records[ip]
		records[:] = [t for t in records if now - t < cls._RATE_LIMIT_WINDOW]
		if len(records) >= cls._RATE_LIMIT_MAX:
			return False
		records.append(now)
		return True

	def get(self):
		if self.current_user:
			self.redirect("/index")
			return
		self.render("login.html", title="用户登录", error=None)

	def post(self):
		# IP 速率限制检查
		remote_ip = self.request.remote_ip or "unknown"
		if not LoginHandler._check_rate_limit(remote_ip):
			self.set_status(429)
			return self.render("login.html", title="用户登录", error="登录尝试过于频繁，请稍后再试")

		username = self.get_body_argument("username", "").strip()
		password = self.get_body_argument("password", "")
		if not username or not password:
			self.set_status(400)
			return self.render("login.html", title="用户登录", error="请输入用户名和密码")

		valid, reason = UserRepository.verify_user(username, password)
		if valid:
			self.set_secure_cookie(
				"username",
				username,
				httponly=True,
				samesite="Lax",
				secure=self.request.protocol == "https",
			)
			self.redirect("/index")
		else:
			# 统一返回模糊错误信息，防止用户名枚举
			self.set_status(401)
			return self.render("login.html", title="用户登录", error="用户名或密码不正确")


class RegisterHandler(BaseHandler):
	"""前台用户注册"""
	
	def get(self):
		if self.current_user:
			self.redirect("/index")
			return
		self.render("register.html", title="用户注册", error=None)
	
	def post(self):
		username = self.get_body_argument("username", "").strip()
		password = self.get_body_argument("password", "")
		confirm_password = self.get_body_argument("confirm_password", "")
		
		# 基础校验
		if not username or not password:
			self.set_status(400)
			return self.render("register.html", title="用户注册", error="用户名和密码不能为空")
		
		if len(username) < 3 or len(username) > 32:
			self.set_status(400)
			return self.render("register.html", title="用户注册", error="用户名长度需在 3-32 个字符之间")
		
		if len(password) < 6 or len(password) > 64:
			self.set_status(400)
			return self.render("register.html", title="用户注册", error="密码长度需在 6-64 个字符之间")
		
		if password != confirm_password:
			self.set_status(400)
			return self.render("register.html", title="用户注册", error="两次输入的密码不一致")
		
		# 创建普通用户，默认角色 role_id=1
		success = UserRepository.create_user(username, password, role_id=1)
		if not success:
			self.set_status(400)
			return self.render("register.html", title="用户注册", error="用户名已存在")
		
		# 注册成功后自动登录
		self.set_secure_cookie(
			"username",
			username,
			httponly=True,
			samesite="Lax",
			secure=self.request.protocol == "https",
		)
		self.redirect("/index")


class LogoutHandler(BaseHandler):
	@tornado.web.authenticated
	def post(self):
		self.clear_cookie("username")
		self.redirect("/")
