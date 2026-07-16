import json
import urllib.request
import urllib.parse
import http.cookiejar

BASE = "http://localhost:10010"
user = "test_user_7_1_195218"
pwd = "Test123456!"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def post(path, data):
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    return opener.open(req)

def get(path):
    return opener.open(BASE + path)

# get xsrf
get("/login")
xsrf = [c.value for c in cj if c.name == "_xsrf"][0]
post("/login", {"username": user, "password": pwd, "_xsrf": xsrf})

try:
    resp = get("/api/chat/export?session_id=48")
    print("status:", resp.status)
    print("content-type:", resp.headers.get("Content-Type"))
    data = resp.read()
    print("len:", len(data))
    print("first 100 bytes:", data[:100])
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code)
    print(e.read().decode("utf-8", errors="replace")[:2000])
