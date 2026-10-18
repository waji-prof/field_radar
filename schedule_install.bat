@echo off
REM Double-click to make Field Radar run automatically every day.
cd /d "%~dp0"
set /p T="What time should it run each day? (24-hour, e.g. 08:00) [08:00]: "
if "%T%"=="" set T=08:00
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0schedule_install.ps1" -Time %T%
pause
