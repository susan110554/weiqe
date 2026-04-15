#!/usr/bin/env python3
"""
临时修改 .env 使用 postgres 用户进行测试
"""
import os
from pathlib import Path

env_file = Path(".env")

if env_file.exists():
    # 读取现有内容
    content = env_file.read_text(encoding='utf-8')
    
    # 替换用户为 postgres
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        if line.startswith('DB_USER='):
            new_lines.append('DB_USER=postgres')
            print("✅ 已将 DB_USER 改为 postgres")
        else:
            new_lines.append(line)
    
    # 写回文件
    env_file.write_text('\n'.join(new_lines), encoding='utf-8')
    print("✅ .env 文件已更新")
    
    # 显示当前配置
    print("\n=== 更新后的配置 ===")
    os.system("python check_config.py")
else:
    print("❌ 找不到 .env 文件")
