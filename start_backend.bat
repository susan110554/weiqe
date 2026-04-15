@echo off
echo ========================================
echo FBI IC3 Web API Backend
echo ========================================
echo.
echo Starting Web Controller (Windows Optimized)...
echo.
echo API will be available at:
echo   http://localhost:8000
echo.
echo API Documentation:
echo   http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop
echo ========================================
echo.

python -m uvicorn web_controller.main_fixed:app --reload --port 8000
