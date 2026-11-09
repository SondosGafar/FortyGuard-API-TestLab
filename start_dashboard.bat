@echo off
cd /d "%~dp0"
echo Launching FortyGuard API Test Lab (local session)...
python -m streamlit run app.py
if errorlevel 1 (
  echo.
  echo If Streamlit is missing, install requirements: python -m pip install -r requirements.txt
  pause
)
