"""
后台管理控制器
"""

import tornado.web
import datetime
import json
from concurrent.futures import ThreadPoolExecutor
from app.controllers.base import BaseHandler, AdminBaseHandler
from app.models.admin import AdminRepository
from app.models.user import UserRepository
from app.models.role import RoleRepository
from app.models.function import FunctionRepository
from app.models.menu import MenuRepository
from app.models.data_source import DataSourceRepository
from app.models.collected_data import CollectedDataRepository
from app.models.data_warehouse import DataWarehouseRepository
from app.models.digital_employee import (
    DigitalEmployeeRepository,
    save_employee_nd_files,
    list_employee_nd_files,
)
from app.models.ai_model import AiModelRepository
from app.models.api_interface import ApiInterfaceRepository
from app.models.skill import SkillRepository, SkillEngine
from app.models.chat import ChatSessionRepository, ChatMessageRepository
import tornado.gen
import urllib.request
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from app.utils.security import safe_int, safe_float, validate_llm_base_url, validate_http_url, validate_employee_api_url

# 深度采集后台线程池，限制并发线程数防止 DoS
_DEEP_COLLECT_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="deep_collect")
_MAX_BATCH_COLLECT_SIZE = 50


def deep_collect_with_crawl4ai(url):
	"""使用 crawl4ai 进行深度采集"""
	import asyncio
	from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
	from crawl4ai.content_filter_strategy import PruningContentFilter
	from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

	async def do_crawl():
		browser_cfg = BrowserConfig(headless=True, verbose=False)
		run_cfg = CrawlerRunConfig(
			markdown_generator=DefaultMarkdownGenerator(
				content_filter=PruningContentFilter(threshold=0.48),
				options={"ignore_links": True}
			),
			exclude_external_links=True,
			remove_overlay_elements=True,
			process_iframes=True
		)
		async with AsyncWebCrawler(config=browser_cfg) as crawler:
			result = await crawler.arun(url, config=run_cfg)
			return result

	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	try:
		result = loop.run_until_complete(do_crawl())
	finally:
		loop.close()

	if result.success:
		title = result.metadata.get('title') if result.metadata else None
		content = result.markdown if result.markdown else None
		return {
			'title': title,
			'content': content,
			'success': True
		}
	else:
		error_msg = result.error_message if hasattr(result, 'error_message') else '未知错误'
		return {
			'title': None,
			'content': None,
			'success': False,
			'error': error_msg
		}


class AdminLoginHandler(BaseHandler):
	"""后台登录页"""
	
	def get(self):
		self.render("admin/login.html", title="后台管理登录", error=None)
	
	def post(self):
		username = self.get_body_argument("username", "")
		password = self.get_body_argument("password", "")
		
		if not username or not password:
			self.set_status(400)
			return self.render("admin/login.html", title="后台管理登录", error="请输入用户名和密码")
		
		# 使用 AdminRepository 验证管理员
		if AdminRepository.verify_admin(username, password):
			self.set_secure_cookie("admin_username", username)
			self.redirect("/admin/")
		else:
			self.set_status(401)
			return self.render("admin/login.html", title="后台管理登录", error="用户名或密码不正确")


class AdminLogoutHandler(BaseHandler):
	"""后台登出"""
	
	def post(self):
		self.clear_cookie("admin_username")
		self.redirect("/admin/login")


class AdminIndexHandler(AdminBaseHandler):
	"""后台首页"""
	
	@tornado.web.authenticated
	def get(self):
		login_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		self.render("admin/index.html", title="后台管理", username=self.current_user, login_time=login_time)


class UserManageHandler(AdminBaseHandler):
	"""用户管理"""
	
	@tornado.web.authenticated
	def get(self):
		page = safe_int(self.get_argument("page", 1), 1)
		search = self.get_argument("search", "")
		
		# 同时获取普通用户和管理员用户
		users_result = UserRepository.get_all_users(page, 20, search)
		admins_result = AdminRepository.get_all_admins(page, 20, search)
		
		# 合并用户列表，添加类型标识
		users = []
		for u in users_result["items"]:
			u_dict = dict(u)
			u_dict["user_type"] = "user"
			users.append(u_dict)
		
		for a in admins_result["items"]:
			a_dict = dict(a)
			a_dict["user_type"] = "admin"
			users.append(a_dict)
		
		# 获取角色列表
		roles = RoleRepository.get_all_roles(1, 100)
		
		self.render("admin/user.html", title="用户管理", 
				   users=users, 
				   roles=roles["items"],
				   username=self.current_user,
				   page=page,
				   total=users_result["total"] + admins_result["total"])
	
	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")
		user_type = self.get_body_argument("user_type", "user")
		user_id = self.get_body_argument("id", None)
		
		# 通用检查：是否操作超级管理员
		target_is_super_admin = False
		if user_id:
			if user_type == "admin":
				target_admin = AdminRepository.get_admin_by_id(safe_int(user_id, 0))
				if target_admin and target_admin["username"] == "admin":
					target_is_super_admin = True
		
		if action == "add":
			username = self.get_body_argument("username", "")
			password = self.get_body_argument("password", "")
			role_id = safe_int(self.get_body_argument("role_id", 1), 1)
			
			if username == "admin":
				self.write({"code": 1, "msg": "不能创建超级管理员账号"})
				return
			
			if user_type == "user":
				success = UserRepository.create_user(username, password, role_id)
			else:
				success = AdminRepository.create_admin(username, password, role_id)
			
			if success:
				self.write({"code": 0, "msg": "添加成功"})
			else:
				self.write({"code": 1, "msg": "用户名已存在"})
		
		elif action == "edit":
			# 检查是否操作超级管理员
			if target_is_super_admin:
				# 只有admin自己可以修改
				if self.current_user != "admin":
					self.write({"code": 1, "msg": "无权修改超级管理员"})
					return
				
				# admin自己只能修改密码，其他属性不能修改
				username = self.get_body_argument("username", None)
				password = self.get_body_argument("password", None)
				role_id = self.get_body_argument("role_id", None)
				
				# 如果是修改admin自己
				if username is not None or role_id is not None:
					# 检查是否只修改密码
					if username and username != "admin":
						self.write({"code": 1, "msg": "超级管理员用户名不可修改"})
						return
					if role_id is not None:
						self.write({"code": 1, "msg": "超级管理员角色不可修改"})
						return
				
				# 允许修改密码
				if password:
					AdminRepository.update_admin(safe_int(user_id, 0), password=password)
					self.write({"code": 0, "msg": "密码修改成功"})
				else:
					self.write({"code": 0, "msg": "未做任何修改"})
				return
			
			# 普通管理员修改逻辑
			username = self.get_body_argument("username", None)
			password = self.get_body_argument("password", None)
			role_id = self.get_body_argument("role_id", None)
			
			if role_id:
				role_id = safe_int(role_id, 1)
			
			if user_type == "user":
				success = UserRepository.update_user(safe_int(user_id, 0), username, password, role_id)
			else:
				success = AdminRepository.update_admin(safe_int(user_id, 0), username, password, role_id)
			
			if success:
				self.write({"code": 0, "msg": "更新成功"})
			else:
				self.write({"code": 1, "msg": "更新失败"})
		
		elif action == "delete":
			if target_is_super_admin:
				self.write({"code": 1, "msg": "不能删除超级管理员"})
				return
			
			if user_type == "user":
				UserRepository.delete_user(safe_int(user_id, 0))
			else:
				# 不能删除自己
				admin = AdminRepository.get_admin_by_id(safe_int(user_id, 0))
				if admin and admin["username"] == self.current_user:
					self.write({"code": 1, "msg": "不能删除当前登录的管理员"})
					return
				AdminRepository.delete_admin(safe_int(user_id, 0))
			self.write({"code": 0, "msg": "删除成功"})
		
		elif action == "toggle":
			if target_is_super_admin:
				self.write({"code": 1, "msg": "不能禁用/启用超级管理员"})
				return
			
			is_disabled = safe_int(self.get_body_argument("is_disabled", 0), 0)
			
			if user_type == "user":
				UserRepository.toggle_user_disabled(safe_int(user_id, 0), is_disabled)
			else:
				# 不能禁用自己
				admin = AdminRepository.get_admin_by_id(safe_int(user_id, 0))
				if admin and admin["username"] == self.current_user:
					self.write({"code": 1, "msg": "不能禁用当前登录的管理员"})
					return
				AdminRepository.toggle_admin_disabled(safe_int(user_id, 0), is_disabled)
			self.write({"code": 0, "msg": "操作成功"})


