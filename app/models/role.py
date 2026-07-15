"""
role.py 是数据库database/finderos.db中roles表和role_functions表的仓储对象
采用Repository模式：把SQL+数据访问集中到一个类里，controller只调用方法
"""

import sqlite3
from app.models.db import get_connection


class RoleRepository:
    """角色数据访问类"""
    
    @staticmethod
    def get_all_roles(page=1, page_size=20, search_keyword=None):
        """获取所有角色（带分页和搜索）"""
        offset = (page - 1) * page_size
        
        with get_connection() as conn:
            query = "SELECT * FROM roles"
            params = []
            
            if search_keyword:
                query += " WHERE name LIKE ?"
                params.append(f"%{search_keyword}%")
            
            query += " ORDER BY id ASC LIMIT ? OFFSET ?"
            params.extend([page_size, offset])
            
            rows = conn.execute(query, params).fetchall()
            
            # 转换为字典列表
            items = []
            for row in rows:
                items.append(dict(row))
            
            # 获取总数
            count_query = "SELECT COUNT(*) as total FROM roles"
            count_params = []
            if search_keyword:
                count_query += " WHERE name LIKE ?"
                count_params.append(f"%{search_keyword}%")
            
            total = conn.execute(count_query, count_params).fetchone()["total"]
            
            return {"items": items, "total": total, "page": page, "page_size": page_size}
    
    @staticmethod
    def get_role_by_id(role_id):
        """根据ID获取角色"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM roles WHERE id = ?",
                (role_id,)
            ).fetchone()
            if row:
                return dict(row)
        return None
    
    @staticmethod
    def create_role(name, description=None):
        """创建角色"""
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO roles (name, description) VALUES (?, ?)",
                    (name, description)
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
    
    @staticmethod
    def update_role(role_id, name, description=None):
        """更新角色"""
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE roles SET name = ?, description = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                    (name, description, role_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False
    
    @staticmethod
    def delete_role(role_id):
        """删除角色"""
        try:
            with get_connection() as conn:
                # 先删除角色-功能关联
                conn.execute("DELETE FROM role_functions WHERE role_id = ?", (role_id,))
                # 再删除角色
                conn.execute("DELETE FROM roles WHERE id = ?", (role_id,))
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_role_functions(role_id):
        """获取角色的功能列表"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT f.* FROM functions f
                INNER JOIN role_functions rf ON f.id = rf.function_id
                WHERE rf.role_id = ?
                """,
                (role_id,)
            ).fetchall()
        return rows
    
    @staticmethod
    def get_function_tree():
        """获取功能树形结构"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM functions WHERE is_disabled = 0 ORDER BY parent_id, sort_order"
            ).fetchall()
        
        # 构建树形结构
        tree = []
        parents = [row for row in rows if row["parent_id"] == 0]
        
        for parent in parents:
            node = {
                "id": parent["id"],
                "title": parent["name"],
                "children": []
            }
            
            children = [row for row in rows if row["parent_id"] == parent["id"]]
            for child in children:
                node["children"].append({
                    "id": child["id"],
                    "title": child["name"]
                })
            
            tree.append(node)
        
        return tree
    
    @staticmethod
    def assign_functions(role_id, function_ids):
        """为角色分配功能"""
        try:
            with get_connection() as conn:
                # 先删除旧的关联
                conn.execute("DELETE FROM role_functions WHERE role_id = ?", (role_id,))
                # 再添加新的关联
                for func_id in function_ids:
                    conn.execute(
                        "INSERT INTO role_functions (role_id, function_id) VALUES (?, ?)",
                        (role_id, func_id)
                    )
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_assigned_function_ids(role_id):
        """获取角色已分配的功能ID列表"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT function_id FROM role_functions WHERE role_id = ?",
                (role_id,)
            ).fetchall()
        return [row["function_id"] for row in rows]
