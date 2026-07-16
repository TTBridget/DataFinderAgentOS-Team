"""
alert.py - 预警管理数据访问层
"""

from app.models.db import get_connection


class AlertRepository:
    
    SENSITIVE_WORD_CATEGORIES = {
        '政治敏感': ['分裂', '台独', '港独', '藏独', '疆独', '颠覆政权', '推翻政府', '叛国', '卖国', '间谍', '泄露国家机密', '暴乱', '暴动', '煽动颠覆', '极端主义', '恐怖主义'],
        '暴力恐怖': ['爆炸', '炸弹', '袭击', '枪击', '杀人', '自杀', '自残', '斩首', '人肉炸弹', '恐怖活动', '圣战', 'ISIS', 'IS', '强奸', '轮奸'],
        '色情低俗': ['色情', '裸照', '性爱', '性交', '自慰', '卖淫', '嫖娼', '鸡婆', '婊子'],
        '网络欺凌': ['草泥马', '卧槽', '傻逼', '脑残', '去死', '滚', '畜生', '狗日的', '他妈的', '操你妈', '侮辱', '诽谤', '人身攻击', '侵犯隐私', '人肉搜索'],
        '毒品违法': ['毒品', '鸦片', '海洛因', '冰毒', '大麻', '可卡因', '摇头丸', 'K粉', '吸毒', '贩毒', '制毒', '赌博', '赌场', '投注', '彩票'],
        '谣言虚假': ['谣言', '虚假信息', '不实传闻', '恐慌', '假消息'],
        '宗教极端': ['邪教', '极端宗教', '宗教极端', '煽动宗教', '法轮功', '全能神'],
        '迷信类': ['封建迷信', '伪科学', '算命', '占卜', '风水', '灵异', '鬼', '神']
    }
    
    @staticmethod
    def get_word_category(word):
        """获取敏感词所属类别"""
        for category, words in AlertRepository.SENSITIVE_WORD_CATEGORIES.items():
            if word in words:
                return category
        return '其他'
    
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
            
            items = []
            for row in rows:
                row_dict = dict(row)
                row_dict['category'] = AlertRepository.get_word_category(row_dict.get('sensitive_word', ''))
                items.append(row_dict)
            
            return {"items": items, "total": total, "page": page, "page_size": page_size}
    
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
        """获取热点话题（从对话内容和采集数据中提取关键词）"""
        import re
        
        with get_connection() as conn:
            word_counts = {}
            
            chat_conditions = []
            chat_params = []
            if start_time:
                chat_conditions.append("cm.created_at >= ?")
                chat_params.append(start_time)
            if end_time:
                chat_conditions.append("cm.created_at <= ?")
                chat_params.append(end_time)
            
            chat_where = ""
            if chat_conditions:
                chat_where = " WHERE " + " AND ".join(chat_conditions)
            
            chat_query = f"""
                SELECT cm.content, cs.title
                FROM chat_messages cm
                JOIN chat_sessions cs ON cm.session_id = cs.id
                {chat_where}
            """
            chat_rows = conn.execute(chat_query, chat_params).fetchall()
            for row in chat_rows:
                content = (row["content"] or "") + " " + (row["title"] or "")
                words = content.split()
                for word in words:
                    word = word.strip().replace('。', '').replace('，', '').replace('！', '').replace('？', '')
                    word = word.replace('.', '').replace(',', '').replace('!', '').replace('?', '')
                    word = word.replace(':', '').replace('：', '').replace('*', '')
                    if len(word) >= 2 and re.match(r'^[\u4e00-\u9fa5]+$', word):
                        word_counts[word] = word_counts.get(word, 0) + 1
            
            collected_conditions = []
            collected_params = []
            if start_time:
                collected_conditions.append("created_at >= ?")
                collected_params.append(start_time)
            if end_time:
                collected_conditions.append("created_at <= ?")
                collected_params.append(end_time)
            
            collected_where = ""
            if collected_conditions:
                collected_where = " WHERE " + " AND ".join(collected_conditions)
            
            collected_query = f"""
                SELECT title, content
                FROM collected_data
                {collected_where}
            """
            collected_rows = conn.execute(collected_query, collected_params).fetchall()
            for row in collected_rows:
                content = (row["title"] or "") + " " + (row["content"] or "")
                words = content.split()
                for word in words:
                    word = word.strip().replace('。', '').replace('，', '').replace('！', '').replace('？', '')
                    word = word.replace('.', '').replace(',', '').replace('!', '').replace('?', '')
                    word = word.replace(':', '').replace('：', '').replace('*', '')
                    if len(word) >= 2 and re.match(r'^[\u4e00-\u9fa5]+$', word):
                        word_counts[word] = word_counts.get(word, 0) + 1
            
            stop_words = {'的', '了', '和', '是', '就', '都', '而', '及', '与', '着', '或', '在', '有', '我', '你', '他', '她', '它', '这', '那', '此', '彼', '之', '于', '以', '为', '因', '由', '从', '到', '向', '往', '对', '对于', '关于', '至于', '至于', '按照', '依照', '根据', '通过', '经过', '由于', '因为', '所以', '因此', '于是', '然而', '但是', '可是', '不过', '虽然', '尽管', '即使', '如果', '假如', '要是', '只要', '只有', '除非', '无论', '不管', '不论', '或者', '还是', '以及', '等等', '例如', '比如', '包括', '特别是', '尤其是', '一般', '通常', '经常', '总是', '偶尔', '有时', '几乎', '差不多', '大概', '大约', '左右', '上下', '之间', '以上', '以下', '之前', '之后', '以来', '以内', '以外', '至少', '至多', '总共', '共计', '合计', '累计', '总计', '其中', '另外', '其他', '其余', '一切', '所有', '任何', '每', '各', '分别', '各自', '互相', '彼此', '共同', '一起', '一同', '同时', '先后', '依次', '逐个', '逐一', '分别', '各自', '互相', '彼此', '共同', '一起', '一同', '同时', '先后', '依次', '逐个', '逐一', '请问', '您好', '谢谢', '抱歉', '可以', '需要', '想要', '希望', '能够', '可能', '应该', '必须', '一定', '不要', '不能', '不会', '不用', '不必', '不用', '不必', '没关系', '不客气', '没问题', '好的', '是的', '不是', '对', '错', '知道', '明白', '理解', '了解', '认识', '熟悉', '清楚', '清楚', '了解', '认识', '熟悉', '清楚', '什么', '怎么', '为什么', '怎么样', '多少', '几', '哪', '谁', '何时', '何地', '如何', '为何', '可否', '能否', '是否', '有无', '多少', '几', '哪', '谁', '何时', '何地', '如何', '为何', '可否', '能否', '是否', '有无', '一个', '一些', '有些', '某些', '许多', '大量', '少量', '全部', '部分', '大部分', '小部分', '所有', '一切', '任何', '每', '各', '分别', '各自', '互相', '彼此', '共同', '一起', '一同', '同时', '先后', '依次', '逐个', '逐一'}
            
            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
            result = []
            for word, count in sorted_words:
                if word not in stop_words:
                    result.append({"topic": word, "count": count})
                if len(result) >= limit:
                    break
            
            return result
    
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