class RoleManageHandler(AdminBaseHandler):
	"""角色管理"""
	
	@tornado.web.authenticated
	def get(self):
		page = safe_int(self.get_argument("page", 1), 1)
		search = self.get_argument("search", "")
		
		result = RoleRepository.get_all_roles(page, 20, search)
		
		self.render("admin/role.html", title="角色管理", 
				   roles=result["items"],
				   page=page,
				   total=result["total"],
				   username=self.current_user)
	
	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")
		role_id = self.get_body_argument("id", None)
		
		if action == "add":
			name = self.get_body_argument("name", "")
			description = self.get_body_argument("description", "")
			
			role_id = RoleRepository.create_role(name, description)
			if role_id:
				self.write({"code": 0, "msg": "添加成功", "data": {"id": role_id}})
			else:
				self.write({"code": 1, "msg": "角色名已存在"})
		
		elif action == "edit":
			name = self.get_body_argument("name", "")
			description = self.get_body_argument("description", "")
			
			# 检查是否是系统角色
			role = RoleRepository.get_role_by_id(safe_int(role_id, 0))
			if role and role["is_system"] == 1:
				self.write({"code": 1, "msg": "系统角色不能修改"})
				return
			
			success = RoleRepository.update_role(safe_int(role_id, 0), name, description)
			if success:
				self.write({"code": 0, "msg": "更新成功"})
			else:
				self.write({"code": 1, "msg": "更新失败"})
		
		elif action == "delete":
			# 检查是否是系统角色
			role = RoleRepository.get_role_by_id(safe_int(role_id, 0))
			if role and role["is_system"] == 1:
				self.write({"code": 1, "msg": "系统角色不能删除"})
				return
			
			RoleRepository.delete_role(safe_int(role_id, 0))
			self.write({"code": 0, "msg": "删除成功"})
		
		elif action == "get_functions":
			# 获取功能树
			tree = RoleRepository.get_function_tree()
			assigned_ids = RoleRepository.get_assigned_function_ids(safe_int(role_id, 0))
			self.write({"code": 0, "data": {"tree": tree, "assigned": assigned_ids}})
		
		elif action == "assign_functions":
			function_ids_str = self.get_body_argument("function_ids", "")
			function_ids = [safe_int(x, 0) for x in function_ids_str.split(",") if x]
			function_ids = [fid for fid in function_ids if fid > 0]
			
			RoleRepository.assign_functions(safe_int(role_id, 0), function_ids)
			self.write({"code": 0, "msg": "分配成功"})


class FunctionManageHandler(AdminBaseHandler):
	"""功能管理"""
	
	@tornado.web.authenticated
	def get(self):
		page = safe_int(self.get_argument("page", 1), 1)
		search = self.get_argument("search", "")
		
		result = FunctionRepository.get_all_functions(page, 20, search)
		parents = FunctionRepository.get_parent_functions()
		
		self.render("admin/function.html", title="功能管理", 
				   functions=result["items"],
				   parents=parents,
				   page=page,
				   total=result["total"],
				   username=self.current_user)
	
	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")
		function_id = self.get_body_argument("id", None)
		
		if action == "add":
			name = self.get_body_argument("name", "")
			code = self.get_body_argument("code", "")
			icon = self.get_body_argument("icon", "")
			route = self.get_body_argument("route", "")
			parent_id = safe_int(self.get_body_argument("parent_id", 0), 0)
			sort_order = safe_int(self.get_body_argument("sort_order", 0), 0)
			
			func_id = FunctionRepository.create_function(name, code, icon, route, parent_id, sort_order)
			if func_id:
				self.write({"code": 0, "msg": "添加成功", "data": {"id": func_id}})
			else:
				self.write({"code": 1, "msg": "功能编码已存在"})
		
		elif action == "edit":
			name = self.get_body_argument("name", "")
			code = self.get_body_argument("code", "")
			icon = self.get_body_argument("icon", "")
			route = self.get_body_argument("route", "")
			parent_id = safe_int(self.get_body_argument("parent_id", 0), 0)
			sort_order = safe_int(self.get_body_argument("sort_order", 0), 0)
			
			success = FunctionRepository.update_function(safe_int(function_id, 0), name, code, icon, route, parent_id, sort_order)
			if success:
				self.write({"code": 0, "msg": "更新成功"})
			else:
				self.write({"code": 1, "msg": "更新失败"})
		
		elif action == "delete":
			success = FunctionRepository.delete_function(safe_int(function_id, 0))
			if success:
				self.write({"code": 0, "msg": "删除成功"})
			else:
				self.write({"code": 1, "msg": "该功能下有子功能，不能删除"})
		
		elif action == "toggle":
			is_disabled = safe_int(self.get_body_argument("is_disabled", 0), 0)
			FunctionRepository.toggle_function_disabled(safe_int(function_id, 0), is_disabled)
			self.write({"code": 0, "msg": "操作成功"})


