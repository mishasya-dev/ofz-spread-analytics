@echo off
chcp 65001 >nul 2>&1
title OFZ Spread Analytics

echo ========================================
echo    OFZ Spread Analytics v0.2.0
echo    Автоматический запуск
echo ========================================
echo.

:: Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не установлен!
    echo Скачайте: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [OK] Python найден
echo.

:: Создание venv если нет
if not exist "venv\Scripts\activate.bat" (
    echo [*] Создание виртуального окружения...
    python -m venv venv
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось создать venv!
        pause
        exit /b 1
    )
    echo [OK] Виртуальное окружение создано
)

:: Активация venv
echo [*] Активация venv...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ОШИБКА] Не удалось активировать venv!
    pause
    exit /b 1
)

:: Проверка и установка зависимостей
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [*] Установка зависимостей...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ОШИБКА] Ошибка установки зависимостей!
        pause
        exit /b 1
    )
    echo [OK] Зависимости установлены
) else (
    echo [OK] Зависимости уже установлены
)

echo.
echo ========================================
echo  Приложение запускается...
echo  Браузер: http://localhost:8501
echo  Остановка: Ctrl+C
echo ========================================
echo.

:: Запуск Streamlit
streamlit run app.py

:: Если Streamlit завершился
echo.
echo Приложение остановлено.
pause
