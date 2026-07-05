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
        ↓ tools/quiz_editor.html でレビュー → data/json/checked/ へ移動  ← 人間が実行
        ↓ [import_json.py]                  ← 人間が実行
data/quiz.db


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
        ↓ tools/quiz_editor.html でレビュー → data/json/checked/ へ移動  ← 人間が実行
        ↓ [import_json.py]                  ← 人間が実行
data/quiz.db
```

> OCR 済み PDF（`*_ocr.pdf`）は文字化けが多いため、原本 PDF を必ず使用してください。

---

## 回号別の手順

### 第 36 回以降（HTML 形式）

#### 1. ダウンロード

```powershell
uv run python converter/download_pdfs.py --edition 38
```

社会福祉振興・試験センターから、音声読み上げ用 HTML（`listen_s*_am/pm_NN.html`）と正答 PDF（`s_kijun_seitou_NN.pdf`）を `data/pdf/38th/` に取得します。

#### 2. スキャフォールド JSON を生成

```powershell
uv run python converter/html_to_scaffold_json.py `
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
uv run python converter/merge_subject_json.py --dir tmp/38_am --out data/json/38th/listen_ss_am_38.json
uv run python converter/normalize_text.py data/json/38th/listen_ss_am_38.json
uv run python converter/validate_quiz_json.py data/json/38th/listen_ss_am_38.json
```

`validate_quiz_json.py` が警告を出した場合は、該当箇所を JSON 内で直接修正してから次に進みます。

---

### 第 35 回以前（PDF 画像形式）

#### 1. ダウンロード

```powershell
uv run python converter/download_pdfs.py --edition 35
```

日本ソーシャルワーク教育学校連盟から、問題 PDF・正答 PDF を `data/pdf/35th/` に取得します（回によっては手動配置が必要な場合があります）。

#### 2. スキャフォールド JSON + PNG を生成

```powershell
uv run python converter/pdf_to_scaffold_json.py --source-dir data/pdf/35th --edition 35
```

`--source-dir` 内の PDF を自動検出します（正答 PDF はファイル名に `seitou` または `answer` を含むもの）。`--out` / `--png-dir` を省略すると `tmp/{edition}th` / `scratch/{edition}th` が使われます。`--scale`（デフォルト 2.0 = 144DPI）で PNG 解像度を調整できます。

`tmp/35th/` に科目別 JSON（`correct_options` のみ、テキストは TODO）、`scratch/35th/` に全ページ PNG が出力されます。

#### 3. Claude Code でテキスト・解説・キーワードを補完

Claude Code を起動し、[`docs/dev/prompts/pdf_to_json.md`](dev/prompts/pdf_to_json.md) の指示（パス B）に従います。[`docs/dev/prompts/pdf_chat_instruction.txt`](dev/prompts/pdf_chat_instruction.txt) の文面をそのまま貼り付けると、対象の PNG / JSON ディレクトリを指定した状態で指示を開始できます。Claude が PNG を視覚で読み取り、`question_text`・`options`・`case_text`・`explanation`・`keywords` をすべて追記します。

#### 4. マージ・正規化・検証

```powershell
uv run python converter/merge_subject_json.py --dir tmp/35th --out data/json/35th/exam_35th.json
uv run python converter/normalize_text.py data/json/35th/exam_35th.json
uv run python converter/validate_quiz_json.py data/json/35th/exam_35th.json
```

---

## 共通: レビューとインポート

### 5. `tools/quiz_editor.html` でレビュー

`tools/quiz_editor.html` を Chrome または Edge で直接開きます（File System Access API を使用するため、この 2 ブラウザのみ対応）。

1. 「📂 JSON ファイルを開く」から `data/json/{edition}th/{file}.json` を選択します。
2. 各問題の内容（問題文・選択肢・正解・解説・キーワード）を目視で確認し、必要であればその場で編集します（テキストはクリックして編集、配列要素の追加・削除も可能）。
3. 確認済みの問題は「未チェック／チェック済」トグルで `is_reviewed: true` に切り替えます。
4. `Ctrl+S`（または「💾 上書き保存」ボタン）で、開いている JSON ファイルに直接上書き保存します。

レビューが完了したファイルは `data/json/checked/` 配下に移動してください（`import_json.py` はこのフォルダのみを走査します）。

### 6. DB へインポート

```powershell
uv run python converter/import_json.py
```

`data/json/checked/` 配下の全 JSON を再帰的に走査し、`is_reviewed: true` の問題のみを `data/quiz.db` に書き込みます（`is_reviewed: false` の問題はスキップされます）。ID（`{edition}_{question_number}`）が既存レコードと重複する場合は上書きされるため、同じファイルを再インポートしても安全です。

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
| `import_json.py` | `data/json/checked/` の `is_reviewed: true` な問題を DB にインポート | 引数なし（固定パスを走査） |

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
- **`is_reviewed` は常に `false` で生成される**: Claude Code は `is_reviewed: false` のまま JSON を出力する仕様です（`pdf_to_json.md` に明記）。人間が `tools/quiz_editor.html` で内容を確認してから `true` に切り替えてください。
- **`import_json.py` は `data/json/checked/` しか見ない**: レビューが終わった JSON を移動し忘れると、いつまでも DB に反映されません。
- **カリキュラム判定**: `import_json.py` は `edition >= 37` を新カリキュラム（`new`）、それ以外を旧カリキュラム（`old`）として自動判定します。
