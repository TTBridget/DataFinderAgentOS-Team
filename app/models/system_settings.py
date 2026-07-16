import sqlite3
from app.models.db import get_connection

class SystemSettings:
    DEFAULT_SETTINGS = {
        'system_name': '智能瞭望与智能问数系统',
        'logo_path': '',
        'timezone': 'Asia/Shanghai',
        'date_format': 'YYYY-MM-DD',
        'page_size': 10,
        'run_mode': 'production',
        'log_level': 'ERROR',
        'session_timeout': 30,
        'max_upload_size': 10
    }

    @staticmethod
    def init_settings():
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            for key, value in SystemSettings.DEFAULT_SETTINGS.items():
                conn.execute("""
                    INSERT OR IGNORE INTO system_settings (key, value)
                    VALUES (?, ?)
                """, (key, str(value)))
            conn.commit()

    @staticmethod
    def get_settings():
        with get_connection() as conn:
            try:
                rows = conn.execute("SELECT key, value FROM system_settings").fetchall()
            except sqlite3.OperationalError:
                SystemSettings.init_settings()
                rows = conn.execute("SELECT key, value FROM system_settings").fetchall()
            
            settings = {}
            for row in rows:
                settings[row['key']] = row['value']
            return settings

    @staticmethod
    def update_settings(settings):
        with get_connection() as conn:
            for key, value in settings.items():
                conn.execute("""
                    UPDATE system_settings SET value = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE key = ?
                """, (str(value), key))
            conn.commit()

    @staticmethod
    def get_setting(key, default=None):
        settings = SystemSettings.get_settings()
        return settings.get(key, default)