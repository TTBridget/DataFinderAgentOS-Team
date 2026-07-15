#test_user_model.py
import os
import sys
import time

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__),os.pardir))

if project_root not in sys.path:
	sys.path.insert(0,project_root)

from app.models.db import init_db
from app.models.user import UserRepository

init_db()

username = f"eeeee_{int(time.time())}"
password = "123456"

print("新建1：",UserRepository.create_user(username,password))
print("新建2：",UserRepository.create_user(username,password))
print("验证正确：",UserRepository.verify_user(username,password))
print("验证错误：",UserRepository.verify_user("admin",password))
print("验证错误：",UserRepository.verify_user(username,"123"))

