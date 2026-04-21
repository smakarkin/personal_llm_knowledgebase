@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
setlocal

set "SCRIPT_DIR=%~dp0"
set "PY_SCRIPTS_DIR=%SCRIPT_DIR%.."

if "%~1"=="" (
    set "FOLDER_NAME=__Inbox"
) else (
    set "FOLDER_NAME=%~1"
)

if "%~2"=="" (
    set "UPDATE_INDEXES=no"
) else (
    set "UPDATE_INDEXES=%~2"
)

if /I not "%UPDATE_INDEXES%"=="yes" if /I not "%UPDATE_INDEXES%"=="no" (
    echo Ошибка: второй параметр должен быть yes или no
    echo Пример: run_inbox_ingest.bat __Inbox yes
    exit /b 1
)

echo ==========================================
echo InBox ingest workflow
echo Папка: %FOLDER_NAME%
echo Обновление index: %UPDATE_INDEXES%
echo ==========================================

echo.
echo =========================
echo 1. Классификация и дозаполнение схемы
echo =========================
python "%PY_SCRIPTS_DIR%\propose_clusters.py" "%FOLDER_NAME%"
if errorlevel 1 exit /b 1

echo.
echo =========================
echo 2. Сборка primary-collections
echo =========================
python "%PY_SCRIPTS_DIR%\build_collection.py" "%FOLDER_NAME%" primary
if errorlevel 1 exit /b 1

echo.
echo =========================
echo 3. Сборка candidate-collections
echo =========================
python "%PY_SCRIPTS_DIR%\build_collection.py" "%FOLDER_NAME%" candidate
if errorlevel 1 exit /b 1

if /I "%UPDATE_INDEXES%"=="yes" (
    echo.
    echo =========================
    echo 4. Обновление primary-index
    echo =========================
    python "%PY_SCRIPTS_DIR%\generate_index.py" primary
    if errorlevel 1 exit /b 1

    echo.
    echo =========================
    echo 5. Обновление candidate-index
    echo =========================
    python "%PY_SCRIPTS_DIR%\generate_index.py" candidate
    if errorlevel 1 exit /b 1
)

echo.
echo =========================
echo Готово
echo =========================

echo Перенос заметок в Zettelkasten выполняется вручную.

endlocal
