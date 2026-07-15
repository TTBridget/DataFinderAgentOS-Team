import sqlite3
import json
import datetime
from app.models.db import get_connection

class DataWarehouseRepository:
    
    @staticmethod
    def save_data(source_id, title, url, content, publish_time, source_name, keyword):
        """保存数据到数据仓库（存在则更新）"""
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO data_warehouse 
                (source_id, title, url, content, publish_time, source_name, keyword, is_deep_collected, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 
                COALESCE((SELECT is_deep_collected FROM data_warehouse WHERE url = ?), 0),
                datetime('now','localtime'))
                """,
                (source_id, title, url, content, publish_time, source_name, keyword, url)
            )
            return cursor.lastrowid
            
    @staticmethod
    def get_all(page=1, per_page=20, search=""):
        """获取数据仓库列表"""
        offset = (page - 1) * per_page
        
        with get_connection() as conn:
            if search:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM data_warehouse WHERE title LIKE ? OR source_name LIKE ? OR keyword LIKE ?",
                    (f"%{search}%", f"%{search}%", f"%{search}%")
                )
                total = cursor.fetchone()[0]
                
                cursor = conn.execute(
                    "SELECT * FROM data_warehouse WHERE title LIKE ? OR source_name LIKE ? OR keyword LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (f"%{search}%", f"%{search}%", f"%{search}%", per_page, offset)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM data_warehouse")
                total = cursor.fetchone()[0]
                
                cursor = conn.execute(
                    "SELECT * FROM data_warehouse ORDER BY id DESC LIMIT ? OFFSET ?",
                    (per_page, offset)
                )
                
            items = cursor.fetchall()
            
            return {
                "total": total,
                "items": items,
                "page": page,
                "per_page": per_page
            }
            
    @staticmethod
    def get_by_id(item_id):
        """根据ID获取数据"""
        with get_connection() as conn:
            cursor = conn.execute("SELECT * FROM data_warehouse WHERE id = ?", (item_id,))
            return cursor.fetchone()
            
    @staticmethod
    def delete(item_id):
        """删除数据"""
        with get_connection() as conn:
            conn.execute("DELETE FROM deep_collected_data WHERE warehouse_id = ?", (item_id,))
            conn.execute("DELETE FROM data_warehouse WHERE id = ?", (item_id,))
            
    @staticmethod
    def toggle_deep_collected(item_id, is_deep_collected):
        """切换深度采集状态"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE data_warehouse SET is_deep_collected = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                (is_deep_collected, item_id)
            )

    @staticmethod
    def create_deep_collect_task(warehouse_id, employee_id=None, employee_name=None):
        """创建深度采集任务"""
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO deep_collected_data (warehouse_id, employee_id, employee_name, status, progress, steps, logs)
                VALUES (?, ?, ?, 'pending', 0, '[]', '[]')
                """,
                (warehouse_id, employee_id, employee_name)
            )
            return cursor.lastrowid

    @staticmethod
    def update_deep_collect_task(task_id, **kwargs):
        """更新深度采集任务"""
        with get_connection() as conn:
            updates = []
            params = []
            
            for key, value in kwargs.items():
                updates.append(f"{key} = ?")
                params.append(value)
            
            if updates:
                updates.append("updated_at = datetime('now','localtime')")
                params.append(task_id)
                
                conn.execute(
                    f"UPDATE deep_collected_data SET {', '.join(updates)} WHERE id = ?",
                    params
                )
            
            return True

    @staticmethod
    def get_deep_collect_task(warehouse_id):
        """获取深度采集任务"""
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM deep_collected_data WHERE warehouse_id = ? ORDER BY id DESC LIMIT 1",
                (warehouse_id,)
            )
            return cursor.fetchone()

    @staticmethod
    def get_deep_collect_task_by_id(task_id):
        """根据任务ID获取深度采集任务"""
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM deep_collected_data WHERE id = ?",
                (task_id,)
            )
            return cursor.fetchone()

    @staticmethod
    def add_deep_collect_step(task_id, step_name, status='running'):
        """添加深度采集步骤"""
        with get_connection() as conn:
            cursor = conn.execute("SELECT steps FROM deep_collected_data WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            steps = json.loads(row["steps"] if row else "[]")
            steps.append({"name": step_name, "status": status, "time": str(datetime.datetime.now())})
            
            conn.execute(
                "UPDATE deep_collected_data SET steps = ? WHERE id = ?",
                (json.dumps(steps), task_id)
            )
            
            return True

    @staticmethod
    def add_deep_collect_log(task_id, message, level='info'):
        """添加深度采集日志"""
        with get_connection() as conn:
            cursor = conn.execute("SELECT logs FROM deep_collected_data WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            logs = json.loads(row["logs"] if row else "[]")
            logs.append({"message": message, "level": level, "time": str(datetime.datetime.now())})
            
            conn.execute(
                "UPDATE deep_collected_data SET logs = ? WHERE id = ?",
                (json.dumps(logs), task_id)
            )
            
            return True

    @staticmethod
    def batch_deep_collect(warehouse_ids, employee_id=None, employee_name=None):
        """批量深度采集"""
        task_ids = []
        for warehouse_id in warehouse_ids:
            task_id = DataWarehouseRepository.create_deep_collect_task(warehouse_id, employee_id, employee_name)
            task_ids.append(task_id)
        return task_ids

    @staticmethod
    def get_deep_collected_items(page=1, per_page=20, search=""):
        """获取已深度采集的数据"""
        offset = (page - 1) * per_page
        
        with get_connection() as conn:
            query = """
                SELECT dw.*, dcd.result_data, dcd.status as task_status, dcd.created_at as collect_time
                FROM data_warehouse dw
                LEFT JOIN deep_collected_data dcd ON dw.id = dcd.warehouse_id
                WHERE dw.is_deep_collected = 1
            """
            
            count_query = "SELECT COUNT(*) FROM data_warehouse WHERE is_deep_collected = 1"
            
            params = []
            
            if search:
                query += " AND (dw.title LIKE ? OR dw.source_name LIKE ? OR dw.keyword LIKE ?)"
                count_query += " AND (title LIKE ? OR source_name LIKE ? OR keyword LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
            
            query += " ORDER BY dw.id DESC LIMIT ? OFFSET ?"
            params.extend([per_page, offset])
            
            cursor = conn.execute(query, params)
            items = cursor.fetchall()
            
            count_params = [f"%{search}%", f"%{search}%", f"%{search}%"] if search else []
            cursor = conn.execute(count_query, count_params)
            total = cursor.fetchone()[0]
            
            return {
                "total": total,
                "items": items,
                "page": page,
                "per_page": per_page
            }