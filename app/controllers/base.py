"""
Controller 公共基础类（BaseHandler）
在tornado中，
-每一个URL对应一个RequestHandler（可以理解成是一个Controller）
-RequestHandler中提供常用的请求和响应逻辑，同时支持重写生命周期内的方法
-get/post/put/delete...

本BaseHandler主要是提供统一的登录态获得逻辑，供其他Handler继承使用
"""

import tornado.web
import traceback
from app.models.admin import AdminRepository
from app.models.user import UserRepository


class BaseHandler(tornado.web.RequestHandler):
	def get_current_user(self):
		username = self.get_secure_cookie("username")
		if not username:
			return None
		username = username.decode("utf-8")
		# 每次请求时验证账户是否仍有效（未被禁用）
		user = UserRepository.get_user_by_username(username)
		if not user or user["is_disabled"] == 1:
			return None
		return username

	def write_error(self, status_code, **kwargs):
		"""统一错误处理：不向客户端暴露堆栈跟踪"""
		exc_info = kwargs.get("exc_info")
		if exc_info:
			traceback.print_exception(*exc_info)
		self.set_status(status_code)
		self.finish({"code": 1, "msg": "服务器内部错误"})


class AdminBaseHandler(tornado.web.RequestHandler):
	# 子类覆盖此属性以指定所需功能代码（例如 "user", "role", "watch"）
	REQUIRED_FUNCTION = None

	def get_current_user(self):
		username = self.get_secure_cookie("admin_username")
		if not username:
			return None
		username = username.decode("utf-8")
		# 每次请求时验证账户是否仍有效（未被禁用）
		admin = AdminRepository.get_admin_by_username(username)
		if not admin or admin["is_disabled"] == 1:
			return None
		return username

	def get_login_url(self):
		"""后台未登录时统一跳转到后台登录页"""
		return "/admin/login"

	def write_error(self, status_code, **kwargs):
		"""统一错误处理：不向客户端暴露堆栈跟踪"""
		exc_info = kwargs.get("exc_info")
		if exc_info:
			traceback.print_exception(*exc_info)
		self.set_status(status_code)
		self.finish({"code": 1, "msg": "服务器内部错误"})

	def authorize(self, function_code=None):
		"""
		RBAC 权限检查：验证当前管理员是否拥有指定功能权限。
		
		如果 function_code 为 None，则使用类属性 REQUIRED_FUNCTION。
		超级管理员 (is_super_admin=1) 自动通过所有权限检查。
		
		Raises:
			tornado.web.HTTPError(403) 如果无权限
		"""
		code = function_code or self.REQUIRED_FUNCTION
		if code is None:
			return  # 无 REQUIRED_FUNCTION 的 Handler 不限制访问

		username = self.current_user
		if not username:
			raise tornado.web.HTTPError(403, reason="未登录")

		# 超级管理员拥有所有权限
		if AdminRepository.is_super_admin(username):
			return

		# 检查角色权限
		allowed_codes = AdminRepository.get_admin_function_codes(username)
		if code not in allowed_codes:
			raise tornado.web.HTTPError(403, reason="无此功能权限")

	def prepare(self):
		"""
		在每次请求处理前自动执行权限检查。
		子类设置 REQUIRED_FUNCTION 即可自动拦截无权限请求。
		"""
		super().prepare()
		self.authorize()