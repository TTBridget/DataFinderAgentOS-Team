"""
dp.py属于SQLite数据库访问层（model的基础设施部分）
-使用python3内置的sqlite3连接到SQLite数据库（零依赖）
-统一管理DB文件路径，连接创建，row_factory
-支持初始化建立及表结构，实现"开箱即用"
"""

import os
import sqlite3
import hashlib
import secrets

def project_root():
	#当前项目的../DataFinderAgentOS/
	return os.path.abspath(os.path.join(os.path.dirname(__file__),os.pardir,os.pardir))

DB_PATH = os.path.join(project_root(),"database","finderos.db")

def get_connection():
	#获得一个数据库的连接，用于操作数据库完成事务和数据操作
	os.makedirs(os.path.dirname(DB_PATH),exist_ok=True)
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row 
	return conn

def _hash_password(password:str,salt:bytes) -> str:
	#将明文相间+salt计算为稳定的hash
	k = hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),salt,100_000)
	return k.hex()

def _migrate_menu_structure(conn):
	"""菜单结构调整迁移：
	- 将原"数据管理"改为"瞭望中心"
	- 将"数据源管理"改为"瞭源管理"并修正路由
	- 将"采集管理"改为"瞭望采集"并修正路由
	- 将"数据仓库"的父级改为瞭望中心
	- 删除"可视化"及其子功能"数智大屏""舆情大屏"
	"""
	# 1. 更新原数据管理为瞭望中心
	conn.execute(
		"UPDATE functions SET name = ?, code = ?, icon = ? WHERE id = ?",
		("瞭望中心", "watch_center", "layui-icon-website", 6)
	)
	
	# 2. 更新数据源管理为瞭源管理
	conn.execute(
		"UPDATE functions SET name = ?, code = ?, route = ? WHERE id = ?",
		("瞭源管理", "data_source", "/admin/data_source", 7)
	)
	
	# 3. 更新采集管理为瞭望采集
	conn.execute(
		"UPDATE functions SET name = ?, code = ?, route = ? WHERE id = ?",
		("瞭望采集", "watch", "/admin/watch", 8)
	)
	
	# 4. 确保数据仓库父级为瞭望中心
	conn.execute(
		"UPDATE functions SET parent_id = ? WHERE id = ?",
		(6, 15)
	)
	
	# 5. 删除可视化相关功能（id 12、13、14）
	for delete_id in (12, 13, 14):
		conn.execute("DELETE FROM role_functions WHERE function_id = ?", (delete_id,))
		conn.execute("DELETE FROM menus WHERE function_id = ?", (delete_id,))
		conn.execute("DELETE FROM functions WHERE id = ?", (delete_id,))
	
	# 6. 确保新结构的功能都已在菜单中可见
	for func_id in (6, 7, 8, 15):
		exists = conn.execute("SELECT 1 FROM menus WHERE function_id = ?", (func_id,)).fetchone()
		if not exists:
			sort_order = conn.execute("SELECT sort_order FROM functions WHERE id = ?", (func_id,)).fetchone()
			conn.execute(
				"INSERT INTO menus (function_id, sort_order, is_visible) VALUES (?, ?, ?)",
				(func_id, sort_order[0] if sort_order else 0, 1)
			)
	
	# 7. 为系统管理员角色补全瞭望中心相关功能权限
	for func_id in (6, 7, 8, 15):
		conn.execute(
			"INSERT OR IGNORE INTO role_functions (role_id, function_id) VALUES (?, ?)",
			(2, func_id)
		)
	
	# 8. 添加舆情大屏功能
	conn.execute(
		"INSERT OR IGNORE INTO functions (id, name, code, icon, route, parent_id, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)",
		(16, "舆情大屏", "public_sentiment", "layui-icon-chart-screen", "/admin/public_sentiment", 9, 3)
	)
	
	# 9. 为舆情大屏创建菜单
	exists = conn.execute("SELECT 1 FROM menus WHERE function_id = 16").fetchone()
	if not exists:
		conn.execute("INSERT INTO menus (function_id, sort_order, is_visible) VALUES (16, 3, 1)")
	
	# 10. 为系统管理员角色添加舆情大屏权限
	conn.execute("INSERT OR IGNORE INTO role_functions (role_id, function_id) VALUES (2, 16)")
	
	print("菜单结构迁移完成")

