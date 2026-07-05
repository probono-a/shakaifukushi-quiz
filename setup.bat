@echo off
chcp 65001 > nul

echo 仮想環境を作成しています...
uv venv

echo ライブラリをインストールしています...
uv pip install -r requirements.txt

echo.
echo セットアップが完了しました
pause