class MenuManageHandler(AdminBaseHandler):
	"""菜单管理"""
	
	@tornado.web.authenticated
	def get(self):
		menus = MenuRepository.get_all_menus()
		self.render("admin/menu.html", title="菜单管理", 
			menus=menus,
			username=self.current_user)
	
	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")
		menu_id = self.get_body_argument("id", None)
		
		if action == "update_order":
			orders_str = self.get_body_argument("orders", "")
			orders = json.loads(orders_str)
			MenuRepository.update_menu_order(orders)
			self.write({"code": 0, "msg": "排序更新成功"})
		
		elif action == "toggle_visible":
			is_visible = safe_int(self.get_body_argument("is_visible", 1), 1)
			MenuRepository.update_menu(safe_int(menu_id, 0), is_visible=is_visible)
			self.write({"code": 0, "msg": "操作成功"})


class DataSourceManageHandler(AdminBaseHandler):
	"""瞭源管理"""
	
	@tornado.web.authenticated
	def get(self):
		page = safe_int(self.get_argument("page", 1), 1)
		search = self.get_argument("search", "")
		
		result = DataSourceRepository.get_all(page, 20, search)
		
		self.render("admin/data_source.html", title="瞭源管理", 
				   data_sources=result["items"],
				   page=page,
				   total=result["total"],
				   username=self.current_user)
	
	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")
		source_id = self.get_body_argument("id", None)
		
		if action == "add":
			name = self.get_body_argument("name", "")
			description = self.get_body_argument("description", "")
			base_url = self.get_body_argument("base_url", "")
			path_template = self.get_body_argument("path_template", "")
			headers = self.get_body_argument("headers", "{}")
			is_enabled = safe_int(self.get_body_argument("is_enabled", 1), 1)
			sort_order = safe_int(self.get_body_argument("sort_order", 0), 0)
			
			sid = DataSourceRepository.create(name, description, base_url, path_template, headers, is_enabled, sort_order)
			if sid:
				self.write({"code": 0, "msg": "添加成功", "data": {"id": sid}})
			else:
				self.write({"code": 1, "msg": "数据源名称已存在"})
		
		elif action == "edit":
			name = self.get_body_argument("name", None)
			description = self.get_body_argument("description", None)
			base_url = self.get_body_argument("base_url", None)
			path_template = self.get_body_argument("path_template", None)
			headers = self.get_body_argument("headers", None)
			is_enabled = self.get_body_argument("is_enabled", None)
			sort_order = self.get_body_argument("sort_order", None)
			
			params = {}
			if name is not None: params["name"] = name
			if description is not None: params["description"] = description
			if base_url is not None: params["base_url"] = base_url
			if path_template is not None: params["path_template"] = path_template
			if headers is not None: params["headers"] = headers
			if is_enabled is not None: params["is_enabled"] = safe_int(is_enabled, 1)
			if sort_order is not None: params["sort_order"] = safe_int(sort_order, 0)
			
			success = DataSourceRepository.update(safe_int(source_id, 0), **params)
			if success:
				self.write({"code": 0, "msg": "更新成功"})
			else:
				self.write({"code": 1, "msg": "更新失败"})
		
		elif action == "delete":
			DataSourceRepository.delete(safe_int(source_id, 0))
			self.write({"code": 0, "msg": "删除成功"})


class WatchManageHandler(AdminBaseHandler):
	"""瞭望中心"""
	
	@tornado.web.authenticated
	def get(self):
		page = safe_int(self.get_argument("page", 1), 1)
		keyword = self.get_argument("keyword", "")
		source_ids_str = self.get_argument("source_ids", "")
		
		# 获取已启用的数据源
		sources = DataSourceRepository.get_enabled()
		
		# 解析选中的瞭源ID；未传则默认展示全部
		if source_ids_str:
			selected_source_ids = [safe_int(x) for x in source_ids_str.split(",") if x]
		else:
			selected_source_ids = [s["id"] for s in sources]
		
		# 获取采集结果（按关键词+瞭源过滤）
		result = CollectedDataRepository.get_all(page, 12, keyword, selected_source_ids)
		
		self.render("admin/watch.html", title="瞭望中心", 
				   data_sources=sources,
				   collected_data=result["items"],
				   selected_source_ids=selected_source_ids,
				   keyword=keyword,
				   page=page,
				   total=result["total"],
				   username=self.current_user)
	
	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")
		
		if action == "collect":
			keyword = self.get_body_argument("keyword", "")
			source_ids_str = self.get_body_argument("source_ids", "")
			page = safe_int(self.get_body_argument("page", 0), 0)
			
			# 解析选中的源ID
			source_ids = [safe_int(x) for x in source_ids_str.split(",") if x]
			
			if not source_ids:
				self.write({"code": 1, "msg": "请至少选择一个数据源"})
				return
			
			total_collected = 0
			errors = []
			for sid in source_ids:
				source = DataSourceRepository.get_by_id(sid)
				if source:
					result = CollectedDataRepository.collect_from_source(source, keyword, page)
					if result["success"]:
						total_collected += result["count"]
					else:
						errors.append(f"{source['name']}: {result.get('error', '采集失败')}")
			
			msg = f"采集成功，共采集 {total_collected} 条数据"
			if errors:
				msg += "（" + "；".join(errors) + "）"
			
			self.write({"code": 0, "msg": msg, "count": total_collected})
		
		elif action == "clear":
			CollectedDataRepository.clear()
			self.write({"code": 0, "msg": "清空成功"})


