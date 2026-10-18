# Field Radar - set up the automatic daily run (Windows Task Scheduler, built in, free).
# Runs every day at the time below. If the PC was off or asleep at that time,
# Windows runs it as soon as the PC is back on. No admin rights needed.
param([string]$Time = "08:00")

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $here "radar.py"

# pythonw.exe = Python without a black console window
$python = (Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike "*WindowsApps*" } | Select-Object -First 1).Source
if (-not $python) { throw "Python was not found. Install it from python.org (free) and tick 'Add to PATH'." }
$pythonw = Join-Path (Split-Path $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $python }

$action   = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $here
$trigger  = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

Register-ScheduledTask -TaskName "FieldRadar" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Field Radar daily briefing ($here)" -Force | Out-Null

Write-Host ""
Write-Host "Done! Field Radar will run every day at $Time." -ForegroundColor Green
Write-Host "If your PC is off at that time, it runs as soon as you switch it on."
Write-Host "To change the time:  run schedule_install.bat again, or edit 'FieldRadar' in Task Scheduler."
Write-Host "To stop it:          run schedule_remove.bat"
