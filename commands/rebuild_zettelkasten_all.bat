@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
setlocal

set "SCRIPT_DIR=%~dp0"
set "PY_SCRIPTS_DIR=%SCRIPT_DIR%.."
set "FOLDER_NAME=Zettelkasten"
set "PIPELINE_MODE=both"
set "CURRENT_STEP=Инициализация"

for /f "tokens=1-4 delims=/.- " %%a in ("%date%") do set d=%%d-%%b-%%c
for /f "tokens=1-3 delims=:." %%a in ("%time%") do set t=%%a-%%b-%%c
set LOG_FILE=zettelkasten_rebuild_%d%_%t%.log

echo ========================================== > "%LOG_FILE%"
echo Полное обновление knowledge layer >> "%LOG_FILE%"
echo Каталог: %FOLDER_NAME% >> "%LOG_FILE%"
echo ========================================== >> "%LOG_FILE%"

echo ==========================================
echo Полное обновление knowledge layer
echo Каталог: %FOLDER_NAME%
echo Лог: %LOG_FILE%
echo ==========================================

set "CURRENT_STEP=1. Дозаполнение схемы и классификации"
python "%PY_SCRIPTS_DIR%\append_log.py" "%FOLDER_NAME%" "%PIPELINE_MODE%" "%CURRENT_STEP%" success >nul 2>&1

echo.>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"
echo 1. Дозаполнение схемы и классификации>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"

echo.
echo =========================
echo 1. Дозаполнение схемы и классификации
echo =========================
python "%PY_SCRIPTS_DIR%\propose_clusters.py" "%FOLDER_NAME%" >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :error

set "CURRENT_STEP=2. Пересборка primary-collections"
python "%PY_SCRIPTS_DIR%\append_log.py" "%FOLDER_NAME%" "%PIPELINE_MODE%" "%CURRENT_STEP%" success >nul 2>&1

echo.>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"
echo 2. Пересборка primary-collections>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"

echo.
echo =========================
echo 2. Пересборка primary-collections
echo =========================
python "%PY_SCRIPTS_DIR%\build_collection.py" "%FOLDER_NAME%" primary >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :error

set "CURRENT_STEP=3. Пересборка primary-concepts"
python "%PY_SCRIPTS_DIR%\append_log.py" "%FOLDER_NAME%" "%PIPELINE_MODE%" "%CURRENT_STEP%" success >nul 2>&1

echo.>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"
echo 3. Пересборка primary-concepts>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"

echo.
echo =========================
echo 3. Пересборка primary-concepts
echo =========================
python "%PY_SCRIPTS_DIR%\generate_concepts.py" primary >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :error

set "CURRENT_STEP=4. Пересборка primary-index"
python "%PY_SCRIPTS_DIR%\append_log.py" "%FOLDER_NAME%" "%PIPELINE_MODE%" "%CURRENT_STEP%" success >nul 2>&1

echo.>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"
echo 4. Пересборка primary-index>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"

echo.
echo =========================
echo 4. Пересборка primary-index
echo =========================
python "%PY_SCRIPTS_DIR%\generate_index.py" primary >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :error

set "CURRENT_STEP=5. Пересборка candidate-collections"
python "%PY_SCRIPTS_DIR%\append_log.py" "%FOLDER_NAME%" "%PIPELINE_MODE%" "%CURRENT_STEP%" success >nul 2>&1

echo.>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"
echo 5. Пересборка candidate-collections>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"

echo.
echo =========================
echo 5. Пересборка candidate-collections
echo =========================
python "%PY_SCRIPTS_DIR%\build_collection.py" "%FOLDER_NAME%" candidate >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :error

set "CURRENT_STEP=6. Пересборка candidate-concepts"
python "%PY_SCRIPTS_DIR%\append_log.py" "%FOLDER_NAME%" "%PIPELINE_MODE%" "%CURRENT_STEP%" success >nul 2>&1

echo.>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"
echo 6. Пересборка candidate-concepts>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"

echo.
echo =========================
echo 6. Пересборка candidate-concepts
echo =========================
python "%PY_SCRIPTS_DIR%\generate_concepts.py" candidate >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :error

set "CURRENT_STEP=7. Пересборка candidate-index"
python "%PY_SCRIPTS_DIR%\append_log.py" "%FOLDER_NAME%" "%PIPELINE_MODE%" "%CURRENT_STEP%" success >nul 2>&1

echo.>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"
echo 7. Пересборка candidate-index>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"

echo.
echo =========================
echo 7. Пересборка candidate-index
echo =========================
python "%PY_SCRIPTS_DIR%\generate_index.py" candidate >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :error

set "CURRENT_STEP=Пайплайн завершен"
python "%PY_SCRIPTS_DIR%\append_log.py" "%FOLDER_NAME%" "%PIPELINE_MODE%" "%CURRENT_STEP%" success >nul 2>&1

echo.>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"
echo Готово>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"

echo.
echo =========================
echo Готово
echo =========================
echo Лог: %LOG_FILE%
goto :end

:error
python "%PY_SCRIPTS_DIR%\append_log.py" "%FOLDER_NAME%" "%PIPELINE_MODE%" "%CURRENT_STEP%" error >nul 2>&1

echo.>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"
echo Пайплайн остановлен из-за ошибки>> "%LOG_FILE%"
echo =========================>> "%LOG_FILE%"

echo.
echo =========================
echo Пайплайн остановлен из-за ошибки
echo =========================
echo Лог: %LOG_FILE%
exit /b 1

:end
endlocal
