#!/usr/bin/env python3
"""检查数据库配置"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=== 数据库配置检查 ===")
print(f"DB_HOST: {os.getenv('DB_HOST', '未设置')}")
print(f"DB_PORT: {os.getenv('DB_PORT', '未设置')}")
print(f"DB_NAME: {os.getenv('DB_NAME', '未设置')}")
print(f"DB_USER: {os.getenv('DB_USER', '未设置')}")
print(f"DB_PASSWORD: {'已设置' if os.getenv('DB_PASSWORD') else '未设置'}")
