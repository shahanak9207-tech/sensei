@echo off
cd /d "%~dp0"
echo Starting HidePix...
py hidepix.py
if %ERRORLEVEL% NEQ 0 (
    python hidepix.py
)
pause
