@echo off
setlocal
set PORT=8000

echo Cleaning up port %PORT%...
powershell -Command "Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue; Write-Host 'Cleaned up old process.' }"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv が見つかりません。先に setup.bat を実行してください。
    pause
    exit /b 1
)

echo Starting FastAPI server...
start "" /min powershell -NoProfile -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:%PORT%/'"
.venv\Scripts\python.exe -m uvicorn main:app --reload --port %PORT%

pause
