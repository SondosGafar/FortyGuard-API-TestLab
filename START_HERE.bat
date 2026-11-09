@echo off
setlocal
cd /d "%~dp0"
title FortyGuard API Test Lab

echo =============================================
echo    FortyGuard API Test Lab - Local Launcher
echo =============================================
echo.
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10+ first and enable Add Python to PATH.
  echo https://www.python.org/downloads/
  pause
  exit /b 1
)
python -c "import streamlit, pandas, plotly, requests" >nul 2>nul
if errorlevel 1 (
  echo Installing the project requirements. Internet access may be needed...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Installation failed. Review the installation error displayed above.
    pause
    exit /b 1
  )
)
echo Launching the local dashboard...
echo Dashboard URL (if not opened automatically): http://localhost:8501
echo To stop the app, press Ctrl+C here.
python -m streamlit run app.py --server.address 127.0.0.1
if errorlevel 1 (
  echo Could not launch. Review the application error displayed above.
  pause
)
