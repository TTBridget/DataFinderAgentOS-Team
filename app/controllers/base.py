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


class BaseHandler(tornado.web.RequestHandler):
	def get_current_user(self):
		username = self.get_secure_cookie("username")
		if not username:
			return None
		return username.decode("utf-8")

	def write_error(self, status_code, **kwargs):
		"""统一错误处理：不向客户端暴露堆栈跟踪"""
		exc_info = kwargs.get("exc_info")
		if exc_info:
			traceback.print_exception(*exc_info)
		self.set_status(status_code)
		self.finish({"code": 1, "msg": "服务器内部错误"})


class AdminBaseHandler(tornado.web.RequestHandler):
	def get_current_user(self):
		username = self.get_secure_cookie("admin_username")
		if not username:
			return None
		return username.decode("utf-8")

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