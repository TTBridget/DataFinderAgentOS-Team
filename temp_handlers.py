
class AiModelManageHandler(AdminBaseHandler):
	"""模型引擎管理"""
	
	@tornado.web.authenticated
	def get(self):
		page = int(self.get_argument("page", 1))
		search = self.get_argument("search", "")
		
		result = AiModelRepository.get_all(page, 6, search)
		
		self.render("admin/ai_model.html", title="模型引擎", 
				   models=result["items"],
				   page=page,
				   total=result["total"],
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
			temperature = float(self.get_body_argument("temperature", 0.7))
			top_p = float(self.get_body_argument("top_p", 1.0))
			max_tokens = int(self.get_body_argument("max_tokens", 2048))
			context_size = int(self.get_body_argument("context_size", 4096))
			is_default = int(self.get_body_argument("is_default", 0))
			
			mid = AiModelRepository.create(name, provider, api_key, base_url, model_type, system_prompt, temperature, top_p, max_tokens, context_size, is_default)
			if mid:
				self.write({"code": 0, "msg": "添加成功", "data": {"id": mid}})
			else:
				self.write({"code": 1, "msg": "添加失败"})
				
		elif action == "edit":
			params = {
				"name": self.get_body_argument("name", None),
				"provider": self.get_body_argument("provider", None),
				"api_key": self.get_body_argument("api_key", None),
				"base_url": self.get_body_argument("base_url", None),
				"model_type": self.get_body_argument("model_type", None),
				"system_prompt": self.get_body_argument("system_prompt", None),
			}
			
			if self.get_body_argument("temperature", None): params["temperature"] = float(self.get_body_argument("temperature"))
			if self.get_body_argument("top_p", None): params["top_p"] = float(self.get_body_argument("top_p"))
			if self.get_body_argument("max_tokens", None): params["max_tokens"] = int(self.get_body_argument("max_tokens"))
			if self.get_body_argument("context_size", None): params["context_size"] = int(self.get_body_argument("context_size"))
			if self.get_body_argument("is_default", None): params["is_default"] = int(self.get_body_argument("is_default"))
			
			# 过滤掉 None 的参数
			params = {k: v for k, v in params.items() if v is not None}
			
			success = AiModelRepository.update(int(model_id), **params)
			if success:
				self.write({"code": 0, "msg": "更新成功"})
			else:
				self.write({"code": 1, "msg": "更新失败"})
				
		elif action == "delete":
			AiModelRepository.delete(int(model_id))
			self.write({"code": 0, "msg": "删除成功"})
			
		elif action == "set_default":
			AiModelRepository.set_default(int(model_id))
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
			model = AiModelRepository.get_by_id(int(model_id))
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
				request_timeout=60
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
