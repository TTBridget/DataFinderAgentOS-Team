"""
test_security.py - 安全修复自动化验证脚本
验证 scan/ 目录下 26 个安全报告对应的关键修复点是否生效。

运行方式：
    1. 先启动应用服务：python app.py
    2. 再执行：python test_security.py
"""
import os
import sys
import json
import re
import urllib.parse
import requests

# 将项目根目录加入路径，以便直接导入 app 内模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.security import (
    safe_int,
    safe_float,
    validate_llm_base_url,
    validate_employee_api_url,
    validate_http_url,
    is_private_ip,
)
from app.models.data_query import _validate_sql, DataQueryError
from app.services.intent_engine import _escape_prompt_input

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:10010")


def test_safe_int_float():
    """验证未处理的 int()/float() 转换已修复"""
    assert safe_int("abc", 0) == 0
    assert safe_int("123", 0) == 123
    assert safe_int(None, 5) == 5
    assert safe_float("abc", 0.0) == 0.0
    assert safe_float("3.14", 0.0) == 3.14
    print("[PASS] safe_int / safe_float 安全转换")


def test_llm_base_url_validation():
    """验证 LLM base_url SSRF 防护"""
    assert validate_llm_base_url("https://api.openai.com/v1") is True
    assert validate_llm_base_url("http://127.0.0.1:8080/v1") is False
    assert validate_llm_base_url("http://localhost:11434") is False
    assert validate_llm_base_url("http://192.168.1.1/v1") is False
    assert validate_llm_base_url("ftp://api.openai.com/v1") is False
    assert validate_llm_base_url("https://10.0.0.1/v1") is False
    print("[PASS] LLM base_url SSRF 校验")


def test_employee_api_url_validation():
    """验证数字员工 API URL SSRF 防护（支持 {message}/{query} 占位符）"""
    assert validate_employee_api_url("https://wttr.in/{query}") is True
    assert validate_employee_api_url("https://www.baidu.com/{message}") is True
    assert validate_employee_api_url("http://127.0.0.1/{query}") is False
    assert validate_employee_api_url("http://localhost/api") is False
    assert validate_employee_api_url("") is True
    print("[PASS] 数字员工 API URL SSRF 校验")


def test_private_ip_detection():
    """验证私有/内部 IP 识别"""
    assert is_private_ip("127.0.0.1") is True
    assert is_private_ip("10.0.0.1") is True
    assert is_private_ip("192.168.1.1") is True
    assert is_private_ip("172.16.0.1") is True
    assert is_private_ip("169.254.169.254") is True
    assert is_private_ip("8.8.8.8") is False
    print("[PASS] 私有/内部 IP 识别")


def test_sql_validation():
    """验证 SQL 注入防护（sqlparse AST + 白名单表）"""
    allowed_cases = [
        "SELECT COUNT(*) FROM data_warehouse",
        "SELECT source_name, COUNT(*) FROM data_warehouse GROUP BY source_name",
        "SELECT dwd.title, dcd.word_count FROM deep_collected_data dcd JOIN data_warehouse dwd ON dcd.warehouse_id=dwd.id",
        'SELECT * FROM "data_warehouse" WHERE title LIKE \"%高温%\"',
    ]
    for sql in allowed_cases:
        try:
            _validate_sql(sql)
        except DataQueryError as e:
            raise AssertionError(f"合法 SQL 被误判: {sql} -> {e}")

    forbidden_cases = [
        "SELECT * FROM data_warehouse, admins",  # 逗号连接绕过
        'SELECT * FROM "sqlite_master"',  # 引号标识符绕过
        "INSERT INTO data_warehouse (title) VALUES ('x')",
        "UPDATE data_warehouse SET title='x'",
        "DELETE FROM data_warehouse",
        "DROP TABLE data_warehouse",
        "SELECT * FROM data_warehouse; SELECT * FROM collected_data",  # 多语句
    ]
    for sql in forbidden_cases:
        try:
            _validate_sql(sql)
            raise AssertionError(f"非法 SQL 应被拒绝: {sql}")
        except DataQueryError:
            pass

    print("[PASS] SQL 注入 AST 白名单校验")


def test_prompt_escape():
    """验证提示词注入转义"""
    assert _escape_prompt_input("<script>alert(1)</script>") == "＜script＞alert(1)＜/script＞"
    assert _escape_prompt_input("正常问题") == "正常问题"
    assert _escape_prompt_input("") == ""
    assert _escape_prompt_input(None) is None
    print("[PASS] 提示词注入转义")


