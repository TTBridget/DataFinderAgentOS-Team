"""
ai_model.py - AI模型管理 Repository
"""
from .db import get_connection
from ..utils.crypto import encrypt, decrypt


def _decrypt_row(row):
    """对查询结果中可能加密的 api_key 字段进行解密（原地修改）"""
    if row is None:
        return None
    if isinstance(row, dict):
        if "api_key" in row:
            row["api_key"] = decrypt(row["api_key"])
    elif hasattr(row, "keys"):
        # sqlite3.Row 对象 — 转为 dict 以便修改
        d = dict(row)
        d["api_key"] = decrypt(d.get("api_key", ""))
        return d
    return row


def _decrypt_rows(rows):
    """批量解密"""
    return [_decrypt_row(dict(r)) for r in rows]


class AiModelRepository:
    @staticmethod
    def get_all(page=1, per_page=6, search="", model_type=""):
        offset = (page - 1) * per_page
        with get_connection() as conn:
            where_clauses = []
            params = []

            if search:
                where_clauses.append("(name LIKE ? OR provider LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])

            if model_type:
                where_clauses.append("model_type = ?")
                params.append(model_type)

            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            sql = f"SELECT * FROM ai_models {where_sql} ORDER BY is_default DESC, id DESC LIMIT ? OFFSET ?"
            count_sql = f"SELECT COUNT(*) as total FROM ai_models {where_sql}"

            rows = conn.execute(sql, params + [per_page, offset]).fetchall()
            total = conn.execute(count_sql, params).fetchone()["total"]

            return {"items": _decrypt_rows(rows), "total": total}

    @staticmethod
    def get_by_id(id):
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM ai_models WHERE id = ?", (id,)).fetchone()
            return _decrypt_row(dict(row)) if row else None

    @staticmethod
    def get_default_model():
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM ai_models WHERE is_default = 1").fetchone()
            if not row:
                row = conn.execute("SELECT * FROM ai_models LIMIT 1").fetchone()
            return _decrypt_row(dict(row)) if row else None

    @staticmethod
    def create(name, provider, api_key, base_url, model_type, system_prompt, temperature, top_p, max_tokens, context_size, is_default=0):
        with get_connection() as conn:
            if is_default == 1:
                conn.execute("UPDATE ai_models SET is_default = 0")

            # 存储前加密 api_key
            encrypted_key = encrypt(api_key) if api_key else ""

            cursor = conn.execute(
                """
                INSERT INTO ai_models (name, provider, api_key, base_url, model_type, system_prompt, temperature, top_p, max_tokens, context_size, is_default)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, provider, encrypted_key, base_url, model_type, system_prompt, temperature, top_p, max_tokens, context_size, is_default)
            )
            return cursor.lastrowid

    @staticmethod
    def update(id, **kwargs):
        if not kwargs:
            return False

        # SQL 注入防护：列名白名单（仅允许 ai_models 表中的可更新列）
        ALLOWED_COLUMNS = {
            "name", "provider", "api_key", "base_url", "model_type",
            "system_prompt", "temperature", "top_p", "max_tokens",
            "context_size", "is_default"
        }

        with get_connection() as conn:
            if kwargs.get('is_default') == 1:
                conn.execute("UPDATE ai_models SET is_default = 0")

            set_clause = []
            params = []
            for key, value in kwargs.items():
                if key not in ALLOWED_COLUMNS:
                    raise ValueError(f"不允许的列名: {key}")
                # api_key 写入前加密
                if key == "api_key" and value:
                    value = encrypt(value)
                set_clause.append(f"{key} = ?")
                params.append(value)

            set_clause.append("updated_at = datetime('now','localtime')")
            params.append(id)

            sql = f"UPDATE ai_models SET {', '.join(set_clause)} WHERE id = ?"
            conn.execute(sql, params)
            return True

    @staticmethod
    def delete(id):
        with get_connection() as conn:
            conn.execute("DELETE FROM ai_models WHERE id = ?", (id,))
            return True

    @staticmethod
    def set_default(id):
        with get_connection() as conn:
            conn.execute("UPDATE ai_models SET is_default = 0")
            conn.execute("UPDATE ai_models SET is_default = 1 WHERE id = ?", (id,))
            return True

    @staticmethod
    def increment_tokens(id, tokens):
        with get_connection() as conn:
            conn.execute("UPDATE ai_models SET total_tokens_used = total_tokens_used + ? WHERE id = ?", (tokens, id))
            return True
