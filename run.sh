#!/bin/bash
PORT=8000

echo "Cleaning up port $PORT..."
lsof -ti :$PORT | xargs kill -9 2>/dev/null

if [ ! -x ".venv/bin/python" ]; then
  echo "[ERROR] .venv が見つかりません。先に ./setup.sh を実行してください。"
  exit 1
fi

echo "Starting FastAPI server..."
.venv/bin/python -m uvicorn main:app --reload --port $PORT
