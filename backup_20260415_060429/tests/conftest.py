"""
集成测试：必须设置 WEIQUAN_TEST_DB_NAME 指向专用 PostgreSQL 库，避免误连生产。
示例（PowerShell）:
  $env:WEIQUAN_TEST_DB_NAME="weiquan_bot_test"
  $env:DB_HOST="localhost"; $env:DB_USER="postgres"; $env:DB_PASSWORD="..."
  pytest tests/test_critical_path_integration.py -v
"""
from __future__ import annotations

import os

# 必须在 import database 之前覆盖 DB_NAME（pytest.ini 已设置 pythonpath = .）
if os.environ.get("WEIQUAN_TEST_DB_NAME"):
    os.environ["DB_NAME"] = os.environ["WEIQUAN_TEST_DB_NAME"]

import pytest
import pytest_asyncio

import database as db


def pytest_collection_modifyitems(config, items):
    """未配置测试库时跳过集成测试模块。"""
    if os.environ.get("WEIQUAN_TEST_DB_NAME"):
        return
    skip_no_db = pytest.mark.skip(
        reason="设置环境变量 WEIQUAN_TEST_DB_NAME 为专用测试库名后运行集成测试",
    )
    for item in items:
        if "integration" in [m.name for m in item.iter_markers()]:
            item.add_marker(skip_no_db)


@pytest_asyncio.fixture(scope="module")
async def db_ready():
    await db.close_pool()
    await db.init_db()
    yield
    await db.close_pool()
