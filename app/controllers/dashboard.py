"""
数智大屏控制器
所有统计数据来自系统真实数据库，动态反映系统运营情况
"""

import tornado.web
import datetime
from app.controllers.base import AdminBaseHandler
from app.models.db import get_connection
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.user import UserRepository
from app.models.admin import AdminRepository


class DashboardHandler(AdminBaseHandler):
    """数智大屏首页"""

    @tornado.web.authenticated
    def get(self):
        self.render("admin/dashboard.html", title="数智大屏", username=self.current_user)


class DashboardDataHandler(AdminBaseHandler):
    """大屏数据接口"""

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
        """核心数字：仓库总数、数据源总数、用户总数、深度采集条数"""
        try:
            with get_connection() as conn:
                total_warehouse = conn.execute(
                    "SELECT COUNT(*) FROM data_warehouse"
                ).fetchone()[0]
                total_sources = conn.execute(
                    "SELECT COUNT(*) FROM data_sources"
                ).fetchone()[0]
                total_users = conn.execute(
                    "SELECT COUNT(*) FROM users"
                ).fetchone()[0]
                total_admins = conn.execute(
                    "SELECT COUNT(*) FROM admins"
                ).fetchone()[0]
                deep_collected = conn.execute(
                    "SELECT COUNT(*) FROM data_warehouse WHERE is_deep_collected = 1"
                ).fetchone()[0]

            self.write({
                "code": 0,
                "data": {
                    "total_warehouse": total_warehouse,
                    "total_sources": total_sources,
                    "total_users": total_users + total_admins,
                    "deep_collected": deep_collected,
                }
            })
        except Exception as e:
            self.write({"code": 1, "msg": str(e)})

    def _get_source_stats(self):
        """数据源分布 - 来源：数据仓库按 source_name 分组"""
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT COALESCE(source_name, '未知') as name, COUNT(*) as count
                    FROM data_warehouse
                    GROUP BY source_name
                    ORDER BY count DESC
                    """
                ).fetchall()

                stats = [
                    {"name": row["name"], "count": row["count"]}
                    for row in rows
                ]

            self.write({"code": 0, "data": stats})
        except Exception as e:
            self.write({"code": 1, "msg": str(e)})

    def _get_keyword_cloud(self):
        """关键词云 - 来源：数据仓库 keyword 字段频率统计"""
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT keyword, COUNT(*) as cnt
                    FROM data_warehouse
                    WHERE keyword IS NOT NULL AND keyword != ''
                    GROUP BY keyword
                    ORDER BY cnt DESC
                    LIMIT 60
                    """
                ).fetchall()

                word_list = [
                    {"name": row["keyword"], "value": row["cnt"]}
                    for row in rows
                ]

            self.write({"code": 0, "data": word_list})
        except Exception as e:
            self.write({"code": 1, "msg": str(e)})

    def _get_collect_trend(self):
        """采集趋势 + 预测 - 来源：数据仓库 created_at 按天统计"""
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM data_warehouse
                    WHERE created_at IS NOT NULL
                      AND created_at != ''
                    GROUP BY DATE(created_at)
                    ORDER BY date ASC
                    LIMIT 30
                    """
                ).fetchall()

                trend_data = [
                    {"date": row["date"], "count": row["count"]}
                    for row in rows
                ]

            # 简单预测：基于最近7天的平均值预测下一天
            recent_counts = [d["count"] for d in trend_data[-7:]] if trend_data else []
            predicted = round(sum(recent_counts) / len(recent_counts)) if recent_counts else 0

            today = datetime.date.today()
            next_day = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            trend_data.append({"date": next_day, "count": predicted, "predicted": True})

            self.write({"code": 0, "data": trend_data})
        except Exception as e:
            self.write({"code": 1, "msg": str(e)})

    def _get_warehouse_stats(self):
        """数据仓库状态：已深度采集 vs 未深度采集"""
        try:
            with get_connection() as conn:
                total = conn.execute(
                    "SELECT COUNT(*) FROM data_warehouse"
                ).fetchone()[0]
                deep_collected = conn.execute(
                    "SELECT COUNT(*) FROM data_warehouse WHERE is_deep_collected = 1"
                ).fetchone()[0]
                not_deep = total - deep_collected

                # 按数据源统计仓库中的数据量
                source_rows = conn.execute(
                    """
                    SELECT COALESCE(source_name, '未知') as name, COUNT(*) as count
                    FROM data_warehouse
                    GROUP BY source_name
                    ORDER BY count DESC
                    """
                ).fetchall()

                source_dist = [
                    {"name": row["name"], "value": row["count"]}
                    for row in source_rows
                ]

            self.write({
                "code": 0,
                "data": {
                    "total": total,
                    "deep_collected": deep_collected,
                    "not_deep_collected": not_deep,
                    "source_distribution": source_dist,
                }
            })
        except Exception as e:
            self.write({"code": 1, "msg": str(e)})

    def _get_employee_stats(self):
        """数字员工统计"""
        try:
            result = DigitalEmployeeRepository.get_all(1, 100, "")
            items = result["items"]

            type_dist = {}
            enabled_count = 0
            disabled_count = 0

            type_labels = {
                "llm": "LLM对话型",
                "api": "API接口型",
                "crawler": "采集型",
            }

            for emp in items:
                emp_type = emp["type"]
                label = type_labels.get(emp_type, emp_type)
                type_dist[label] = type_dist.get(label, 0) + 1
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
                    "type_distribution": type_dist,
                }
            })
        except Exception as e:
            self.write({"code": 1, "msg": str(e)})

    def _get_user_stats(self):
        """用户统计"""
        try:
            users_result = UserRepository.get_all_users(1, 1000, "")
            admins_result = AdminRepository.get_all_admins(1, 1000, "")

            users = users_result["items"]
            admins = admins_result["items"]

            user_enabled = sum(1 for u in users if u["is_disabled"] == 0)
            user_disabled = sum(1 for u in users if u["is_disabled"] == 1)
            admin_enabled = sum(1 for a in admins if a["is_disabled"] == 0)
            admin_disabled = sum(1 for a in admins if a["is_disabled"] == 1)

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
        except Exception as e:
            self.write({"code": 1, "msg": str(e)})