class AiModelManageHandler(AdminBaseHandler):
	"""模型引擎管理"""
	
	@tornado.web.authenticated
	def get(self):
		page = safe_int(self.get_argument("page", 1), 1)
		search = self.get_argument("search", "")
		model_type = self.get_argument("model_type", "")
		
		result = AiModelRepository.get_all(page, 6, search, model_type)
		
		self.render("admin/ai_model.html", title="模型引擎", 
				   models=result["items"],
				   page=page,
				   total=result["total"],
				   search=search,
				   model_type=model_type,
				   username=self.current_user)
	
	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")
		model_id = self.get_body_argument("id", None)
		
		if action == "add":
			name = self.get_body_argument("name", "")
			provider = self.get_body_argument("provider", "")
			api_key = self.get_body_argument("api_key", "")
			base_url = self.get_body_argument("base_url", "")
			model_type = self.get_body_argument("model_type", "text")
			system_prompt = self.get_body_argument("system_prompt", "")
			temperature = safe_float(self.get_body_argument("temperature", 0.7), 0.7)
			top_p = safe_float(self.get_body_argument("top_p", 1.0), 1.0)
			max_tokens = safe_int(self.get_body_argument("max_tokens", 2048), 2048)
			context_size = safe_int(self.get_body_argument("context_size", 4096), 4096)
			is_default = safe_int(self.get_body_argument("is_default", 0), 0)
			
			if not validate_llm_base_url(base_url):
				self.write({"code": 1, "msg": "Base URL 不合法或存在 SSRF 风险，请使用受信任的 LLM 服务商地址"})
				return
			
			mid = AiModelRepository.create(name, provider, api_key, base_url, model_type, system_prompt, temperature, top_p, max_tokens, context_size, is_default)
			if mid:
				self.write({"code": 0, "msg": "添加成功", "data": {"id": mid}})
			else:
				self.write({"code": 1, "msg": "添加失败"})
				
		elif action == "edit":
			api_key = self.get_body_argument("api_key", None)
			params = {
				"name": self.get_body_argument("name", None),
				"provider": self.get_body_argument("provider", None),
				"base_url": self.get_body_argument("base_url", None),
				"model_type": self.get_body_argument("model_type", None),
				"system_prompt": self.get_body_argument("system_prompt", None),
			}
			# 仅在提供了新的 API Key 时才更新，避免前端不展示旧 Key 导致被清空
			if api_key:
				params["api_key"] = api_key
			
			if self.get_body_argument("temperature", None): params["temperature"] = safe_float(self.get_body_argument("temperature"), 0.7)
			if self.get_body_argument("top_p", None): params["top_p"] = safe_float(self.get_body_argument("top_p"), 1.0)
			if self.get_body_argument("max_tokens", None): params["max_tokens"] = safe_int(self.get_body_argument("max_tokens"), 2048)
			if self.get_body_argument("context_size", None): params["context_size"] = safe_int(self.get_body_argument("context_size"), 4096)
			if self.get_body_argument("is_default", None): params["is_default"] = safe_int(self.get_body_argument("is_default"), 0)
			
			# 过滤掉 None 的参数
			params = {k: v for k, v in params.items() if v is not None}
			
			if "base_url" in params and not validate_llm_base_url(params["base_url"]):
				self.write({"code": 1, "msg": "Base URL 不合法或存在 SSRF 风险，请使用受信任的 LLM 服务商地址"})
				return
			
			success = AiModelRepository.update(safe_int(model_id, 0), **params)
			if success:
				self.write({"code": 0, "msg": "更新成功"})
			else:
				self.write({"code": 1, "msg": "更新失败"})
				
		elif action == "delete":
			AiModelRepository.delete(safe_int(model_id, 0))
			self.write({"code": 0, "msg": "删除成功"})
			
		elif action == "set_default":
			AiModelRepository.set_default(safe_int(model_id, 0))
			self.write({"code": 0, "msg": "设置成功"})


class AiModelChatHandler(AdminBaseHandler):
	"""模型对话接口 (SSE)"""
	
	@tornado.web.authenticated
	async def get(self):
		self.set_header("Content-Type", "text/event-stream")
		self.set_header("Cache-Control", "no-cache")
		self.set_header("Connection", "keep-alive")
		
		model_id = self.get_argument("model_id", None)
		message = self.get_argument("message", "")
		
		if not message:
			self.write("data: " + json.dumps({"error": "消息不能为空"}) + "\n\n")
			self.flush()
			return
			
		if model_id:
			model = AiModelRepository.get_by_id(safe_int(model_id, 0))
		else:
			model = AiModelRepository.get_default_model()
			
		if not model:
			self.write("data: " + json.dumps({"error": "未找到可用模型"}) + "\n\n")
			self.flush()
			return
			
		# 准备 OpenAI API 请求
		headers = {
			"Content-Type": "application/json",
			"Authorization": f"Bearer {model['api_key']}"
		}
		
		messages = []
		if model['system_prompt']:
			messages.append({"role": "system", "content": model['system_prompt']})
		messages.append({"role": "user", "content": message})
		
		payload = {
			"model": model['name'],
			"messages": messages,
			"temperature": model['temperature'],
			"top_p": model['top_p'],
			"max_tokens": model['max_tokens'],
			"stream": True
		}
		
		if not validate_llm_base_url(model['base_url']):
			self.write("data: " + json.dumps({"error": "模型 Base URL 不合法或存在 SSRF 风险"}) + "\n\n")
			self.flush()
			return
		
		url = model['base_url']
		if not url.endswith('/'):
			url += '/'
		url += 'chat/completions'
		
		try:
			# 使用 AsyncHTTPClient 进行流式请求
			client = AsyncHTTPClient()
			
			def streaming_callback(chunk):
				# chunk 是 bytes，需要解码
				chunk_str = chunk.decode('utf-8')
				# 处理可能粘连的多个 data: 开头的行
				for line in chunk_str.split('\n'):
					if line.startswith('data: '):
						data_str = line[6:]
						if data_str == '[DONE]':
							continue
						try:
							data_json = json.loads(data_str)
							if 'choices' in data_json and len(data_json['choices']) > 0:
								delta = data_json['choices'][0].get('delta', {})
								if 'content' in delta:
									# 将内容发送给客户端
									content = delta['content']
									self.write("data: " + json.dumps({"content": content}) + "\n\n")
									self.flush()
						except json.JSONDecodeError:
							pass
			
			request = HTTPRequest(
				url=url,
				method="POST",
				headers=headers,
				body=json.dumps(payload),
				streaming_callback=streaming_callback,
				request_timeout=60,
				follow_redirects=False
			)
			
			response = await client.fetch(request)
			
			# 对话结束后更新 token 使用量 (简单估算: 输入字数 + 响应字数)
			# 实际应用中可能需要更精确的 token 计算，这里仅为演示
			estimated_tokens = len(message) + 100 
			AiModelRepository.increment_tokens(model['id'], estimated_tokens)
			
			self.write("data: [DONE]\n\n")
			self.flush()
			
		except Exception as e:
			self.write("data: " + json.dumps({"error": f"模型请求失败: {str(e)}"}) + "\n\n")
			self.write("data: [DONE]\n\n")
			self.flush()


