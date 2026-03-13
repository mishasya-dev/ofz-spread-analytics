@echo off
chcp 65001 >nul 2>&1
title OFZ Spread Analytics

echo ========================================
echo    OFZ Spread Analytics v0.2.0
echo    Automatic start
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not installed!
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found

:: Create venv if not exists
if not exist "venv" (
    echo [*] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv!
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment exists
)

:: Activate venv
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate venv!
    pause
    exit /b 1
)
echo [OK] Virtual environment activated

:: Install dependencies
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [*] Installing dependencies...
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies!
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed
) else (
    echo [OK] Dependencies already installed
)

echo.
echo  Starting application...
echo  Browser: http://localhost:8501
echo  Stop: Ctrl+C
echo.

streamlit run app.py
