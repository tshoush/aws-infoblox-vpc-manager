@echo off
setlocal enabledelayedexpansion

REM AWS to InfoBlox VPC Manager Setup Script (Windows)
REM This script creates a virtual environment and installs dependencies

echo ==========================================
echo AWS to InfoBlox VPC Manager Setup
echo ==========================================

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed or not in PATH. Please install Python 3.7+ first.
    echo    Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo ✅ Python found: !PYTHON_VERSION!

REM Create virtual environment
echo.
echo 🔧 Creating virtual environment...
if exist "venv" (
    echo ⚠️  Virtual environment already exists. Removing old one...
    rmdir /s /q venv
)

python -m venv venv
if %errorlevel% neq 0 (
    echo ❌ Failed to create virtual environment
    pause
    exit /b 1
)

echo ✅ Virtual environment created successfully

REM Activate virtual environment
echo.
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ❌ Failed to activate virtual environment
    pause
    exit /b 1
)

echo ✅ Virtual environment activated

REM Upgrade pip
echo.
echo 🔧 Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo.
echo 🔧 Installing Python packages...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ❌ Failed to install requirements
    pause
    exit /b 1
)

echo ✅ All packages installed successfully

REM Create config file if it doesn't exist
echo.
echo 🔧 Setting up configuration...
if not exist "config.env" (
    copy config.env.template config.env >nul
    echo ✅ Created config.env from template
    echo ⚠️  Please edit config.env with your InfoBlox details before running the tool
) else (
    echo ℹ️  config.env already exists, skipping creation
)

echo.
echo ==========================================
echo 🎉 Setup Complete!
echo ==========================================
echo.
echo Next Steps:
echo 1. Edit config.env with your InfoBlox Grid Master details:
echo    notepad config.env
echo.
echo 2. Test the parsing functionality:
echo    venv\Scripts\activate.bat
echo    python example_usage.py
echo.
echo 3. Run the main tool in dry-run mode (safe, no changes made):
echo    python aws_infoblox_vpc_manager.py --dry-run
echo.
echo 4. Run with actual changes (after testing):
echo    python aws_infoblox_vpc_manager.py
echo.
echo 5. For help and options:
echo    python aws_infoblox_vpc_manager.py --help
echo.
echo 🔒 Remember: Always test with --dry-run first!
echo.
echo Press any key to exit...
pause >nul
