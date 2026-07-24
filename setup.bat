@echo off
chcp 65001 > nul

where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv が見つかりません。
    echo Python をインストールしてから、コマンドプロンプトで "pip install uv" を実行してください。
    echo 詳しくは README.md の「ステップ1: Python と uv をインストールする」を参照してください。
    pause
    exit /b 1
)

echo 仮想環境を作成しています...
uv venv

echo ライブラリをインストールしています...
uv pip install -r requirements.txt

echo.
echo セットアップが完了しました
pause
