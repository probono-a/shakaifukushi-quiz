#!/bin/bash
PORT=8000

echo "Cleaning up port $PORT..."
lsof -ti :$PORT | xargs kill -9 2>/dev/null

echo "Starting FastAPI server..."
uv run uvicorn main:app --reload --port $PORT
