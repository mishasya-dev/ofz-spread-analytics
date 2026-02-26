@echo off
chcp 65001 > nul
echo ========================================
echo    OFZ Analytics - Запуск
echo ========================================
echo.

echo Проверка зависимостей...
pip show streamlit > nul 2>&1
if errorlevel 1 (
    echo [ВНИМАНИЕ] Зависимости не установлены!
    echo Запустите install.bat
    pause
    exit /b 1
)

echo Запуск приложения...
echo.
echo Приложение откроется в браузере: http://localhost:8501
echo Для остановки нажмите Ctrl+C
echo.

streamlit run app.py --server.headless=true

pause