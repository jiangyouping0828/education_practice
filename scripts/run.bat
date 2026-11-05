@echo off
rem Windows launcher: run scripts\run.bat in cmd (NOT bash - that goes to WSL)
cd /d "%~dp0.."

if not exist .env (
  echo [WARN] .env not found. Creating from template - fill in your API key first.
  copy .env.example .env
  exit /b 1
)

rem dependency self-check: auto-install if missing
python -c "import fastapi, uvicorn, jinja2, requests" >nul 2>&1
if errorlevel 1 (
  echo [INFO] Installing requirements.txt, please wait ...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] pip install failed. Run manually: python -m pip install -r requirements.txt
    exit /b 1
  )
)

set PYTHONPATH=src
echo [START] http://127.0.0.1:8000  (Ctrl+C to stop)
python -m intern_assistant.main
