# DataFinderAgentOS 代码模板规范

## Controller 模板

### 基础 Controller 模板

```python
import tornado.web
from app.controllers.base import BaseHandler

class ExampleHandler(BaseHandler):
	"""示例 Controller"""
	
	def get(self):
		"""GET 请求处理"""
		self.render("example.html", title="示例页面")
	
	def post(self):
		"""POST 请求处理"""
		# 获取参数
		param = self.get_body_argument("param_name", "")
		# 处理逻辑
		self.redirect("/index")
```

### 需要认证的 Controller 模板

```python
import tornado.web
from app.controllers.base import BaseHandler

class ProtectedHandler(BaseHandler):
	"""需要认证的页面"""
	
	@tornado.web.authenticated
	def get(self):
		"""需要登录才能访问的页面"""
		self.render("protected.html", 
			title="受保护页面", 
			username=self.current_user)
```

## Repository 模板

### Repository 类模板

```python
"""
[模块名].py 是数据库表的仓储对象
主要实现与数据库表有关的操作：新增/修改/删除/查询等
采用 Repository 模式：把 SQL+数据访问集中到一个类里
"""

import sqlite3
from app.models.db import get_connection

class ExampleRepository:
	"""示例数据访问类"""
	
	@staticmethod
	def create_example(param1: str, param2: str) -&gt; bool:
		"""创建示例记录"""
		try:
			with get_connection() as conn:
				conn.execute(
					"insert into examples (col1, col2) values (?, ?)",
					(param1, param2)
				)
			return True
		except sqlite3.IntegrityError:
			return False
	
	@staticmethod
	def get_example_by_id(example_id: int):
		"""根据 ID 获取示例记录"""
		with get_connection() as conn:
			row = conn.execute(
				"select id, col1, col2 from examples where id=?", 
				(example_id,)
			).fetchone()
		return row
	
	@staticmethod
	def get_all_examples():
		"""获取所有示例记录"""
		with get_connection() as conn:
			rows = conn.execute(
				"select id, col1, col2 from examples"
			).fetchall()
		return rows
	
	@staticmethod
	def update_example(example_id: int, param1: str, param2: str) -&gt; bool:
		"""更新示例记录"""
		with get_connection() as conn:
			result = conn.execute(
				"update examples set col1=?, col2=? where id=?",
				(param1, param2, example_id)
			)
		return result.rowcount &gt; 0
	
	@staticmethod
	def delete_example(example_id: int) -&gt; bool:
		"""删除示例记录"""
		with get_connection() as conn:
			result = conn.execute(
				"delete from examples where id=?",
				(example_id,)
			)
		return result.rowcount &gt; 0
```

## 模板文件模板

### 基础页面模板

```html
{% extends "base.html" %}
{% block body %}

&lt;div class="layui-container"&gt;
	&lt;div class="layui-row"&gt;
		&lt;div class="layui-col-md12"&gt;
			&lt;h2&gt;{{ title }}&lt;/h2&gt;
		&lt;/div&gt;
	&lt;/div&gt;
&lt;/div&gt;

{% end %}
```

### 表单页面模板

```html
{% extends "base.html" %}
{% block body %}

{% if error %}
&lt;div class="error"&gt;{{ error }}&lt;/div&gt;
{% end %}

&lt;form method="post" action="/action-url"&gt;
	{% module xsrf_form_html() %}
	&lt;div&gt;
		&lt;label&gt;字段1：&lt;/label&gt;
		&lt;input type="text" name="field1"&gt;
	&lt;/div&gt;
	&lt;div&gt;
		&lt;label&gt;字段2：&lt;/label&gt;
		&lt;input type="text" name="field2"&gt;
	&lt;/div&gt;
	&lt;button type="submit"&gt;提交&lt;/button&gt;
&lt;/form&gt;

{% end %}
```

## 路由注册模板

