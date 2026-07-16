import json
import os
import re
import time
import random
import asyncio
import urllib.parse
import datetime

import tornado.web
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

from app.controllers.base import BaseHandler
from app.models.chat import ChatSessionRepository, ChatMessageRepository
from app.models.ai_model import AiModelRepository
from app.models.digital_employee import DigitalEmployeeRepository, read_employee_nd_contents
from app.models.user import UserRepository
from app.models.skill import SkillRepository, SkillEngine
from app.services.intent_engine import recognize_intent, execute_database_query, generate_chart_config
from app.utils.security import safe_int, validate_llm_base_url, validate_employee_api_url


def _get_user_id(handler):
	"""根据当前登录用户名获取用户ID"""
	username = handler.current_user
	if not username:
		return None
	user = UserRepository.get_user_by_username(username)
	if user:
		return user["id"]
	return None


def _build_title_from_message(message, max_len=20):
	"""根据用户消息生成会话标题"""
	message = message.strip().replace('\n', ' ')
	if not message:
		return "新对话"
	if len(message) <= max_len:
		return message
	return message[:max_len] + "..."


def _translate_weather_desc(desc):
	"""将 wttr.in 英文天气描述翻译为中文"""
	if not desc:
		return "未知"
	mapping = {
		"Sunny": "晴",
		"Clear": "晴",
		"Partly cloudy": "多云",
		"Cloudy": "阴",
		"Overcast": "阴",
		"Rain": "雨",
		"Light rain": "小雨",
		"Moderate rain": "中雨",
		"Heavy rain": "大雨",
		"Torrential rain": "暴雨",
		"Showers": "阵雨",
		"Light snow": "小雪",
		"Moderate snow": "中雪",
		"Heavy snow": "大雪",
		"Snow": "雪",
		"Thunderstorm": "雷阵雨",
		"Thunder": "雷",
		"Fog": "雾",
		"Mist": "薄雾",
		"Haze": "霾",
		"Smoky haze": "雾霾",
		"Smoke": "烟雾",
		"Dust": "扬尘",
		"Sand": "沙尘",
		"Dusty": "扬尘",
		"Blizzard": "暴风雪",
		"Drizzle": "毛毛雨",
		"Freezing drizzle": "冻毛毛雨",
		"Freezing fog": "冻雾",
		"Ice pellets": "冰粒",
		"Light drizzle": "小毛毛雨",
		"Heavy drizzle": "大毛毛雨",
		"Light showers": "小阵雨",
		"Heavy showers": "大阵雨",
		"Light thunderstorm": "小雷阵雨",
		"Heavy thunderstorm": "大雷阵雨",
		"Patchy rain possible": "可能有零星小雨",
		"Patchy snow possible": "可能有零星小雪",
		"Patchy light rain": "零星小雨",
		"Patchy light snow": "零星小雪",
		"Thundery outbreaks possible": "可能有雷暴",
		"Blowing snow": "吹雪",
		"Windy": "大风",
		"Clear ": "晴",
	}
	result = mapping.get(desc.strip(), desc)
	# 如果仍然包含英文字母，说明没有匹配到翻译，尝试模糊匹配
	if result == desc and any(c.isalpha() for c in result):
		desc_lower = desc.lower()
		for en, zh in mapping.items():
			if en.lower() in desc_lower:
				return zh
	return result


