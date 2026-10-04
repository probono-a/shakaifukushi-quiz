# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## コマンド

```bash
# 開発サーバー起動 (Windows — ポート 8000 の既存プロセスを終了してブラウザを開く)
run.bat

# 手動起動 (pyproject.toml がないため、uv run は .venv を使わない。.venv の python を直接呼ぶ)
.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000

# サーバー停止
stop.bat

# 初回セットアップ (venv作成・依存パッケージインストール)
setup.bat

# テスト (初回のみ dev 用パッケージを入れる)
uv pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest

# 本番 DB に触らずに画面を確認する (DB のコピーを環境変数 QUIZ_DB_PATH で指定する)
cp data/quiz.db data/quiz_test.db
QUIZ_DB_PATH=data/quiz_test.db .venv/Scripts/python.exe -m uvicorn main:app --port 8000
```

lint コマンドは存在しない。テストは `tests/` の pytest で、DB は一時フォルダに作るので本番の `data/quiz.db` には触らない。画面の動作確認はブラウザで `http://localhost:8000/` を開いて手動で行う。API ドキュメントは `http://localhost:8000/docs` で確認できる。

DB のパスは `db.py` の `get_db_path()` だけが決める。環境変数 `QUIZ_DB_PATH` があればそのパス (相対パスはプロジェクトのルート基準)、なければ `data/quiz.db`。アプリの起動時とインポートの実行時に、使う DB のパスが表示される。

## アーキテクチャ

**バックエンド**: FastAPI (`main.py`) が `/api/` 以下の REST API を提供し、`static/` ディレクトリをフロントエンドとしてマウントする。

**フロントエンド**: バニラ JS + HTML — ビルドステップなし。`static/index.html` がダッシュボード、`static/quiz.html` がクイズ画面。共通リソースとして `static/css/style.css` と `static/js/` (`api.js`、`theme.js`、`sound.js`) を使用。

**データベース**: `data/quiz.db` (SQLite、git 管理外) 。テーブル作成・列の移行・初期データは `db.py` の `init_db()` に集約され、`main.py` の起動時と `import_json.py` の実行時に呼ばれる。  
**主要テーブル：**

- `questions` — 過去問。`id` は `{回}_{問番号}` 形式。`is_reviewed` (0 = 未確認、1 = 確認済み) で人の確認状態を持つ
- `sessions` — 学習セッションのメタデータ (UUID、mode、config JSON)
- `history` — 1解答ごとの記録 (`time_sec`、`is_correct`、`curriculum` を含む)
- `subject_mapping` — 旧カリキュラム→新カリキュラムの科目名マッピング (2024年改定対応) 。クエリでは `COALESCE(sm.subject_new, q.subject)` で統一表示する

**ルーター** (`routers/`) : `questions.py`、`sessions.py`、`history.py`、`stats.py`、`recommend.py`、`link_preview.py`。各ファイルは FastAPI の `APIRouter` として `main.py` に登録される。

## ディレクトリ構成

```
static/         フロントエンド（HTML・CSS・JS）
routers/        FastAPI ルーター
converter/      データパイプライン用スクリプト
tools/          quiz_editor.html など補助ツール
docs/
  screenshots/  README 用スクリーンショット
  dev/          開発・内部ドキュメント
    prompts/    AI プロンプト集
    archive/    旧ドキュメント
tests/          pytest による自動テスト (DB・インポート・API)
data/           SQLite DB・PDF・JSON（すべて git 管理外）
```

## データパイプライン

試験データは以下のステップで処理される：

1. **ダウンロード**: 試験団体から PDF/HTML を取得 (`converter/download_pdfs.py`)
2. **変換**: スキャフォールド JSON へ変換

- 第36回以降: HTML → `converter/html_to_scaffold_json.py --html ... --answers ... --edition N --out tmp/`
- 第35回以前: PDF 画像 → `converter/pdf_to_scaffold_json.py --source-dir ... --edition N`

