@echo off
cd /d "%~dp0"

:: Anaconda 초기화 (conda activate를 사용하기 위해)
call conda activate base 2>nul
if %errorlevel% neq 0 (
    :: conda activate 실패 시 직접 경로 시도
    for %%p in (
        "%USERPROFILE%\anaconda3"
        "%USERPROFILE%\Anaconda3"
        "%USERPROFILE%\miniconda3"
        "%ProgramData%\anaconda3"
        "%ProgramData%\Anaconda3"
    ) do (
        if exist "%%~p\python.exe" (
            set "PATH=%%~p;%%~p\Scripts;%%~p\Library\bin;%PATH%"
            goto :found
        )
    )
    echo [오류] Python을 찾을 수 없습니다.
    echo Anaconda Prompt에서 직접 실행해주세요.
    pause
    exit /b 1
)

:found
pip install -r requirements.txt --quiet 2>nul
start "" pythonw main.py