在 [app.py](file:///c:/Users/Wu/Desktop/shixun/day5/DataFinderAgentOS/app.py) 中添加路由：

```python
from app.controllers.example import ExampleHandler

# 在 webapp() 函数的路由配置中添加
(r"/example", ExampleHandler),
```

## 数据库表初始化模板

在 [app/models/db.py](file:///c:/Users/Wu/Desktop/shixun/day5/DataFinderAgentOS/app/models/db.py) 的 `init_db()` 函数中添加表创建语句：

```python
conn.execute(
	"""
	CREATE TABLE IF NOT EXISTS examples(
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		col1 TEXT NOT NULL,
		col2 TEXT NOT NULL,
		created_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
	)
	"""
)
```

## 前端框架使用模板

### Layui 基础页面模板

```html
{% extends "base.html" %}
{% block body %}

&lt;div class="layui-container" style="padding: 20px;"&gt;
	&lt;div class="layui-row"&gt;
		&lt;div class="layui-col-md12"&gt;
			&lt;fieldset class="layui-elem-field layui-field-title"&gt;
				&lt;legend&gt;{{ title }}&lt;/legend&gt;
			&lt;/fieldset&gt;
		&lt;/div&gt;
	&lt;/div&gt;
&lt;/div&gt;

&lt;script&gt;
	layui.use(['layer', 'form'], function(){
		var layer = layui.layer;
		var form = layui.form;
		// 页面初始化代码
	});
&lt;/script&gt;

{% end %}
```

### Layui 表单页面模板

```html
{% extends "base.html" %}
{% block body %}

&lt;div class="layui-container" style="padding: 20px;"&gt;
	&lt;div class="layui-row"&gt;
		&lt;div class="layui-col-md6 layui-col-md-offset3"&gt;
			&lt;fieldset class="layui-elem-field layui-field-title"&gt;
				&lt;legend&gt;{{ title }}&lt;/legend&gt;
			&lt;/fieldset&gt;
			
			{% if error %}
			&lt;div class="layui-alert layui-bg-red" style="color: white; padding: 10px; margin-bottom: 15px;"&gt;
				{{ error }}
			&lt;/div&gt;
			{% end %}
			
			&lt;form class="layui-form" method="post" action="/action-url"&gt;
				{% module xsrf_form_html() %}
				&lt;div class="layui-form-item"&gt;
					&lt;label class="layui-form-label"&gt;字段1&lt;/label&gt;
					&lt;div class="layui-input-block"&gt;
						&lt;input type="text" name="field1" required lay-verify="required" placeholder="请输入字段1" autocomplete="off" class="layui-input"&gt;
					&lt;/div&gt;
				&lt;/div&gt;
				&lt;div class="layui-form-item"&gt;
					&lt;label class="layui-form-label"&gt;字段2&lt;/label&gt;
					&lt;div class="layui-input-block"&gt;
						&lt;input type="text" name="field2" required lay-verify="required" placeholder="请输入字段2" autocomplete="off" class="layui-input"&gt;
					&lt;/div&gt;
				&lt;/div&gt;
				&lt;div class="layui-form-item"&gt;
					&lt;div class="layui-input-block"&gt;
						&lt;button class="layui-btn" lay-submit lay-filter="formDemo"&gt;提交&lt;/button&gt;
						&lt;button type="reset" class="layui-btn layui-btn-primary"&gt;重置&lt;/button&gt;
					&lt;/div&gt;
				&lt;/div&gt;
			&lt;/form&gt;
		&lt;/div&gt;
	&lt;/div&gt;
&lt;/div&gt;

&lt;script&gt;
	layui.use(['form', 'layer'], function(){
		var form = layui.form;
		var layer = layui.layer;
		
		// 监听提交
		form.on('submit(formDemo)', function(data){
			// 提交前的验证逻辑
			return true;
		});
	});
&lt;/script&gt;

{% end %}
```

### base.html 基础模板（引入 Layui 和 Bootstrap）

```html
&lt;!DOCTYPE html&gt;
&lt;html&gt;
&lt;head&gt;
	&lt;meta charset="utf-8"&gt;
	&lt;meta name="viewport" content="width=device-width, initial-scale=1"&gt;
	&lt;title&gt;{{ title if title else 'DataFinderAgentOS' }}&lt;/title&gt;
	&lt;!-- 引入 Layui CSS --&gt;
	&lt;link rel="stylesheet" href="{{ static_url('dist/layui/css/layui.css') }}"&gt;
	&lt;!-- 引入 Bootstrap CSS（可选，作为补充） --&gt;
	&lt;link rel="stylesheet" href="{{ static_url('dist/bootstrap/css/bootstrap.min.css') }}"&gt;
	&lt;!-- 引入自定义 CSS --&gt;
	&lt;link rel="stylesheet" href="{{ static_url('css/base.css') }}"&gt;
&lt;/head&gt;
&lt;body&gt;
	&lt;div class="container-fluid"&gt;
		{% block body %}{% end %}
	&lt;/div&gt;
	
	&lt;!-- 引入 Layui JS --&gt;
	&lt;script src="{{ static_url('dist/layui/layui.js') }}"&gt;&lt;/script&gt;
	&lt;!-- 引入 Bootstrap JS（可选，作为补充） --&gt;
	&lt;script src="{{ static_url('dist/bootstrap/js/bootstrap.bundle.min.js') }}"&gt;&lt;/script&gt;
	&lt;!-- 引入自定义 JS --&gt;
	&lt;script src="{{ static_url('js/base.js') }}"&gt;&lt;/script&gt;
&lt;/body&gt;
&lt;/html&gt;
```

## 实时通信功能模板

### WebSocket Handler 模板

```python
import tornado.websocket
from tornado.web import authenticated
from app.controllers.base import BaseHandler

class ChatWebSocketHandler(tornado.websocket.WebSocketHandler):
	"""WebSocket 聊天处理器"""
	
	# 存储所有连接的客户端
	clients = set()
	
	def check_origin(self, origin):
		"""允许跨域连接（根据需要调整）"""
		return True
	
	def open(self):
		"""连接打开时调用"""
		print("WebSocket 连接已建立")
		self.clients.add(self)
	
	def on_message(self, message):
		"""收到消息时调用"""
		print(f"收到消息：{message}")
		# 广播消息给所有客户端
		for client in self.clients:
			client.write_message(message)
	
	def on_close(self):
		"""连接关闭时调用"""
		print("WebSocket 连接已关闭")
		self.clients.remove(self)

	@classmethod
	def send_message(cls, message):
		"""向所有连接的客户端发送消息"""
		for client in cls.clients:
			client.write_message(message)
```

### SSE (Server-Sent Events) Handler 模板

```python
import tornado.web
import tornado.gen
import time
from app.controllers.base import BaseHandler

class SSEHandler(BaseHandler):
	"""SSE 处理器"""
	
	@authenticated
	@tornado.gen.coroutine
	def get(self):
		self.set_header('Content-Type', 'text/event-stream')
		self.set_header('Cache-Control', 'no-cache')
		self.set_header('Connection', 'keep-alive')
		
		# 发送初始消息
		self.write(f"data: {{\'type\': \'connected\', \'time\': \'{time.time()}\'}}\n\n")
		self.flush()
		
		# 保持连接并定期发送心跳
		while True:
			yield tornado.gen.sleep(30)
			try:
				self.write(f": heartbeat\n\n")
				self.flush()
			except:
				break
```

### 前端 WebSocket 连接模板

```javascript
&lt;script&gt;
	layui.use(['layer'], function(){
		var layer = layui.layer;
		
		// 建立 WebSocket 连接
		var ws = new WebSocket('ws://' + window.location.host + '/ws');
		
		ws.onopen = function() {
			console.log('WebSocket 连接已建立');
			layer.msg('连接成功');
		};
		
		ws.onmessage = function(event) {
			console.log('收到消息：', event.data);
			var data = JSON.parse(event.data);
			// 处理消息
		};
		
		ws.onclose = function() {
			console.log('WebSocket 连接已关闭');
			layer.msg('连接已断开');
		};
		
		ws.onerror = function(error) {
			console.error('WebSocket 错误：', error);
			layer.msg('连接出错');
		};
		
		// 发送消息
		function sendMessage(message) {
			if (ws.readyState === WebSocket.OPEN) {
				ws.send(JSON.stringify(message));
			} else {
				layer.msg('连接未建立');
			}
		}
	});
&lt;/script&gt;
```

## OpenAI 集成模板

### OpenAI 服务类模板

```python
import openai
import os

class OpenAIService:
	"""OpenAI 服务封装类"""
	
	def __init__(self):
		# 从环境变量或配置中获取 API Key
		self.api_key = os.environ.get('OPENAI_API_KEY', '')
		openai.api_key = self.api_key
	
	def chat_completion(self, messages, model='gpt-3.5-turbo', temperature=0.7):
		"""聊天补全"""
		try:
			response = openai.ChatCompletion.create(
				model=model,
				messages=messages,
				temperature=temperature
			)
			return response.choices[0].message.content
		except Exception as e:
			print(f"OpenAI 错误：{e}")
			return None
	
	def stream_chat_completion(self, messages, model='gpt-3.5-turbo', temperature=0.7):
		"""流式聊天补全"""
		try:
			response = openai.ChatCompletion.create(
				model=model,
				messages=messages,
				temperature=temperature,
				stream=True
			)
			for chunk in response:
				if chunk.choices[0].delta.get('content'):
					yield chunk.choices[0].delta.content
		except Exception as e:
			print(f"OpenAI 流式错误：{e}")
			yield None
```

### OpenAI 对话 Controller 模板

```python
import tornado.web
from tornado.web import authenticated
from app.controllers.base import BaseHandler
from app.services.openai_service import OpenAIService

class ChatHandler(BaseHandler):
	"""聊天页面"""
	
	@authenticated
	def get(self):
		self.render("chat.html", title="AI 对话")

class ChatApiHandler(BaseHandler):
	"""聊天 API"""
	
	@authenticated
	def post(self):
		user_message = self.get_body_argument("message", "")
		if not user_message:
			self.set_status(400)
			return self.write({"error": "消息不能为空"})
		
		# 构建对话上下文
		messages = [
			{"role": "system", "content": "你是一个有帮助的助手。"},
			{"role": "user", "content": user_message}
		]
		
		# 调用 OpenAI 服务
		service = OpenAIService()
		response = service.chat_completion(messages)
		
		if response:
			self.write({"success": True, "response": response})
		else:
			self.set_status(500)
			self.write({"success": False, "error": "服务错误"})
```

### 前端对话页面模板

```html
{% extends "base.html" %}
{% block body %}

&lt;div class="layui-container" style="padding: 20px;"&gt;
	&lt;div class="layui-row"&gt;
		&lt;div class="layui-col-md12"&gt;
			&lt;fieldset class="layui-elem-field layui-field-title"&gt;
				&lt;legend&gt;{{ title }}&lt;/legend&gt;
			&lt;/fieldset&gt;
			
			&lt;!-- 聊天消息区域 --&gt;
			&lt;div id="chat-messages" class="layui-card" style="height: 500px; overflow-y: auto; padding: 20px;"&gt;
				&lt;div class="layui-card-body"&gt;
					&lt;!-- 消息将在这里显示 --&gt;
				&lt;/div&gt;
			&lt;/div&gt;
			
			&lt;!-- 输入区域 --&gt;
			&lt;div class="layui-card" style="margin-top: 20px;"&gt;
				&lt;div class="layui-card-body"&gt;
					&lt;form class="layui-form" lay-filter="chat-form"&gt;
						&lt;div class="layui-form-item"&gt;
							&lt;textarea name="message" placeholder="请输入消息..." class="layui-textarea" style="height: 80px;"&gt;&lt;/textarea&gt;
						&lt;/div&gt;
						&lt;div class="layui-form-item" style="text-align: right;"&gt;
							&lt;button type="button" class="layui-btn" lay-submit lay-filter="send"&gt;发送&lt;/button&gt;
						&lt;/div&gt;
					&lt;/form&gt;
				&lt;/div&gt;
			&lt;/div&gt;
		&lt;/div&gt;
	&lt;/div&gt;
&lt;/div&gt;

&lt;script&gt;
	layui.use(['form', 'layer'], function(){
		var form = layui.form;
		var layer = layui.layer;
		var $ = layui.jquery;
		
		// 发送消息
		form.on('submit(send)', function(data){
			var message = data.field.message;
			if(!message.trim()){
				layer.msg('请输入消息');
				return false;
			}
			
			// 显示用户消息
			appendMessage('user', message);
			
			// 清空输入框
			$('textarea[name="message"]').val('');
			
			// 发送到后端
			$.ajax({
				url: '/api/chat',
				type: 'POST',
				data: {
					message: message,
					_xsrf: getCookie('_xsrf')
				},
				success: function(res){
					if(res.success){
						appendMessage('ai', res.response);
					} else {
						layer.msg(res.error || '发送失败');
					}
				},
				error: function(){
					layer.msg('请求出错');
				}
			});
			
			return false;
		});
		
		// 追加消息到聊天区域
		function appendMessage(role, content){
			var html = '';
			if(role === 'user'){
				html = '&lt;div style="text-align: right; margin-bottom: 15px;"&gt;' +
					'&lt;span style="background-color: #009688; color: white; padding: 10px; border-radius: 5px; display: inline-block; max-width: 70%; word-wrap: break-word;"&gt;' + content + '&lt;/span&gt;' +
				'&lt;/div&gt;';
			} else {
				html = '&lt;div style="text-align: left; margin-bottom: 15px;"&gt;' +
					'&lt;span style="background-color: #f0f0f0; padding: 10px; border-radius: 5px; display: inline-block; max-width: 70%; word-wrap: break-word;"&gt;' + content + '&lt;/span&gt;' +
				'&lt;/div&gt;';
			}
			$('#chat-messages .layui-card-body').append(html);
			// 滚动到底部
			$('#chat-messages').scrollTop($('#chat-messages')[0].scrollHeight);
		}
		
		// 获取 Cookie
		function getCookie(name){
			var r = document.cookie.match('\\b' + name + '=([^;]*)\\b');
			return r ? r[1] : undefined;
		}
	});
&lt;/script&gt;

{% end %}
```
