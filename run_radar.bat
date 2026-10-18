@echo off
REM Double-click to fetch today's updates and open your dashboard.
cd /d "%~dp0"
echo Fetching updates... (about 30-60 seconds)
python radar.py --open --no-notify
if errorlevel 1 (
  echo.
  echo Something went wrong. See data\last_run.log
  pause
) else (
  timeout /t 4 >nul
)
