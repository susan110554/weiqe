#!/usr/bin/env python3
"""
启动Web Controller (Windows优化版)
"""
import os
import sys

print("=" * 60)
print("🚀 启动FBI IC3 Web Controller (Windows优化版)")
print("=" * 60)
print()

# 检查环境变量
print("📋 检查配置...")
required_env = {
    "DB_HOST": os.getenv("DB_HOST", "localhost"),
    "DB_PORT": os.getenv("DB_PORT", "5432"),
    "DB_NAME": os.getenv("DB_NAME", "weiquan_bot"),
    "DB_USER": os.getenv("DB_USER", "postgres"),
}

for key, value in required_env.items():
    print(f"   {key}: {value}")

print()
print("⚠️  使用main_fixed.py (Windows单连接模式)")
print()
print("启动中...")
print("   - API地址: http://localhost:8000")
print("   - API文档: http://localhost:8000/docs")
print()
print("按 Ctrl+C 停止服务器")
print("=" * 60)
print()

# 启动uvicorn
os.system("python -m uvicorn web_controller.main_fixed:app --reload --port 8000")
