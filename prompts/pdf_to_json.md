# 社会福祉士国家試験 データ抽出プロトコル (v5.2 — Claude Code 向け)

このプロンプトは、スキャフォールド生成済みの `tmp/` 配下 JSON へのデータ追記作業の指示です。

- **パス A (HTML 源 / 第 36 回以降)**: `explanation` と `keywords` を追記する
- **パス B (画像 PDF 源 / 第 35 回以前)**: PNG を視覚で読み取り、`question_text`・`options`・`case_text`・`explanation`・`keywords` をすべて追記する

スキャフォールド生成 (ステップ 2) と後処理 (ステップ 4 以降) は人間が実行します。詳細は `README.md` を参照してください。

> **重要**: `is_reviewed` は **必ず `false` で出力**してください。人間による最終確認は `tools/quiz_editor.html` で行います。

---

## 0\. 基本方針

- AI が生成するデータは「下書き」です。構造が正確であることを最優先にしてください
- **一度に全問を扱わない**: 科目単位 (6〜9 問) に分けて処理する
- 不確実な箇所 (文字が読めない、選択肢が不明など) は推測せず `TODO:` コメントを残す
- **許可ダイアログを最小化する**: PowerShell (要許可) ではなく Read / Write ツール (自動許可) を優先使用する

---

## 1\. 全体フロー (参考)

### パス A: HTML 源 (第 36 回以降)

```
[html_to_scaffold_json.py]  ←  HTML + 正答 PDF          ← 人間が実行
        ↓ 自動 (テキスト正規化も自動適用)
tmp/{edition}_{file}/{科目}.json × N ファイル  (question_text・options 入り、explanation は TODO)
        ↓ Claude が科目ごとにパッチスクリプトを書いて実行    ← ここが Claude の担当
tmp/{edition}_{file}/{科目}.json × N ファイル  (explanation・keywords 追記済み)
        ↓
[merge_subject_json.py] → [normalize_text.py] → [validate_quiz_json.py]  ← 人間が実行
        ↓
data/json/{edition}th/{file}.json  (最終 JSON)
```

### パス B: 画像 PDF 源 (第 35 回以前)

```
[pdf_to_scaffold_json.py]  ←  問題 PDF + 正答 PDF        ← 人間が実行
        ↓ 自動
scratch/{png-dir}/p{NN}.png × 全ページ               (Claude 視覚読み取り用)
tmp/{edition}_{file}/{科目}.json × N ファイル  (correct_options のみ入り、テキストは TODO)
        ↓ Claude が科目ごとに PNG を読んでテキスト・解説パッチスクリプトを書いて実行  ← ここが Claude の担当
tmp/{edition}_{file}/{科目}.json × N ファイル  (explanation・keywords 追記済み)
        ↓
[merge_subject_json.py] → [normalize_text.py] → [validate_quiz_json.py]  ← 人間が実行
        ↓
data/json/{edition}th/{file}.json  (最終 JSON)
```

> **注意**: OCR 済み PDF (`*_ocr.pdf`) は文字化け多数のため、原本 PDF を必ず使用してください。

---

## 2\. パス A の作業 (解説・キーワード追記)

生成された科目別 JSON を Read ツールで確認し、Write ツールでパッチスクリプトを保存して PowerShell で実行します。1 科目あたり 1 回の PowerShell 許可で済みます。

```python
# scratch/patch_37_am_医学概論.py
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

PATH = 'tmp/37_am/01_医学概論.json'

def patch(data, qid, **kwargs):
    for q in data:
        if q['id'] == qid:
            q.update(kwargs)
            return
    raise KeyError(f'{qid} not found')

data = json.load(open(PATH, encoding='utf-8'))

patch(data, '37_1',
    explanation="""### × 1：...
...
### 〇 2：...
...これが**正解**です。
### 💡 試験対策のポイント
...""",
    keywords=['キーワード1', 'キーワード2'],
)
# 残りの問題も同様に ...

with open(PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print('done')
```

```powershell
.venv\Scripts\python scratch/patch_37_am_医学概論.py
```

