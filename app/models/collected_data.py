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
	def collect_from_source(source, keyword, page=0):
		"""
		从指定数据源采集数据
		"""
		try:
			# 构建 URL
			base_url = source["base_url"]
			path_template = source["path_template"]
			
			# 计算分页步长（百度是每页10条）
			page_num = page * 10
			
			# 替换模板参数
			url = base_url + path_template.format(
				keyword=urllib.parse.quote(keyword),
				page=page_num
			)
			
			# 解析 headers
			headers = json.loads(source["headers"])
			
			# 修复：requests 可能无法处理 br 和 zstd 编码，强制改为 gzip, deflate
			if "Accept-Encoding" in headers:
				headers["Accept-Encoding"] = "gzip, deflate"
				
			# 修复：百度新闻必须有 Cookie 才能通过安全验证
			if source["name"] == "百度新闻" and "Cookie" not in headers:
				headers["Cookie"] = "BAIDUID=8A9A2116228B24C21CB8F516B31237EA:FG=1;"
			
			# 发送请求
			response = requests.get(url, headers=headers, timeout=30)
			response.encoding = "utf-8"
			
			# 解析百度新闻
			if source["name"] == "百度新闻":
				from bs4 import Comment
				soup = BeautifulSoup(response.text, "html.parser")
				results = []
				
				# 查找新闻项（百度新闻的结构）
				news_items = soup.find_all("div", class_="result-op")
				
				for item in news_items:
					# 百度新闻的数据通常存在于 <!--s-data:{...}--> 注释中，这种方式比匹配动态 class 更稳定
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
							except Exception as e:
								pass
				
				return {"success": True, "data": results, "count": len(results)}
			
			return {"success": True, "data": [], "count": 0}
		except Exception as e:
			print(f"采集数据错误: {e}")
			return {"success": False, "error": str(e)}
