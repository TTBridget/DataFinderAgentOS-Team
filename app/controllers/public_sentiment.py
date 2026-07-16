"""
public_sentiment.py - 舆情大屏控制器
"""

import json
import datetime
from tornado.web import authenticated
from app.controllers.base import AdminBaseHandler
from app.models.alert import AlertRepository, NotificationRepository
from app.models.chat import ChatSessionRepository, ChatMessageRepository
from app.models.collected_data import CollectedDataRepository
from app.models.user import UserRepository
from app.services.sensitive_word_service import SensitiveWordService


class PublicSentimentHandler(AdminBaseHandler):
    """舆情大屏首页"""
    
    @authenticated
    def get(self):
        self.render("admin/public_sentiment.html", title="舆情大屏", username=self.current_user)


class PublicSentimentStatsHandler(AdminBaseHandler):
    """获取统计数据"""
    
    @authenticated
    def get(self):
        time_range = self.get_argument("time_range", "24h")
        now = datetime.datetime.now()
        
        if time_range == "1h":
            start_time = (now - datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        elif time_range == "24h":
            start_time = (now - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        elif time_range == "7d":
            start_time = (now - datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        else:
            start_time = self.get_argument("start_time", "")
            end_time = self.get_argument("end_time", "")
        
        stats = AlertRepository.get_stats(start_time, end_time)
        
        with self.application.settings.get("db_connection", None) or __import__('app.models.db').models.db.get_connection() as conn:
            session_query = "SELECT COUNT(*) as cnt FROM chat_sessions"
            message_query = "SELECT COUNT(*) as cnt FROM chat_messages"
            collected_query = "SELECT COUNT(*) as cnt FROM collected_data"
            params = []
            
            if start_time and end_time:
                session_query += " WHERE created_at >= ? AND created_at <= ?"
                message_query += " WHERE created_at >= ? AND created_at <= ?"
                collected_query += " WHERE created_at >= ? AND created_at <= ?"
                params = [start_time, end_time]
            
            session_count = conn.execute(session_query, params).fetchone()["cnt"]
            message_count = conn.execute(message_query, params).fetchone()["cnt"]
            collected_count = conn.execute(collected_query, params).fetchone()["cnt"]
        
        self.write({
            "code": 0,
            "data": {
                "total_sessions": session_count,
                "total_messages": message_count,
                "total_collected": collected_count,
                "pending_alerts": stats["pending"],
                "total_alerts": stats["total"]
            }
        })


class PublicSentimentAlertsHandler(AdminBaseHandler):
    """获取预警列表"""
    
    @authenticated
    def get(self):
        page = int(self.get_argument("page", 1))
        page_size = int(self.get_argument("page_size", 20))
        status = self.get_argument("status", "")
        time_range = self.get_argument("time_range", "")
        
        now = datetime.datetime.now()
        start_time = ""
        end_time = ""
        
        if time_range == "1h":
            start_time = (now - datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        elif time_range == "24h":
            start_time = (now - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        elif time_range == "7d":
            start_time = (now - datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        
        result = AlertRepository.get_alerts(page, page_size, status, start_time, end_time)
        self.write({
            "code": 0,
            "msg": "",
            "count": result["total"],
            "data": result["items"]
        })


class PublicSentimentAlertDetailHandler(AdminBaseHandler):
    """获取预警详情"""
    
    @authenticated
    def get(self, alert_id):
        alert = AlertRepository.get_alert_by_id(alert_id)
        if alert:
            self.write({"code": 0, "data": alert})
        else:
            self.write({"code": 1, "msg": "预警不存在"})


class PublicSentimentAlertActionHandler(AdminBaseHandler):
    """预警操作（标记已处理、发送反馈等）"""
    
    @authenticated
    def post(self):
        try:
            body = json.loads(self.request.body) if self.request.body else {}
            action = body.get("action", "")
            alert_id = body.get("alert_id", "")
        except:
            action = self.get_body_argument("action", "")
            alert_id = self.get_body_argument("alert_id", "")
        
        if action == "mark_handled":
            AlertRepository.update_status(alert_id, "handled")
            self.write({"code": 0, "msg": "已标记为已处理"})
        
        elif action == "mark_ignored":
            AlertRepository.update_status(alert_id, "ignored")
            self.write({"code": 0, "msg": "已标记为已忽略"})
        
        elif action == "send_feedback":
            alert = AlertRepository.get_alert_by_id(alert_id)
            if alert and alert["user_id"]:
                SensitiveWordService.send_notification(
                    alert["user_id"],
                    "发言规范提醒",
                    "您的发言包含敏感词汇，请遵守社区规范"
                )
                AlertRepository.update_status(alert_id, "feedback_sent")
                self.write({"code": 0, "msg": "反馈已发送"})
            else:
                self.write({"code": 1, "msg": "无法发送反馈"})
        
        else:
            self.write({"code": 1, "msg": "无效操作"})


class PublicSentimentTrendHandler(AdminBaseHandler):
    """获取预警趋势数据"""
    
    @authenticated
    def get(self):
        time_range = self.get_argument("time_range", "24h")
        now = datetime.datetime.now()
        
        if time_range == "1h":
            start_time = (now - datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
            data = AlertRepository.get_trend_by_hour(start_time, end_time)
        elif time_range == "24h":
            start_time = (now - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
            data = AlertRepository.get_trend_by_hour(start_time, end_time)
        else:
            start_time = (now - datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
            data = AlertRepository.get_trend_by_day(start_time, end_time)
        
        self.write({"code": 0, "data": data})


class PublicSentimentHotTopicsHandler(AdminBaseHandler):
    """获取热点话题"""
    
    @authenticated
    def get(self):
        time_range = self.get_argument("time_range", "24h")
        now = datetime.datetime.now()
        
        if time_range == "1h":
            start_time = (now - datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        elif time_range == "24h":
            start_time = (now - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        else:
            start_time = (now - datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        
        data = AlertRepository.get_hot_topics(start_time, end_time, 10)
        self.write({"code": 0, "data": data})


class PublicSentimentRiskLevelHandler(AdminBaseHandler):
    """获取风险等级分布"""
    
    @authenticated
    def get(self):
        time_range = self.get_argument("time_range", "24h")
        now = datetime.datetime.now()
        
        if time_range == "24h":
            start_time = (now - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        else:
            start_time = (now - datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        
        stats = AlertRepository.get_stats(start_time, end_time)
        
        risk_level = "low"
        if stats["total"] >= 20:
            risk_level = "high"
        elif stats["total"] >= 5:
            risk_level = "medium"
        
        self.write({
            "code": 0,
            "data": {
                "risk_level": risk_level,
                "stats": stats
            }
        })


class PublicSentimentSensitiveWordsHandler(AdminBaseHandler):
    """敏感词管理"""
    
    @authenticated
    def get(self):
        words = SensitiveWordService.get_all_words()
        self.write({"code": 0, "data": words})
    
    @authenticated
    def post(self):
        action = self.get_body_argument("action", "")
        
        if action == "add":
            word = self.get_body_argument("word", "")
            level = int(self.get_body_argument("level", 1))
            description = self.get_body_argument("description", "")
            if SensitiveWordService.add_word(word, level, description):
                self.write({"code": 0, "msg": "添加成功"})
            else:
                self.write({"code": 1, "msg": "添加失败，敏感词可能已存在"})
        
        elif action == "delete":
            word_id = self.get_body_argument("id", "")
            SensitiveWordService.delete_word(word_id)
            self.write({"code": 0, "msg": "删除成功"})
        
        elif action == "update":
            word_id = self.get_body_argument("id", "")
            word = self.get_body_argument("word", "")
            level = int(self.get_body_argument("level", 1))
            description = self.get_body_argument("description", "")
            SensitiveWordService.update_word(word_id, word, level, description)
            self.write({"code": 0, "msg": "更新成功"})


class PublicSentimentScanHandler(AdminBaseHandler):
    """手动扫描数据"""
    
    @authenticated
    def post(self):
        try:
            body = json.loads(self.request.body) if self.request.body else {}
            scan_type = body.get("scan_type", "")
        except:
            scan_type = self.get_body_argument("scan_type", "")
        count = 0
        
        if scan_type == "chat":
            with __import__('app.models.db').models.db.get_connection() as conn:
                rows = conn.execute("SELECT m.*, s.user_id, u.username FROM chat_messages m "
                                   "JOIN chat_sessions s ON m.session_id = s.id "
                                   "JOIN users u ON s.user_id = u.id").fetchall()
                for row in rows:
                    matches = SensitiveWordService.scan_content(row["content"])
                    if matches:
                        SensitiveWordService.scan_and_create_alerts(
                            row["user_id"],
                            row["username"],
                            row["content"],
                            "chat",
                            row["session_id"],
                            f"会话ID:{row['session_id']}"
                        )
                        count += 1
        
        elif scan_type == "collected":
            with __import__('app.models.db').models.db.get_connection() as conn:
                rows = conn.execute("SELECT * FROM collected_data").fetchall()
                for row in rows:
                    content = (row["title"] or "") + " " + (row["content"] or "")
                    matches = SensitiveWordService.scan_content(content)
                    if matches:
                        SensitiveWordService.scan_and_create_alerts(
                            None,
                            row["source_name"] or "系统",
                            content,
                            "collected",
                            row["id"],
                            row["source_name"] or "采集数据"
                        )
                        count += 1
        
        self.write({"code": 0, "msg": f"扫描完成，共发现 {count} 条敏感内容"})