---

## 3\. パス B の作業 (テキスト + 解説・キーワード追記)

1. Read ツールで対象科目の PNG を読む (1 科目分のページ数は 3〜5 枚程度)
2. Write ツールでパッチスクリプトを保存 (テキストと解説を **1 科目 1 スクリプト** にまとめる)
3. PowerShell で実行 (許可 1 回)

```python
# scratch/patch_35_common_医学概論.py
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

PATH = 'tmp/35_common/01_医学概論.json'

def patch(data, qid, **kwargs):
    for q in data:
        if q['id'] == qid:
            q.update(kwargs)
            return
    raise KeyError(f'{qid} not found')

data = json.load(open(PATH, encoding='utf-8'))

patch(data, '35_1',
    question_type='通常',
    case_text='',
    question_text='...',
    options=['...', '...', '...', '...', '...'],
    explanation="""### × 1：...
...
### 〇 2：...
...これが**正解**です。
### 💡 試験対策のポイント
...""",
    keywords=['キーワード1', 'キーワード2'],
)
# 残りの問題も同様に ...

with open(PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print('done: 01_医学概論')
```

```powershell
.venv\Scripts\python scratch/patch_35_common_医学概論.py
```

---

## 4\. JSON スキーマ

| フィールド | 型 | 説明 |
| :-- | :-- | :-- |
| `id` | string | `{edition}_{question_number}` 例: `"35_6"` |
| `edition` | integer | 試験回 例: `35` |
| `curriculum` | string | 37 以上 → `"new"`, 36 以下 → `"old"` |
| `subject` | string | 科目名 (ソースの表記を正確に) |
| `question_number` | integer | 問題番号 |
| `question_type` | string | `case_text` が空 → `"通常"`、非空 → `"事例"` |
| `case_text` | string | 事例文 (ない場合は `""`) |
| `question_text` | string | 問題文 (「問題 N」の接頭辞は削除) |
| `is_multiple_answers` | boolean | 正解が 2 つ以上 → `true` |
| `options` | array\[str\] | 選択肢 (先頭の番号は削除) |
| `correct_options` | array\[int\] | 正解番号 (1〜5) |
| `explanation` | string | 解説 Markdown (下記フォーマット参照) |
| `keywords` | array\[str\] | 重要語句 3〜5 個 |
| `reference_links` | array\[str\] | 参考 URL (デフォルト `[]`) |
| `image_paths` | array\[str\] | 画像パス (デフォルト `[]`) |
| `is_reviewed` | boolean | **必ず `false`** |

---

## 5\. 解説 (explanation) のフォーマット

```markdown
### × 1：選択肢の見出し (誤答)
なぜ誤りかの説明。重要語は**太字**。
### 〇 2：選択肢の見出し (正答)
なぜ正しいかの説明。これが**正解**です。
### × 3：選択肢の見出し (誤答)
...

(全選択肢を × / 〇 で記載)

### 💡 試験対策のポイント
試験でよく問われる観点や、混同しやすい類似概念の整理。
表 (Markdown) を使って比較すると効果的。
```

- 正答行は `### 〇 N：`、誤答行は `### × N：` で始める
- 複数正解 (`is_multiple_answers=true`) の場合は正答が複数 `〇` になる
- 最後は必ず `### 💡 試験対策のポイント` で締める

---

## 6\. テキスト成形ルール

> **適用タイミング**
> - **パス A**: `html_to_scaffold_json.py` が抽出時に自動適用する。パッチスクリプトで書く `explanation` / `keywords` は整形済みでなくてもよい。マージ後に `normalize_text.py` で一括補正される。
> - **パス B**: OCR 書き起こし時は整形を意識して書くが、確定は `normalize_text.py` に委ねてよい。

`normalize_text.py` は `question_text`・`case_text`・`explanation`・`options`・`keywords` の全フィールドに自動適用される。解説・キーワードを書くときは下記ガイドラインを守れば細かいスペーシングはスクリプトが補正する。

