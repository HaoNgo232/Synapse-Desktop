@echo off
REM Startup script for Synapse Desktop (Windows)
REM Automatically checks and creates virtual environment if needed

setlocal

set VENV_DIR=.venv
set REQUIREMENTS_FILE=requirements.txt

echo === Synapse Desktop Startup Script (Windows) ===
echo.

REM Check if virtual environment exists
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Virtual environment not found. Creating at: %VENV_DIR%...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Could not create virtual environment!
        echo Make sure Python 3.12+ is installed and in PATH.
        pause
        exit /b 1
    )
    
    echo [INFO] Activating virtual environment and installing dependencies...
    call "%VENV_DIR%\Scripts\activate.bat"
    
    if exist "%REQUIREMENTS_FILE%" (
        echo [INFO] Installing requirements...
        python -m pip install --upgrade pip
        pip install -r "%REQUIREMENTS_FILE%"
        if errorlevel 1 (
            echo [ERROR] Failed to install dependencies!
            pause
            exit /b 1
        )
    )
    echo [INFO] Setup complete!
    echo.
) else (
    REM Activate existing virtual environment
    echo [INFO] Activating virtual environment...
    call "%VENV_DIR%\Scripts\activate.bat"
)

REM Check main_window.py
if not exist "presentation\main_window.py" (
    echo [ERROR] presentation\main_window.py not found!
    pause
    exit /b 1
)

REM Start application
echo Starting application (Synapse Desktop)...
echo.
set PYTHONPATH=%PYTHONPATH%;.
python -m presentation.main_window

set APP_EXIT_CODE=%errorlevel%

if %APP_EXIT_CODE% neq 0 (
    echo.
    echo Application exited with error code: %APP_EXIT_CODE%
)

pause