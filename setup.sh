#!/bin/bash
if ! command -v uv >/dev/null 2>&1; then
  echo "[ERROR] uv が見つかりません。"
  echo "Python をインストールしてから、ターミナルで \"pip install uv\" を実行してください。"
  echo "詳しくは README.md の「ステップ1: Python と uv をインストールする」を参照してください。"
  exit 1
fi

echo "Creating virtual environment..."
uv venv

echo "Installing libraries..."
uv pip install -r requirements.txt

echo ""
echo "Setup complete. You can now start the app with ./run.sh"