class DataWarehouseManageHandler(AdminBaseHandler):
	"""数据仓库管理"""
	
	@tornado.web.authenticated
	def get(self):
		page = safe_int(self.get_argument("page", 1), 1)
		search = self.get_argument("search", "")
		
		result = DataWarehouseRepository.get_all(page, 20, search)
		
		self.render("admin/data_warehouse.html", title="数据仓库", 
				   items=result["items"],
				   page=page,
				   total=result["total"],
				   search=search,
				   username=self.current_user)
	
	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")
		
		if action == "save_selected":
			# 从瞭望采集保存到数据仓库
			data_json = self.get_body_argument("data", "[]")
			try:
				items = json.loads(data_json)
				saved_count = 0
				for item in items:
					DataWarehouseRepository.save_data(
						source_id=item.get("source_id"),
						title=item.get("title", ""),
						url=item.get("url", ""),
						content=item.get("content", ""),
						publish_time=item.get("publish_time", ""),
						source_name=item.get("source_name", ""),
						keyword=item.get("keyword", "")
					)
					saved_count += 1
				self.write({"code": 0, "msg": f"成功保存 {saved_count} 条数据到数据仓库"})
			except Exception as e:
				self.write({"code": 1, "msg": f"保存失败: {str(e)}"})
				
		elif action == "delete":
			item_id = self.get_body_argument("id", None)
			if item_id:
				DataWarehouseRepository.delete(item_id)
				self.write({"code": 0, "msg": "删除成功"})
			else:
				self.write({"code": 1, "msg": "参数错误"})
				
		elif action == "toggle_deep":
			item_id = self.get_body_argument("id", None)
			is_deep = safe_int(self.get_body_argument("is_deep", 0), 0)
			if item_id:
				DataWarehouseRepository.toggle_deep_collected(item_id, is_deep)
				self.write({"code": 0, "msg": "状态更新成功"})
			else:
				self.write({"code": 1, "msg": "参数错误"})
		
		elif action == "get_deep_task":
			warehouse_id = self.get_body_argument("id", None)
			if warehouse_id:
				task = DataWarehouseRepository.get_deep_collect_task(warehouse_id)
				if task:
					self.write({"code": 0, "data": dict(task)})
				else:
					self.write({"code": 1, "msg": "暂无深度采集任务"})
			else:
				self.write({"code": 1, "msg": "参数错误"})
		
		elif action == "start_deep_collect":
			warehouse_id = self.get_body_argument("id", None)
			employee_id = self.get_body_argument("employee_id", None)
			employee_name = self.get_body_argument("employee_name", "")
			
			if not warehouse_id:
				self.write({"code": 1, "msg": "参数错误"})
				return
			
			warehouse_item = DataWarehouseRepository.get_by_id(warehouse_id)
			if not warehouse_item:
				self.write({"code": 1, "msg": "数据不存在"})
				return
			
			task_id = DataWarehouseRepository.create_deep_collect_task(warehouse_id, employee_id, employee_name)
			
			try:
				def run_collect():
					try:
						DataWarehouseRepository.update_deep_collect_task(task_id, status='running', progress=10)
						DataWarehouseRepository.add_deep_collect_step(task_id, '初始化采集任务')
						DataWarehouseRepository.add_deep_collect_log(task_id, f'开始深度采集任务，ID: {task_id}', 'info')
						
						DataWarehouseRepository.update_deep_collect_task(task_id, progress=20)
						DataWarehouseRepository.add_deep_collect_step(task_id, '调度采集专员')
						DataWarehouseRepository.add_deep_collect_log(task_id, f'调度数字员工: {employee_name or "采集专员"}', 'info')
						
						DataWarehouseRepository.update_deep_collect_task(task_id, progress=50)
						DataWarehouseRepository.add_deep_collect_step(task_id, '执行网页内容提取')
						DataWarehouseRepository.add_deep_collect_log(task_id, f'正在提取 URL: {warehouse_item["url"]}', 'info')
						
						try:
							crawl_result = deep_collect_with_crawl4ai(warehouse_item["url"])
							
							if crawl_result['success']:
								title = crawl_result['title'] or warehouse_item["title"]
								content = crawl_result['content'] or warehouse_item["content"]
								
								result_data = {
									'title': title,
									'url': warehouse_item["url"],
									'content': content[:8000],
									'word_count': len(content),
									'original_content': warehouse_item["content"]
								}
								
								DataWarehouseRepository.add_deep_collect_log(task_id, '网页内容提取成功', 'info')
							else:
								raise Exception(f'crawl4ai 爬取失败: {crawl_result.get("error", "未知错误")}')
						except Exception as e:
							result_data = {
								'title': warehouse_item["title"],
								'url': warehouse_item["url"],
								'content': warehouse_item["content"],
								'word_count': len(warehouse_item["content"]),
								'original_content': warehouse_item["content"],
								'warning': f'网页访问失败，使用原始摘要: {str(e)}'
							}
							DataWarehouseRepository.add_deep_collect_log(task_id, f'网页访问失败: {str(e)}', 'warning')
						
						DataWarehouseRepository.update_deep_collect_task(task_id, progress=80)
						DataWarehouseRepository.add_deep_collect_step(task_id, '整理结构化数据')
						DataWarehouseRepository.add_deep_collect_log(task_id, '正在整理结构化数据', 'info')
						
						DataWarehouseRepository.update_deep_collect_task(
							task_id,
							progress=100,
							status='completed',
							result_data=json.dumps(result_data),
							title=result_data.get('title'),
							content=result_data.get('content'),
							url=result_data.get('url'),
							word_count=result_data.get('word_count', 0)
						)
						DataWarehouseRepository.add_deep_collect_step(task_id, '采集完成', 'completed')
						DataWarehouseRepository.add_deep_collect_log(task_id, '深度采集任务完成', 'info')
						
						DataWarehouseRepository.toggle_deep_collected(warehouse_id, 1)
					except Exception as e:
						DataWarehouseRepository.update_deep_collect_task(task_id, status='failed', error_message=str(e))
						DataWarehouseRepository.add_deep_collect_log(task_id, f'采集失败: {str(e)}', 'error')
				
				_DEEP_COLLECT_EXECUTOR.submit(run_collect)
				self.write({"code": 0, "msg": "深度采集任务已启动", "task_id": task_id})
			except Exception as e:
				self.write({"code": 1, "msg": f"启动失败: {str(e)}"})
		
		elif action == "get_employees":
			result = DigitalEmployeeRepository.get_all(1, 100, "")
			employees = []
			for emp in result["items"]:
				# 深度采集仅支持启用状态的 LLM 类型且启用了 crawl4ai 的数字员工
				if emp["is_enabled"] == 1 and emp["type"] == "llm" and emp["use_crawl4ai"] == 1:
					employees.append({"id": emp["id"], "name": emp["name"], "type": emp["type"], "description": emp["description"]})
			self.write({"code": 0, "data": employees})
		
		elif action == "batch_deep_collect":
			ids_json = self.get_body_argument("ids", "[]")
			employee_id = self.get_body_argument("employee_id", None)
			employee_name = self.get_body_argument("employee_name", "")
			
			try:
				ids = json.loads(ids_json)
				if not ids:
					self.write({"code": 1, "msg": "请选择要采集的数据"})
					return
				
				if len(ids) > _MAX_BATCH_COLLECT_SIZE:
					self.write({"code": 1, "msg": f"批量采集单次最多 {_MAX_BATCH_COLLECT_SIZE} 条数据"})
					return
				
				task_ids = DataWarehouseRepository.batch_deep_collect(ids, employee_id, employee_name)
				
				def run_batch_collect():
					for i, warehouse_id in enumerate(ids):
						warehouse_item = DataWarehouseRepository.get_by_id(warehouse_id)
						if warehouse_item:
							task_id = task_ids[i]
							try:
								DataWarehouseRepository.update_deep_collect_task(task_id, status='running', progress=10)
								DataWarehouseRepository.add_deep_collect_step(task_id, '初始化采集任务')
								
								DataWarehouseRepository.update_deep_collect_task(task_id, progress=50)
								DataWarehouseRepository.add_deep_collect_step(task_id, '执行网页内容提取')
								
								try:
									crawl_result = deep_collect_with_crawl4ai(warehouse_item["url"])
									
									if crawl_result['success']:
										title = crawl_result['title'] or warehouse_item["title"]
										content = crawl_result['content'] or warehouse_item["content"]
										
										result_data = {
											'title': title,
											'url': warehouse_item["url"],
											'content': content[:8000],
											'word_count': len(content),
											'original_content': warehouse_item["content"]
										}
									else:
										raise Exception(f'crawl4ai 爬取失败: {crawl_result.get("error", "未知错误")}')
								except Exception as e:
									result_data = {
										'title': warehouse_item["title"],
										'url': warehouse_item["url"],
										'content': warehouse_item["content"],
										'word_count': len(warehouse_item["content"]),
										'original_content': warehouse_item["content"],
										'warning': f'网页访问失败，使用原始摘要: {str(e)}'
									}
								
								DataWarehouseRepository.update_deep_collect_task(
									task_id,
									progress=100,
									status='completed',
									result_data=json.dumps(result_data),
									title=result_data.get('title'),
									content=result_data.get('content'),
									url=result_data.get('url'),
									word_count=result_data.get('word_count', 0)
								)
								DataWarehouseRepository.add_deep_collect_step(task_id, '采集完成', 'completed')
								DataWarehouseRepository.toggle_deep_collected(warehouse_id, 1)
							except Exception as e:
								DataWarehouseRepository.update_deep_collect_task(task_id, status='failed', error_message=f'采集失败: {str(e)}')
				
				_DEEP_COLLECT_EXECUTOR.submit(run_batch_collect)
				self.write({"code": 0, "msg": f"批量深度采集已启动，共 {len(ids)} 条数据"})
			except Exception as e:
				self.write({"code": 1, "msg": f"启动失败: {str(e)}"})


