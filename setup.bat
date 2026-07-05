@echo off
rem 仮想環境を作成してライブラリをインストールするスクリプト

echo 仮想環境を作成しています...
uv venv

echo ライブラリをインストールしています...
uv pip install -r requirements.txt

echo.
echo セットアップが完了しました
pause
