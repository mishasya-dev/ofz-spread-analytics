@echo off
chcp 65001 >nul
title OFZ Spread Analytics

echo ╔══════════════════════════════════════╗
echo ║     OFZ Spread Analytics             ║
echo ║     Автоматический запуск            ║
echo ╚══════════════════════════════════════╝
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не установлен!
    echo Скачайте: https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist "venv" (
    echo [*] Создание виртуального окружения...
    python -m venv venv
)

call venv\Scripts\activate.bat

pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [*] Установка зависимостей...
    pip install -r requirements.txt -q
)

echo.
echo  Приложение запускается...
echo  Браузер: http://localhost:8501
echo  Остановка: Ctrl+C
echo.

streamlit run app.py
pause
