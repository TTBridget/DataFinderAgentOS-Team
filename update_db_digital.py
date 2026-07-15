import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "finderos.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

try:
    # 创建数字员工表
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS digital_employees(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            type TEXT NOT NULL, -- 'llm' 或 'api'
            
            -- LLM类型员工字段
            model_id INTEGER,
            system_prompt TEXT,
            use_skills INTEGER DEFAULT 0,
            use_crawl4ai INTEGER DEFAULT 0,
            
            -- API类型员工字段
            api_url TEXT,
            api_method TEXT DEFAULT 'GET',
            api_headers TEXT, -- JSON
            api_params TEXT, -- JSON
            
            is_enabled INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime'))
        )
        """
    )
    
    # 检查数字员工功能是否存在
    func_exists = conn.execute("SELECT id FROM functions WHERE code = 'digital'").fetchone()
    
    if not func_exists:
        # 查找智能应用的ID
        parent_func = conn.execute("SELECT id FROM functions WHERE code = 'ai'").fetchone()
        if parent_func:
            parent_id = parent_func[0]
            # 添加数字员工功能
            cursor = conn.execute(
                "INSERT INTO functions (name, code, icon, route, parent_id, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
                ("数字员工", "digital", "layui-icon-user", "/admin/digital", parent_id, 2)
            )
            new_func_id = cursor.lastrowid
            
            # 分配给系统管理员
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (?, ?)", (2, new_func_id))
            
            # 添加到菜单
            conn.execute("INSERT INTO menus (function_id, sort_order, is_visible) VALUES (?, ?, ?)", (new_func_id, 2, 1))
            
            print("数字员工功能和菜单已添加成功！")
        else:
            print("智能应用功能未找到，请先初始化数据库！")
    
    conn.commit()
    print("数字员工表结构更新完成！")
    
except Exception as e:
    print(f"更新失败：{e}")
finally:
    conn.close()
