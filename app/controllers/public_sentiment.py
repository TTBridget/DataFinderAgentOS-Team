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
    """手动扫描数据（带分页 + 上限 + 超时防护）"""
    
    BATCH_SIZE = 500       # 每批处理行数
    MAX_ROWS = 20000       # 单次扫描最大行数
    TIME_LIMIT = 60        # 单次扫描最大秒数
    
    @authenticated
    def post(self):
        try:
            body = json.loads(self.request.body) if self.request.body else {}
            scan_type = body.get("scan_type", "")
        except:
            scan_type = self.get_body_argument("scan_type", "")
        
        import time
        start_time = time.time()
        count = 0
        scanned_rows = 0
        
        # 一次性预加载所有敏感词（避免每行重复查询）
        words = SensitiveWordService.get_all_words()
        if not words:
            self.write({"code": 0, "msg": "暂无敏感词，扫描完成"})
            return
        
        if scan_type == "chat":
            import app.models.db as db_module
            with db_module.get_connection() as conn:
                offset = 0
                while scanned_rows < self.MAX_ROWS:
                    # 超时检查
                    if time.time() - start_time > self.TIME_LIMIT:
                        break
                    
                    rows = conn.execute(
                        "SELECT m.*, s.user_id, u.username FROM chat_messages m "
                        "JOIN chat_sessions s ON m.session_id = s.id "
                        "JOIN users u ON s.user_id = u.id "
                        "LIMIT ? OFFSET ?",
                        (self.BATCH_SIZE, offset)
                    ).fetchall()
                    
                    if not rows:
                        break
                    
                    # 扫描当前批次并收集匹配结果
                    matched_rows = []
                    for row in rows:
                        matches = SensitiveWordService.scan_content(row["content"], words=words)
                        if matches:
                            matched_rows.append((row, matches))
                    
                    # 批量创建预警（一次 DB 连接）
                    if matched_rows:
                        count += SensitiveWordService.scan_and_create_alerts_batch(
                            matched_rows,
                            "chat",
                            get_user_id=lambda r: r["user_id"],
                            get_user_name=lambda r: r["username"],
                            get_content=lambda r: r["content"],
                            get_source_id=lambda r: r["session_id"],
                            get_source_name=lambda r: f"会话ID:{r['session_id']}"
                        )
                    
                    scanned_rows += len(rows)
                    offset += self.BATCH_SIZE
        
        elif scan_type == "collected":
            import app.models.db as db_module
            with db_module.get_connection() as conn:
                offset = 0
                while scanned_rows < self.MAX_ROWS:
                    if time.time() - start_time > self.TIME_LIMIT:
                        break
                    
                    rows = conn.execute(
                        "SELECT * FROM collected_data LIMIT ? OFFSET ?",
                        (self.BATCH_SIZE, offset)
                    ).fetchall()
                    
                    if not rows:
                        break
                    
                    matched_rows = []
                    for row in rows:
                        content = (row["title"] or "") + " " + (row["content"] or "")
                        matches = SensitiveWordService.scan_content(content, words=words)
                        if matches:
                            matched_rows.append((row, matches))
                    
                    if matched_rows:
                        count += SensitiveWordService.scan_and_create_alerts_batch(
                            matched_rows,
                            "collected",
                            get_user_id=lambda r: None,
                            get_user_name=lambda r: r["source_name"] or "系统",
                            get_content=lambda r: (r["title"] or "") + " " + (r["content"] or ""),
                            get_source_id=lambda r: r["id"],
                            get_source_name=lambda r: r["source_name"] or "采集数据"
                        )
                    
                    scanned_rows += len(rows)
                    offset += self.BATCH_SIZE
        
        elapsed = round(time.time() - start_time, 1)
        truncated = "（已达到扫描上限）" if scanned_rows >= self.MAX_ROWS else ""
        self.write({"code": 0, "msg": f"已扫描 {scanned_rows} 行（耗时 {elapsed}s），共发现 {count} 条敏感内容{truncated}"})