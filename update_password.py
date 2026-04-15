#!/usr/bin/env python3
"""更新 .env 文件中的数据库密码"""
import os
from pathlib import Path

def update_password():
    env_file = Path(".env")
    
    if not env_file.exists():
        print("❌ 找不到 .env 文件")
        return
    
    # 获取用户输入的密码
    password = input("请输入 PostgreSQL 密码: ")
    
    # 读取现有内容
    content = env_file.read_text(encoding='utf-8')
    lines = content.split('\n')
    new_lines = []
    password_updated = False
    
    for line in lines:
        if line.startswith('DB_PASSWORD='):
            new_lines.append(f'DB_PASSWORD={password}')
            password_updated = True
            print("✅ 密码已更新")
        else:
            new_lines.append(line)
    
    # 如果没找到 DB_PASSWORD 行，添加一行
    if not password_updated:
        new_lines.append(f'DB_PASSWORD={password}')
        print("✅ 已添加密码配置")
    
    # 写回文件
    env_file.write_text('\n'.join(new_lines), encoding='utf-8')
    print("✅ .env 文件已保存")

if __name__ == "__main__":
    update_password()
