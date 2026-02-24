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
    echo Virtual environment does not exist at: %VENV_DIR%
    set /p REPLY="Do you want to create a virtual environment? (y/n): "
    if /i "!REPLY!"=="y" (
        echo Creating virtual environment...
        python -m venv "%VENV_DIR%"
        if errorlevel 1 (
            echo [ERROR] Could not create virtual environment!
            echo Make sure Python 3.12+ is installed and in PATH.
            pause
            exit /b 1
        )
        echo Virtual environment created successfully!
        echo.
    ) else (
        echo Cannot continue without a virtual environment.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

REM Install dependencies
if exist "%REQUIREMENTS_FILE%" (
    echo Installing dependencies from %REQUIREMENTS_FILE%...
    pip install -r "%REQUIREMENTS_FILE%"
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies!
        pause
        exit /b 1
    )
    echo Dependencies installed successfully!
    echo.
)

REM Check main_window.py
if not exist "main_window.py" (
    echo [ERROR] main_window.py not found!
    pause
    exit /b 1
)

REM Start application
echo Starting application (PySide6)...
echo.
python main_window.py

set APP_EXIT_CODE=%errorlevel%

if %APP_EXIT_CODE% neq 0 (
    echo.
    echo Application exited with error code: %APP_EXIT_CODE%
)

pause