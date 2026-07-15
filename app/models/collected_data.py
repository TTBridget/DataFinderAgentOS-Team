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
<<<<<<< HEAD
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
			# 跳过非搜索结果组件（如输入框、tab 栏）
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
						
						# 某些结果 titleUrl 为空，尝试从其他字段补全
						if not link_url and 'url' in data:
							link_url = data['url']
						
						if title and link_url:
							data_id = CollectedDataRepository.create(
								source["id"],
								title,
								link_url,
								content,
								"",
								"百度搜索",
								keyword
							)
							results.append({
								"id": data_id,
								"title": title,
								"url": link_url,
								"content": content,
								"publish_time": "",
								"source_name": "百度搜索",
								"keyword": keyword
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
					source["id"],
					title,
					link_url,
					content,
					"",
					"百度搜索",
					keyword
				)
				results.append({
					"id": data_id,
					"title": title,
					"url": link_url,
					"content": content,
					"publish_time": "",
					"source_name": "百度搜索",
					"keyword": keyword
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
								source["id"],
								title,
								link_url,
								content,
								publish_time,
								source_name,
								keyword
							)
							results.append({
								"id": data_id,
								"title": title,
								"url": link_url,
								"content": content,
								"publish_time": publish_time,
								"source_name": source_name,
								"keyword": keyword
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
			
			# 热度
			heat_tag = row.find("span")
			heat = heat_tag.get_text(strip=True) if heat_tag else ""
			
			content = f"热度：{heat}" if heat else ""
			
			if title:
				data_id = CollectedDataRepository.create(
					source["id"],
					title,
					link_url,
					content,
					"",
					"微博热搜",
					keyword
				)
				results.append({
					"id": data_id,
					"title": title,
					"url": link_url,
					"content": content,
					"publish_time": "",
					"source_name": "微博热搜",
					"keyword": keyword
				})
		
		return results
	
	@staticmethod
	def _parse_weibo_search(source, response_text, keyword):
		"""解析微博搜索结果页"""
		# 微博搜索需要登录态，若被重定向到登录/访客页则明确报错
		if "passport.weibo.com" in response_text or "Sina Visitor System" in response_text:
			raise Exception("微博搜索需要登录态，当前请求被重定向到访客验证页面，无法匿名采集")
		
		soup = BeautifulSoup(response_text, "html.parser")
		results = []
		
		cards = soup.find_all("div", class_="card-wrap")
		
		for card in cards:
			# 用户名
			name_tag = card.find("a", class_="name")
			user_name = name_tag.get_text(strip=True) if name_tag else ""
			
			# 微博内容
			content_tag = card.find("p", class_="txt")
			if not content_tag:
				content_tag = card.find("div", class_="txt")
			content = content_tag.get_text(strip=True) if content_tag else ""
			
			# 发布时间
			time_tag = card.find("a", href=re.compile(r"weibo.com.*/\d+"))
			publish_time = time_tag.get_text(strip=True) if time_tag else ""
			link_url = time_tag.get("href", "") if time_tag else ""
			
			if content:
				title = content[:60] + "..." if len(content) > 60 else content
				data_id = CollectedDataRepository.create(
					source["id"],
					title,
					link_url,
					content,
					publish_time,
					user_name or "微博用户",
					keyword
				)
				results.append({
					"id": data_id,
					"title": title,
					"url": link_url,
					"content": content,
					"publish_time": publish_time,
					"source_name": user_name or "微博用户",
					"keyword": keyword
				})
		
		return results
=======
	def count_by_source(source_id):
		"""按数据源ID统计采集数量"""
		with get_connection() as conn:
			result = conn.execute(
				"SELECT COUNT(*) as count FROM collected_data WHERE source_id = ?",
				(source_id,)
			).fetchone()
			return result["count"] if result else 0
>>>>>>> main
	
	@staticmethod
	def collect_from_source(source, keyword, page=0):
		"""
		从指定数据源采集数据
		"""
		try:
			# 统一转换为 dict，兼容 sqlite3.Row 与字典
			if not isinstance(source, dict):
				source = dict(source)
			
<<<<<<< HEAD
			url = CollectedDataRepository._build_request_url(source, keyword, page)
			headers = CollectedDataRepository._prepare_headers(source)
=======
			# 根据数据源类型计算分页参数
			if source["name"] == "百度新闻":
				page_num = page * 10
			elif source["name"] == "百度搜索":
				page_num = page * 10
			elif source["name"] == "微博搜索":
				page_num = page + 1
			else:
				page_num = page
			
			# 安全替换模板参数
			import re
			url = base_url + path_template
			if "{keyword}" in url:
				url = url.replace("{keyword}", urllib.parse.quote(keyword))
			if "{page}" in url:
				url = url.replace("{page}", str(page_num))
			
			# 解析 headers
			headers = json.loads(source["headers"])
			
			# 修复：requests 可能无法处理 br 和 zstd 编码，强制改为 gzip, deflate
			if "Accept-Encoding" in headers:
				headers["Accept-Encoding"] = "gzip, deflate"
				
			# 修复：百度新闻必须有 Cookie 才能通过安全验证
			if source["name"] == "百度新闻" and "Cookie" not in headers:
				headers["Cookie"] = "BAIDUID=8A9A2116228B24C21CB8F516B31237EA:FG=1;"
>>>>>>> main
			
			# 微博需要特殊的headers
			if source["name"] in ["微博热搜", "微博搜索"] and "Cookie" not in headers:
				headers["Cookie"] = "SUB=_2A25I8K8mDeRhGeBN41AQ9S7PyjiIHXVkO5V2rDV_PUNbm9ANLVbkW9NMU2gPvE00a0yQH0X49q-2B6D8M6rD84FZ;"
				headers["Referer"] = "https://s.weibo.com/"
			
			# 发送请求
			response = requests.get(url, headers=headers, timeout=30)
			response.encoding = "utf-8"
			
<<<<<<< HEAD
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
=======
			# 调试：打印响应状态和长度
			print(f"采集{source['name']}: URL={url}, 状态={response.status_code}, 长度={len(response.text)}")
			
			soup = BeautifulSoup(response.text, "html.parser")
			results = []
			
			if source["name"] == "百度新闻":
				from bs4 import Comment
				news_items = soup.find_all("div", class_="result-op")
				for item in news_items:
					comments = item.find_all(string=lambda text: isinstance(text, Comment))
					for c in comments:
						if c.startswith('s-data:'):
							try:
								data_str = c[len('s-data:'):]
								data = json.loads(data_str)
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
										"id": data_id, "title": title, "url": link_url, "content": content,
										"publish_time": publish_time, "source_name": source_name, "keyword": keyword
									})
							except Exception:
								pass
			
			elif source["name"] == "百度搜索":
				search_items = soup.find_all("div", class_="result")
				for item in search_items:
					title_tag = item.find("h3") or item.find("h2")
					link_tag = item.find("a")
					summary_tag = item.find("div", class_="c-abstract") or item.find("p", class_="content-right_8Zs40")
					if title_tag and link_tag:
						title = title_tag.get_text(strip=True)
						link_url = link_tag.get("href", "")
						content = summary_tag.get_text(strip=True) if summary_tag else ""
						source_name = "百度搜索"
						publish_time = ""
						if title and link_url:
							data_id = CollectedDataRepository.create(
								source["id"], title, link_url, content, publish_time, source_name, keyword
							)
							results.append({
								"id": data_id, "title": title, "url": link_url, "content": content,
								"publish_time": publish_time, "source_name": source_name, "keyword": keyword
							})
			
			elif source["name"] == "微博热搜":
				hot_list = soup.find("tbody")
				if hot_list:
					rows = hot_list.find_all("tr")
					for row in rows:
						title_tag = row.find("td", class_="td-02")
						if title_tag:
							a_tag = title_tag.find("a")
							if a_tag:
								title = a_tag.get_text(strip=True)
								link_href = a_tag.get("href", "")
								if link_href.startswith("//"):
									link_url = "https:" + link_href
								elif not link_href.startswith("http"):
									link_url = "https://s.weibo.com" + link_href
								else:
									link_url = link_href
								hot_value_tag = row.find("td", class_="td-03")
								content = "热度: " + hot_value_tag.get_text(strip=True) if hot_value_tag else ""
								source_name = "微博热搜"
								publish_time = ""
								if title and link_url:
									data_id = CollectedDataRepository.create(
										source["id"], title, link_url, content, publish_time, source_name, keyword
									)
									results.append({
										"id": data_id, "title": title, "url": link_url, "content": content,
										"publish_time": publish_time, "source_name": source_name, "keyword": keyword
									})
			
			elif source["name"] == "微博搜索":
				card_list = soup.find_all("div", class_="card")
				for card in card_list:
					main_card = card.find("div", class_="card-main") or card.find("div", class_="content")
					if main_card:
						title_tag = main_card.find("h3", class_="name") or main_card.find("a", class_="name")
						content_tag = main_card.find("p", class_="txt") or main_card.find("p")
						if title_tag and content_tag:
							title = title_tag.get_text(strip=True)
							content = content_tag.get_text(strip=True)
							link_tag = card.find("a", class_="from") or card.find("a", class_="expand")
							if link_tag:
								link_href = link_tag.get("href", "")
								if link_href.startswith("//"):
									link_url = "https:" + link_href
								elif not link_href.startswith("http"):
									link_url = "https://s.weibo.com" + link_href
								else:
									link_url = link_href
							else:
								link_url = ""
							source_name = "微博"
							publish_time = ""
							if title and content:
								data_id = CollectedDataRepository.create(
									source["id"], title, link_url, content, publish_time, source_name, keyword
								)
								results.append({
									"id": data_id, "title": title, "url": link_url, "content": content,
									"publish_time": publish_time, "source_name": source_name, "keyword": keyword
								})
>>>>>>> main
			
			return {"success": True, "data": results, "count": len(results)}
		except Exception as e:
			print(f"采集数据错误: {e}")
			return {"success": False, "error": str(e)}
