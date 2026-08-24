@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo Milk Analyzer Automation - Demo Setup
echo ==========================================

if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"

echo [2/5] Installing requirements...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 goto :error

echo [3/5] Applying LOCAL database migrations...
python manage.py migrate
if errorlevel 1 goto :error

echo [4/5] Applying SERVER demo database migrations...
python manage.py migrate --database=server
if errorlevel 1 goto :error

echo [5/5] Starting server...
echo Open http://127.0.0.1:8000/
python manage.py runserver
goto :eof

:error
echo.
echo Setup failed. Check the error above.
pause
exit /b 1
