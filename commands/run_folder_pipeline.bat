@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
setlocal

set "SCRIPT_DIR=%~dp0"
set "PY_SCRIPTS_DIR=%SCRIPT_DIR%.."

if "%~1"=="" (
    echo Использование:
    echo   run_folder_pipeline.bat "Имя папки" [primary^|candidate^|both] [reset^|noreset]
    echo.
    echo Примеры:
    echo   run_folder_pipeline.bat "Проекты"
    echo   run_folder_pipeline.bat "Проекты" primary
    echo   run_folder_pipeline.bat "Проекты" candidate
    echo   run_folder_pipeline.bat "Проекты" both
    echo   run_folder_pipeline.bat "Проекты" both reset
    echo   run_folder_pipeline.bat "Проекты" primary noreset
    exit /b 1
)

set FOLDER_NAME=%~1

if "%~2"=="" (
    set COLLECTION_MODE=primary
) else (
    set COLLECTION_MODE=%~2
)

if "%~3"=="" (
    set RESET_MODE=noreset
) else (
    set RESET_MODE=%~3
)

if /I not "%COLLECTION_MODE%"=="primary" if /I not "%COLLECTION_MODE%"=="candidate" if /I not "%COLLECTION_MODE%"=="both" (
    echo Ошибка: второй параметр должен быть primary, candidate или both
    exit /b 1
)

if /I not "%RESET_MODE%"=="reset" if /I not "%RESET_MODE%"=="noreset" (
    echo Ошибка: третий параметр должен быть reset или noreset
    exit /b 1
)

echo ==========================================
echo Каталог: %FOLDER_NAME%
echo Режим коллекций: %COLLECTION_MODE%
echo Режим сброса: %RESET_MODE%
echo ==========================================

if /I "%RESET_MODE%"=="reset" (
    echo.
    echo =========================
    echo Сброс llm-полей
    echo =========================
    python "%PY_SCRIPTS_DIR%\reset_llm_fields.py" "%FOLDER_NAME%"
    if errorlevel 1 exit /b 1
)

echo.
echo =========================
echo Дозаполнение схемы и классификации
echo =========================
python "%PY_SCRIPTS_DIR%\propose_clusters.py" "%FOLDER_NAME%"
if errorlevel 1 exit /b 1

if /I "%COLLECTION_MODE%"=="primary" (
    echo.
    echo =========================
    echo Сборка primary-коллекций
    echo =========================
    python "%PY_SCRIPTS_DIR%\build_collection.py" "%FOLDER_NAME%" primary
    if errorlevel 1 exit /b 1
)

if /I "%COLLECTION_MODE%"=="candidate" (
    echo.
    echo =========================
    echo Сборка candidate-коллекций
    echo =========================
    python "%PY_SCRIPTS_DIR%\build_collection.py" "%FOLDER_NAME%" candidate
    if errorlevel 1 exit /b 1
)

if /I "%COLLECTION_MODE%"=="both" (
    echo.
    echo =========================
    echo Сборка primary-коллекций
    echo =========================
    python "%PY_SCRIPTS_DIR%\build_collection.py" "%FOLDER_NAME%" primary
    if errorlevel 1 exit /b 1

    echo.
    echo =========================
    echo Сборка candidate-коллекций
    echo =========================
    python "%PY_SCRIPTS_DIR%\build_collection.py" "%FOLDER_NAME%" candidate
    if errorlevel 1 exit /b 1
)

echo.
echo =========================
echo Готово
echo =========================

endlocal
