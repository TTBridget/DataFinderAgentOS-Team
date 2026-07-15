import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "finderos.db")

conn = sqlite3.connect(DB_PATH)

# 创建数据仓库表
conn.execute("""
CREATE TABLE IF NOT EXISTS data_warehouse(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    title TEXT,
    url TEXT UNIQUE,
    content TEXT,
    publish_time TEXT,
    source_name TEXT,
    keyword TEXT,
    is_deep_collected INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
)
""")

# 检查是否已存在数据仓库功能
func_exists = conn.execute("SELECT id FROM functions WHERE code = 'data_warehouse'").fetchone()

if not func_exists:
    # 获取“数据管理”模块的ID (通常是 parent_id = 0, name = '数据管理')
    parent_id = conn.execute("SELECT id FROM functions WHERE code = 'data'").fetchone()
    if parent_id:
        parent_id = parent_id[0]
        # 插入功能
        conn.execute(
            "INSERT INTO functions (name, code, icon, route, parent_id, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
            ("数据仓库", "data_warehouse", "layui-icon-table", "/admin/data_warehouse", parent_id, 3)
        )
        new_func_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # 分配给系统管理员
        conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (?, ?)", (2, new_func_id))
        
        # 添加到菜单
        conn.execute("INSERT INTO menus (function_id, sort_order, is_visible) VALUES (?, ?, ?)", (new_func_id, 3, 1))

conn.commit()
conn.close()
print("DB updated.")
