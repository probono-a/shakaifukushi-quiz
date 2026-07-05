@echo off
setlocal
set PORT=8000

echo Checking process on port %PORT%...
powershell -Command "Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue; Write-Host 'Stopped PID: ' $_ }"

if %ERRORLEVEL% equ 0 (
    echo Done.
) else (
    echo Process not found or failed to stop.
)

pause
