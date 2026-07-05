# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## コマンド

```bash
開発サーバー起動 (Windows — ポート 8000 の既存プロセスを終了してブラウザを開く)
run.bat

# 手動起動
uv run uvicorn main:app --reload --port 8000

# サーバー停止
stop.bat

# 初期セットアップ (venv作成・依存パッケージインストール) 
setup.bat
```

lint・テストコマンドは存在しない。動作確認はブラウザで `http://localhost:8000/` を開いて手動で行う。API ドキュメントは `http://localhost:8000/docs` で確認できる。

## アーキテクチャ

**バックエンド**: FastAPI (`main.py`) が `/api/` 以下の REST API を提供し、`static/` ディレクトリをフロントエンドとしてマウントする。

**フロントエンド**: バニラ JS + HTML — ビルドステップなし。`static/index.html` がダッシュボード、`static/quiz.html` がクイズ画面。共通リソースとして `static/css/style.css` と `static/js/` (`api.js`、`theme.js`、`sound.js`) を使用。

**データベース**: `data/quiz.db` (SQLite、git 管理外) 。`main.py` 起動時に初期化される。  
**主要テーブル：**

- `questions` — 過去問。`id` は `{回}_{科目}_{問番号}` 形式
- `sessions` — 学習セッションのメタデータ (UUID、mode、config JSON)
- `history` — 1解答ごとの記録 (`time_sec`、`is_correct`、`curriculum` を含む)
- `subject_mapping` — 旧カリキュラム→新カリキュラムの科目名マッピング (2024年改定対応) 。クエリでは `COALESCE(sm.subject_new, q.subject)` で統一表示する

**ルーター** (`routers/`) : `questions.py`、`sessions.py`、`history.py`、`stats.py`、`recommend.py`、`link_preview.py`。各ファイルは FastAPI の `APIRouter` として `main.py` に登録される。

## データパイプライン

試験データは以下のステップで処理される：

1. **ダウンロード**: 試験団体から PDF/HTML を取得 (`converter/download_pdfs.py`)
2. **変換**: スキャフォールド JSON へ変換

- 第36回以降: HTML → `converter/html_to_scaffold_json.py --html ... --answers ... --edition N --out tmp/`
- 第35回以前: PDF 画像 → `converter/pdf_to_scaffold_json.py --source-dir ... --edition N`

3. **補完**: 変換スクリプトが出力するプロンプトを Claude に貼り付け、`explanation`・`keywords` を生成する
4. **正規化**: `uv run python converter/normalize_text.py <dir>` (日本語句読点・空白の統一)
5. **レビュー**: 人間が `tools/quiz_editor.html` で内容を目視確認・編集し、`is_reviewed: true` にチェックを入れる
6. **インポート**: `uv run python converter/import_json.py` — `is_reviewed: true` のレコードのみ `data/quiz.db` に書き込まれる

JSON ファイルは `data/json/{回}th/` 以下に配置され、レビュー済みのものは `data/json/checked/` に移動する。

## 重要なパターン

- **科目マッピングは常に必要**: 問題レコードには旧カリキュラムの科目名が格納されている。フロントエンド向けのクエリはすべて `subject_mapping` を JOIN し、新旧カリキュラムの科目を統一表示する必要がある。
- **`curriculum` フィールド**: `questions` と `history` 両方に存在する。値は `'旧'` (2024年以前) または `'新'` (2024年以降) 。絞り込みや統計では別々に扱う。
- **問題取得モード**: `questions.py` のクエリパラメータ `mode` で切り替える — `subject` (科目別) 、`random` (ランダム) 、`wrong_only` (間違いのみ) 、`edition` (回別) 、`weak` (正答率低順) 、`unanswered` (未解答) 。
- **外部サービスなし**: すべてのデータはローカル完結。外部依存は CDN の Chart.js と Google Fonts のみ (HTML `<head>` でロード) 。
- **`.mcp.json`**: Claude Code の MCP SQLite 連携を設定し、開発時に `data/quiz.db` を直接参照できるようにしている。
