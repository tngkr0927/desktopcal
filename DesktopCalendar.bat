@echo off
cd /d "%~dp0"
pip install -r requirements.txt --quiet 2>nul
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [오류 발생] 위 메시지를 확인하세요.
    pause
)
