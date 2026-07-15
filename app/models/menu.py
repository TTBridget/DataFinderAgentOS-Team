"""
menu.py 是数据库database/finderos.db中menus表的仓储对象
采用Repository模式：把SQL+数据访问集中到一个类里，controller只调用方法
"""

import sqlite3
from app.models.db import get_connection


class MenuRepository:
    """菜单数据访问类"""
    
    @staticmethod
    def get_all_menus():
        """获取所有菜单（带功能信息）"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT m.*, f.name, f.icon, f.route, f.parent_id, f.sort_order as func_sort
                FROM menus m
                INNER JOIN functions f ON m.function_id = f.id
                ORDER BY f.parent_id, m.sort_order, f.sort_order
                """
            ).fetchall()
            # 转换为字典列表
            items = []
            for row in rows:
                items.append(dict(row))
        return items
    
    @staticmethod
    def get_menu_tree():
        """获取菜单树形结构"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT m.*, f.name, f.icon, f.route, f.parent_id
                FROM menus m
                INNER JOIN functions f ON m.function_id = f.id
                WHERE m.is_visible = 1
                ORDER BY f.parent_id, m.sort_order
                """
            ).fetchall()
        
        # 构建树形结构
        tree = []
        parents = [row for row in rows if row["parent_id"] == 0]
        
        for parent in parents:
            node = {
                "id": parent["id"],
                "function_id": parent["function_id"],
                "name": parent["name"],
                "icon": parent["icon"],
                "route": parent["route"],
                "sort_order": parent["sort_order"],
                "children": []
            }
            
            children = [row for row in rows if row["parent_id"] == parent["function_id"]]
            for child in children:
                node["children"].append({
                    "id": child["id"],
                    "function_id": child["function_id"],
                    "name": child["name"],
                    "icon": child["icon"],
                    "route": child["route"],
                    "sort_order": child["sort_order"]
                })
            
            tree.append(node)
        
        return tree
    
    @staticmethod
    def create_menu(function_id, sort_order=0, is_visible=1):
        """创建菜单"""
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO menus (function_id, sort_order, is_visible) VALUES (?, ?, ?)",
                    (function_id, sort_order, is_visible)
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
    
    @staticmethod
    def update_menu(menu_id, sort_order=None, is_visible=None):
        """更新菜单"""
        with get_connection() as conn:
            updates = []
            params = []
            
            if sort_order is not None:
                updates.append("sort_order = ?")
                params.append(sort_order)
            
            if is_visible is not None:
                updates.append("is_visible = ?")
                params.append(is_visible)
            
            if updates:
                updates.append("updated_at = datetime('now','localtime')")
                params.append(menu_id)
                
                conn.execute(
                    f"UPDATE menus SET {', '.join(updates)} WHERE id = ?",
                    params
                )
        return True
    
    @staticmethod
    def delete_menu(menu_id):
        """删除菜单"""
        with get_connection() as conn:
            conn.execute("DELETE FROM menus WHERE id = ?", (menu_id,))
        return True
    
    @staticmethod
    def update_menu_order(menu_orders):
        """批量更新菜单排序"""
        with get_connection() as conn:
            for menu_id, sort_order in menu_orders:
                conn.execute(
                    "UPDATE menus SET sort_order = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                    (sort_order, menu_id)
                )
        return True
    
    @staticmethod
    def get_menu_by_function_id(function_id):
        """根据功能ID获取菜单"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM menus WHERE function_id = ?",
                (function_id,)
            ).fetchone()
            if row:
                return dict(row)
        return None