3. **補完**: 変換スクリプトが出力するプロンプトを Claude に貼り付け、`explanation`・`keywords` を生成する
4. **正規化**: `.venv\Scripts\python.exe converter/normalize_text.py <dir>` (日本語句読点・空白の統一)
5. **AI精査**: `/check_explanations <対象ファイル/ディレクトリ>` — AI が解説文 (`explanation`) の制度名・条文番号・年次・統計数値などを Web 検索で裏取りし、`question_text`/`options`/`case_text` の OCR起因の誤字・欠落・混入も原本 PDF (`data/pdf/{回}th/`) と照合して修正する。確度の高い誤りを自動修正し、完了したファイルは `data/json/ai_reviewed/` に移動される
   - 原本 PDF (第35回以前はスキャン画像でテキスト層なし) との照合を高速化するため、`converter/ocr_pdf.py` で `tools/ndlocr-lite` (国立国会図書館製の軽量 OCR) を使い問題 PDF から `{PDF名}.ocr.txt` を事前生成できる。初回のみ `tools/ndlocr-lite` に専用 venv のセットアップが必要 (`cd tools/ndlocr-lite && python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt`、メインの `.venv` とは別)。OCR結果は目安であり (rn/m 等の字形誤認識がありうる)、最終確認は該当ページを PyMuPDF で画像化して視覚で行う
   - 正答 PDF (`*_answer.pdf`/`*seitou*.pdf`) はスキャン画像と違って元からテキスト層を持つため OCR は行わない (画像化すると表レイアウトが崩れてかえって読みにくくなる)。`ocr_pdf.py` は正答 PDF を検出すると `parse_answers_pdf.py` で直接テキスト抽出し、`{PDF名}.md` に科目別の正答一覧を Markdown 表として出力する
6. **インポート**: `/import_to_db` (内部で `.venv\Scripts\python.exe converter/import_json.py` を実行) — `data/json/ai_reviewed/` 以下の JSON を走査して `data/quiz.db` に書き込む。人の確認は待たない
   - DB に未登録の問題は INSERT する (`is_reviewed` は JSON の値)
   - DB で未確認 (`is_reviewed = 0`) の問題は、JSON の内容で上書きする (AI 精査のやり直しを反映できる)
   - DB で確認済み (`is_reviewed = 1`) の問題は何もしない (人が確認した内容を守る)
   - 1 ファイルずつ commit してから `data/json/imported_to_db/` に移す (同名のファイルがあれば日時付きの名前で移す)
   - 実行のたびに、JSON と DB の差分を `data/json/imported_to_db/log/import_log_*.md` に出す
7. **確認**: 人がアプリで問題を解きながら確認する。未確認の問題には「未確認」バッジが出る。解答後の「確認済みにする」ボタン、またはエディタ (`/editor.html`) の「確認済み」チェックで確認済みにする。修正もエディタで行い、内容は DB にだけ残る

JSON ファイルは `data/json/{回}th/` 以下に配置される。AI精査後は `data/json/ai_reviewed/`、DBインポート後は `data/json/imported_to_db/` に移動する。確認状態の正は、インポート後は DB の `questions.is_reviewed` で、JSON の `is_reviewed` はインポート時に一度だけ読む。`data/json/checked/` と `tools/quiz_editor.html` は、この流れでは使わない。

## 重要なパターン

- **科目マッピングは常に必要**: 問題レコードには旧カリキュラムの科目名が格納されている。フロントエンド向けのクエリはすべて `subject_mapping` を JOIN し、新旧カリキュラムの科目を統一表示する必要がある。
- **`curriculum` フィールド**: `questions` と `history` 両方に存在する。値は `'old'` (2024年以前) または `'new'` (2024年以降) 。絞り込みや統計では別々に扱う。
- **問題取得モード**: `questions.py` のクエリパラメータ `mode` で切り替える — `subject` (科目別) 、`random` (ランダム) 、`wrong_only` (間違いのみ) 、`edition` (回別) 、`weak` (正答率低順) 、`rare` (未出題・少ない順) 。
- **外部サービスなし**: すべてのデータはローカル完結。外部依存は CDN の Chart.js と Google Fonts のみ (HTML `<head>` でロード) 。
- **`.mcp.json`**: Claude Code の MCP SQLite 連携を設定し、開発時に `data/quiz.db` を直接参照できるようにしている。
- **`CHANGELOG.md`**: ユーザーに影響する変更（機能追加・修正）をコミットしたら、都度先頭に追記する。内部的なリファクタリングやドキュメントのみの変更は記載しなくてよい。
