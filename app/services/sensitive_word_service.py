"""
sensitive_word_service.py - 敏感词检测服务
负责敏感词库管理、内容扫描和预警生成
"""

import re
from app.models.db import get_connection


class SensitiveWordService:
    @staticmethod
    def get_all_words():
        """获取所有敏感词"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sensitive_words WHERE is_enabled = 1 ORDER BY level DESC, word ASC"
            ).fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    def add_word(word, level=1, description=""):
        """添加敏感词"""
        with get_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO sensitive_words (word, level, description) VALUES (?, ?, ?)",
                    (word, level, description)
                )
                return True
            except Exception:
                return False
    
    @staticmethod
    def delete_word(word_id):
        """删除敏感词"""
        with get_connection() as conn:
            conn.execute("DELETE FROM sensitive_words WHERE id = ?", (word_id,))
            return True
    
    @staticmethod
    def update_word(word_id, word=None, level=None, description=None):
        """更新敏感词"""
        with get_connection() as conn:
            updates = []
            params = []
            if word:
                updates.append("word = ?")
                params.append(word)
            if level is not None:
                updates.append("level = ?")
                params.append(level)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if updates:
                updates.append("updated_at = datetime('now','localtime')")
                params.append(word_id)
                conn.execute(
                    f"UPDATE sensitive_words SET {', '.join(updates)} WHERE id = ?",
                    params
                )
            return True
    
    @staticmethod
    def scan_content(content):
        """扫描内容中的敏感词"""
        if not content:
            return []
        
        words = SensitiveWordService.get_all_words()
        if not words:
            return []
        
        matches = []
        for word_entry in words:
            word = word_entry["word"]
            if word in content:
                matches.append({
                    "word": word,
                    "level": word_entry["level"],
                    "description": word_entry["description"]
                })
        
        return matches
    
    @staticmethod
    def scan_and_create_alerts(user_id, user_name, content, content_type, source_id, source_name):
        """扫描内容并创建预警记录（去重）"""
        matches = SensitiveWordService.scan_content(content)
        if not matches:
            return []
        
        alerts = []
        with get_connection() as conn:
            for match in matches:
                exists = conn.execute(
                    """
                    SELECT id FROM alerts WHERE user_id = ? AND sensitive_word = ? 
                    AND content_type = ? AND source_id = ?
                    """,
                    (user_id, match["word"], content_type, source_id)
                ).fetchone()
                
                if not exists:
                    cursor = conn.execute(
                        """
                        INSERT INTO alerts (user_id, user_name, sensitive_word, content, 
                                           content_type, source_id, source_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (user_id, user_name, match["word"], content, content_type, source_id, source_name)
                    )
                    alerts.append({
                        "id": cursor.lastrowid,
                        "sensitive_word": match["word"],
                        "level": match["level"]
                    })
        
        return alerts
    
    @staticmethod
    def send_notification(user_id, title, content):
        """发送系统通知"""
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO notifications (user_id, title, content) VALUES (?, ?, ?)",
                (user_id, title, content)
            )
            return True
    
    @staticmethod
    def get_user_notifications(user_id, limit=20):
        """获取用户通知"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    def mark_notification_read(notification_id):
        """标记通知已读"""
        with get_connection() as conn:
            conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
            return True