"""
系统配置文件
所有配置项集中管理
"""

import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 应用配置
APP_CONFIG = {
    'name': 'DataFinderAgentOS',
    'version': '1.0.0',
    'debug': os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes'),
    'port': 10010,
    'cookie_secret': os.environ.get('COOKIE_SECRET', ''),
    'login_url': '/',
    'xsrf_cookies': True,
}

# 数据库配置
DATABASE_CONFIG = {
    'path': os.path.join(BASE_DIR, 'database', 'finderos.db'),
}

# 模板和静态文件配置
TEMPLATE_CONFIG = {
    'template_path': os.path.join(BASE_DIR, 'app', 'templates'),
    'static_path': os.path.join(BASE_DIR, 'app', 'static'),
}

# OpenAI 配置（大模型集成）
OPENAI_CONFIG = {
    'api_key': os.environ.get('OPENAI_API_KEY', ''),
    'model': 'gpt-3.5-turbo',
    'temperature': 0.7,
    'max_tokens': 2000,
}

# 安全配置
SECURITY_CONFIG = {
    'password_hash_iterations': 100000,
    'session_timeout': 3600,  # 会话超时时间（秒）
    'csrf_enabled': True,
}

# 日志配置
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file_path': os.path.join(BASE_DIR, 'logs', 'app.log'),
}
