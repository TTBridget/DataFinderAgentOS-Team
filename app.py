import os
import tornado.ioloop 
import tornado.web 
from tornado.httpserver import HTTPServer

from app.controllers.auth import LoginHandler, LogoutHandler, RegisterHandler
from app.controllers.home import IndexHandler
from app.controllers.chat import ChatHandler, ChatSessionHandler, ChatMessageHandler, ChatResendHandler, ChatExportHandler, ModelListHandler, EmployeeListHandler
from app.controllers.admin import AdminLoginHandler, AdminLogoutHandler, AdminIndexHandler, UserManageHandler, RoleManageHandler, FunctionManageHandler, MenuManageHandler, DataSourceManageHandler, WatchManageHandler, AiModelManageHandler, AiModelChatHandler, DataWarehouseManageHandler, DigitalEmployeeManageHandler
from app.controllers.dashboard import DashboardHandler, DashboardDataHandler
from app.controllers.public_sentiment import PublicSentimentHandler, PublicSentimentStatsHandler, PublicSentimentAlertsHandler, PublicSentimentAlertDetailHandler, PublicSentimentAlertActionHandler, PublicSentimentTrendHandler, PublicSentimentHotTopicsHandler, PublicSentimentRiskLevelHandler, PublicSentimentSensitiveWordsHandler, PublicSentimentScanHandler
from app.models.db import init_db



def webapp():
	#定义一个web应用程序，并配置访问各个模块/页面路由
	#整个程序的安全配置也需要在此处完成
	base_dir = os.path.dirname(os.path.abspath(__file__))
	cookie_secret = os.environ.get('COOKIE_SECRET')
	if not cookie_secret:
		raise RuntimeError("COOKIE_SECRET 环境变量未设置，请在启动前配置安全的随机密钥")
	debug = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
	settings = dict(
		template_path=os.path.join(base_dir,"app","templates"),
		static_path=os.path.join(base_dir,"app","static"),
		cookie_secret=cookie_secret,
		login_url="/",
		xsrf_cookies=True,
		debug=debug,
		autoreload=debug
	)
	return tornado.web.Application([
		#前台路由：http://host:port/
		(r"/", LoginHandler),
		(r"/login", LoginHandler),
		(r"/logout", LogoutHandler),
		(r"/register", RegisterHandler),
		(r"/index", IndexHandler),
		
		# 前台API路由
		(r"/api/chat", ChatHandler),
		(r"/api/chat/sessions", ChatSessionHandler),
		(r"/api/chat/messages", ChatMessageHandler),
		(r"/api/chat/resend", ChatResendHandler),
		(r"/api/chat/export", ChatExportHandler),
		(r"/api/models", ModelListHandler),
		(r"/api/employees", EmployeeListHandler),
		
		#后台路由：http://host:port/admin/
		(r"/admin/login", AdminLoginHandler),
		(r"/admin/logout", AdminLogoutHandler),
		(r"/admin/", AdminIndexHandler),
		(r"/admin/user", UserManageHandler),
		(r"/admin/role", RoleManageHandler),
		(r"/admin/function", FunctionManageHandler),
		(r"/admin/menu", MenuManageHandler),
		(r"/admin/data_source", DataSourceManageHandler),
		(r"/admin/watch", WatchManageHandler),
		(r"/admin/data_warehouse", DataWarehouseManageHandler),
		(r"/admin/digital", DigitalEmployeeManageHandler),
		(r"/admin/ai", AiModelManageHandler),
		(r"/admin/ai/chat", AiModelChatHandler),

		(r"/admin/dashboard", DashboardHandler),
		(r"/admin/dashboard/data", DashboardDataHandler),
		
		(r"/admin/public_sentiment", PublicSentimentHandler),
		(r"/admin/public_sentiment/stats", PublicSentimentStatsHandler),
		(r"/admin/public_sentiment/alerts", PublicSentimentAlertsHandler),
		(r"/admin/public_sentiment/alert/(\d+)", PublicSentimentAlertDetailHandler),
		(r"/admin/public_sentiment/alert_action", PublicSentimentAlertActionHandler),
		(r"/admin/public_sentiment/trend", PublicSentimentTrendHandler),
		(r"/admin/public_sentiment/hot_topics", PublicSentimentHotTopicsHandler),
		(r"/admin/public_sentiment/risk_level", PublicSentimentRiskLevelHandler),
		(r"/admin/public_sentiment/sensitive_words", PublicSentimentSensitiveWordsHandler),
		(r"/admin/public_sentiment/scan", PublicSentimentScanHandler),
	],
	**settings
	)

if __name__ == '__main__':
	init_db()
	webapp = webapp()
	#将应用程序部署到服务器
	server = HTTPServer(webapp)
	server.listen(10010)
	print("Server Started: http://localhost:10010/", flush=True)
	print("前台首页: http://localhost:10010/", flush=True)
	print("后台首页: http://localhost:10010/admin/", flush=True)
	tornado.ioloop.IOLoop.current().start()