def _estimate_tokens(text):
	"""粗略估算文本 Token 数（中文按约 1 字符/token，英文按约 4 字符/token）"""
	if not text:
		return 0
	# 简单统计：中文字符按 1 个 token，非中文按 4 字符 1 个 token
	cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
	other_chars = len(text) - cn_chars
	return max(1, cn_chars + other_chars // 4)


def _parse_weather_card(response_text, user_query=""):
	"""解析 wttr.in JSON 响应为天气卡片数据"""
	try:
		data = json.loads(response_text)
		current = data.get("current_condition", [{}])[0]

		# 优先使用用户输入的城市名（中文），其次尝试 API 返回的中文区域名
		city = user_query.strip() if user_query.strip() else ""
		if not city:
			area = data.get("nearest_area", [{}])[0]
			# 尝试中文区域名
			area_zh = area.get("areaName", [{}])
			if area_zh and isinstance(area_zh, list) and area_zh[0].get("value"):
				city = area_zh[0]["value"]
			else:
				city = "未知城市"

		# 优先读取中文天气描述（lang=zh 时 wttr.in 返回 lang_zh 字段）
		desc_zh = ""
		lang_zh = current.get("lang_zh", [])
		if lang_zh and isinstance(lang_zh, list) and lang_zh[0].get("value"):
			desc_zh = lang_zh[0]["value"]

		# 如果没有中文描述，尝试翻译英文描述
		desc_en = current.get("weatherDesc", [{}])[0].get("value", "") if current.get("weatherDesc") else ""
		description = desc_zh if desc_zh else _translate_weather_desc(desc_en)

		return {
			"city": city,
			"temperature": current.get("temp_C", "--"),
			"feels_like": current.get("FeelsLikeC", "--"),
			"description": description,
			"description_en": desc_en,
			"humidity": current.get("humidity", "--"),
			"wind_speed": current.get("windspeedKmph", "--"),
			"wind_dir": current.get("winddir16Point", ""),
			"pressure": current.get("pressure", "--"),
			"visibility": current.get("visibility", "--"),
			"uv_index": current.get("uvIndex", "--"),
			"observation_time": current.get("observation_time", "")
		}
	except Exception:
		return None


# 随机音乐曲目库（使用 SoundHelix 等可在线播放的示例音频）
_MUSIC_LIBRARY = [
	{"id": 1, "title": "夏日微风", "artist": "SoundHelix", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"},
	{"id": 2, "title": "城市霓虹", "artist": "SoundHelix", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"},
	{"id": 3, "title": "星际漫游", "artist": "SoundHelix", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3"},
	{"id": 4, "title": "清晨咖啡", "artist": "SoundHelix", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3"},
	{"id": 5, "title": "山间小溪", "artist": "SoundHelix", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3"},
	{"id": 6, "title": "午夜爵士", "artist": "SoundHelix", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3"},
	{"id": 7, "title": "电子脉冲", "artist": "SoundHelix", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-7.mp3"},
	{"id": 8, "title": "雨后彩虹", "artist": "SoundHelix", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3"},
	{"id": 9, "title": "远方旅途", "artist": "SoundHelix", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3"},
	{"id": 10, "title": "梦境花园", "artist": "SoundHelix", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3"},
]


def _get_random_music():
	"""获取一首随机音乐"""
	track = random.choice(_MUSIC_LIBRARY)
	return {
		"id": track["id"],
		"title": track["title"],
		"artist": track["artist"],
		"cover": "https://www.soundhelix.com/examples/mp3/SoundHelix.png",
		"url": track["url"]
	}


def _parse_news_card(response_text):
	"""解析热点新闻 API 响应为新闻卡片数据，兼容多种格式"""
	try:
		data = json.loads(response_text)
		items = []

		# 格式1：vvhan API — {"data": [{"title": "...", "url": "..."}]}
		# 格式2：60s API — {"data": {"news": ["新闻1", "新闻2", ...], "link": "..."}}
		# 格式3：直接列表 — [{"title": "...", "url": "..."}]
		if isinstance(data, dict):
			inner = data.get("data")
			if isinstance(inner, dict):
				# 60s API 格式
				news_list = inner.get("news", [])
				news_link = inner.get("link", "#")
				for item in news_list[:10]:
					if isinstance(item, str):
						items.append({"title": item, "url": news_link if news_link else "#"})
					elif isinstance(item, dict):
						title = item.get("title") or item.get("desc") or "无标题"
						url = item.get("url") or item.get("link") or news_link or "#"
						items.append({"title": str(title), "url": str(url)})
			elif isinstance(inner, list):
				# vvhan API 格式
				for item in inner[:10]:
					if isinstance(item, dict):
						title = item.get("title") or item.get("desc") or item.get("name") or "无标题"
						url = item.get("url") or item.get("link") or item.get("href") or "#"
						items.append({"title": str(title), "url": str(url)})
					elif isinstance(item, str):
						items.append({"title": item, "url": "#"})
		elif isinstance(data, list):
			for item in data[:10]:
				if isinstance(item, dict):
					title = item.get("title") or item.get("desc") or "无标题"
					url = item.get("url") or item.get("link") or "#"
					items.append({"title": str(title), "url": str(url)})
				elif isinstance(item, str):
					items.append({"title": item, "url": "#"})

		return {
			"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
			"items": items
		}
	except Exception:
		return None


def _fallback_news_card():
	"""新闻 API 失败时的兜底数据"""
	return {
		"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
		"items": [
			{"title": "当前热点新闻服务暂时不可用，请稍后重试", "url": "#"}
		]
	}


def _deep_collect_with_crawl4ai(url):
	"""使用 crawl4ai 进行深度采集（供 @采集专员 在前台调用）"""
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
		return {'title': title, 'content': content, 'success': True}
	else:
		error_msg = result.error_message if hasattr(result, 'error_message') else '未知错误'
		return {'title': None, 'content': None, 'success': False, 'error': error_msg}


class ModelListHandler(BaseHandler):
	"""获取模型引擎中可用模型列表"""
	
	@tornado.web.authenticated
	def get(self):
		default_model = AiModelRepository.get_default_model()
		result = AiModelRepository.get_all(1, 1000, "")
		models = []
		for m in result["items"]:
			model_dict = dict(m)
			model_dict["is_default"] = bool(default_model and model_dict["id"] == default_model["id"])
			# 向前台暴露模型信息时不得泄露 API 密钥
			model_dict.pop("api_key", None)
			models.append(model_dict)
		
		self.write({"code": 0, "data": models})


class EmployeeListHandler(BaseHandler):
	"""获取已启用的数字员工列表（前台可用）"""
	
	@tornado.web.authenticated
	def get(self):
		result = DigitalEmployeeRepository.get_all(1, 1000, "")
		employees = []
		for emp in result["items"]:
			if emp["is_enabled"] == 1:
				employees.append({
					"id": emp["id"],
					"name": emp["name"],
					"type": emp["type"],
					"description": emp["description"],
					"model_id": emp["model_id"],
					"card_type": emp["card_type"]
				})
		
		self.write({"code": 0, "data": employees})


class ChatSessionHandler(BaseHandler):
	"""对话会话管理"""
	
	@tornado.web.authenticated
	def get(self):
		"""获取当前用户的会话列表"""
		user_id = _get_user_id(self)
		if not user_id:
			self.write({"code": 1, "msg": "用户不存在"})
			return
		
		result = ChatSessionRepository.get_user_sessions(user_id)
		sessions = []
		for s in result["items"]:
			sessions.append({
				"id": s["id"],
				"title": s["title"],
				"model_id": s["model_id"],
				"employee_id": s["employee_id"],
				"is_pinned": s["is_pinned"],
				"created_at": s["created_at"],
				"updated_at": s["updated_at"]
			})
		
		self.write({"code": 0, "data": sessions})
	
	@tornado.web.authenticated
	def post(self):
		"""创建新会话"""
		user_id = _get_user_id(self)
		if not user_id:
			self.write({"code": 1, "msg": "用户不存在"})
			return
		
		action = self.get_body_argument("action", "create")
		
		if action == "create":
			model_id = self.get_body_argument("model_id", None)
			model_id = safe_int(model_id) if model_id else None
			session_id = ChatSessionRepository.create(user_id, title="新对话", model_id=model_id)
			self.write({"code": 0, "data": {"id": session_id, "title": "新对话"}})
			return
		
		if action == "update_title":
			session_id = safe_int(self.get_body_argument("session_id", 0), 0)
			title = self.get_body_argument("title", "").strip()
			if not session_id or not title:
				self.write({"code": 1, "msg": "参数错误"})
				return
			
			# 验证归属
			session = ChatSessionRepository.get_by_id(session_id)
			if not session or session["user_id"] != user_id:
				self.write({"code": 1, "msg": "无权操作"})
				return
			
			ChatSessionRepository.update_title(session_id, title)
			self.write({"code": 0, "msg": "更新成功"})
			return
		
		if action == "pin":
			session_id = safe_int(self.get_body_argument("session_id", 0), 0)
			is_pinned = safe_int(self.get_body_argument("is_pinned", 0), 0)
			if not session_id:
				self.write({"code": 1, "msg": "参数错误"})
				return
			
			session = ChatSessionRepository.get_by_id(session_id)
			if not session or session["user_id"] != user_id:
				self.write({"code": 1, "msg": "无权操作"})
				return
			
			ChatSessionRepository.update_pinned(session_id, user_id, is_pinned)
			self.write({"code": 0, "msg": "置顶状态更新成功"})
			return
		
		if action == "delete":
			session_id = safe_int(self.get_body_argument("session_id", 0), 0)
			if not session_id:
				self.write({"code": 1, "msg": "参数错误"})
				return
			
			# 显式校验会话归属后再删除
			session = ChatSessionRepository.get_by_id(session_id)
			if not session or session["user_id"] != user_id:
				self.write({"code": 1, "msg": "无权操作"})
				return
			
			ChatSessionRepository.delete(session_id, user_id)
			self.write({"code": 0, "msg": "删除成功"})
			return
		
		self.write({"code": 1, "msg": "未知操作"})


class ChatMessageHandler(BaseHandler):
	"""对话消息历史"""
	
	@tornado.web.authenticated
	def get(self):
		session_id = safe_int(self.get_argument("session_id", 0), 0)
		user_id = _get_user_id(self)
		if not session_id or not user_id:
			self.write({"code": 1, "msg": "参数错误"})
			return
		
		messages = ChatMessageRepository.get_session_messages(session_id, user_id)
		data = []
		for msg in messages:
			data.append({
				"id": msg["id"],
				"role": msg["role"],
				"content": msg["content"],
				"model_id": msg["model_id"],
				"employee_id": msg["employee_id"],
				"response_time": msg["response_time"],
				"token_count": msg["token_count"],
				"created_at": msg["created_at"]
			})
		
		self.write({"code": 0, "data": data})


class ChatResendHandler(BaseHandler):
	"""编辑并重发消息：更新指定用户消息，并删除其后的所有消息"""
	
	@tornado.web.authenticated
	def post(self):
		user_id = _get_user_id(self)
		if not user_id:
			self.write({"code": 1, "msg": "用户不存在"})
			return
		
		message_id = safe_int(self.get_body_argument("message_id", 0), 0)
		new_content = self.get_body_argument("content", "").strip()
		
		if not message_id or not new_content:
			self.write({"code": 1, "msg": "参数错误"})
			return
		
		msg = ChatMessageRepository.get_by_id(message_id)
		if not msg or msg["role"] != "user":
			self.write({"code": 1, "msg": "消息不存在或不可编辑"})
			return
		
		# 校验会话归属
		session = ChatSessionRepository.get_by_id(msg["session_id"])
		if not session or session["user_id"] != user_id:
			self.write({"code": 1, "msg": "无权操作"})
			return
		
		ChatMessageRepository.update_content_and_mark_edited(message_id, new_content)
		ChatMessageRepository.truncate_after(message_id, msg["session_id"])
		ChatSessionRepository.touch(msg["session_id"])
		
		self.write({"code": 0, "msg": "已更新消息，可重新发送"})


class ChatExportHandler(BaseHandler):
	"""导出当前会话为 PDF"""
	
	@tornado.web.authenticated
	def get(self):
		user_id = _get_user_id(self)
		session_id = safe_int(self.get_argument("session_id", 0), 0)
		
		if not user_id or not session_id:
			self.write({"code": 1, "msg": "参数错误"})
			return
		
		session = ChatSessionRepository.get_by_id(session_id)
		if not session or session["user_id"] != user_id:
			self.write({"code": 1, "msg": "无权操作"})
			return
		
		messages = ChatMessageRepository.get_session_messages(session_id, user_id)
		if not messages:
			self.write({"code": 1, "msg": "当前对话为空，无法导出"})
			return
		
		font_dir = os.path.normpath(
			os.path.join(os.path.dirname(__file__), os.pardir, "static", "fonts")
		)
		bundled_fonts = [
			os.path.join(font_dir, "NotoSansCJKsc-Regular.ttf"),
			os.path.join(font_dir, "NotoSansCJKsc-Regular.otf"),
		]
		windows_font_dir = os.path.join(
			os.environ.get("WINDIR", r"C:\Windows"), "Fonts"
		)
		system_fonts = [
			os.path.join(windows_font_dir, "simhei.ttf"),
			os.path.join(windows_font_dir, "msyh.ttc"),
			os.path.join(windows_font_dir, "simsun.ttc"),
		]
		font_path = next(
			(path for path in bundled_fonts + system_fonts if os.path.exists(path)),
			None,
		)

		# 优先使用项目内或 Windows 自带的中文字体。仅在两者都不存在时联网下载。
		if font_path is None:
			os.makedirs(font_dir, exist_ok=True)
			download_path = os.path.join(font_dir, "NotoSansCJKsc-Regular.otf")
			try:
				from tornado.httpclient import HTTPClient

				client = HTTPClient()
				try:
					resp = client.fetch(
						"https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/"
						"Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
						request_timeout=60,
						follow_redirects=True,
					)
				finally:
					client.close()

				with open(download_path, "wb") as file:
					file.write(resp.body)
				font_path = download_path
			except Exception:
				self.set_status(500)
				self.write({
					"code": 1,
					"msg": "PDF 导出失败：未找到可用的中文字体。"
				})
				return

		from fpdf import FPDF

		pdf = FPDF()
		pdf.add_page()
		try:
			pdf.add_font("DataFinderCJK", "", font_path)
			pdf.set_font("DataFinderCJK", "", 12)
		except Exception:
			self.set_status(500)
			self.write({
				"code": 1,
				"msg": "PDF 导出失败：中文字体加载失败。"
			})
			return

		# 标题
		pdf.set_font_size(16)
		pdf.cell(0, 10, txt=f"对话记录：{session['title'] or '未命名对话'}", ln=True, align="C")
		pdf.set_font_size(10)
		pdf.cell(0, 6, txt=f"导出时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
		pdf.ln(5)
		
		for msg in messages:
			role_label = "用户" if msg["role"] == "user" else "AI"
			pdf.set_font_size(10)
			pdf.set_text_color(22, 93, 255)
			pdf.cell(0, 6, txt=f"[{role_label}] {msg['created_at']}", ln=True)
			pdf.set_text_color(0, 0, 0)
			pdf.set_font_size(11)
			
			content = msg["content"] or ""
			# 去除 Markdown 简单标记，避免 PDF 中充斥星号等符号
			content = re.sub(r'```[\s\S]*?```', '[代码块]', content)
			content = re.sub(r'`([^`]+)`', r'\1', content)
			content = content.replace("**", "").replace("*", "")
			
			for line in content.split("\n"):
				pdf.multi_cell(0, 6, txt=line)
			pdf.ln(3)
		
		filename = f"chat_export_{session_id}_{int(time.time())}.pdf"
		self.set_header("Content-Type", "application/pdf")
		self.set_header("Content-Disposition", f"attachment; filename={filename}")
		self.write(pdf.output(dest="S"))


class ChatHandler(BaseHandler):
	"""SSE 对话接口"""
	
	@tornado.web.authenticated
	async def get(self):
		self.set_header("Content-Type", "text/event-stream")
		self.set_header("Cache-Control", "no-cache")
		self.set_header("Connection", "keep-alive")
		
		user_id = _get_user_id(self)
		if not user_id:
			self.write("data: " + json.dumps({"error": "用户不存在"}) + "\n\n")
			self.flush()
			return
		
		session_id = self.get_argument("session_id", None)
		message = self.get_argument("message", "").strip()
		model_id = self.get_argument("model_id", None)
		employee_id = self.get_argument("employee_id", None)
		resend_message_id = self.get_argument("resend_message_id", None)
		resend_message_id = safe_int(resend_message_id) if resend_message_id else None
		
		if not message:
			self.write("data: " + json.dumps({"error": "消息不能为空"}) + "\n\n")
			self.flush()
			return
		
		# 记录请求开始时间，用于计算响应耗时
		start_time = time.time()
		
		def _save_assistant_message(content, model_id=None, employee_id=None):
			"""保存助手回复并返回耗时/token等元信息"""
			response_time = round(time.time() - start_time, 2)
			token_count = _estimate_tokens(original_message) + _estimate_tokens(content)
			msg_id = ChatMessageRepository.create(
				session_id, "assistant", content,
				model_id=model_id, employee_id=employee_id,
				response_time=response_time, token_count=token_count
			)
			return {"response_time": response_time, "token_count": token_count, "message_id": msg_id}
		
		def _send_meta(meta):
			"""向前端推送元信息事件"""
			self.write("data: " + json.dumps({"type": "meta", "data": meta}) + "\n\n")
			self.flush()
		
		# 保留原始消息用于前端展示和历史记录
		original_message = message
		
		# 解析 @员工 指令
		mentioned_employee = None
		if message.startswith("@"):
			# 匹配 @员工名 或 @员工名+空格 的形式
			match = re.match(r"@([^\s]+)(?:\s+(.*))?$", message)
			if match:
				employee_name = match.group(1)
				content_after_at = (match.group(2) or "").strip()
				# 查找启用的数字员工
				emp_result = DigitalEmployeeRepository.get_all(1, 1000, "")
				for emp in emp_result["items"]:
					if emp["is_enabled"] == 1 and emp["name"] == employee_name:
						mentioned_employee = emp
						break
				
				if mentioned_employee:
					# sqlite3.Row 不支持 .get()，统一转换为 dict 使用
					mentioned_employee = dict(mentioned_employee)
					employee_id = mentioned_employee["id"]
					message = content_after_at
					if not message:
						message = "你好"
						# 天气员工默认查询北京
						if mentioned_employee["name"] == "天气":
							message = "北京"
		
		# 处理会话
		if session_id:
			session_id = safe_int(session_id, 0)
			if not session_id:
				session_id = None
			else:
				session = ChatSessionRepository.get_by_id(session_id)
				if not session or session["user_id"] != user_id:
					self.write("data: " + json.dumps({"error": "会话不存在"}) + "\n\n")
					self.flush()
					return
		
		# 统一解析模型和员工ID
		model_id_int = safe_int(model_id) if model_id else None
		employee_id_int = safe_int(employee_id) if employee_id else None
		
		if not session_id:
			# 自动创建新会话
			session_id = ChatSessionRepository.create(
				user_id,
				title=_build_title_from_message(message),
				model_id=model_id_int,
				employee_id=employee_id_int
			)
			# 发送会话信息
			self.write("data: " + json.dumps({"type": "session", "data": {"id": session_id, "title": _build_title_from_message(message)}}) + "\n\n")
			self.flush()
		else:
			# 更新会话模型/员工绑定
			if model_id_int:
				ChatSessionRepository.update_model(session_id, model_id_int)
			if employee_id_int:
				ChatSessionRepository.update_employee(session_id, employee_id_int)
			ChatSessionRepository.touch(session_id)
		
		# 保存用户消息（保留原始输入，便于历史记录和前端展示一致）
		# 若是编辑重发，则更新原消息而不是新建
		if resend_message_id:
			msg = ChatMessageRepository.get_by_id(resend_message_id)
			if msg and msg["session_id"] == session_id and msg["role"] == "user":
				ChatMessageRepository.update_content_and_mark_edited(resend_message_id, original_message)
				ChatMessageRepository.truncate_after(resend_message_id, session_id)
		else:
			ChatMessageRepository.create(session_id, "user", original_message, model_id=model_id_int, employee_id=employee_id_int)
		
		# 敏感词检测
		from app.services.sensitive_word_service import SensitiveWordService
		sensitive_matches = SensitiveWordService.scan_content(original_message)
		if sensitive_matches:
			warning_msg = "您的发言包含敏感词汇，请遵守社区规范"
			self.write("data: " + json.dumps({"type": "system_warning", "content": warning_msg}) + "\n\n")
			self.flush()
			
			username = self.current_user
			SensitiveWordService.scan_and_create_alerts(
				user_id,
				username,
				original_message,
				"chat",
				session_id,
				f"会话ID:{session_id}"
			)
			
			self.write("event: done\ndata: {}\n\n")
			self.flush()
			return
		
		# 确定使用的模型
		model = None
		if mentioned_employee and mentioned_employee["type"] == "llm":
			if mentioned_employee["model_id"]:
				model = AiModelRepository.get_by_id(mentioned_employee["model_id"])
			# 如果员工没有配置模型，使用默认模型
			if not model:
				model = AiModelRepository.get_default_model()
		elif model_id:
			model = AiModelRepository.get_by_id(safe_int(model_id, 0))
		else:
			# 尝试使用会话当前模型或默认模型
			session = ChatSessionRepository.get_by_id(session_id)
			if session and session["model_id"]:
				model = AiModelRepository.get_by_id(session["model_id"])
			if not model:
				model = AiModelRepository.get_default_model()
		
		# sqlite3.Row 不支持 .get()，统一转换为 dict 使用
		if model:
			model = dict(model)
		
		# 特殊数字员工：随机音乐、新闻（不依赖外部 API 配置，内置实现）
		if mentioned_employee and mentioned_employee["type"] == "api":
			emp_name = mentioned_employee["name"]
			api_url = mentioned_employee.get("api_url") or ""
			
			if emp_name == "随机音乐" or api_url.startswith("internal://music"):
				try:
					card_data = _get_random_music()
					display_text = f"随机推荐：{card_data['title']} - {card_data['artist']}"
					self.write("data: " + json.dumps({"content": display_text}) + "\n\n")
					self.flush()
					self.write("data: " + json.dumps({"type": "card", "card_type": "music", "card_data": card_data}) + "\n\n")
					self.flush()
					meta = _save_assistant_message(display_text, employee_id=mentioned_employee["id"])
					_send_meta(meta)
					self.write("event: done\ndata: {}\n\n")
					self.flush()
					return
				except Exception as e:
					error_msg = f"随机音乐获取失败: {str(e)}"
					self.write("data: " + json.dumps({"error": error_msg}) + "\n\n")
					self.flush()
					meta = _save_assistant_message(error_msg, employee_id=mentioned_employee["id"])
					_send_meta(meta)
					self.write("event: done\ndata: {}\n\n")
					self.flush()
					return
			
			if emp_name == "新闻":
				try:
					card_data = None
					client = AsyncHTTPClient()

					# 主 API：vvhan 热榜
					if validate_employee_api_url(api_url):
						try:
							request = HTTPRequest(url=api_url, method="GET", headers={"User-Agent": "Mozilla/5.0"}, request_timeout=10, follow_redirects=True)
							response = await client.fetch(request)
							response_text = response.body.decode("utf-8", errors="replace")
							card_data = _parse_news_card(response_text)
						except Exception:
							card_data = None

					# 备用 API：60s 读懂世界
					if not card_data or not card_data.get("items"):
						try:
							backup_url = "https://60s.viki.moe/v2/60s"
							request2 = HTTPRequest(url=backup_url, method="GET", headers={"User-Agent": "Mozilla/5.0"}, request_timeout=10, follow_redirects=True)
							response2 = await client.fetch(request2)
							response_text2 = response2.body.decode("utf-8", errors="replace")
							card_data = _parse_news_card(response_text2)
						except Exception:
							pass

					# 最终兜底
					if not card_data or not card_data.get("items"):
						card_data = _fallback_news_card()

					display_text = f"当前全国热点新闻（共 {len(card_data.get('items', []))} 条）"
					self.write("data: " + json.dumps({"content": display_text}) + "\n\n")
					self.flush()
					self.write("data: " + json.dumps({"type": "card", "card_type": "news", "card_data": card_data}) + "\n\n")
					self.flush()
					meta = _save_assistant_message(display_text, employee_id=mentioned_employee["id"])
					_send_meta(meta)
					self.write("event: done\ndata: {}\n\n")
					self.flush()
					return
				except Exception as e:
					card_data = _fallback_news_card()
					display_text = f"当前全国热点新闻（共 {len(card_data.get('items', []))} 条）"
					self.write("data: " + json.dumps({"content": display_text}) + "\n\n")
					self.flush()
					self.write("data: " + json.dumps({"type": "card", "card_type": "news", "card_data": card_data}) + "\n\n")
					self.flush()
					meta = _save_assistant_message(display_text, employee_id=mentioned_employee["id"])
					_send_meta(meta)
					self.write("event: done\ndata: {}\n\n")
					self.flush()
					return
		
		# 非 @员工 场景下，进行意图识别与工具调度
		if not mentioned_employee and model:
			try:
				intent_result = await recognize_intent(original_message, model)
				intent = intent_result.get("intent", "chat")
			except Exception:
				intent = "chat"
			
			if intent in ("database_query", "chart_request"):
				try:
					query_result = await execute_database_query(original_message, model)
					if query_result.get("error"):
						raise Exception(query_result["error"])
					
					rows = query_result.get("data", [])
					columns = query_result.get("columns", [])
					analysis = query_result.get("analysis") or ""
					query_type = query_result.get("query_type", "database_query")
					
					# 构建展示文本：AI 分析解读 + 详细数据表格（不暴露 SQL）
					display_parts = []
					if analysis:
						display_parts.append(analysis)
					
					if rows and columns:
						if analysis:
							display_parts.append("\n\n详细数据：")
						else:
							display_parts.append("查询结果如下：")
						display_parts.append(" | ".join(columns))
						for row in rows[:20]:
							display_parts.append(" | ".join(str(row.get(c, "")) for c in columns))
						if len(rows) > 20:
							display_parts.append(f"... 共 {len(rows)} 条，仅展示前 20 条")
					elif not analysis:
						display_parts.append("未查询到相关数据。")
					
					display_text = "\n".join(display_parts)
					
					# 流式发送文本
					chunk_size = 50
					for i in range(0, len(display_text), chunk_size):
						chunk = display_text[i:i+chunk_size]
						self.write("data: " + json.dumps({"content": chunk}) + "\n\n")
						self.flush()
						await asyncio.sleep(0.01)
					
					# 图表请求：生成图表配置并推送
					if intent == "chart_request":
						chart_config = await generate_chart_config(original_message, query_result, model)
						if chart_config:
							self.write("data: " + json.dumps({
								"type": "chart",
								"chart_type": chart_config.get("type", "bar"),
								"chart_config": chart_config,
								"chart_data": rows
							}) + "\n\n")
							self.flush()
					
					# 保存完整回复并发送元信息
					meta = _save_assistant_message(display_text, model_id=model["id"] if model else None)
					_send_meta(meta)
					
					self.write("event: done\ndata: {}\n\n")
					self.flush()
					return
					
				except Exception as e:
					error_msg = f"数据库查询失败: {str(e)}"
					self.write("data: " + json.dumps({"error": error_msg}) + "\n\n")
					self.flush()
					meta = _save_assistant_message(error_msg, model_id=model["id"] if model else None)
					_send_meta(meta)
					self.write("event: done\ndata: {}\n\n")
					self.flush()
					return
		
		# API 类型数字员工处理
		if mentioned_employee and mentioned_employee["type"] == "api":
			try:
				api_url = mentioned_employee["api_url"]
				if not validate_employee_api_url(api_url):
					raise ValueError("数字员工 API URL 不合法或存在 SSRF 风险")
				
				api_method = mentioned_employee["api_method"] or "GET"
				api_headers = mentioned_employee["api_headers"]
				api_params = mentioned_employee["api_params"]
				
				headers = {"Content-Type": "application/json"}
				if api_headers:
					try:
						headers.update(json.loads(api_headers))
					except Exception:
						pass
				
				params = {}
				if api_params:
					try:
						params = json.loads(api_params)
					except Exception:
						pass
				
				# 将用户消息追加到参数中（如果有 query/message 字段则填充）
				for key in params:
					if isinstance(params[key], str) and "{" in params[key]:
						params[key] = params[key].replace("{message}", message).replace("{query}", message)
				
				# 替换 URL 路径中的占位符（如天气员工的 https://wttr.in/{query}）
				if api_url and "{" in api_url:
					encoded_message = urllib.parse.quote(message)
					api_url = api_url.replace("{message}", encoded_message).replace("{query}", encoded_message)
				
				client = AsyncHTTPClient()
				method = api_method.upper()
				if method == "GET":
					url = api_url
					if params:
						url += "?" + urllib.parse.urlencode(params)
					request = HTTPRequest(url=url, method="GET", headers=headers, request_timeout=15, follow_redirects=False)
				elif method == "POST":
					request = HTTPRequest(url=api_url, method="POST", headers=headers, body=json.dumps(params), request_timeout=15, follow_redirects=False)
				else:
					raise Exception(f"不支持的请求方法: {api_method}")
				
				response = await client.fetch(request)
				response_text = response.body.decode("utf-8", errors="replace")
				
				card_type = mentioned_employee["card_type"]
				card_data = None
				display_text = response_text
				
				# 根据卡片类型解析数据并生成展示文本
				if card_type == "weather":
					card_data = _parse_weather_card(response_text, message)
					if card_data:
						display_text = f"{card_data['city']}：{card_data['description']}，气温{card_data['temperature']}°C，湿度{card_data['humidity']}%，风速{card_data['wind_speed']}km/h"
				elif card_type in ("json", "table"):
					try:
						card_data = json.loads(response_text)
						display_text = json.dumps(card_data, ensure_ascii=False, indent=2)
					except Exception:
						card_data = {"raw": response_text}
				elif card_type == "html":
					card_data = {"html": response_text}
				else:
					# 默认尝试美化 JSON
					try:
						response_json = json.loads(response_text)
						display_text = json.dumps(response_json, ensure_ascii=False, indent=2)
					except Exception:
						pass
				
				# 流式发送展示文本，模拟打字效果
				chunk_size = 50
				for i in range(0, len(display_text), chunk_size):
					chunk = display_text[i:i+chunk_size]
					self.write("data: " + json.dumps({"content": chunk}) + "\n\n")
					self.flush()
					await asyncio.sleep(0.02)
				
				# 推送卡片事件（供前端渲染数据卡片）
				if card_data:
					self.write("data: " + json.dumps({"type": "card", "card_type": card_type, "card_data": card_data}) + "\n\n")
					self.flush()
				
				# 保存完整回复并发送元信息
				meta = _save_assistant_message(
					display_text,
					model_id=model["id"] if model else None,
					employee_id=mentioned_employee["id"]
				)
				_send_meta(meta)
				
				self.write("event: done\ndata: {}\n\n")
				self.flush()
				
			except Exception as e:
				error_msg = f"数字员工调用失败: {str(e)}"
				self.write("data: " + json.dumps({"error": error_msg}) + "\n\n")
				self.flush()
				meta = _save_assistant_message(error_msg, employee_id=mentioned_employee["id"])
				_send_meta(meta)
				self.write("event: done\ndata: {}\n\n")
				self.flush()
			return
		
		if not model:
			self.write("data: " + json.dumps({"error": "未找到可用模型，请先配置模型引擎"}) + "\n\n")
			self.flush()
			return
		
		# 构建消息历史
		history_messages = []
		system_content_parts = []
		if mentioned_employee and mentioned_employee["type"] == "llm":
			if mentioned_employee["system_prompt"]:
				system_content_parts.append(mentioned_employee["system_prompt"])
			# 动态读取该员工目录下的 .nd 文件内容并补充到 system prompt
			nd_contents = read_employee_nd_contents(mentioned_employee["id"])
			if nd_contents:
				system_content_parts.append(nd_contents)
			# 若启用技能增强，将已启用技能注入系统提示词
			if mentioned_employee.get("use_skills") == 1:
				skills = SkillRepository.get_enabled()
				enhanced = SkillEngine.apply_skills("\n\n".join(system_content_parts), skills, message)
				system_content_parts = [enhanced]
		elif model["system_prompt"]:
			system_content_parts.append(model["system_prompt"])
		
		if system_content_parts:
			history_messages.append({"role": "system", "content": "\n\n".join(system_content_parts)})
		
		# 追加最近 10 条历史消息
		past_messages = ChatMessageRepository.get_session_messages(session_id, user_id)
		for msg in past_messages[-10:]:
			if msg["role"] in ("user", "assistant"):
				history_messages.append({"role": msg["role"], "content": msg["content"]})
		
		# 若当前员工是采集专员且启用了网页抓取，尝试从用户消息中提取 URL 并采集内容
		collected_context = ""
		if mentioned_employee and mentioned_employee["name"] == "采集专员" and mentioned_employee.get("use_crawl4ai") == 1:
			urls = re.findall(r'https?://[^\s<>"\']+', message)
			if urls:
				target_url = urls[0]
				self.write("data: " + json.dumps({"content": f"正在采集 {target_url} 的详细内容，请稍候..."}) + "\n\n")
				self.flush()
				try:
					crawl_result = _deep_collect_with_crawl4ai(target_url)
					if crawl_result.get("success"):
						title = crawl_result.get("title") or "未获取标题"
						content = crawl_result.get("content") or ""
						# 限制上下文长度，避免超出模型上下文
						max_content_len = 6000
						if len(content) > max_content_len:
							content = content[:max_content_len] + "\n...（内容已截断）"
						collected_context = f"【采集到的网页内容】\n标题：{title}\nURL：{target_url}\n正文：\n{content}\n\n请基于以上内容回答用户问题，并可生成表格或报表呈现关键数据。"
					else:
						collected_context = f"【采集提示】网页 {target_url} 采集失败：{crawl_result.get('error', '未知错误')}，请用户提供可访问的链接或补充描述。"
				except Exception as e:
					collected_context = f"【采集提示】采集过程发生异常：{str(e)}，请稍后重试。"
		
		# 添加当前消息
		final_user_content = message
		if collected_context:
			final_user_content = f"{collected_context}\n\n{message}"
		history_messages.append({"role": "user", "content": final_user_content})
		
		# 调用模型
		try:
			if not validate_llm_base_url(model.get("base_url", "")):
				raise ValueError("模型 Base URL 不合法或存在 SSRF 风险")
			
			client = AsyncHTTPClient()
			
			headers = {
				"Content-Type": "application/json",
				"Authorization": f"Bearer {model['api_key'] or ''}"
			}
			
			payload = {
				"model": model["name"],
				"messages": history_messages,
				"temperature": float(model["temperature"] or 0.7),
				"top_p": float(model["top_p"] or 1.0),
				"max_tokens": int(model["max_tokens"] or 2048),
				"stream": True
			}
			
			url = model["base_url"] or ""
			if not url.endswith("/"):
				url += "/"
			url += "chat/completions"
			
			full_response = []
			
			def streaming_callback(chunk):
				chunk_str = chunk.decode("utf-8", errors="replace")
				for line in chunk_str.split("\n"):
					if line.startswith("data: "):
						data_str = line[6:]
						if data_str == "[DONE]":
							continue
						try:
							data_json = json.loads(data_str)
							if "choices" in data_json and len(data_json["choices"]) > 0:
								delta = data_json["choices"][0].get("delta", {})
								if "content" in delta:
									content = delta["content"]
									if content:
										full_response.append(content)
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
			
			await client.fetch(request)
			
			# 保存完整回复并发送元信息
			full_text = "".join(full_response)
			if not full_text:
				full_text = "模型未返回有效内容"
				self.write("data: " + json.dumps({"content": full_text}) + "\n\n")
				self.flush()
			
			meta = _save_assistant_message(
				full_text,
				model_id=model["id"],
				employee_id=employee_id_int
			)
			_send_meta(meta)
			
			# 更新 token 使用量
			AiModelRepository.increment_tokens(model["id"], meta["token_count"])
			
			self.write("event: done\ndata: {}\n\n")
			self.flush()
			
		except Exception as e:
			error_msg = f"模型请求失败: {str(e)}"
			self.write("data: " + json.dumps({"error": error_msg}) + "\n\n")
			self.flush()
			meta = _save_assistant_message(error_msg, model_id=model["id"] if model else None)
			_send_meta(meta)
			self.write("event: done\ndata: {}\n\n")
			self.flush()