class DigitalEmployeeManageHandler(AdminBaseHandler):
	"""数字员工管理"""
	
	@tornado.web.authenticated
	def get(self):
		page = safe_int(self.get_argument("page", 1), 1)
		search = self.get_argument("search", "")
		
		result = DigitalEmployeeRepository.get_all(page, 20, search)
		models = AiModelRepository.get_all(1, 1000, "")
		interfaces = ApiInterfaceRepository.get_enabled()
		
		self.render("admin/digital_employee.html", 
			title="数字员工",
			employees=result["items"],
			page=page,
			total=result["total"],
			search=search,
			models=models["items"],
			interfaces=interfaces,
			username=self.current_user
		)
	
	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")
		
		if action == "add":
			name = self.get_body_argument("name", "")
			description = self.get_body_argument("description", "")
			emp_type = self.get_body_argument("type", "llm")
			
			model_id = self.get_body_argument("model_id", None)
			system_prompt = self.get_body_argument("system_prompt", None)
			use_skills = safe_int(self.get_body_argument("use_skills", 0), 0)
			use_crawl4ai = safe_int(self.get_body_argument("use_crawl4ai", 0), 0)
			
			api_interface_id = self.get_body_argument("api_interface_id", None)
			api_url = self.get_body_argument("api_url", None)
			api_method = self.get_body_argument("api_method", "GET")
			api_headers = self.get_body_argument("api_headers", None)
			api_params = self.get_body_argument("api_params", None)
			card_type = self.get_body_argument("card_type", None)
			
			sort_order = safe_int(self.get_body_argument("sort_order", 0), 0)
			
			# API 类型员工必须配置合法 URL，防止存储型 SSRF
			if emp_type == "api" and api_url and not validate_employee_api_url(api_url):
				self.write({"code": 1, "msg": "API URL 不合法或存在 SSRF 风险"})
				return
			
			emp_id = DigitalEmployeeRepository.create(
				name=name,
				description=description,
				emp_type=emp_type,
				model_id=safe_int(model_id) if model_id else None,
				system_prompt=system_prompt,
				use_skills=use_skills,
				use_crawl4ai=use_crawl4ai,
				api_interface_id=safe_int(api_interface_id) if api_interface_id else None,
				api_url=api_url,
				api_method=api_method,
				api_headers=api_headers,
				api_params=api_params,
				card_type=card_type if card_type else None,
				sort_order=sort_order
			)
			
			if emp_id:
				# 保存上传的 .nd 文件到 data/dgUser/{emp_id}/
				nd_files = self.request.files.get("nd_files", [])
				save_employee_nd_files(emp_id, nd_files)
				self.write({"code": 0, "msg": "创建成功", "data": {"id": emp_id}})
			else:
				self.write({"code": 1, "msg": "创建失败，名称可能已存在"})
		
		elif action == "edit":
			emp_id = safe_int(self.get_body_argument("id", 0), 0)
			name = self.get_body_argument("name", None)
			description = self.get_body_argument("description", None)
			emp_type = self.get_body_argument("type", None)
			
			model_id = self.get_body_argument("model_id", None)
			system_prompt = self.get_body_argument("system_prompt", None)
			use_skills = self.get_body_argument("use_skills", None)
			use_crawl4ai = self.get_body_argument("use_crawl4ai", None)
			
			api_interface_id = self.get_body_argument("api_interface_id", None)
			api_url = self.get_body_argument("api_url", None)
			api_method = self.get_body_argument("api_method", None)
			api_headers = self.get_body_argument("api_headers", None)
			api_params = self.get_body_argument("api_params", None)
			card_type = self.get_body_argument("card_type", None)
			
			sort_order = self.get_body_argument("sort_order", None)
			
			# 若更新 api_url，需再次校验防止存储型 SSRF
			if api_url and not validate_employee_api_url(api_url):
				self.write({"code": 1, "msg": "API URL 不合法或存在 SSRF 风险"})
				return
			
			success = DigitalEmployeeRepository.update(
				emp_id,
				name=name,
				description=description,
				emp_type=emp_type,
				model_id=safe_int(model_id) if model_id and model_id != '' else None,
				system_prompt=system_prompt,
				use_skills=safe_int(use_skills) if use_skills is not None else None,
				use_crawl4ai=safe_int(use_crawl4ai) if use_crawl4ai is not None else None,
				api_interface_id=safe_int(api_interface_id) if api_interface_id is not None else None,
				api_url=api_url,
				api_method=api_method,
				api_headers=api_headers,
				api_params=api_params,
				card_type=card_type if card_type else None,
				sort_order=safe_int(sort_order) if sort_order is not None else None
			)
			
			if success:
				# 保存新上传的 .nd 文件到 data/dgUser/{emp_id}/
				nd_files = self.request.files.get("nd_files", [])
				save_employee_nd_files(emp_id, nd_files)
				self.write({"code": 0, "msg": "更新成功"})
			else:
				self.write({"code": 1, "msg": "更新失败"})
		
		elif action == "delete":
			emp_id = safe_int(self.get_body_argument("id", 0), 0)
			DigitalEmployeeRepository.delete(emp_id)
			self.write({"code": 0, "msg": "删除成功"})
		
		elif action == "toggle":
			emp_id = safe_int(self.get_body_argument("id", 0), 0)
			is_enabled = safe_int(self.get_body_argument("is_enabled", 0), 0)
			DigitalEmployeeRepository.toggle_enabled(emp_id, is_enabled)
			self.write({"code": 0, "msg": "状态更新成功"})
		
		elif action == "get_detail":
			emp_id = safe_int(self.get_body_argument("id", 0), 0)
			employee = DigitalEmployeeRepository.get_by_id(emp_id)
			if employee:
				data = dict(employee)
				data["nd_files"] = list_employee_nd_files(emp_id)
				self.write({"code": 0, "data": data})
			else:
				self.write({"code": 1, "msg": "员工不存在"})
		
		elif action == "preview_api":
			emp_id = safe_int(self.get_body_argument("id", 0), 0)
			employee = DigitalEmployeeRepository.get_by_id(emp_id)
			if not employee:
				self.write({"code": 1, "msg": "员工不存在"})
				return
			
			if employee["type"] != "api":
				self.write({"code": 1, "msg": "只有API类型员工才能预览"})
				return
			
			try:
				import requests
				import json
				
				api_url = employee["api_url"]
				if not validate_employee_api_url(api_url):
					self.write({"code": 1, "msg": "API URL 不合法或存在 SSRF 风险"})
					return
				
				api_method = employee["api_method"] or "GET"
				api_headers = employee["api_headers"]
				api_params = employee["api_params"]
				
				# 读取预览时传入的动态参数并合并到已有参数
				preview_params_str = self.get_body_argument("preview_params", "{}")
				preview_params = {}
				if preview_params_str:
					try:
						preview_params = json.loads(preview_params_str)
					except Exception:
						pass
				
				headers = {}
				if api_headers:
					try:
						headers = json.loads(api_headers)
					except:
						pass
				
				params = {}
				if api_params:
					try:
						params = json.loads(api_params)
					except:
						pass
				params.update(preview_params)
				
				response = None
				if api_method.upper() == "GET":
					response = requests.get(api_url, headers=headers, params=params, timeout=10, allow_redirects=False)
				elif api_method.upper() == "POST":
					response = requests.post(api_url, headers=headers, json=params, timeout=10, allow_redirects=False)
				elif api_method.upper() == "PUT":
					response = requests.put(api_url, headers=headers, json=params, timeout=10, allow_redirects=False)
				elif api_method.upper() == "DELETE":
					response = requests.delete(api_url, headers=headers, params=params, timeout=10, allow_redirects=False)
				
				if response and response.status_code == 200:
					try:
						result_data = response.json()
						self.write({"code": 0, "msg": "预览成功", "data": result_data})
					except:
						self.write({"code": 0, "msg": "预览成功", "data": {"raw": response.text}})
				else:
					self.write({"code": 1, "msg": f"API请求失败，状态码: {response.status_code if response else '未知'}"})
			except Exception as e:
				self.write({"code": 1, "msg": f"预览失败: {str(e)}"})


