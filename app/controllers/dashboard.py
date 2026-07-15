"""
数智大屏控制器
所有统计数据来自数据仓库（data_warehouse），动态反映用户采集情况
"""

import tornado.web
import json
from app.controllers.base import AdminBaseHandler
from app.models.db import get_connection
from app.models.data_source import DataSourceRepository
from app.models.user import UserRepository
from app.models.admin import AdminRepository
from app.models.digital_employee import DigitalEmployeeRepository


class DashboardHandler(AdminBaseHandler):
    """数智大屏首页"""

    @tornado.web.authenticated
    def get(self):
        self.render("admin/dashboard.html", title="数智大屏", username=self.current_user)


class DashboardDataHandler(AdminBaseHandler):
    """大屏数据接口 - 数据来源：数据仓库"""

    @tornado.web.authenticated
    def get(self):
        action = self.get_argument("action", "")

        if action == "overview":
            self._get_overview_data()
        elif action == "source_stats":
            self._get_source_stats()
        elif action == "keyword_cloud":
            self._get_keyword_cloud()
        elif action == "collect_trend":
            self._get_collect_trend()
        elif action == "warehouse_stats":
            self._get_warehouse_stats()
        elif action == "employee_stats":
            self._get_employee_stats()
        elif action == "user_stats":
            self._get_user_stats()
        else:
            self.write({"code": 1, "msg": "无效的操作"})

    def _get_overview_data(self):
        """概览数据 - 全部来自数据仓库"""
        with get_connection() as conn:
            # 数据仓库总条数
            total_warehouse = conn.execute("SELECT COUNT(*) FROM data_warehouse").fetchone()[0]

            # 已启用数据源个数
            total_sources = conn.execute(
                "SELECT COUNT(*) FROM data_sources WHERE is_enabled = 1"
            ).fetchone()[0]

            # 用户总数
            total_users = conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_disabled = 0"
            ).fetchone()[0]

            # 管理员总数
            total_admins = conn.execute(
                "SELECT COUNT(*) FROM admins WHERE is_disabled = 0"
            ).fetchone()[0]

            # 已深度采集条数
            deep_collected = conn.execute(
                "SELECT COUNT(*) FROM data_warehouse WHERE is_deep_collected = 1"
            ).fetchone()[0]

        self.write({
            "code": 0,
            "data": {
                "total_warehouse": total_warehouse,
                "total_sources": total_sources,
                "total_users": total_users,
                "total_admins": total_admins,
                "deep_collected": deep_collected,
            }
        })

    def _get_source_stats(self):
        """数据源分布统计 - 来自数据仓库"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT ds.name as source_name, COUNT(dw.id) as count, ds.is_enabled
                FROM data_sources ds
                LEFT JOIN data_warehouse dw ON ds.id = dw.source_id
                GROUP BY ds.id
                ORDER BY count DESC
                """
            ).fetchall()

            stats = [
                {
                    "name": row["source_name"],
                    "count": row["count"],
                    "is_enabled": row["is_enabled"],
                }
                for row in rows
            ]

        self.write({"code": 0, "data": stats})

    def _get_keyword_cloud(self):
        """关键词云 - 来自数据仓库，动态反映用户搜索采集"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT keyword, COUNT(*) as cnt
                FROM data_warehouse
                WHERE keyword IS NOT NULL AND keyword != ''
                GROUP BY keyword
                ORDER BY cnt DESC
                LIMIT 50
                """
            ).fetchall()

            word_list = [
                {"name": row["keyword"], "value": row["cnt"]}
                for row in rows
            ]

        self.write({"code": 0, "data": word_list})

    def _get_collect_trend(self):
        """采集趋势 - 来自数据仓库 updated_at，动态反映用户采集活动"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT DATE(updated_at) as date, COUNT(*) as count
                FROM data_warehouse
                WHERE updated_at IS NOT NULL
                GROUP BY DATE(updated_at)
                ORDER BY date DESC
                LIMIT 30
                """
            ).fetchall()

            # 反转为正序
            trend_data = [
                {"date": row["date"], "count": row["count"]}
                for row in reversed(rows)
            ]

        self.write({"code": 0, "data": trend_data})

    def _get_warehouse_stats(self):
        """数据仓库状态统计"""
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM data_warehouse").fetchone()[0]
            deep_collected = conn.execute(
                "SELECT COUNT(*) FROM data_warehouse WHERE is_deep_collected = 1"
            ).fetchone()[0]
            not_deep_collected = total - deep_collected

            # 按数据源分布
            source_rows = conn.execute(
                """
                SELECT COALESCE(source_name, '未知') as name, COUNT(*) as count
                FROM data_warehouse
                GROUP BY source_name
                ORDER BY count DESC
                """
            ).fetchall()

            source_distribution = {
                row["name"]: row["count"] for row in source_rows
            }

        self.write({
            "code": 0,
            "data": {
                "total": total,
                "deep_collected": deep_collected,
                "not_deep_collected": not_deep_collected,
                "source_distribution": source_distribution,
            }
        })

    def _get_employee_stats(self):
        """数字员工统计"""
        result = DigitalEmployeeRepository.get_all(1, 100, "")
        items = result["items"]

        type_distribution = {}
        enabled_count = 0
        disabled_count = 0

        for emp in items:
            emp_type = emp["type"]
            type_distribution[emp_type] = type_distribution.get(emp_type, 0) + 1

            if emp["is_enabled"] == 1:
                enabled_count += 1
            else:
                disabled_count += 1

        self.write({
            "code": 0,
            "data": {
                "total": result["total"],
                "enabled": enabled_count,
                "disabled": disabled_count,
                "type_distribution": type_distribution,
            }
        })

    def _get_user_stats(self):
        """用户统计"""
        users_result = UserRepository.get_all_users(1, 1000, "")
        admins_result = AdminRepository.get_all_admins(1, 1000, "")

        users = users_result["items"]
        admins = admins_result["items"]

        user_enabled = 0
        user_disabled = 0
        admin_enabled = 0
        admin_disabled = 0

        for u in users:
            if u["is_disabled"] == 0:
                user_enabled += 1
            else:
                user_disabled += 1

        for a in admins:
            if a["is_disabled"] == 0:
                admin_enabled += 1
            else:
                admin_disabled += 1

        self.write({
            "code": 0,
            "data": {
                "total_users": users_result["total"],
                "total_admins": admins_result["total"],
                "user_enabled": user_enabled,
                "user_disabled": user_disabled,
                "admin_enabled": admin_enabled,
                "admin_disabled": admin_disabled,
            }
        })
