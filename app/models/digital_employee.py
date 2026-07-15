import os
import re
import sqlite3
import json
from app.models.db import get_connection


# 数字员工 .nd 文件存储根目录
DG_USER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "dgUser")


def _get_employee_dir(emp_id):
    """获取指定数字员工的文件存放目录"""
    return os.path.join(DG_USER_DIR, str(emp_id))


def _sanitize_filename(filename):
    """清理文件名，防止目录遍历和非法字符"""
    if not filename:
        return "unnamed.nd"
    basename = os.path.basename(filename)
    name, ext = os.path.splitext(basename)
    name = re.sub(r'[^\w\-\.\u4e00-\u9fff]', '_', name)
    ext = ext.lower()
    if ext != ".nd":
        ext = ".nd"
    return name + ext


def save_employee_nd_files(emp_id, file_list):
    """
    保存上传的 .nd 文件到 data/dgUser/{emp_id}/
    file_list: tornado 上传文件对象列表，每个对象包含 filename 和 body
    返回成功保存的文件名列表
    """
    if not file_list:
        return []

    emp_dir = _get_employee_dir(emp_id)
    os.makedirs(emp_dir, exist_ok=True)

    saved_files = []
    for f in file_list:
        original_name = f.get("filename") if isinstance(f, dict) else getattr(f, "filename", "")
        body = f.get("body") if isinstance(f, dict) else getattr(f, "body", b"")
        if not body:
            continue

        safe_name = _sanitize_filename(original_name)
        # 如果重名，添加序号
        target_path = os.path.join(emp_dir, safe_name)
        if os.path.exists(target_path):
            name, ext = os.path.splitext(safe_name)
            counter = 1
            while os.path.exists(os.path.join(emp_dir, f"{name}_{counter}{ext}")):
                counter += 1
            safe_name = f"{name}_{counter}{ext}"
            target_path = os.path.join(emp_dir, safe_name)

        with open(target_path, "wb") as fp:
            fp.write(body)
        saved_files.append(safe_name)

    return saved_files


def read_employee_nd_contents(emp_id):
    """
    读取指定数字员工目录下所有 .nd 文件内容并拼接
    返回拼接后的字符串；如果没有文件或目录不存在，返回空字符串
    """
    emp_dir = _get_employee_dir(emp_id)
    if not os.path.isdir(emp_dir):
        return ""

    contents = []
    # 按文件名排序，保证拼接顺序稳定
    for filename in sorted(os.listdir(emp_dir)):
        if not filename.lower().endswith(".nd"):
            continue
        file_path = os.path.join(emp_dir, filename)
        if not os.path.isfile(file_path):
            continue
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fp:
                text = fp.read()
            if text.strip():
                contents.append(f"\n\n--- 来自文件 {filename} ---\n{text}")
        except Exception:
            continue

    return "".join(contents)


def list_employee_nd_files(emp_id):
    """列出指定数字员工目录下的 .nd 文件"""
    emp_dir = _get_employee_dir(emp_id)
    if not os.path.isdir(emp_dir):
        return []
    return sorted([f for f in os.listdir(emp_dir) if f.lower().endswith(".nd")])


def delete_employee_dir(emp_id):
    """删除数字员工文件目录（删除员工时调用）"""
    emp_dir = _get_employee_dir(emp_id)
    if os.path.isdir(emp_dir):
        import shutil
        shutil.rmtree(emp_dir, ignore_errors=True)


