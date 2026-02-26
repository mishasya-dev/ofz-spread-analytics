@echo off
chcp 65001 > nul
echo ========================================
echo    OFZ Analytics - Установка
echo ========================================
echo.

echo Проверка Python...
python --version > nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден!
    echo Установите Python 3.10+ с https://python.org
    pause
    exit /b 1
)

echo.
echo Установка зависимостей...
pip install -r requirements.txt

if errorlevel 1 (
    echo [ОШИБКА] Ошибка при установке зависимостей!
    pause
    exit /b 1
)

echo.
echo ========================================
echo    Установка завершена!
echo ========================================
echo.
echo Запустите start.bat для запуска приложения
pause