import tornado.web

from app.controllers.base import BaseHandler
from app.models.ai_model import AiModelRepository


class IndexHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self):
		default_model = AiModelRepository.get_default_model()
		model_id = default_model["id"] if default_model else ""
		model_name = default_model["name"] if default_model else "系统默认模型"
		
		self.render(
			"index.html",
			title="智能问数",
			username=self.current_user,
			default_model_id=model_id,
			default_model_name=model_name
		)