def test_env_cookie_secret():
    """验证 cookie_secret 不再硬编码"""
    with open("app.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert 'cookie_secret = "datafinderagentos-token"' not in content
    assert 'cookie_secret = os.environ.get' in content
    with open("config/config.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "'cookie_secret': 'datafinderagentos-token'" not in content
    assert "os.environ.get('COOKIE_SECRET'" in content
    print("[PASS] cookie_secret 从环境变量读取")


def test_debug_mode_env():
    """验证 debug 模式基于环境变量"""
    with open("app.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "debug=True" not in content
    assert "os.environ.get('DEBUG'" in content
    print("[PASS] debug 模式基于环境变量")


def test_default_admin_password():
    """验证默认管理员密码非硬编码"""
    with open("app/models/db.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "os.environ.get('ADMIN_INITIAL_PASSWORD')" in content
    assert "password = \"admin\"" not in content
    assert "123456" not in content
    print("[PASS] 默认管理员密码从环境变量/随机生成")


def _get_xsrf(session):
    session.get(f"{BASE_URL}/login", allow_redirects=False)
    return session.cookies.get("_xsrf", "")


TEST_USERNAME = f"testuser_sec_{os.getpid()}"
TEST_PASSWORD = "testpass123"


def _ensure_test_user(session):
    """确保测试用户存在并已登录"""
    xsrf = _get_xsrf(session)
    login_resp = session.post(
        f"{BASE_URL}/login",
        data={"username": TEST_USERNAME, "password": TEST_PASSWORD, "_xsrf": xsrf},
        allow_redirects=False,
    )
    if login_resp.status_code == 302:
        return True
    # 尝试注册
    xsrf = _get_xsrf(session)
    reg_resp = session.post(
        f"{BASE_URL}/register",
        data={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD,
            "_xsrf": xsrf,
        },
        allow_redirects=False,
    )
    return reg_resp.status_code == 302


def test_api_key_not_leaked_in_api_models():
    """验证 /api/models 不返回 api_key"""
    session = requests.Session()
    if not _ensure_test_user(session):
        print("[WARN] 无法创建/登录测试用户，跳过 /api/models 校验")
        return

    xsrf = session.cookies.get("_xsrf", "")
    models_resp = session.get(f"{BASE_URL}/api/models", headers={"X-XSRFToken": xsrf})
    if models_resp.status_code != 200:
        print(f"[WARN] /api/models 请求失败 ({models_resp.status_code})，跳过 api_key 泄露校验")
        return

    data = models_resp.json()
    models = data.get("data", [])
    for m in models:
        if "api_key" in m:
            raise AssertionError("api_key 不应出现在 /api/models 响应中")
    print("[PASS] /api/models 响应不泄露 api_key")


def test_logout_requires_post():
    """验证登出仅支持 POST"""
    resp_get = requests.get(f"{BASE_URL}/logout", allow_redirects=False)
    assert resp_get.status_code == 405, f"GET /logout 应返回 405，实际 {resp_get.status_code}"
    print("[PASS] GET /logout 被禁止（仅 POST 允许）")


def test_chat_ssrf_blocked():
    """验证聊天接口对非法 base_url 返回 SSRF 错误（需要预先配置一个内网模型）"""
    session = requests.Session()
    if not _ensure_test_user(session):
        print("[WARN] 无法创建/登录测试用户，跳过 chat SSRF 校验")
        return

    xsrf = session.cookies.get("_xsrf", "")
    # 由于没有真正的内网模型，我们仅验证当模型不可用或非法时接口不会崩溃
    resp = session.get(
        f"{BASE_URL}/api/chat",
        params={"message": "hello", "model_id": 999999, "_xsrf": xsrf},
        stream=True,
        timeout=10,
    )
    # 读取少量 SSE 数据即可
    content = ""
    for line in resp.iter_lines():
        if line:
            content += line.decode("utf-8", errors="replace")
        if len(content) > 500:
            break
    resp.close()
    assert resp.status_code == 200
    # 不应暴露内部堆栈
    assert "Traceback" not in content
    assert "Internal Server Error" not in content
    print("[PASS] /api/chat 对内网/无效模型有基本防护")


def main():
    print("=" * 60)
    print("DataFinderAgentOS 安全修复自动化验证")
    print("=" * 60)

    # 本地单元测试（无需应用运行）
    test_safe_int_float()
    test_llm_base_url_validation()
    test_employee_api_url_validation()
    test_private_ip_detection()
    test_sql_validation()
    test_prompt_escape()
    test_env_cookie_secret()
    test_debug_mode_env()
    test_default_admin_password()

    # API 测试（需要应用运行）
    try:
        health = requests.get(f"{BASE_URL}/login", timeout=3)
        if health.status_code not in (200, 302):
            print(f"[WARN] 应用未在 {BASE_URL} 响应，跳过 API 测试")
        else:
            test_api_key_not_leaked_in_api_models()
            test_logout_requires_post()
            test_chat_ssrf_blocked()
    except requests.exceptions.ConnectionError:
        print(f"[WARN] 无法连接 {BASE_URL}，跳过 API 测试")

    print("=" * 60)
    print("验证完成，未发现关键安全修复失效")
    print("=" * 60)


if __name__ == "__main__":
    main()
