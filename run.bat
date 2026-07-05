@echo off
setlocal
set PORT=8000

echo Cleaning up port %PORT%...
powershell -Command "Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue; Write-Host 'Cleaned up old process.' }"

echo Starting FastAPI server...
start "" /min powershell -NoProfile -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:%PORT%/'"
uv run uvicorn main:app --reload --port %PORT%

pause
