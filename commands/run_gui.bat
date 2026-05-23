@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

pushd "%REPO_ROOT%" || (
    echo Ошибка: не удалось перейти в корень репозитория: "%REPO_ROOT%"
    exit /b 1
)

echo ==========================================
echo Запуск GUI приложения Obsidian Knowledge Base
echo Корень репозитория: %CD%
echo ==========================================

echo.
python -m gui_app.main
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo GUI завершился с ошибкой. Код: %EXIT_CODE%
) else (
    echo.
    echo GUI завершён успешно.
)

popd
endlocal & exit /b %EXIT_CODE%