class ApiInterfaceManageHandler(AdminBaseHandler):
	"""接口管理"""

	@tornado.web.authenticated
	def get(self):
		page = safe_int(self.get_argument("page", 1), 1)
		search = self.get_argument("search", "")
		result = ApiInterfaceRepository.get_all(page, 20, search)

		self.render("admin/api_interface.html",
					title="接口管理",
					interfaces=result["items"],
					page=page,
					total=result["total"],
					search=search,
					username=self.current_user)

	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")

		if action == "add":
			name = self.get_body_argument("name", "")
			description = self.get_body_argument("description", "")
			api_url = self.get_body_argument("api_url", "")
			api_method = self.get_body_argument("api_method", "GET")
			api_headers = self.get_body_argument("api_headers", "{}")
			api_params = self.get_body_argument("api_params", "{}")
			api_body = self.get_body_argument("api_body", "{}")
			response_type = self.get_body_argument("response_type", "json")
			card_type = self.get_body_argument("card_type", "")
			sort_order = safe_int(self.get_body_argument("sort_order", "0"), 0)

			if not name or not api_url:
				self.write({"code": 1, "msg": "名称和API URL不能为空"})
				return

			if not validate_employee_api_url(api_url):
				self.write({"code": 1, "msg": "API URL 不合法或存在 SSRF 风险"})
				return

			interface_id = ApiInterfaceRepository.create(
				name, description, api_url, api_method, api_headers, api_params, api_body,
				response_type, card_type or None, sort_order=sort_order
			)
			if interface_id:
				self.write({"code": 0, "msg": "创建成功"})
			else:
				self.write({"code": 1, "msg": "创建失败，名称可能已存在"})

		elif action == "edit":
			interface_id = safe_int(self.get_body_argument("id", "0"), 0)
			name = self.get_body_argument("name", None)
			description = self.get_body_argument("description", None)
			api_url = self.get_body_argument("api_url", None)
			api_method = self.get_body_argument("api_method", None)
			api_headers = self.get_body_argument("api_headers", None)
			api_params = self.get_body_argument("api_params", None)
			api_body = self.get_body_argument("api_body", None)
			response_type = self.get_body_argument("response_type", None)
			card_type = self.get_body_argument("card_type", None)
			sort_order = self.get_body_argument("sort_order", None)

			if api_url and not validate_employee_api_url(api_url):
				self.write({"code": 1, "msg": "API URL 不合法或存在 SSRF 风险"})
				return

			success = ApiInterfaceRepository.update(
				interface_id, name, description, api_url, api_method, api_headers,
				api_params, api_body, response_type, card_type if card_type else None,
				sort_order=safe_int(sort_order) if sort_order is not None else None
			)
			if success:
				self.write({"code": 0, "msg": "更新成功"})
			else:
				self.write({"code": 1, "msg": "更新失败"})

		elif action == "delete":
			interface_id = safe_int(self.get_body_argument("id", "0"), 0)
			ApiInterfaceRepository.delete(interface_id)
			self.write({"code": 0, "msg": "删除成功"})

		elif action == "toggle":
			interface_id = safe_int(self.get_body_argument("id", "0"), 0)
			is_enabled = safe_int(self.get_body_argument("is_enabled", "0"), 0)
			ApiInterfaceRepository.toggle_enabled(interface_id, is_enabled)
			self.write({"code": 0, "msg": "状态更新成功"})

		elif action == "get_detail":
			interface_id = safe_int(self.get_body_argument("id", "0"), 0)
			interface = ApiInterfaceRepository.get_by_id(interface_id)
			if interface:
				self.write({"code": 0, "data": dict(interface)})
			else:
				self.write({"code": 1, "msg": "接口不存在"})

		elif action == "preview":
			interface_id = safe_int(self.get_body_argument("id", "0"), 0)
			interface = ApiInterfaceRepository.get_by_id(interface_id)
			if not interface:
				self.write({"code": 1, "msg": "接口不存在"})
				return

			api_url = interface["api_url"]
			if not validate_employee_api_url(api_url):
				self.write({"code": 1, "msg": "API URL 不合法或存在 SSRF 风险"})
				return

			try:
				import requests
				method = (interface["api_method"] or "GET").upper()
				headers = json.loads(interface["api_headers"] or "{}")
				params = json.loads(interface["api_params"] or "{}")
				body = json.loads(interface["api_body"] or "{}")

				response = None
				if method == "GET":
					response = requests.get(api_url, headers=headers, params=params, timeout=15, allow_redirects=False)
				elif method == "POST":
					response = requests.post(api_url, headers=headers, json=body, params=params, timeout=15, allow_redirects=False)
				elif method == "PUT":
					response = requests.put(api_url, headers=headers, json=body, params=params, timeout=15, allow_redirects=False)
				elif method == "DELETE":
					response = requests.delete(api_url, headers=headers, params=params, timeout=15, allow_redirects=False)

				if response and response.status_code == 200:
					try:
						data = response.json()
						self.write({"code": 0, "msg": "预览成功", "data": data})
					except Exception:
						self.write({"code": 0, "msg": "预览成功", "data": {"raw": response.text}})
				else:
					self.write({"code": 1, "msg": f"API请求失败，状态码: {response.status_code if response else '未知'}"})
			except Exception as e:
				self.write({"code": 1, "msg": f"预览失败: {str(e)}"})