class DigitalEmployeeRepository:
    """数字员工仓储类"""

    @staticmethod
    def get_all(page=1, per_page=20, search_keyword=None):
        """获取所有数字员工，带分页和搜索"""
        offset = (page - 1) * per_page
        
        with get_connection() as conn:
            query = "SELECT de.*, am.name as model_name, ai.name as interface_name FROM digital_employees de LEFT JOIN ai_models am ON de.model_id = am.id LEFT JOIN api_interfaces ai ON de.api_interface_id = ai.id"
            count_query = "SELECT COUNT(*) as total FROM digital_employees de"
            params = []
            count_params = []
            
            if search_keyword:
                where_clause = " WHERE de.name LIKE ? OR de.description LIKE ?"
                query += where_clause
                count_query += where_clause
                params.extend([f'%{search_keyword}%', f'%{search_keyword}%'])
                count_params.extend([f'%{search_keyword}%', f'%{search_keyword}%'])
            
            query += " ORDER BY de.sort_order ASC, de.id DESC LIMIT ? OFFSET ?"
            params.extend([per_page, offset])
            
            rows = conn.execute(query, params).fetchall()
            total = conn.execute(count_query, count_params).fetchone()['total']
            
            return {"items": rows, "total": total, "page": page, "per_page": per_page}

    @staticmethod
    def get_by_id(emp_id):
        """根据ID获取数字员工"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT de.*, am.name as model_name, ai.name as interface_name FROM digital_employees de LEFT JOIN ai_models am ON de.model_id = am.id LEFT JOIN api_interfaces ai ON de.api_interface_id = ai.id WHERE de.id = ?",
                (emp_id,)
            ).fetchone()
            return row

    @staticmethod
    def create(name, description, emp_type, model_id=None, system_prompt=None,
               use_skills=0, use_crawl4ai=0, api_interface_id=None, api_url=None, api_method='GET',
               api_headers=None, api_params=None, card_type=None, is_enabled=1, sort_order=0):
        """创建数字员工"""
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO digital_employees 
                    (name, description, type, model_id, system_prompt, use_skills, use_crawl4ai, api_interface_id,
                     api_url, api_method, api_headers, api_params, card_type, is_enabled, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, description, emp_type, model_id, system_prompt, use_skills, use_crawl4ai, api_interface_id,
                     api_url, api_method, api_headers, api_params, card_type, is_enabled, sort_order)
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    @staticmethod
    def update(emp_id, name=None, description=None, emp_type=None, model_id=None,
               system_prompt=None, use_skills=None, use_crawl4ai=None, api_interface_id=None,
               api_url=None, api_method=None, api_headers=None, api_params=None, card_type=None,
               is_enabled=None, sort_order=None):
        """更新数字员工"""
        try:
            with get_connection() as conn:
                updates = []
                params = []
                
                if name is not None:
                    updates.append("name = ?")
                    params.append(name)
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                if emp_type is not None:
                    updates.append("type = ?")
                    params.append(emp_type)
                if model_id is not None:
                    updates.append("model_id = ?")
                    params.append(model_id)
                if system_prompt is not None:
                    updates.append("system_prompt = ?")
                    params.append(system_prompt)
                if use_skills is not None:
                    updates.append("use_skills = ?")
                    params.append(use_skills)
                if use_crawl4ai is not None:
                    updates.append("use_crawl4ai = ?")
                    params.append(use_crawl4ai)
                if api_interface_id is not None:
                    updates.append("api_interface_id = ?")
                    params.append(api_interface_id)
                if api_url is not None:
                    updates.append("api_url = ?")
                    params.append(api_url)
                if api_method is not None:
                    updates.append("api_method = ?")
                    params.append(api_method)
                if api_headers is not None:
                    updates.append("api_headers = ?")
                    params.append(api_headers)
                if api_params is not None:
                    updates.append("api_params = ?")
                    params.append(api_params)
                if card_type is not None:
                    updates.append("card_type = ?")
                    params.append(card_type)
                if is_enabled is not None:
                    updates.append("is_enabled = ?")
                    params.append(is_enabled)
                if sort_order is not None:
                    updates.append("sort_order = ?")
                    params.append(sort_order)
                
                if updates:
                    updates.append("updated_at = datetime('now','localtime')")
                    params.append(emp_id)
                    
                    conn.execute(
                        f"UPDATE digital_employees SET {', '.join(updates)} WHERE id = ?",
                        params
                    )
                
                return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete(emp_id):
        """删除数字员工及其文件目录"""
        with get_connection() as conn:
            conn.execute("DELETE FROM digital_employees WHERE id = ?", (emp_id,))
        delete_employee_dir(emp_id)
        return True

    @staticmethod
    def toggle_enabled(emp_id, is_enabled):
        """启用/禁用数字员工"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE digital_employees SET is_enabled = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                (is_enabled, emp_id)
            )
        return True
