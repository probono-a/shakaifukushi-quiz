# データパイプラインガイド

PDF や HTML の過去問から問題データを一括生成し、`data/quiz.db` に投入するための開発者向けガイドです。

**対象読者**: Claude Code を使える、またはコマンドラインに慣れている人。日常的に問題を 1 問ずつ入力するだけなら、このドキュメントは不要です（README の「問題の入力方法」を参照してください）。

---

## 全体像

回号によって元データの形式が異なり、処理経路が 2 つに分かれます。

```
パス A: 第 36 回以降（HTML 形式）
[download_pdfs.py]                          ← 人間が実行
        ↓
HTML + 正答 PDF
        ↓ [html_to_scaffold_json.py]        ← 人間が実行（テキスト正規化も自動適用）
tmp/{edition}_{file}/{科目}.json × N        （question_text・options 入り、explanation は TODO）
        ↓ Claude が科目ごとにパッチスクリプトを書いて実行  ← Claude Code が担当
tmp/{edition}_{file}/{科目}.json × N        （explanation・keywords 追記済み）
        ↓ [merge_subject_json.py] → [normalize_text.py] → [validate_quiz_json.py]  ← 人間が実行
data/json/{edition}th/{file}.json           （最終 JSON）
        ↓ /check_explanations（AI 精査）→ data/json/ai_reviewed/ へ移動  ← Claude Code が担当
        ↓ [import_json.py]                  ← 人間が実行（人の確認は待たない）
data/quiz.db                                （is_reviewed = 0 の「未確認」で入る）
        ↓ アプリで解きながら確認・修正し、確認済みにする  ← 人間が実行


パス B: 第 35 回以前（PDF 画像形式）
[download_pdfs.py]                          ← 人間が実行
        ↓
問題 PDF（画像）+ 正答 PDF
        ↓ [pdf_to_scaffold_json.py]         ← 人間が実行
scratch/{png-dir}/p{NN}.png × 全ページ      （Claude 視覚読み取り用）
tmp/{edition}_{file}/{科目}.json × N        （correct_options のみ入り、テキストは TODO）
        ↓ Claude が PNG を読んでテキスト・解説パッチスクリプトを書いて実行  ← Claude Code が担当
tmp/{edition}_{file}/{科目}.json × N        （explanation・keywords 追記済み）
        ↓ [merge_subject_json.py] → [normalize_text.py] → [validate_quiz_json.py]  ← 人間が実行
data/json/{edition}th/{file}.json           （最終 JSON）
        ↓ /check_explanations（AI 精査）→ data/json/ai_reviewed/ へ移動  ← Claude Code が担当
        ↓ [import_json.py]                  ← 人間が実行（人の確認は待たない）
data/quiz.db                                （is_reviewed = 0 の「未確認」で入る）
        ↓ アプリで解きながら確認・修正し、確認済みにする  ← 人間が実行
```

> OCR 済み PDF（`*_ocr.pdf`）は文字化けが多いため、原本 PDF を必ず使用してください。

---

## 回号別の手順

### 第 36 回以降（HTML 形式）

#### 1. ダウンロード

```powershell
.venv\Scripts\python.exe converter/download_pdfs.py --edition 38
```

社会福祉振興・試験センターから、音声読み上げ用 HTML（`listen_s*_am/pm_NN.html`）と正答 PDF（`s_kijun_seitou_NN.pdf`）を `data/pdf/38th/` に取得します。

#### 2. スキャフォールド JSON を生成

```powershell
.venv\Scripts\python.exe converter/html_to_scaffold_json.py `
  --html    data/pdf/38th/listen_ss_am_38.html `
  --answers data/pdf/38th/s_kijun_seitou_38.pdf `
  --edition 38 `
  --out     tmp/38_am
```

`tmp/38_am/` 配下に科目別 JSON（`question_text`・`options` 入り、`explanation` は TODO）が出力されます。完了時にコンソールへ、次のステップで Claude Code に渡すプロンプトが表示されます。

#### 3. Claude Code で解説・キーワードを補完

Claude Code を起動し、[`docs/dev/prompts/pdf_to_json.md`](dev/prompts/pdf_to_json.md) の指示（パス A）に従って、手順 2 で表示されたプロンプトを貼り付けます。Claude が科目ごとにパッチスクリプトを書いて `explanation`・`keywords` を追記します。

