import tornado.web

from app.controllers.base import BaseHandler
from app.models.user import UserRepository


class LoginHandler(BaseHandler):
	def get(self):
		if self.current_user:
			self.redirect("/index")
			return
		self.render("login.html", title="用户登录", error=None)

	def post(self):
		username = self.get_body_argument("username", "").strip()
		password = self.get_body_argument("password", "")
		if not username or not password:
			self.set_status(400)
			return self.render("login.html", title="用户登录", error="请输入用户名和密码")

		if not UserRepository.verify_user(username, password):
			self.set_status(401)
			return self.render("login.html", title="用户登录", error="用户名或密码不正确")

		self.set_secure_cookie("username", username)
		self.redirect("/index")


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
		self.set_secure_cookie("username", username)
		self.redirect("/index")


class LogoutHandler(BaseHandler):
	@tornado.web.authenticated
	def post(self):
		self.clear_cookie("username")
		self.redirect("/")
