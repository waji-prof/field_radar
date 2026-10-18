@echo off
REM Double-click to stop the automatic daily run. (Your data and settings are kept.)
powershell -NoProfile -Command "Unregister-ScheduledTask -TaskName 'FieldRadar' -Confirm:$false; Write-Host 'Daily run removed.'"
pause
