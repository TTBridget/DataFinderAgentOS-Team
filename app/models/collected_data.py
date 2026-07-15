"""
collected_data.py - 采集数据管理 Repository
"""
from .db import get_connection
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup


class CollectedDataRepository:
	@staticmethod
	def get_all(page=1, per_page=12, keyword=""):
		offset = (page - 1) * per_page
		with get_connection() as conn:
			if keyword:
				sql = "SELECT * FROM collected_data WHERE keyword LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?"
				rows = conn.execute(sql, (f"%{keyword}%", per_page, offset)).fetchall()
				count_sql = "SELECT COUNT(*) as total FROM collected_data WHERE keyword LIKE ?"
				total = conn.execute(count_sql, (f"%{keyword}%",)).fetchone()["total"]
			else:
				sql = "SELECT * FROM collected_data ORDER BY id DESC LIMIT ? OFFSET ?"
				rows = conn.execute(sql, (per_page, offset)).fetchall()
				count_sql = "SELECT COUNT(*) as total FROM collected_data"
				total = conn.execute(count_sql).fetchone()["total"]
			
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
	def collect_from_source(source, keyword, page=0):
		"""
		从指定数据源采集数据
		"""
		try:
			# 构建 URL
			base_url = source["base_url"]
			path_template = source["path_template"]
			
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
			
			# 微博需要特殊的headers
			if source["name"] in ["微博热搜", "微博搜索"] and "Cookie" not in headers:
				headers["Cookie"] = "SUB=_2A25I8K8mDeRhGeBN41AQ9S7PyjiIHXVkO5V2rDV_PUNbm9ANLVbkW9NMU2gPvE00a0yQH0X49q-2B6D8M6rD84FZ;"
				headers["Referer"] = "https://s.weibo.com/"
			
			# 发送请求
			response = requests.get(url, headers=headers, timeout=30)
			response.encoding = "utf-8"
			
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
			
			return {"success": True, "data": results, "count": len(results)}
		except Exception as e:
			print(f"采集数据错误: {e}")
			return {"success": False, "error": str(e)}
