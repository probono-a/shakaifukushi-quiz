#!/bin/bash
PORT=8000

echo "Stopping process on port $PORT..."
lsof -ti :$PORT | xargs kill -9 2>/dev/null
echo "Done."
