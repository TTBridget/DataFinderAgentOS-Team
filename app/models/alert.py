"""
alert.py - 预警管理数据访问层
"""

from app.models.db import get_connection


class AlertRepository:
    @staticmethod
    def get_alerts(page=1, page_size=20, status=None, start_time=None, end_time=None):
        """获取预警列表（支持分页、状态筛选、时间范围）"""
        offset = (page - 1) * page_size
        with get_connection() as conn:
            query = "SELECT * FROM alerts"
            params = []
            
            conditions = []
            if status:
                conditions.append("status = ?")
                params.append(status)
            if start_time:
                conditions.append("created_at >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("created_at <= ?")
                params.append(end_time)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, offset])
            
            rows = conn.execute(query, params).fetchall()
            
            count_query = "SELECT COUNT(*) as total FROM alerts"
            if conditions:
                count_query += " WHERE " + " AND ".join(conditions)
            total = conn.execute(count_query, params[:-2]).fetchone()["total"]
            
            return {"items": [dict(row) for row in rows], "total": total, "page": page, "page_size": page_size}
    
    @staticmethod
    def get_alert_by_id(alert_id):
        """根据ID获取预警"""
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def update_status(alert_id, status):
        """更新预警状态"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE alerts SET status = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                (status, alert_id)
            )
            return True
    
    @staticmethod
    def get_stats(start_time=None, end_time=None):
        """获取预警统计数据"""
        with get_connection() as conn:
            conditions = []
            params = []
            
            if start_time:
                conditions.append("created_at >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("created_at <= ?")
                params.append(end_time)
            
            where_clause = ""
            if conditions:
                where_clause = " WHERE " + " AND ".join(conditions)
            
            total = conn.execute(f"SELECT COUNT(*) as cnt FROM alerts{where_clause}", params).fetchone()["cnt"]
            pending = conn.execute(f"SELECT COUNT(*) as cnt FROM alerts{where_clause} AND status = 'pending'", params).fetchone()["cnt"]
            handled = conn.execute(f"SELECT COUNT(*) as cnt FROM alerts{where_clause} AND status = 'handled'", params).fetchone()["cnt"]
            ignored = conn.execute(f"SELECT COUNT(*) as cnt FROM alerts{where_clause} AND status = 'ignored'", params).fetchone()["cnt"]
            
            return {
                "total": total,
                "pending": pending,
                "handled": handled,
                "ignored": ignored
            }
    
    @staticmethod
    def get_trend_by_hour(start_time=None, end_time=None):
        """按小时获取预警趋势"""
        with get_connection() as conn:
            conditions = []
            params = []
            
            if start_time:
                conditions.append("created_at >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("created_at <= ?")
                params.append(end_time)
            
            where_clause = ""
            if conditions:
                where_clause = " WHERE " + " AND ".join(conditions)
            
            query = f"""
                SELECT strftime('%Y-%m-%d %H:00', created_at) as hour, COUNT(*) as count
                FROM alerts{where_clause}
                GROUP BY hour
                ORDER BY hour DESC
                LIMIT 24
            """
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_trend_by_day(start_time=None, end_time=None):
        """按天获取预警趋势"""
        with get_connection() as conn:
            conditions = []
            params = []
            
            if start_time:
                conditions.append("created_at >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("created_at <= ?")
                params.append(end_time)
            
            where_clause = ""
            if conditions:
                where_clause = " WHERE " + " AND ".join(conditions)
            
            query = f"""
                SELECT strftime('%Y-%m-%d', created_at) as day, COUNT(*) as count
                FROM alerts{where_clause}
                GROUP BY day
                ORDER BY day DESC
                LIMIT 7
            """
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    def get_hot_topics(start_time=None, end_time=None, limit=10):
        """获取热点话题（基于敏感词触发频率）"""
        with get_connection() as conn:
            conditions = []
            params = []
            
            if start_time:
                conditions.append("created_at >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("created_at <= ?")
                params.append(end_time)
            
            where_clause = ""
            if conditions:
                where_clause = " WHERE " + " AND ".join(conditions)
            
            query = f"""
                SELECT sensitive_word as topic, COUNT(*) as count
                FROM alerts{where_clause}
                GROUP BY sensitive_word
                ORDER BY count DESC
                LIMIT ?
            """
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    def delete_alert(alert_id):
        """删除预警记录"""
        with get_connection() as conn:
            conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
            return True


class NotificationRepository:
    @staticmethod
    def get_notifications(page=1, page_size=20, user_id=None, is_read=None):
        """获取通知列表"""
        offset = (page - 1) * page_size
        with get_connection() as conn:
            query = "SELECT * FROM notifications"
            params = []
            
            conditions = []
            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)
            if is_read is not None:
                conditions.append("is_read = ?")
                params.append(is_read)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, offset])
            
            rows = conn.execute(query, params).fetchall()
            
            count_query = "SELECT COUNT(*) as total FROM notifications"
            if conditions:
                count_query += " WHERE " + " AND ".join(conditions)
            total = conn.execute(count_query, params[:-2]).fetchone()["total"]
            
            return {"items": [dict(row) for row in rows], "total": total}
    
    @staticmethod
    def get_unread_count(user_id):
        """获取未读通知数量"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND is_read = 0",
                (user_id,)
            ).fetchone()
            return row["cnt"] if row else 0
    
    @staticmethod
    def mark_all_read(user_id):
        """标记所有通知已读"""
        with get_connection() as conn:
            conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
            return True