### `normalize_text.py` の自動補正一覧

| 規則 | 変換前の例 | 変換後 |
| :-- | :-- | :-- |
| ふりがな除去 | `誤嚥｛えん｝` | `誤嚥` |
| ノーブレークスペース → 通常スペース | `第\xa038回` | `第 38 回` |
| 全角括弧 → 半角 | `（注）` | `(注)` |
| 全角コロン → 半角 + 直後にスペース | `DSM-5：変更点` | `DSM-5: 変更点` |
| 連続する空白を１つに整理 | `第　38　回` | `第 38 回` |
| CJK・仮名 ↔ 半角英数字の間にスペース | `第38回` | `第 38 回` |
| 日本語閉じ括弧・CJK の後の `(` 前にスペース | `白書」(内閣府)に` | `白書」 (内閣府) に` |
| `)` の直後に CJK が来る場合にスペース | `(昭和38年)の` | `(昭和 38 年) の` |
| 一桁の半角数字 → 全角 | `第 1 号` | `第１号` |
| 全角数字と CJK の間のスペース除去 | `の５ つ` | `の５つ` |

**自動補正されない (意図的な例外):**

- `は、(` → そのまま (`、` U+3001 は補正対象の CJK 範囲外)
- `)、` `)。` → そのまま (同上)
- `DSM-5`・`pH7`・`B型` など英数字に挟まれた一桁数字は全角にしない
- URL 中の `://` は `:` の後にスペースを補わない

### 選択肢・問題文の抽出ルール

- 先頭の番号 (`1`, `(1)`, `①` など) を削除する
- 「問題 N　次の記述のうち〜」→「次の記述のうち〜」(番号部分を削除)
- 事例問題の `case_text` は「〔事　例〕」などの見出しを除去してテキストのみ格納する
- HTML の `（注）` 脚注は、対応する問題の `question_text` 末尾に `\n\n(注) ...` で追記する
- 不自然な改行 (PDF の行折り) は結合する

### 解説・キーワードを書くときのガイドライン

細かいスペーシングは normalize_text.py が補正するため、以下の点だけ守れば十分。

- **括弧は半角** `()` を使う (`（）` は自動補正されるが最初から半角が望ましい)
- **コロンは半角** `:` を使う。`### × 1:` `### 〇 2:` の形式では直後にスペースが自動挿入される
- **二桁以上の数字は半角**: `38年` → normalize 後 `38 年`、`1963年` → `1963 年`
- **一桁の数字はどちらでもよい**: `1つ` でも `１つ` でも normalize 後は `１つ` になる
- **Markdown の改行・見出し・箇条書きは保持される**: `\n` `###` `-` `*` `**` はそのまま通る
- **法律名・人名・略語は公式表記で書く**: `ICF`、`DSM-5`、`措置制度`、`ゴッフマン` など

### OCR 誤り (画像からの書き起こし時に注意)

- 見間違いやすいペア: `己/已`, `末/未`, `己/巳`, `土/士`, `目/日`
- 特に人名・法律名は公式表記を確認して書く (例: `ゴッフマン`, `DSM-5`, `ICF`)
- 「裁判所」「福祉事務所」等の固有名詞は正確に

---

## 7\. 特殊ケース

| ケース | 処理 |
| :-- | :-- |
| 事例問題 (複数問で共通事例) | 各問の `case_text` に事例文を重複して格納 |
| 不適切問題 (正答なし) | `correct_options: []`、`explanation` に「不適切問題」旨を記載 |
| 図表を含む問題 | `image_paths: ["{edition}_{qnum}.png"]` を仮設定し、`TODO: 画像のクロップが必要` を explanation に追記 |
| 問題文に選択肢が混入 (OCR 誤り) | 問題文と選択肢を正確に分離する |

---

## 8\. 完了時の報告

全科目のパッチ完了後、ユーザーに以下を伝えてください:

> `tmp/{edition}_{file}/` 配下の全科目 JSON に explanation・keywords を追記しました。ステップ 3 (マージ・正規化・検証) を実行してください。