class SkillManageHandler(AdminBaseHandler):
	"""技能管理"""

	@tornado.web.authenticated
	def get(self):
		page = safe_int(self.get_argument("page", 1), 1)
		search = self.get_argument("search", "")
		result = SkillRepository.get_all(page, 20, search)

		self.render("admin/skill.html",
					title="技能管理",
					skills=result["items"],
					page=page,
					total=result["total"],
					search=search,
					username=self.current_user)

	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")

		if action == "add":
			name = self.get_body_argument("name", "")
			code = self.get_body_argument("code", "")
			description = self.get_body_argument("description", "")
			config = self.get_body_argument("config", "{}")
			sort_order = safe_int(self.get_body_argument("sort_order", "0"), 0)

			if not name or not code:
				self.write({"code": 1, "msg": "名称和编码不能为空"})
				return

			skill_id = SkillRepository.create(name, code, description, config, sort_order=sort_order)
			if skill_id:
				self.write({"code": 0, "msg": "创建成功"})
			else:
				self.write({"code": 1, "msg": "创建失败，名称或编码可能已存在"})

		elif action == "edit":
			skill_id = safe_int(self.get_body_argument("id", "0"), 0)
			name = self.get_body_argument("name", None)
			code = self.get_body_argument("code", None)
			description = self.get_body_argument("description", None)
			config = self.get_body_argument("config", None)
			sort_order = self.get_body_argument("sort_order", None)

			success = SkillRepository.update(
				skill_id, name, code, description, config,
				sort_order=safe_int(sort_order) if sort_order is not None else None
			)
			if success:
				self.write({"code": 0, "msg": "更新成功"})
			else:
				self.write({"code": 1, "msg": "更新失败"})

		elif action == "delete":
			skill_id = safe_int(self.get_body_argument("id", "0"), 0)
			SkillRepository.delete(skill_id)
			self.write({"code": 0, "msg": "删除成功"})

		elif action == "toggle":
			skill_id = safe_int(self.get_body_argument("id", "0"), 0)
			is_enabled = safe_int(self.get_body_argument("is_enabled", "0"), 0)
			SkillRepository.toggle_enabled(skill_id, is_enabled)
			self.write({"code": 0, "msg": "状态更新成功"})

		elif action == "get_detail":
			skill_id = safe_int(self.get_body_argument("id", "0"), 0)
			skill = SkillRepository.get_by_id(skill_id)
			if skill:
				self.write({"code": 0, "data": dict(skill)})
			else:
				self.write({"code": 1, "msg": "技能不存在"})


class ChatSessionManageHandler(AdminBaseHandler):
	"""会话管理"""

	@tornado.web.authenticated
	def get(self):
		page = safe_int(self.get_argument("page", 1), 1)
		search = self.get_argument("search", "")
		user_id = safe_int(self.get_argument("user_id", "0"), 0) or None
		result = ChatSessionRepository.get_all_sessions(page, 20, search, user_id)

		self.render("admin/chat_session.html",
					title="会话管理",
					sessions=result["items"],
					page=page,
					total=result["total"],
					search=search,
					user_id=user_id or "",
					username=self.current_user)

	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")

		if action == "delete":
			session_id = safe_int(self.get_body_argument("id", "0"), 0)
			ChatSessionRepository.admin_delete(session_id)
			self.write({"code": 0, "msg": "删除成功"})

		elif action == "get_detail":
			session_id = safe_int(self.get_body_argument("id", "0"), 0)
			session = ChatSessionRepository.get_by_id(session_id)
			if session:
				self.write({"code": 0, "data": dict(session)})
			else:
				self.write({"code": 1, "msg": "会话不存在"})


class ChatMessageManageHandler(AdminBaseHandler):
	"""对话管理"""

	@tornado.web.authenticated
	def get(self):
		page = safe_int(self.get_argument("page", 1), 1)
		search = self.get_argument("search", "")
		session_id = safe_int(self.get_argument("session_id", "0"), 0) or None
		user_id = safe_int(self.get_argument("user_id", "0"), 0) or None
		result = ChatMessageRepository.get_all_messages(page, 20, search, session_id, user_id)

		self.render("admin/chat_message.html",
					title="对话管理",
					messages=result["items"],
					page=page,
					total=result["total"],
					search=search,
					session_id=session_id or "",
					user_id=user_id or "",
					username=self.current_user)

	@tornado.web.authenticated
	def post(self):
		action = self.get_body_argument("action", "")

		if action == "delete":
			message_id = safe_int(self.get_body_argument("id", "0"), 0)
			ChatMessageRepository.admin_delete(message_id)
			self.write({"code": 0, "msg": "删除成功"})

		elif action == "get_detail":
			message_id = safe_int(self.get_body_argument("id", "0"), 0)
			message = ChatMessageRepository.get_by_id(message_id)
			if message:
				self.write({"code": 0, "data": dict(message)})
			else:
				self.write({"code": 1, "msg": "消息不存在"})
