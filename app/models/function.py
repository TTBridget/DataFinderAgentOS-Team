"""
function.py 是数据库database/finderos.db中functions表的仓储对象
采用Repository模式：把SQL+数据访问集中到一个类里，controller只调用方法
"""

import sqlite3
from app.models.db import get_connection


class FunctionRepository:
    """功能数据访问类"""
    
    @staticmethod
    def get_all_functions(page=1, page_size=20, search_keyword=None):
        """获取所有功能（带分页和搜索）"""
        offset = (page - 1) * page_size
        
        with get_connection() as conn:
            query = "SELECT * FROM functions"
            params = []
            
            if search_keyword:
                query += " WHERE name LIKE ? OR code LIKE ?"
                params.extend([f"%{search_keyword}%", f"%{search_keyword}%"])
            
            query += " ORDER BY parent_id, sort_order LIMIT ? OFFSET ?"
            params.extend([page_size, offset])
            
            rows = conn.execute(query, params).fetchall()
            
            # 转换为字典列表
            items = []
            for row in rows:
                items.append(dict(row))
            
            # 获取总数
            count_query = "SELECT COUNT(*) as total FROM functions"
            count_params = []
            if search_keyword:
                count_query += " WHERE name LIKE ? OR code LIKE ?"
                count_params.extend([f"%{search_keyword}%", f"%{search_keyword}%"])
            
            total = conn.execute(count_query, count_params).fetchone()["total"]
            
            return {"items": items, "total": total, "page": page, "page_size": page_size}
    
    @staticmethod
    def get_function_by_id(function_id):
        """根据ID获取功能"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM functions WHERE id = ?",
                (function_id,)
            ).fetchone()
            if row:
                return dict(row)
        return None
    
    @staticmethod
    def get_parent_functions():
        """获取所有父级功能"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM functions WHERE parent_id = 0 ORDER BY sort_order"
            ).fetchall()
            # 转换为字典列表
            items = []
            for row in rows:
                items.append(dict(row))
        return items
    
    @staticmethod
    def create_function(name, code, icon=None, route=None, parent_id=0, sort_order=0):
        """创建功能"""
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO functions (name, code, icon, route, parent_id, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (name, code, icon, route, parent_id, sort_order)
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
    
    @staticmethod
    def update_function(function_id, name, code, icon=None, route=None, parent_id=0, sort_order=0):
        """更新功能"""
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE functions
                    SET name = ?, code = ?, icon = ?, route = ?, parent_id = ?, sort_order = ?,
                        updated_at = datetime('now','localtime')
                    WHERE id = ?
                    """,
                    (name, code, icon, route, parent_id, sort_order, function_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False
    
    @staticmethod
    def delete_function(function_id):
        """删除功能"""
        try:
            with get_connection() as conn:
                # 先检查是否有子功能
                children = conn.execute(
                    "SELECT 1 FROM functions WHERE parent_id = ?",
                    (function_id,)
                ).fetchone()
                
                if children:
                    return False  # 有子功能不能删除
                
                # 删除角色-功能关联
                conn.execute("DELETE FROM role_functions WHERE function_id = ?", (function_id,))
                # 删除菜单关联
                conn.execute("DELETE FROM menus WHERE function_id = ?", (function_id,))
                # 删除功能
                conn.execute("DELETE FROM functions WHERE id = ?", (function_id,))
            return True
        except Exception:
            return False
    
    @staticmethod
    def toggle_function_disabled(function_id, is_disabled):
        """启用/禁用功能"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE functions SET is_disabled = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                (is_disabled, function_id)
            )
        return True
