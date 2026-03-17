@echo off
setlocal enabledelayedexpansion

where py >nul 2>nul
if %errorlevel%==0 (
  set PY_CMD=py -3
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set PY_CMD=python
  ) else (
    echo [ERROR] Python not found. Install Python 3.10+ and retry.
    exit /b 1
  )
)

if not exist .venv (
  echo [INFO] Creating virtual environment...
  call %PY_CMD% -m venv .venv
  if errorlevel 1 exit /b 1
)

call .venv\Scripts\python -m pip install --upgrade pip
call .venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

call .venv\Scripts\python -m PyInstaller --noconfirm --onefile --windowed --name video-caption-studio app.py
if errorlevel 1 exit /b 1

echo [DONE] Build output: dist\video-caption-studio.exe
