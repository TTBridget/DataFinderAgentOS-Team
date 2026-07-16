import json
import urllib.request
import urllib.parse
import http.cookiejar
import re
import sys

BASE = "http://localhost:10010"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def post(path, data):
    url = BASE + path
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    return opener.open(req)

def get(path):
    return opener.open(BASE + path)

def get_xsrf():
    for c in cj:
        if c.name == "_xsrf":
            return c.value
    return ""

user = "test_user_7_1_" + str(id({}))[:6]
pwd = "Test123456!"

print("先 GET /login 获取 xsrf...")
get("/login")
xsrf = get_xsrf()
print("xsrf:", xsrf)

print("注册...")
resp = post("/register", {"username": user, "password": pwd, "confirm_password": pwd, "_xsrf": xsrf})
print(resp.read().decode("utf-8", errors="replace")[:200])

print("登录...")
resp = post("/login", {"username": user, "password": pwd, "_xsrf": xsrf})
print(resp.read().decode("utf-8", errors="replace")[:200])

xsrf = get_xsrf()
print("xsrf:", xsrf)

print("\n获取数字员工列表...")
resp = get("/api/employees")
emps = json.loads(resp.read().decode("utf-8"))
emp_names = [e["name"] for e in emps.get("data", [])]
print("employees:", emp_names)
required = ["天气", "随机音乐", "新闻", "文案写作助手", "小智", "采集专员"]
missing = [r for r in required if r not in emp_names]
print("missing:", missing)

print("\n发送 @天气 北京...")
params = urllib.parse.urlencode({
    "message": "@天气 北京",
    "model_id": "",
    "session_id": "",
    "employee_id": "",
    "_xsrf": xsrf
})
resp = opener.open(urllib.request.Request(BASE + "/api/chat?" + params, method="GET"))
body = resp.read().decode("utf-8", errors="replace")
lines = body.strip().split("\n")
session_id = None
card_type = None
for line in lines:
    if line.startswith("data:"):
        data = line[5:].strip()
        if not data:
            continue
        try:
            obj = json.loads(data)
        except Exception:
            continue
        if obj.get("type") == "session":
            session_id = obj.get("data", {}).get("id")
        if obj.get("type") == "card":
            card_type = obj.get("card_type")
            print("收到卡片:", card_type, obj.get("card_data", {}).keys() if isinstance(obj.get("card_data"), dict) else obj.get("card_data"))
print("session_id:", session_id, "card_type:", card_type)

if session_id:
    print("\n查询历史消息...")
    resp = get("/api/chat/messages?session_id=" + str(session_id))
    msgs = json.loads(resp.read().decode("utf-8"))
    for m in msgs.get("data", []):
        print("msg", m["role"], "card_type:", m.get("card_type"), "content[:30]:", (m.get("content") or "")[:30])

    print("\n导出 PDF...")
    resp = get("/api/chat/export?session_id=" + str(session_id))
    ct = resp.headers.get("Content-Type")
    print("PDF Content-Type:", ct)
    data = resp.read()
    print("PDF size:", len(data))
    if ct == "application/pdf" and len(data) > 0:
        print("PDF OK")
    else:
        print("PDF FAILED")

    print("\n测试置顶会话...")
    # pin the session
    post("/api/chat/sessions", {"action": "pin", "session_id": str(session_id), "is_pinned": "1", "_xsrf": xsrf})
    # create another session via chat
    params2 = urllib.parse.urlencode({
        "message": "新建会话测试",
        "model_id": "",
        "session_id": "",
        "employee_id": "",
        "_xsrf": xsrf
    })
    resp = opener.open(urllib.request.Request(BASE + "/api/chat?" + params2, method="GET"))
    # wait done
    resp.read()
    # get sessions
    resp = get("/api/chat/sessions")
    sessions = json.loads(resp.read().decode("utf-8")).get("data", [])
    print("sessions order:", [(s["id"], s["title"], s["is_pinned"]) for s in sessions[:5]])
    if sessions and sessions[0]["is_pinned"] == 1:
        print("PIN OK")
    else:
        print("PIN FAILED")

print("\n测试 @采集专员...")
params3 = urllib.parse.urlencode({
    "message": "@采集专员 https://www.example.com",
    "model_id": "",
    "session_id": "",
    "employee_id": "",
    "_xsrf": xsrf
})
resp = opener.open(urllib.request.Request(BASE + "/api/chat?" + params3, method="GET"))
body = resp.read().decode("utf-8", errors="replace")
print(body[:1500])
