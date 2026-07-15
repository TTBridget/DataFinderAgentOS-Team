"""
数智大屏控制器
支持采集数据及系统运营的数智大屏呈现
"""

import tornado.web
import json
from concurrent.futures import ThreadPoolExecutor
from app.controllers.base import AdminBaseHandler
from app.models.collected_data import CollectedDataRepository
from app.models.data_source import DataSourceRepository
from app.models.data_warehouse import DataWarehouseRepository
from app.models.user import UserRepository
from app.models.admin import AdminRepository
from app.models.digital_employee import DigitalEmployeeRepository
from app.utils.security import safe_int

_DASHBOARD_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dashboard")


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
        result = CollectedDataRepository.get_all(1, 1, "")
        total_collected = result["total"]

        sources = DataSourceRepository.get_enabled()
        total_sources = len(sources)

        warehouse_result = DataWarehouseRepository.get_all(1, 1, "")
        total_warehouse = warehouse_result["total"]

        users_result = UserRepository.get_all_users(1, 1, "")
        total_users = users_result["total"]

        admins_result = AdminRepository.get_all_admins(1, 1, "")
        total_admins = admins_result["total"]

        employees_result = DigitalEmployeeRepository.get_all(1, 100, "")
        total_employees = employees_result["total"]

        self.write({
            "code": 0,
            "data": {
                "total_collected": total_collected,
                "total_sources": total_sources,
                "total_warehouse": total_warehouse,
                "total_users": total_users,
                "total_admins": total_admins,
                "total_employees": total_employees,
            }
        })

    def _get_source_stats(self):
        sources = DataSourceRepository.get_all(1, 100, "")["items"]
        stats = []

        for source in sources:
            source_id = source["id"]
            count = CollectedDataRepository.count_by_source(source_id)
            stats.append({
                "id": source_id,
                "name": source["name"],
                "count": count,
                "is_enabled": source["is_enabled"],
            })

        self.write({"code": 0, "data": stats})

    def _get_keyword_cloud(self):
        result = CollectedDataRepository.get_all(1, 500, "")
        items = result["items"]

        keyword_counts = {}
        for item in items:
            keyword = item["keyword"]
            if keyword:
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

        word_list = [
            {"name": kw, "value": count}
            for kw, count in sorted(keyword_counts.items(), key=lambda x: -x[1])[:50]
        ]

        self.write({"code": 0, "data": word_list})

    def _get_collect_trend(self):
        result = CollectedDataRepository.get_all(1, 1000, "")
        items = result["items"]

        daily_counts = {}
        for item in items:
            created_at = item["created_at"]
            if created_at:
                date_str = created_at.split(" ")[0]
                daily_counts[date_str] = daily_counts.get(date_str, 0) + 1

        sorted_dates = sorted(daily_counts.keys())[-30:]
        trend_data = [
            {"date": date, "count": daily_counts[date]}
            for date in sorted_dates
        ]

        self.write({"code": 0, "data": trend_data})

    def _get_warehouse_stats(self):
        result = DataWarehouseRepository.get_all(1, 1000, "")
        items = result["items"]

        deep_collected = 0
        not_deep_collected = 0
        source_distribution = {}

        for item in items:
            if item["is_deep_collected"] == 1:
                deep_collected += 1
            else:
                not_deep_collected += 1

            source_name = item["source_name"] or "未知"
            source_distribution[source_name] = source_distribution.get(source_name, 0) + 1

        self.write({
            "code": 0,
            "data": {
                "total": result["total"],
                "deep_collected": deep_collected,
                "not_deep_collected": not_deep_collected,
                "source_distribution": source_distribution,
            }
        })

    def _get_employee_stats(self):
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
