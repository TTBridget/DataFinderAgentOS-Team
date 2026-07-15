"""
collected_data.py - 采集数据管理 Repository
"""
from .db import get_connection
import json
import urllib.parse
import requests
import re
from bs4 import BeautifulSoup


class CollectedDataRepository:
	@staticmethod
	def get_all(page=1, per_page=12, keyword="", source_ids=None):
		offset = (page - 1) * per_page
		with get_connection() as conn:
			conditions = []
			params = []
			
			# 关键词同时匹配标题与正文
			if keyword:
				conditions.append("(title LIKE ? OR content LIKE ?)")
				params.extend([f"%{keyword}%", f"%{keyword}%"])
			
			# 按选中的瞭源过滤
			if source_ids:
				placeholders = ",".join("?" for _ in source_ids)
				conditions.append(f"source_id IN ({placeholders})")
				params.extend(source_ids)
			
			where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
			
			sql = f"SELECT * FROM collected_data {where_clause} ORDER BY id DESC LIMIT ? OFFSET ?"
			rows = conn.execute(sql, (*params, per_page, offset)).fetchall()
			
			count_sql = f"SELECT COUNT(*) as total FROM collected_data {where_clause}"
			total = conn.execute(count_sql, params).fetchone()["total"]
			
			return {"items": rows, "total": total}
	
	@staticmethod
	def create(source_id, title, url, content, publish_time, source_name, keyword):
		with get_connection() as conn:
			cursor = conn.execute(
				"""
				INSERT INTO collected_data (source_id, title, url, content, publish_time, source_name, keyword)
				VALUES (?, ?, ?, ?, ?, ?, ?)
				""",
				(source_id, title, url, content, publish_time, source_name, keyword)
			)
			return cursor.lastrowid
	
	@staticmethod
	def clear():
		with get_connection() as conn:
			conn.execute("DELETE FROM collected_data")
			return True
	
	@staticmethod
	def count_by_source(source_id):
		"""按数据源ID统计采集数量"""
		with get_connection() as conn:
			result = conn.execute(
				"SELECT COUNT(*) as count FROM collected_data WHERE source_id = ?",
				(source_id,)
			).fetchone()
			return result["count"] if result else 0
	
	@staticmethod
	def _build_request_url(source, keyword, page):
		"""根据数据源模板构建请求 URL"""
		base_url = source["base_url"].rstrip("/")
		path_template = source["path_template"]
		
		# 微博热搜不需要关键词和分页
		if "热搜" in source["name"] and "微博" in source["name"]:
			return base_url + path_template
		
		# 计算分页步长（通用每页10条）
		page_num = page * 10
		
		return base_url + path_template.format(
			keyword=urllib.parse.quote(keyword),
			page=page_num
		)
	
	@staticmethod
	def _prepare_headers(source):
		"""解析并补全请求头"""
		headers = json.loads(source["headers"])
		
		# requests 可能无法处理 br 和 zstd 编码，强制改为 gzip, deflate
		if "Accept-Encoding" in headers:
			headers["Accept-Encoding"] = "gzip, deflate"
		
		name = source.get("name", "")
		
		# 百度类站点需要 Cookie 才能通过安全验证
		if "百度" in name and "Cookie" not in headers:
			headers["Cookie"] = "BAIDUID=8A9A2116228B24C21CB8F516B31237EA:FG=1;"
		
		# 微博类站点需要基础 Cookie，否则搜索会被拦截
		if "微博" in name and "Cookie" not in headers:
			headers["Cookie"] = "SUB=_2AkMUJySSf8NxqwFRmP8Ty2PrZY12zAvEieKjwkPXJRMxHRl-yT9jqkMStRB6OZUDzVfATJ2F0X1qP0V9YE7Yf-UKMMh;"
			headers["Referer"] = "https://s.weibo.com/"
		
		return headers
	
	@staticmethod
	def _parse_baidu_search(source, response_text, keyword):
		"""解析百度搜索结果页（兼容传统 result 与现代 result-molecule 结构）"""
		from bs4 import Comment
		soup = BeautifulSoup(response_text, "html.parser")
		results = []
		
		# 1) 先尝试新版 result-molecule 结果块
		molecules = soup.find_all("div", class_=re.compile(r"result-molecule"))
		for container in molecules:
			tpl = container.get("tpl", "")
			if not tpl or tpl in ("app/chat-input", "app/head-tab", "app/logo",
								"app/related-search", "app/page-banner"):
				continue
			
			comments = container.find_all(string=lambda text: isinstance(text, Comment))
			for c in comments:
				if c.startswith('s-data:'):
					try:
						data = json.loads(c[len('s-data:'):])
						title = data.get('title', '').replace('<em>', '').replace('</em>', '')
						link_url = data.get('titleUrl', '')
						content = data.get('summary', '').replace('<em>', '').replace('</em>', '')
						
						if not link_url and 'url' in data:
							link_url = data['url']
						
						if title and link_url:
							data_id = CollectedDataRepository.create(
								source["id"], title, link_url, content, "", "百度搜索", keyword
							)
							results.append({
								"id": data_id, "title": title, "url": link_url,
								"content": content, "publish_time": "",
								"source_name": "百度搜索", "keyword": keyword
							})
						break
					except Exception:
						pass
		
		# 2) 再尝试传统 result/c-container 结构
		containers = soup.find_all("div", class_=re.compile(r"result\b|c-container"))
		for container in containers:
			title_tag = container.find("h3") or container.find(class_="t")
			if not title_tag:
				continue
			
			link_tag = title_tag.find("a")
			if not link_tag or not link_tag.get("href"):
				continue
			
			title = link_tag.get_text(strip=True)
			link_url = link_tag["href"]
			
			abstract_tag = (
				container.find(class_="content-right_8Zs40")
				or container.find(class_="c-abstract")
				or container.find("span", class_=re.compile(r"abstract"))
			)
			content = abstract_tag.get_text(strip=True) if abstract_tag else ""
			
			comments = container.find_all(string=lambda text: isinstance(text, Comment))
			for c in comments:
				if c.startswith('s-data:'):
					try:
						data = json.loads(c[len('s-data:'):])
						title = data.get('title', title).replace('<em>', '').replace('</em>', '')
						link_url = data.get('titleUrl', link_url)
						content = data.get('summary', content).replace('<em>', '').replace('</em>', '')
						break
					except Exception:
						pass
			
			if title and link_url:
				data_id = CollectedDataRepository.create(
					source["id"], title, link_url, content, "", "百度搜索", keyword
				)
				results.append({
					"id": data_id, "title": title, "url": link_url,
					"content": content, "publish_time": "",
					"source_name": "百度搜索", "keyword": keyword
				})
		
		return results
	
	@staticmethod
	def _parse_baidu_news(source, response_text, keyword):
		"""解析百度新闻搜索结果页"""
		from bs4 import Comment
		soup = BeautifulSoup(response_text, "html.parser")
		results = []
		
		news_items = soup.find_all("div", class_="result-op")
		
		for item in news_items:
			comments = item.find_all(string=lambda text: isinstance(text, Comment))
			for c in comments:
				if c.startswith('s-data:'):
					try:
						data = json.loads(c[len('s-data:'):])
						title = data.get('title', '').replace('<em>', '').replace('</em>', '')
						link_url = data.get('titleUrl', '')
						content = data.get('summary', '').replace('<em>', '').replace('</em>', '')
						source_name = data.get('sourceName', data.get('source', ''))
						publish_time = data.get('dispTime', '')
						
						if title and link_url and content:
							data_id = CollectedDataRepository.create(
								source["id"], title, link_url, content, publish_time, source_name, keyword
							)
							results.append({
								"id": data_id, "title": title, "url": link_url,
								"content": content, "publish_time": publish_time,
								"source_name": source_name, "keyword": keyword
							})
					except Exception:
						pass
		
		return results
	
	@staticmethod
	def _parse_weibo_hot(source, response_text, keyword):
		"""解析微博热搜榜"""
		soup = BeautifulSoup(response_text, "html.parser")
		results = []
		
		tbody = soup.find("tbody")
		if tbody:
			rows = tbody.find_all("tr")
		else:
			rows = soup.find_all("tr")
		
		for row in rows:
			link_tag = row.find("a", href=re.compile(r"weibo"))
			if not link_tag:
				continue
			
			title = link_tag.get_text(strip=True)
			link_url = urllib.parse.urljoin("https://s.weibo.com", link_tag.get("href", ""))
			
			heat_tag = row.find("span")
			heat = heat_tag.get_text(strip=True) if heat_tag else ""
			content = f"热度：{heat}" if heat else ""
			
			if title:
				data_id = CollectedDataRepository.create(
					source["id"], title, link_url, content, "", "微博热搜", keyword
				)
				results.append({
					"id": data_id, "title": title, "url": link_url,
					"content": content, "publish_time": "",
					"source_name": "微博热搜", "keyword": keyword
				})
		
		return results
	
	@staticmethod
	def _parse_weibo_search(source, response_text, keyword):
		"""解析微博搜索结果页"""
		if "passport.weibo.com" in response_text or "Sina Visitor System" in response_text:
			raise Exception("微博搜索需要登录态，当前请求被重定向到访客验证页面，无法匿名采集")
		
		soup = BeautifulSoup(response_text, "html.parser")
		results = []
		
		cards = soup.find_all("div", class_="card-wrap")
		
		for card in cards:
			name_tag = card.find("a", class_="name")
			user_name = name_tag.get_text(strip=True) if name_tag else ""
			
			content_tag = card.find("p", class_="txt")
			if not content_tag:
				content_tag = card.find("div", class_="txt")
			content = content_tag.get_text(strip=True) if content_tag else ""
			
			time_tag = card.find("a", href=re.compile(r"weibo.com.*/\d+"))
			publish_time = time_tag.get_text(strip=True) if time_tag else ""
			link_url = time_tag.get("href", "") if time_tag else ""
			
			if content:
				title = content[:60] + "..." if len(content) > 60 else content
				data_id = CollectedDataRepository.create(
					source["id"], title, link_url, content, publish_time, user_name or "微博用户", keyword
				)
				results.append({
					"id": data_id, "title": title, "url": link_url,
					"content": content, "publish_time": publish_time,
					"source_name": user_name or "微博用户", "keyword": keyword
				})
		
		return results
	
	@staticmethod
	def collect_from_source(source, keyword, page=0):
		"""从指定数据源采集数据"""
		try:
			if not isinstance(source, dict):
				source = dict(source)
			
			url = CollectedDataRepository._build_request_url(source, keyword, page)
			headers = CollectedDataRepository._prepare_headers(source)
			
			response = requests.get(url, headers=headers, timeout=30)
			response.encoding = "utf-8"
			
			name = source.get("name", "")
			results = []
			
			if name == "百度新闻":
				results = CollectedDataRepository._parse_baidu_news(source, response.text, keyword)
			elif name == "百度搜索":
				results = CollectedDataRepository._parse_baidu_search(source, response.text, keyword)
			elif name == "微博热搜":
				results = CollectedDataRepository._parse_weibo_hot(source, response.text, keyword)
			elif name == "微博搜索":
				results = CollectedDataRepository._parse_weibo_search(source, response.text, keyword)
			
			return {"success": True, "data": results, "count": len(results)}
		except Exception as e:
			print(f"采集数据错误: {e}")
			return {"success": False, "error": str(e)}
