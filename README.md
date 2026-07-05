# 社会福祉士過去問アプリ

社会福祉士国家試験の過去問を手元で繰り返し解くための、**完全ローカル動作**の学習支援ツールです。

- 🧠 **問題単位のトラッキング** — 解答履歴を SQLite に蓄積し、苦手問題を自動検出
- 📊 **学習ダッシュボード** — 科目別正答率・時系列推移グラフをブラウザで可視化
- 🎯 **今日のおすすめ機能** — 正答率が低く学習が疎かな科目を自動推薦
- 🔄 **4 種のセッションモード** — ランダム N 問 / 科目指定 / 間違えた問題のみ / 模擬受験
- ⬇️ **CSV エクスポート** — 学習記録を Gemini 等の外部 AI に渡して詳細分析

> **データについて**: 本リポジトリに問題データは含まれていません。PDF からのデータ作成フロー（下記）に従って自分でデータを用意する必要があります。

---

## スクリーンショット

| ダッシュボード（ダークモード） | クイズ画面（ライトモード） |
| --- | --- |
| ![Dashboard Dark Mode](docs/screenshots/dashboard_dark.png) | ![Quiz Light Mode](docs/screenshots/quiz_light.png) |

---

## 必要な環境

| ツール | バージョン | 用途 |
| --- | --- | --- |
| Python | 3.11 以上 | バックエンド API |
| [uv](https://docs.astral.sh/uv/) | 最新 | 仮想環境・パッケージ管理 |
| Google Chrome / Edge | 最新 | フロントエンド表示 |

> `uv` のインストール: `pip install uv` または [公式手順](https://docs.astral.sh/uv/#getting-started)

---

## セットアップ

### Windows

```bat
git clone https://github.com/kentaro-anno/shakaifukushi-quiz.git
cd shakaifukushi-quiz
setup.bat
```

### Linux (Ubuntu 等)

```bash
git clone https://github.com/kentaro-anno/shakaifukushi-quiz.git
cd shakaifukushi-quiz
chmod +x *.sh
./setup.sh
```

### 仮想環境の有効化（任意）

コマンドを直接実行したい場合は、仮想環境を有効化するか、`uv run` を使用してください。

#### 仮想環境に入る

- **Windows**: `.venv\Scripts\activate`
- **Linux**: `source .venv/bin/activate`

#### 有効化せずに実行（推奨）

コマンドの前に `uv run` をつけるだけで、自動的に仮想環境が使用されます。

```bash
uv run python --version
```

---

## データの準備

問題データは次の 5 ステップで作成します。ステップ 3 のみ Claude Code が担当し、それ以外は人間がコマンドを実行します。

### Step 1: 問題ファイルをダウンロード

```powershell
.venv\Scripts\python tools/download_pdfs_from_jaswe.py
```

取得元と形式は回号によって異なります。`data/pdf/{edition}th/` に保存されます。

| 回号 | 問題ファイル | 正答ファイル | 取得元 |
| --- | --- | --- | --- |
| 第 36 回以降 | 音声読み上げ用 HTML (`listen_s*_am/pm_NN.html`) | `s_kijun_seitou_NN.pdf` | [社会福祉振興・試験センター](https://www.sssc.or.jp/shakai/past_exam/index.html) |
| 第 35 回以前 | 問題 PDF | 正答 PDF | [日本ソーシャルワーク教育学校連盟](https://jaswe.jp/kokushiinfo.html) |

### Step 2: スキャフォールド JSON を生成

**パス A: HTML 源（第 36 回以降）**

```powershell
.venv\Scripts\python converter/html_to_scaffold_json.py `
  --html    data/pdf/37th/listen_ss_am_37.html `
  --answers data/pdf/37th/s_kijun_seitou_37.pdf `
  --edition 37 `
  --out     tmp/37_am
```

**パス B: 画像 PDF 源（第 35 回以前）**

```powershell
.venv\Scripts\python converter/pdf_to_scaffold_json.py `
  --source-dir data/pdf/35th `
  --edition    35
```

`--source-dir` 内の PDF を自動検出します。正答 PDF はファイル名に `seitou` または `answer` を含むものが対象です。`--out` / `--png-dir` を省略すると `tmp/{edition}th` / `scratch/{edition}th` が使われます。

`tmp/{edition}th/` 配下に科目別 JSON が、`scratch/{edition}th/` に全ページ PNG が出力されます（Claude の視覚読み取り用）。

### Step 3: Claude Code でデータを補完

Claude Code を起動し、以下のパスに応じた指示文を貼り付けて実行します。

**パス A（第 36 回以降）**: `html_to_scaffold_json.py` の完了時に出力されるプロンプト文を貼り付けます。

> Claude が `tmp/{edition}_{file}/` の科目別 JSON に `explanation` と `keywords` を科目ごとにパッチスクリプト経由で追記します。

**パス B（第 35 回以前）**: `pdf_to_scaffold_json.py` の完了時に出力されるプロンプト文を貼り付けます。

> Claude が `scratch/{png-dir}/` の PNG を視覚で読み取り、`tmp/{edition}_{file}/` の科目別 JSON に `question_text`・`options`・`case_text`・`explanation`・`keywords` をすべて科目ごとにパッチスクリプト経由で書き込みます。

### Step 4: テキスト正規化

```powershell
.venv\Scripts\python converter/normalize_text.py tmp/37_am
```

ディレクトリを指定すると配下の全 JSON に一括適用されます。

### Step 5: 人間による最終確認と DB インポート

1. **専用エディタを開く**: `tools/quiz_editor.html` をブラウザで直接開きます。

2. JSON をエディタで開き、目視で内容を確認・微修正します。

3. 確認が済んだ問題の `is_reviewed` フラグを `true` にして保存します。

4. 以下のコマンドで、確認済み（`is_reviewed: true`）のデータのみを DB に取り込みます。

```powershell
.venv\Scripts\python converter/import_json.py
```

既存データとの重複は自動でスキップされます。

---

## アプリの起動

### Windows

```bat
run.bat
```

### Linux (Ubuntu 等)

```bash
./run.sh
```

- ブラウザで [http://localhost:8000/](http://localhost:8000/) を開いてください。
- **自動プロセス掃除**: 起動時にポート 8000 を使用している古いプロセスがあれば、自動的に終了させてから起動します。
- **強制終了**: 万が一プロセスが残ってしまった場合は、Windows なら `stop.bat`、Linux なら `./stop.sh` を実行してください。

| URL | 内容 |
| --- | --- |
| `http://localhost:8000/` | ダッシュボード |
| `http://localhost:8000/quiz.html` | クイズ（セッション設定） |
| `http://localhost:8000/docs` | API ドキュメント (Swagger UI) |

---

## セッションモード

| モード | 内容 |
| --- | --- |
| **ランダム N 問** | 選んだ科目からランダムに N 問出題 |
| **科目指定** | 選んだ科目の全問を出題 |
| **間違えた問題のみ** | 過去に 1 度でも不正解だった問題に絞って出題 |
| **模擬受験** | 特定の回の全問を通しで解く |

---

## CSV エクスポートと AI 分析

ダッシュボードの **「⬇ CSV 出力」** ボタンで学習記録を CSV にダウンロードできます。  
Gemini や Claude などに CSV を添付して「弱点を分析してください」と聞くと、より詳細なフィードバックが得られます。

---

## プロジェクト構成

```
shakaifukushi-quiz/
├── main.py                     # FastAPI エントリーポイント
├── db.py                       # SQLite 接続ヘルパー
├── routers/
│   ├── questions.py            # GET /api/subjects, /api/editions, /api/questions
│   ├── sessions.py             # POST /api/sessions, PATCH /api/sessions/{id}
│   ├── history.py              # POST /api/history, GET /api/history/export
│   ├── stats.py                # GET /api/stats
│   └── recommend.py            # GET /api/recommend
├── static/
│   ├── index.html              # ダッシュボード
│   ├── quiz.html               # クイズ画面
│   ├── css/style.css           # デザインシステム（ダーク / ライトモード対応）
│   └── js/
│       ├── api.js              # 共通 API クライアント
│       ├── theme.js            # ライト / ダークモード切り替え
│       ├── dashboard.js        # ダッシュボード描画
│       └── quiz.js             # クイズ全フロー
├── converter/
│   ├── download_pdfs.py        # PDF 自動ダウンロード
│   ├── import_json.py          # JSON → SQLite インポート
│   └── validate_quiz_json.py   # JSON バリデーション
├── tools/
│   └── quiz_editor.html        # JSON 確認・修正 GUI
├── prompts/
│   └── pdf_to_json.md          # AI 抽出プロンプト
├── data/
│   ├── pdf/                    # ダウンロードした PDF（Git 管理外）
│   ├── images/                 # 変換後の画像（Git 管理外）
│   ├── json/                   # 抽出・レビュー済み JSON（Git 管理外）
│   └── quiz.db                 # SQLite DB（Git 管理外）
├── docs/
│   ├── app_requirement.md      # 要件定義
│   ├── implementation_plan.md  # 実装計画
│   └── screenshots/            # README 用スクリーンショット
├── setup.bat                   # 初回セットアップ (Windows)
├── setup.sh                    # 初回セットアップ (Linux)
├── run.bat                     # アプリ起動 (Windows)
├── run.sh                      # アプリ起動 (Linux)
├── stop.bat                    # プロセス強制終了 (Windows)
└── stop.sh                     # プロセス強制終了 (Linux)
```

---

## API エンドポイント一覧

| メソッド | パス | 説明 |
| --- | --- | --- |
| GET | `/api/subjects` | 科目一覧 |
| GET | `/api/editions` | エディション（回号）一覧 |
| GET | `/api/questions` | 問題取得（モード・科目・問題数でフィルタ） |
| POST | `/api/sessions` | セッション作成 |
| PATCH | `/api/sessions/{id}` | セッション終了 |
| POST | `/api/history` | 解答記録 |
| GET | `/api/history/export` | 学習履歴 CSV ダウンロード |
| GET | `/api/stats` | ダッシュボード用統計データ |
| GET | `/api/recommend` | 今日のおすすめセッション |

---

## ライセンス

[MIT License](LICENSE)

---

## ⚠️注意事項

- 本アプリは個人学習目的のツールです
- 商用利用や大規模なデータ収集には使用しないでください
- 問題データの著作権は各権利者に帰属します
- データの再配布はしないでください。
- 外部サーバーへの通信は行いません（フォント・Chart.js は CDN を使用）