def init_db():
	with get_connection() as conn:
		# 创建用户表（更新）
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS users(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				username TEXT NOT NULL UNIQUE,
				password_hash TEXT NOT NULL,
				salt TEXT NOT NULL,
				role_id INTEGER DEFAULT 1,
				is_disabled INTEGER DEFAULT 0,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 创建角色表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS roles(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				description TEXT,
				is_system INTEGER DEFAULT 0,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 创建功能表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS functions(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL,
				code TEXT NOT NULL UNIQUE,
				icon TEXT,
				route TEXT,
				parent_id INTEGER DEFAULT 0,
				sort_order INTEGER DEFAULT 0,
				is_disabled INTEGER DEFAULT 0,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 创建角色-功能关联表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS role_functions(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				role_id INTEGER NOT NULL,
				function_id INTEGER NOT NULL,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				UNIQUE(role_id, function_id)
			)
			"""
		)
		
		# 创建菜单表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS menus(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				function_id INTEGER NOT NULL,
				sort_order INTEGER DEFAULT 0,
				is_visible INTEGER DEFAULT 1,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 创建管理员表（更新）
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS admins(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				username TEXT NOT NULL UNIQUE,
				password_hash TEXT NOT NULL,
				salt TEXT NOT NULL,
				role_id INTEGER DEFAULT 2,
				is_disabled INTEGER DEFAULT 0,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 检查是否存在默认角色
		role_exists = conn.execute(
			"SELECT 1 FROM roles WHERE id IN (1, 2)"
		).fetchall()
		
		if len(role_exists) < 2:
			# 不存在，创建默认角色
			conn.execute(
				"INSERT OR IGNORE INTO roles (id, name, description, is_system) VALUES (?, ?, ?, ?)",
				(1, "普通用户", "普通用户角色，只能登录前台", 1)
			)
			conn.execute(
				"INSERT OR IGNORE INTO roles (id, name, description, is_system) VALUES (?, ?, ?, ?)",
				(2, "系统管理员", "系统管理员角色，只能登录后台管理系统", 1)
			)
			print("默认角色创建成功！")
		
		# 检查是否存在默认功能
		func_exists = conn.execute(
			"SELECT 1 FROM functions LIMIT 1"
		).fetchone()
		
		if not func_exists:
			# 不存在，创建默认功能
			default_functions = [
				(1, "系统管理", "system", "layui-icon-console", None, 0, 1),
				(2, "用户管理", "user", "layui-icon-user", "/admin/user", 1, 1),
				(3, "角色管理", "role", "layui-icon-group", "/admin/role", 1, 2),
				(4, "功能管理", "function", "layui-icon-set", "/admin/function", 1, 3),
				(5, "菜单管理", "menu", "layui-icon-template", "/admin/menu", 1, 4),
				(6, "瞭望中心", "watch_center", "layui-icon-website", None, 0, 2),
				(7, "瞭源管理", "data_source", "layui-icon-database", "/admin/data_source", 6, 1),
				(8, "瞭望采集", "watch", "layui-icon-download-circle", "/admin/watch", 6, 2),
				(15, "数据仓库", "data_warehouse", "layui-icon-table", "/admin/data_warehouse", 6, 3),
				(9, "智能应用", "ai", "layui-icon-util", None, 0, 3),
				(10, "模型引擎", "engine", "layui-icon-engine", "/admin/ai", 9, 1),
				(11, "数字员工", "digital", "layui-icon-user", "/admin/digital", 9, 2),
			]
			
			for func in default_functions:
				conn.execute(
					"INSERT INTO functions (id, name, code, icon, route, parent_id, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)",
					func
				)
			
			# 为系统管理员角色分配所有功能
			for func in default_functions:
				conn.execute(
					"INSERT INTO role_functions (role_id, function_id) VALUES (?, ?)",
					(2, func[0])
				)
			
			# 创建默认菜单
			for func in default_functions:
				conn.execute(
					"INSERT INTO menus (function_id, sort_order, is_visible) VALUES (?, ?, ?)",
					(func[0], func[6], 1)
				)
			
			print("默认功能和菜单创建成功！")
		else:
			# 已存在数据时，执行菜单结构调整迁移
			_migrate_menu_structure(conn)
		
		# 检查是否存在默认超级管理员
		admin_exists = conn.execute(
			"SELECT 1 FROM admins WHERE username = ?",
			("admin",)
		).fetchone()
		
		if not admin_exists:
			# 不存在，创建默认超级管理员
			# 优先从环境变量读取初始密码，未设置则生成随机强密码
			default_password = os.environ.get('ADMIN_INITIAL_PASSWORD')
			if not default_password:
				default_password = secrets.token_urlsafe(16)
				display_password = default_password
			else:
				display_password = "（由 ADMIN_INITIAL_PASSWORD 环境变量提供）"
			
			salt = secrets.token_bytes(16)
			password_hash = _hash_password(default_password, salt)
			conn.execute(
				"INSERT INTO admins (username, password_hash, salt, role_id) VALUES (?, ?, ?, ?)",
				("admin", password_hash, salt.hex(), 2)
			)
			print(f"默认超级管理员创建成功！用户名: admin, 密码: {display_password}")
		else:
			print("默认超级管理员已存在")
		
		# 创建瞭源表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS data_sources(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				description TEXT,
				base_url TEXT NOT NULL,
				path_template TEXT NOT NULL,
				headers TEXT NOT NULL,
				is_enabled INTEGER DEFAULT 1,
				sort_order INTEGER DEFAULT 0,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 创建采集结果表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS collected_data(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				source_id INTEGER NOT NULL,
				title TEXT,
				url TEXT,
				content TEXT,
				publish_time TEXT,
				source_name TEXT,
				keyword TEXT,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 创建数据仓库表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS data_warehouse(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				source_id INTEGER,
				title TEXT,
				url TEXT UNIQUE,
				content TEXT,
				publish_time TEXT,
				source_name TEXT,
				keyword TEXT,
				is_deep_collected INTEGER DEFAULT 0,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 创建深度采集数据表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS deep_collected_data(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				warehouse_id INTEGER NOT NULL,
				employee_id INTEGER,
				employee_name TEXT,
				status TEXT DEFAULT 'pending', -- pending, running, completed, failed
				progress INTEGER DEFAULT 0,
				steps TEXT, -- JSON array
				logs TEXT, -- JSON array
				result_data TEXT, -- JSON
				title TEXT, -- 采集标题
				content TEXT, -- 采集正文
				url TEXT, -- 采集URL
				word_count INTEGER DEFAULT 0, -- 正文字数
				error_message TEXT,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				FOREIGN KEY (warehouse_id) REFERENCES data_warehouse(id)
			)
			"""
		)
		
		# 为已存在的深度采集数据表添加新字段
		try:
			conn.execute("ALTER TABLE deep_collected_data ADD COLUMN title TEXT")
		except sqlite3.OperationalError:
			pass
		try:
			conn.execute("ALTER TABLE deep_collected_data ADD COLUMN content TEXT")
		except sqlite3.OperationalError:
			pass
		try:
			conn.execute("ALTER TABLE deep_collected_data ADD COLUMN url TEXT")
		except sqlite3.OperationalError:
			pass
		try:
			conn.execute("ALTER TABLE deep_collected_data ADD COLUMN word_count INTEGER DEFAULT 0")
		except sqlite3.OperationalError:
			pass
		
		# 创建数字员工表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS digital_employees(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				description TEXT,
				type TEXT NOT NULL, -- 'llm' 或 'api'
				
				-- LLM类型员工字段
				model_id INTEGER,
				system_prompt TEXT,
				use_skills INTEGER DEFAULT 0,
				use_crawl4ai INTEGER DEFAULT 0,
				
				-- API类型员工字段
				api_url TEXT,
				api_method TEXT DEFAULT 'GET',
				api_headers TEXT, -- JSON
				api_params TEXT, -- JSON
				
				-- 卡片渲染配置
				card_type TEXT, -- 'weather'、'table'、'json'、'html' 等，NULL 表示纯文本
				
				is_enabled INTEGER DEFAULT 1,
				sort_order INTEGER DEFAULT 0,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 为已存在的数字员工表添加卡片类型字段
		try:
			conn.execute("ALTER TABLE digital_employees ADD COLUMN card_type TEXT")
		except sqlite3.OperationalError:
			pass

		# 为已存在的数字员工表添加关联接口字段
		try:
			conn.execute("ALTER TABLE digital_employees ADD COLUMN api_interface_id INTEGER REFERENCES api_interfaces(id)")
		except sqlite3.OperationalError:
			pass
		
		# 检查是否存在默认百度新闻数据源
		source_exists = conn.execute(
			"SELECT 1 FROM data_sources WHERE name = ?",
			("百度新闻",)
		).fetchone()
		
		# 通用 PC 浏览器请求头，适用于百度、微博等站点
		baidu_headers = """{
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
			"Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,zh-HK;q=0.7,en-US;q=0.6,en;q=0.5",
			"Accept-Encoding": "gzip, deflate, br, zstd",
			"Connection": "keep-alive",
			"Upgrade-Insecure-Requests": "1",
			"Sec-Fetch-Dest": "document",
			"Sec-Fetch-Mode": "navigate",
			"Sec-Fetch-Site": "none",
			"Sec-Fetch-User": "?1"
		}"""
		
		if not source_exists:
			conn.execute(
				"""
				INSERT INTO data_sources (name, description, base_url, path_template, headers, is_enabled, sort_order)
				VALUES (?, ?, ?, ?, ?, ?, ?)
				""",
				(
					"百度新闻",
					"百度新闻搜索采集源",
					"https://www.baidu.com",
					"/s?rtt=1&bsst=1&cl=2&tn=news&rsv_dl=ns_pc&word={keyword}&pn={page}",
					baidu_headers,
					1,
					1
				)
			)
			print("默认百度新闻数据源创建成功！")
		else:
			print("默认百度新闻数据源已存在")
		
		# 补充其他默认瞭源
		default_sources = [
			(
				"百度搜索",
				"百度搜索网页采集源",
				"https://www.baidu.com",
				"/s?wd={keyword}&pn={page}",
				baidu_headers,
				1,
				2
			),
			(
				"百度百科",
				"百度百科词条采集源",
				"https://baike.baidu.com",
				"/item/{keyword}",
				baidu_headers,
				1,
				3
			),
			(
				"微博热搜",
				"微博实时热搜榜采集源",
				"https://s.weibo.com",
				"/top/summary",
				baidu_headers,
				1,
				4
			),
			(
				"微博搜索",
				"微博关键词搜索采集源",
				"https://s.weibo.com",
				"/weibo?q={keyword}&page={page}",
				baidu_headers,
				1,
				5
			)
		]
		
		for ds in default_sources:
			exists = conn.execute(
				"SELECT 1 FROM data_sources WHERE name = ?",
				(ds[0],)
			).fetchone()
			if not exists:
				conn.execute(
					"""
					INSERT INTO data_sources (name, description, base_url, path_template, headers, is_enabled, sort_order)
					VALUES (?, ?, ?, ?, ?, ?, ?)
					""",
					ds
				)
				print(f"默认{ds[0]}数据源创建成功！")
			else:
				print(f"默认{ds[0]}数据源已存在")

		# 创建模型引擎表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS ai_models(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL,
				provider TEXT NOT NULL,
				api_key TEXT,
				base_url TEXT,
				model_type TEXT DEFAULT 'text',
				system_prompt TEXT,
				temperature REAL DEFAULT 0.7,
				top_p REAL DEFAULT 1.0,
				max_tokens INTEGER DEFAULT 2048,
				context_size INTEGER DEFAULT 4096,
				is_default INTEGER DEFAULT 0,
				total_tokens_used INTEGER DEFAULT 0,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 创建接口管理表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS api_interfaces(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				description TEXT,
				api_url TEXT NOT NULL,
				api_method TEXT DEFAULT 'GET',
				api_headers TEXT, -- JSON
				api_params TEXT, -- JSON
				api_body TEXT, -- JSON
				response_type TEXT DEFAULT 'json', -- json / text
				card_type TEXT, -- weather / table / json / html / text
				is_enabled INTEGER DEFAULT 1,
				sort_order INTEGER DEFAULT 0,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 创建技能管理表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS skills(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				code TEXT NOT NULL UNIQUE,
				description TEXT,
				config TEXT, -- JSON
				is_enabled INTEGER DEFAULT 1,
				sort_order INTEGER DEFAULT 0,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 初始化默认技能：当前时间感知
		_skill_exists = conn.execute("SELECT 1 FROM skills WHERE code = ?", ("current_time",)).fetchone()
		if not _skill_exists:
			conn.execute(
				"""
				INSERT INTO skills (name, code, description, config, is_enabled, sort_order)
				VALUES (?, ?, ?, ?, ?, ?)
				""",
				(
					"当前时间感知",
					"current_time",
					"自动在系统提示词中注入当前日期和时间，增强模型对时间的感知能力",
					'{"format": "%Y-%m-%d %H:%M:%S"}',
					1,
					1
				)
			)
			print("默认技能[当前时间感知]创建成功！")
		
		# 检查是否存在默认采集专员数字员工
		collector_exists = conn.execute(
			"SELECT 1 FROM digital_employees WHERE name = ?",
			("采集专员",)
		).fetchone()
		
		if not collector_exists:
			conn.execute(
				"""
				INSERT INTO digital_employees (name, description, type, model_id, system_prompt, use_skills, use_crawl4ai, is_enabled, sort_order)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					"采集专员",
					"负责深度采集任务的数字化员工，能够自动获取网页的详细内容",
					"llm",
					None,
					"你是一名专业的数据采集专员，负责从网页中提取详细内容。请按照以下步骤执行：1. 访问目标URL；2. 提取页面的完整正文内容；3. 提取页面中的关键数据和表格；4. 整理并返回结构化的数据。",
					0,
					1,
					1,
					1
				)
			)
			print("默认采集专员数字员工创建成功！")
		else:
			print("默认采集专员数字员工已存在")
		
		# 检查是否存在默认天气数字员工
		weather_exists = conn.execute(
			"SELECT 1 FROM digital_employees WHERE name = ?",
			("天气",)
		).fetchone()
		
		if not weather_exists:
			conn.execute(
				"""
				INSERT INTO digital_employees
				(name, description, type, model_id, system_prompt, use_skills, use_crawl4ai,
				 api_url, api_method, api_headers, api_params, card_type, is_enabled, sort_order)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					"天气",
					"查询指定城市天气，输入 @天气 即可获取天气信息",
					"api",
					None,
					"",
					0,
					0,
					"https://wttr.in/{query}",
					"GET",
					'{"User-Agent": "curl/7.68.0"}',
					'{"format": "j1", "lang": "zh"}',
					"weather",
					1,
					2
				)
			)
			print("默认天气数字员工创建成功！")
		else:
			# 同步更新已有天气员工的配置（启用 JSON 格式和天气卡片渲染）
			conn.execute(
				"UPDATE digital_employees SET api_headers = ?, api_params = ?, card_type = ? WHERE name = ?",
				('{"User-Agent": "curl/7.68.0"}', '{"format": "j1", "lang": "zh"}', "weather", "天气")
			)
			print("默认天气数字员工已存在")
		
		# 同步旧名称：如存在“文案编写”则重命名为“文案写作助手”
		conn.execute(
			"UPDATE digital_employees SET name = ?, description = ? WHERE name = ?",
			("文案写作助手", "专家级论文/专业文案写作助手，输入 @文案写作助手 即可调用", "文案编写")
		)
		
		# 检查是否存在默认文案写作助手数字员工
		writer_exists = conn.execute(
			"SELECT 1 FROM digital_employees WHERE name = ?",
			("文案写作助手",)
		).fetchone()
		
		if not writer_exists:
			conn.execute(
				"""
				INSERT INTO digital_employees (name, description, type, model_id, system_prompt, use_skills, use_crawl4ai, is_enabled, sort_order)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
				"文案写作助手",
				"专家级论文/专业文案写作助手，输入 @文案写作助手 即可调用",
				"llm",
				None,
				"",
				0,
				0,
				1,
				3
			)
			)
			print("默认文案写作助手数字员工创建成功！")
		else:
			print("默认文案写作助手数字员工已存在")
		
		# 检查是否存在默认随机音乐数字员工
		music_exists = conn.execute(
			"SELECT 1 FROM digital_employees WHERE name = ?",
			("随机音乐",)
		).fetchone()
		
		if not music_exists:
			conn.execute(
				"""
				INSERT INTO digital_employees
				(name, description, type, model_id, system_prompt, use_skills, use_crawl4ai,
				 api_url, api_method, api_headers, api_params, card_type, is_enabled, sort_order)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					"随机音乐",
					"随机推荐一首可在线播放的音乐，输入 @随机音乐 即可调用",
					"api",
					None,
					"",
					0,
					0,
					"internal://music",
					"GET",
					'{}',
					'{}',
					"music",
					1,
					4
				)
			)
			print("默认随机音乐数字员工创建成功！")
		else:
			print("默认随机音乐数字员工已存在")
		
		# 检查是否存在默认新闻数字员工
		news_exists = conn.execute(
			"SELECT 1 FROM digital_employees WHERE name = ?",
			("新闻",)
		).fetchone()
		
		if not news_exists:
			conn.execute(
				"""
				INSERT INTO digital_employees
				(name, description, type, model_id, system_prompt, use_skills, use_crawl4ai,
				 api_url, api_method, api_headers, api_params, card_type, is_enabled, sort_order)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					"新闻",
					"获取当前全国范围热点新闻，输入 @新闻 即可调用",
					"api",
					None,
					"",
					0,
					0,
					"https://api.vvhan.com/api/hotlist?type=baidu",
					"GET",
					'{"User-Agent": "Mozilla/5.0"}',
					'{}',
					"news",
					1,
					5
				)
			)
			print("默认新闻数字员工创建成功！")
		else:
			print("默认新闻数字员工已存在")
		
		# 检查是否存在默认小智数字员工
		xiaozhi_exists = conn.execute(
			"SELECT 1 FROM digital_employees WHERE name = ?",
			("小智",)
		).fetchone()
		
		if not xiaozhi_exists:
			conn.execute(
				"""
				INSERT INTO digital_employees (name, description, type, model_id, system_prompt, use_skills, use_crawl4ai, is_enabled, sort_order)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					"小智",
					"AI 聊天助手，输入 @小智 即可开始对话",
					"llm",
					None,
					"你是小智，一名友好、耐心的 AI 聊天助手。你能够回答用户的各类问题，进行自然流畅的对话，并在需要时提供清晰、有用的建议。",
					0,
					0,
					1,
					6
				)
			)
			print("默认小智数字员工创建成功！")
		else:
			print("默认小智数字员工已存在")
		
		# 同步并补充默认数字员工的排序与启用状态，确保六个员工均存在
		default_employees = ["采集专员", "天气", "文案写作助手", "随机音乐", "新闻", "小智"]
		for idx, emp_name in enumerate(default_employees, start=1):
			conn.execute(
				"UPDATE digital_employees SET sort_order = ? WHERE name = ?",
				(idx, emp_name)
			)
		
		# 为文案写作助手补充 WriteToolsAgent 的 .nd 提示文件，按角色->约束->场景->模板顺序拼接
		writer_row = conn.execute(
			"SELECT id FROM digital_employees WHERE name = ?",
			("文案写作助手",)
		).fetchone()
		if writer_row:
			writer_id = writer_row["id"]
			writer_dir = os.path.join(project_root(), "data", "dgUser", str(writer_id))
			os.makedirs(writer_dir, exist_ok=True)
			source_docs = os.path.join(project_root(), "temp", "WriteToolsAgent", "Docs")
			if os.path.isdir(source_docs):
				# 清理旧版无序号前缀的同名提示文件，避免内容重复
				for old_name in ["role.nd", "constraint.nd", "scene.nd", "template.nd"]:
					old_path = os.path.join(writer_dir, old_name)
					if os.path.exists(old_path):
						try:
							os.remove(old_path)
						except Exception:
							pass
				# 按顺序写入带前缀的 .nd 文件，保证 read_employee_nd_contents 读取顺序稳定
				ordered_docs = [
					("01_role.nd", "role.md"),
					("02_constraint.nd", "constraint.md"),
					("03_scene.nd", "scene.md"),
					("04_template.nd", "template.md"),
				]
				for dst_name, src_name in ordered_docs:
					src = os.path.join(source_docs, src_name)
					dst = os.path.join(writer_dir, dst_name)
					if os.path.exists(src):
						import shutil
						shutil.copy2(src, dst)
		
		# 创建前台对话会话表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS chat_sessions(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				user_id INTEGER NOT NULL,
				title TEXT,
				model_id INTEGER,
				employee_id INTEGER,
				is_pinned INTEGER DEFAULT 0, -- 是否置顶
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				FOREIGN KEY (user_id) REFERENCES users(id)
			)
			"""
		)
		
		# 创建前台对话消息表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS chat_messages(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				session_id INTEGER NOT NULL,
				role TEXT NOT NULL, -- 'user' 或 'assistant'
				content TEXT,
				model_id INTEGER,
				employee_id INTEGER,
				response_time REAL, -- 响应耗时（秒）
				token_count INTEGER, -- Token 数量
				is_edited INTEGER DEFAULT 0, -- 是否经过编辑重发
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
			)
			"""
		)
		
		# 迁移：为已有 chat_messages 表添加 response_time 和 token_count 字段
		try:
			conn.execute("ALTER TABLE chat_messages ADD COLUMN response_time REAL")
		except sqlite3.OperationalError:
			pass
		try:
			conn.execute("ALTER TABLE chat_messages ADD COLUMN token_count INTEGER")
		except sqlite3.OperationalError:
			pass
		# 迁移：为已有 chat_sessions 表添加 is_pinned 字段
		try:
			conn.execute("ALTER TABLE chat_sessions ADD COLUMN is_pinned INTEGER DEFAULT 0")
		except sqlite3.OperationalError:
			pass
		# 迁移：为已有 chat_messages 表添加 is_edited 字段
		try:
			conn.execute("ALTER TABLE chat_messages ADD COLUMN is_edited INTEGER DEFAULT 0")
		except sqlite3.OperationalError:
			pass
		
		# 创建敏感词库表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS sensitive_words(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				word TEXT NOT NULL UNIQUE,
				level INTEGER DEFAULT 1, -- 1-低, 2-中, 3-高
				description TEXT,
				is_enabled INTEGER DEFAULT 1,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 创建预警记录表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS alerts(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				user_id INTEGER,
				user_name TEXT,
				sensitive_word TEXT,
				content TEXT,
				content_type TEXT NOT NULL, -- 'chat' 或 'collected'
				source_id INTEGER, -- 会话ID或采集数据ID
				source_name TEXT, -- 会话标题或采集来源
				status TEXT DEFAULT 'pending', -- pending, ignored, handled, feedback_sent
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
				updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 创建通知表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS notifications(
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				user_id INTEGER NOT NULL,
				title TEXT NOT NULL,
				content TEXT NOT NULL,
				is_read INTEGER DEFAULT 0,
				created_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
			)
			"""
		)
		
		# 初始化默认敏感词 - 政治敏感类
		default_words = [
			("分裂", 3, "政治敏感-分裂国家"),
			("台独", 3, "政治敏感-分裂国家"),
			("港独", 3, "政治敏感-分裂国家"),
			("藏独", 3, "政治敏感-分裂国家"),
			("疆独", 3, "政治敏感-分裂国家"),
			("颠覆政权", 3, "政治敏感-颠覆政权"),
			("推翻政府", 3, "政治敏感-颠覆政权"),
			("叛国", 3, "政治敏感-危害国家安全"),
			("卖国", 3, "政治敏感-危害国家安全"),
			("间谍", 3, "政治敏感-危害国家安全"),
			("泄露国家机密", 3, "政治敏感-危害国家安全"),
			("暴乱", 3, "政治敏感-煽动动乱"),
			("暴动", 3, "政治敏感-煽动动乱"),
			("煽动颠覆", 3, "政治敏感-煽动颠覆"),
			("极端主义", 3, "政治敏感-极端主义"),
			("恐怖主义", 3, "政治敏感-恐怖主义"),
			("爆炸", 3, "暴力恐怖-爆炸袭击"),
			("炸弹", 3, "暴力恐怖-爆炸袭击"),
			("袭击", 3, "暴力恐怖-恐怖袭击"),
			("枪击", 3, "暴力恐怖-暴力行为"),
			("杀人", 3, "暴力恐怖-暴力行为"),
			("自杀", 3, "暴力恐怖-自杀行为"),
			("自残", 3, "暴力恐怖-自残行为"),
			("斩首", 3, "暴力恐怖-极端暴力"),
			("人肉炸弹", 3, "暴力恐怖-极端暴力"),
			("恐怖活动", 3, "暴力恐怖-恐怖活动"),
			("圣战", 3, "暴力恐怖-极端思想"),
			("ISIS", 3, "暴力恐怖-极端组织"),
			("IS", 3, "暴力恐怖-极端组织"),
			("色情", 3, "色情低俗-色情内容"),
			("裸照", 3, "色情低俗-色情内容"),
			("性爱", 3, "色情低俗-色情内容"),
			("性交", 3, "色情低俗-色情内容"),
			("自慰", 3, "色情低俗-色情内容"),
			("卖淫", 3, "色情低俗-卖淫嫖娼"),
			("嫖娼", 3, "色情低俗-卖淫嫖娼"),
			("鸡婆", 3, "色情低俗-低俗用语"),
			("婊子", 3, "色情低俗-侮辱性用语"),
			("草泥马", 3, "网络欺凌-辱骂"),
			("卧槽", 3, "网络欺凌-辱骂"),
			("傻逼", 3, "网络欺凌-辱骂"),
			("脑残", 3, "网络欺凌-辱骂"),
			("去死", 3, "网络欺凌-人身攻击"),
			("滚", 3, "网络欺凌-人身攻击"),
			("傻逼", 3, "网络欺凌-辱骂"),
			("畜生", 3, "网络欺凌-侮辱"),
			("狗日的", 3, "网络欺凌-辱骂"),
			("他妈的", 3, "网络欺凌-辱骂"),
			("操你妈", 3, "网络欺凌-辱骂"),
			("强奸", 3, "暴力恐怖-性暴力"),
			("轮奸", 3, "暴力恐怖-性暴力"),
			("侮辱", 2, "网络欺凌-侮辱"),
			("诽谤", 2, "网络欺凌-诽谤"),
			("人身攻击", 2, "网络欺凌-人身攻击"),
			("侵犯隐私", 2, "网络欺凌-侵犯隐私"),
			("人肉搜索", 2, "网络欺凌-人肉搜索"),
			("毒品", 3, "毒品违法-毒品名称"),
			("鸦片", 3, "毒品违法-毒品名称"),
			("海洛因", 3, "毒品违法-毒品名称"),
			("冰毒", 3, "毒品违法-毒品名称"),
			("大麻", 3, "毒品违法-毒品名称"),
			("可卡因", 3, "毒品违法-毒品名称"),
			("摇头丸", 3, "毒品违法-毒品名称"),
			("K粉", 3, "毒品违法-毒品名称"),
			("吸毒", 3, "毒品违法-吸毒行为"),
			("贩毒", 3, "毒品违法-贩毒行为"),
			("制毒", 3, "毒品违法-制毒行为"),
			("赌博", 3, "毒品违法-赌博"),
			("赌场", 3, "毒品违法-赌博"),
			("投注", 3, "毒品违法-赌博投注"),
			("彩票", 2, "毒品违法-彩票赌博"),
			("谣言", 2, "谣言虚假-谣言"),
			("虚假信息", 2, "谣言虚假-虚假信息"),
			("不实传闻", 2, "谣言虚假-不实传闻"),
			("恐慌", 2, "谣言虚假-引发恐慌"),
			("假消息", 2, "谣言虚假-假消息"),
			("邪教", 3, "宗教极端-邪教"),
			("极端宗教", 3, "宗教极端-极端思想"),
			("宗教极端", 3, "宗教极端-极端思想"),
			("煽动宗教", 3, "宗教极端-煽动对立"),
			("法轮功", 3, "宗教极端-邪教组织"),
			("全能神", 3, "宗教极端-邪教组织"),
			("封建迷信", 2, "迷信类-封建迷信"),
			("伪科学", 2, "迷信类-伪科学"),
			("算命", 2, "迷信类-算命占卜"),
			("占卜", 2, "迷信类-算命占卜"),
			("风水", 2, "迷信类-风水"),
			("灵异", 2, "迷信类-灵异"),
			("鬼", 2, "迷信类-鬼怪"),
			("神", 2, "迷信类-迷信"),
		]
		for word, level, desc in default_words:
			try:
				conn.execute(
					"INSERT OR IGNORE INTO sensitive_words (word, level, description) VALUES (?, ?, ?)",
					(word, level, desc)
				)
			except:
				pass
		
		try:
			from app.models.system_settings import SystemSettings
			SystemSettings.init_settings()
		except:
			pass
