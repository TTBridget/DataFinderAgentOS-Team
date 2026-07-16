import json
import os
from app.controllers.base import AdminBaseHandler
from app.models.system_settings import SystemSettings
from app.models.db import init_db

class SystemSettingsHandler(AdminBaseHandler):
    def get(self):
        settings = SystemSettings.get_settings()
        title = '系统设置 - ' + settings.get('system_name', '智能瞭望与智能问数系统')
        self.render('admin/system_settings.html', title=title, username=self.current_user, settings=settings)

class SystemSettingsSaveHandler(AdminBaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body)
            settings = {}
            
            basic_settings = ['system_name', 'timezone', 'date_format', 'page_size']
            for key in basic_settings:
                if key in data:
                    settings[key] = data[key]
            
            security_settings = ['run_mode', 'log_level', 'session_timeout', 'max_upload_size']
            for key in security_settings:
                if key in data:
                    settings[key] = data[key]
            
            SystemSettings.update_settings(settings)
            
            self.write({
                'code': 0,
                'msg': '设置保存成功',
                'data': settings
            })
        except Exception as e:
            self.write({
                'code': -1,
                'msg': str(e)
            })

class SystemSettingsLogoUploadHandler(AdminBaseHandler):
    def post(self):
        try:
            file_metas = self.request.files.get('logo', None)
            if not file_metas:
                self.write({'code': -1, 'msg': '请选择文件'})
                return
            
            file_meta = file_metas[0]
            filename = file_meta['filename']
            ext = os.path.splitext(filename)[1].lower()
            
            if ext not in ['.png', '.jpg', '.jpeg', '.gif']:
                self.write({'code': -1, 'msg': '仅支持PNG、JPG、GIF格式'})
                return
            
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            
            new_filename = 'logo' + ext
            file_path = os.path.join(upload_dir, new_filename)
            
            with open(file_path, 'wb') as f:
                f.write(file_meta['body'])
            
            SystemSettings.update_settings({'logo_path': '/static/uploads/' + new_filename})
            
            self.write({
                'code': 0,
                'msg': 'Logo上传成功',
                'data': {'logo_path': '/static/uploads/' + new_filename}
            })
        except Exception as e:
            self.write({'code': -1, 'msg': str(e)})