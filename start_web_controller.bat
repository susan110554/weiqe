@echo off
echo 🚀 启动IC3 Multi-Channel Web控制器...
echo.

REM 检查环境变量
if not defined WEB_ADMIN_TOKEN (
    echo ⚠️ 警告: WEB_ADMIN_TOKEN未设置，使用默认值
    set WEB_ADMIN_TOKEN=admin-token
)

if not defined WEB_SECRET_KEY (
    echo ⚠️ 警告: WEB_SECRET_KEY未设置，使用默认值
    set WEB_SECRET_KEY=change-me-in-production
)

echo 📋 配置信息:
echo    - 端口: 8000
echo    - Swagger文档: http://localhost:8000/docs
echo    - ReDoc文档: http://localhost:8000/redoc
echo.

REM 启动Web控制器
echo 🔄 正在启动FastAPI服务器...
uvicorn web_controller.main:app --reload --port 8000

pause
