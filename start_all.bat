@echo off
echo ========================================
echo FBI IC3 - Starting All Services
echo ========================================
echo.

echo Starting Backend API...
start "Backend API" cmd /k "cd /d C:\Users\Administrator\Desktop\weiqe && python -m uvicorn web_controller.main_fixed:app --port 8000"

echo Waiting for backend to start...
timeout /t 3 /nobreak > nul

echo Starting Frontend...
start "Frontend" cmd /k "cd /d C:\Users\Administrator\Desktop\weiqe\frontend && npm run dev"

echo.
echo ========================================
echo Both services are starting!
echo.
echo Backend:  http://localhost:8000/docs
echo Frontend: http://localhost:3000
echo.
echo Login: admin-token
echo ========================================
echo.
echo Waiting for frontend to start...
timeout /t 5 /nobreak > nul

echo Opening browser...
start http://localhost:3000