#### 4. マージ・正規化・検証

```powershell
.venv\Scripts\python.exe converter/merge_subject_json.py --dir tmp/38_am --out data/json/38th/listen_ss_am_38.json
.venv\Scripts\python.exe converter/normalize_text.py data/json/38th/listen_ss_am_38.json
.venv\Scripts\python.exe converter/validate_quiz_json.py data/json/38th/listen_ss_am_38.json
```

`validate_quiz_json.py` が警告を出した場合は、該当箇所を JSON 内で直接修正してから次に進みます。

---

### 第 35 回以前（PDF 画像形式）

#### 1. ダウンロード

```powershell
.venv\Scripts\python.exe converter/download_pdfs.py --edition 35
```

日本ソーシャルワーク教育学校連盟から、問題 PDF・正答 PDF を `data/pdf/35th/` に取得します（回によっては手動配置が必要な場合があります）。

#### 2. スキャフォールド JSON + PNG を生成

```powershell
.venv\Scripts\python.exe converter/pdf_to_scaffold_json.py --source-dir data/pdf/35th --edition 35
```

`--source-dir` 内の PDF を自動検出します（正答 PDF はファイル名に `seitou` または `answer` を含むもの）。`--out` / `--png-dir` を省略すると `tmp/{edition}th` / `scratch/{edition}th` が使われます。`--scale`（デフォルト 2.0 = 144DPI）で PNG 解像度を調整できます。

`tmp/35th/` に科目別 JSON（`correct_options` のみ、テキストは TODO）、`scratch/35th/` に全ページ PNG が出力されます。

#### 3. Claude Code でテキスト・解説・キーワードを補完

Claude Code を起動し、[`docs/dev/prompts/pdf_to_json.md`](dev/prompts/pdf_to_json.md) の指示（パス B）に従います。[`docs/dev/prompts/pdf_chat_instruction.txt`](dev/prompts/pdf_chat_instruction.txt) の文面をそのまま貼り付けると、対象の PNG / JSON ディレクトリを指定した状態で指示を開始できます。Claude が PNG を視覚で読み取り、`question_text`・`options`・`case_text`・`explanation`・`keywords` をすべて追記します。

#### 4. マージ・正規化・検証

```powershell
.venv\Scripts\python.exe converter/merge_subject_json.py --dir tmp/35th --out data/json/35th/exam_35th.json
.venv\Scripts\python.exe converter/normalize_text.py data/json/35th/exam_35th.json
.venv\Scripts\python.exe converter/validate_quiz_json.py data/json/35th/exam_35th.json
```

---

## 共通: インポートと確認

### 5. AI 精査

`/check_explanations <対象ファイル/ディレクトリ>` で、解説文の事実確認と、原本 PDF との照合による誤字・欠落の修正を行います。完了したファイルは `data/json/ai_reviewed/` に移動します。

### 6. DB へインポート

```powershell
.venv\Scripts\python.exe converter/import_json.py
```

`data/json/ai_reviewed/` 配下の全 JSON を再帰的に走査し、`data/quiz.db` に書き込みます。人の確認は待ちません。

| DB の状態 | 処理 |
| --- | --- |
| 未登録 | INSERT（`is_reviewed` は JSON の値） |
| 登録済み・未確認（`is_reviewed = 0`） | JSON の内容で上書き（AI 精査のやり直しを反映できる） |
| 登録済み・確認済み（`is_reviewed = 1`） | 何もしない（人が確認した内容を守る） |

- 1 ファイルずつ commit してから `data/json/imported_to_db/` に移します。確認済みのために飛ばした問題を含むファイルも移します
- 移動先に同じ名前のファイルがあるときは、新しいほうに日時を付けて移します（前のファイルは消えません）
- 同じ ID が複数のファイルにあるときは、何も書き込まずに止めます
- 読めない JSON や、`id` のないレコードを含むファイルは、元の場所に残します
- 実行のたびに、JSON と DB の差分を `data/json/imported_to_db/log/import_log_{日時}.md` に出します（スキップした問題・上書きした問題の差分、新規登録の ID、警告）

