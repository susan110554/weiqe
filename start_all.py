import subprocess
import time
import os
import webbrowser

BASE = os.path.dirname(os.path.abspath(__file__))

print("Starting Backend...")
backend = subprocess.Popen(
    ["python", "-m", "uvicorn", "web_controller.main_fixed:app", "--port", "8000"],
    cwd=BASE
)

time.sleep(3)

print("Starting Frontend...")
frontend = subprocess.Popen(
    ["npm", "run", "dev"],
    cwd=os.path.join(BASE, "frontend"),
    shell=True
)

time.sleep(4)
webbrowser.open("http://localhost:3000")

print("\n========================================")
print("Backend:  http://localhost:8000/docs")
print("Frontend: http://localhost:3000")
print("Login:    admin-token")
print("Press Ctrl+C to stop all services")
print("========================================\n")

try:
    backend.wait()
except KeyboardInterrupt:
    print("\nStopping all services...")
    backend.terminate()
    frontend.terminate()