### 7. アプリで確認

インポートされた問題は、未確認として入ります。

1. クイズ画面で問題を解くと、未確認の問題には「未確認」バッジが出ます
2. 内容に問題がなければ、解答後の「✓ 確認済みにする」を押します
3. 直す箇所があれば「✏️ 編集」でエディタを開いて直し、「確認済み」にチェックを入れて保存します

確認済みにした問題は、再インポートしても上書きされません。確認状態の正はインポート後は DB の `questions.is_reviewed` で、JSON の `is_reviewed` はインポート時に一度だけ読みます。

> `tools/quiz_editor.html` と `data/json/checked/` は、この流れでは使いません。

---

## converter/ 各スクリプトのリファレンス

| スクリプト | 役割 | 主な引数 |
| --- | --- | --- |
| `download_pdfs.py` | 過去問 PDF/HTML の自動ダウンロード | `--edition`（試験回、例: `38`） |
| `html_to_scaffold_json.py` | HTML + 正答 PDF → 科目別スキャフォールド JSON（第 36 回以降用） | `--html`, `--answers`, `--edition`, `--out` |
| `pdf_to_scaffold_json.py` | 問題 PDF（画像）+ 正答 PDF → PNG + 科目別スキャフォールド JSON（第 35 回以前用） | `--source-dir`, `--edition`, `--out`（省略可）, `--png-dir`（省略可）, `--scale`（省略可） |
| `merge_subject_json.py` | 科目別 JSON → 1 ファイルの最終 JSON（問題番号順にソート） | `--dir`, `--out` |
| `normalize_text.py` | 日本語の句読点・全角半角・スペーシングを自動補正 | JSON ファイルまたはフォルダ（複数可） |
| `validate_quiz_json.py` | スキーマ・ID 整合性・全角半角スペーシングを検証 | JSON ファイルパス（1 つ） |
| `import_json.py` | `data/json/ai_reviewed/` の問題を DB にインポート（未確認は上書き、確認済みはスキップ。差分をログに出力） | 引数なし（固定パスを走査） |

---

## `docs/dev/prompts/` の使い方

| ファイル | 用途 |
| --- | --- |
| [`pdf_to_json.md`](dev/prompts/pdf_to_json.md) | Claude Code 向けの本体プロンプト。JSON スキーマ・解説フォーマット・テキスト成形ルール・特殊ケースの扱いを定義。スキャフォールド JSON 生成後、この内容を Claude Code に渡して補完作業を依頼する |
| [`pdf_chat_instruction.txt`](dev/prompts/pdf_chat_instruction.txt) | パス B（PDF 画像）用の短い指示文。対象の PNG / JSON ディレクトリだけを差し替えて Claude Code に貼り付ける |

---

## つまずきやすいポイント

- **`normalize_text.py` の実行順序**: 必ず `merge_subject_json.py` の後、`validate_quiz_json.py` の前に実行してください。全角半角の補正が入る前に検証すると誤検知が出ます。
- **`validate_quiz_json.py` の警告**: `TODO` が残っている・正解番号が選択肢数の範囲外・全角半角スペース不足などを検出しますが、自動修正はしません。JSON を直接編集してから再実行してください。
- **`is_reviewed` は常に `false` で生成される**: Claude Code は `is_reviewed: false` のまま JSON を出力する仕様です（`pdf_to_json.md` に明記）。インポートすると DB 上で未確認になり、人がアプリで確認済みにします。
- **`import_json.py` は `data/json/ai_reviewed/` を見る**: AI 精査が終わっていない JSON（`dayNN/` など）は取り込まれません。
- **確認済みの問題は JSON を直しても反映されない**: 確認済みにした問題は再インポートで上書きされません。直したいときはアプリのエディタで直します。JSON との差分はインポートのログで確認できます。
- **DB を指定して実行する**: 環境変数 `QUIZ_DB_PATH` で、使う DB を変えられます（本番の DB を触らずに試したいとき）。実行時に使う DB のパスが表示されます。
- **カリキュラム判定**: `import_json.py` は `edition >= 37` を新カリキュラム（`new`）、それ以外を旧カリキュラム（`old`）として自動判定します。
