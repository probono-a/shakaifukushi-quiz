# quiz_editor.html 仕様書

## 概要

社会福祉士クイズの問題データ（JSON）をブラウザ上で閲覧・編集するためのシングルページアプリ。  
File System Access API を使用し、ローカルの JSON ファイルを直接上書き保存できる。

---

## ファイル操作

| 操作 | 手段 |
|------|------|
| ファイルを開く | 「📂 JSON ファイルを開く」ボタン（OS標準ダイアログ） |
| ドラッグ＆ドロップで開く | `.json` ファイルをウィンドウにドロップ（読み書き権限あり/なしで挙動が分岐） |
| 新規問題集を作成 | 「📝 新規問題集を作成」ボタン → 空の配列で `showSaveFilePicker` |
| 上書き保存 | FAB「💾 上書き保存」ボタン または `Ctrl+S` |

**D&D の権限挙動：**
- `getAsFileSystemHandle` が使える場合 → 読み書き権限を要求し、取得できれば完全編集可能
- フォールバック時（権限なし） → 読み取り専用で表示。保存ボタンは機能しない

---

## データ形式（JSONスキーマ）

ルート要素は **配列**。各要素は以下のフィールドを持つ。

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | string | 問題ID |
| `edition` | number | 回次（例: 37） |
| `subject` | string | 科目名 |
| `curriculum` | string | カリキュラム項目 |
| `question_number` | number | 問題番号 |
| `question_type` | string | `"通常"` or `"事例"` |
| `case_text` | string | 事例文（事例問題のみ） |
| `question_text` | string | 問題文 |
| `image_paths` | string[] | 画像パス一覧 |
| `options` | string[] | 選択肢テキスト（通常5件） |
| `correct_options` | number[] | 正答番号（1始まり）の配列 |
| `is_multiple_answers` | boolean | 複数正答フラグ（`correct_options.length > 1` で自動セット） |
| `explanation` | string | 解説文（Markdown） |
| `keywords` | string[] | キーワード一覧 |
| `reference_links` | string[] | 参考URL一覧 |
| `is_reviewed` | boolean | 校閲済みフラグ |

---

## UI レイアウト

```
┌──────────────────────────────────────┐
│          ヘッダー（タイトル）          │
│    [📂開く] [📝新規] [ファイル名表示] │
├──────────────────────────────────────┤  ← sticky
│  進捗バー: チェック済 N/M (%)          │
│  未入力あり: N 問  [次の未入力へ ↓]    │
├──────────────────────────────────────┤
│  問題カード × N                       │
│    ...                               │
│  [➕ 新しい問題を追加]                │
└──────────────────────────────────────┘
                          [💾 上書き保存]  ← FAB (fixed)
```

---

## 問題カードの構成

各問題カードは以下のセクションをこの順に表示する。

1. **ヘッダー行**
   - 第N回 / 科目名 / 問題番号 / 問題種別（セレクト）
   - チェック済トグル (`is_reviewed`)
   - ID
   - 削除ボタン

2. **カリキュラム行**
   - 📚 カリキュラム: （インライン編集）

3. **事例テキスト** (`case_text`) ← `contenteditable`

4. **問題文** (`question_text`) ← `contenteditable`

5. **画像パスセクション**（追加・削除可能、パス入力で画像プレビュー表示）

6. **選択肢** (`options`)
   - 番号部分をクリック → 正答トグル（緑色ハイライト）
   - `correct_options` と `is_multiple_answers` を自動更新

7. **解説セクション**（Markdownエディタ）
   - 「編集 (MD)」「プレビュー」タブで切り替え
   - プレビューはシンプルな自前 Markdown レンダラー

8. **キーワード・参考リンクセクション**（追加・削除可能）
   - キーワードはリアルタイムで Google 検索リンクとしてバッジ表示

---

## 進捗バー

画面上部に sticky 表示される。

- `is_reviewed === true` の問題数 / 全問数 をカウント
- **未入力判定** (`isIncomplete`)：以下のいずれかに該当する問題
  - `question_text` が空
  - `correct_options` が空
  - `explanation` が空
  - `options` に空要素がある
- 未入力問題のカードには黄色のボーダーを付与
- 「次の未入力へ ↓」ボタンで循環スクロール

---

## 編集操作まとめ

| 操作 | 手段 |
|---|---|
| テキスト編集 | `contenteditable` 要素を直接クリック |
| 正答切り替え | 選択肢の番号バッジをクリック（トグル） |
| 問題種別変更 | セレクトボックスで `通常` / `事例` を切り替え |
| 解説編集 | Markdown テキストエリアに入力 |
| 解説プレビュー | 「プレビュー」タブをクリック |
| 配列要素追加 | `+ 追加` ボタン |
| 配列要素削除 | `×` ボタン |
| 問題削除 | 🗑️ ボタン（確認ダイアログあり） |
| 問題追加 | ページ末尾「➕ 新しい問題を追加」ボタン |
| 保存 | FAB または `Ctrl+S` |

---

## Markdown レンダラー仕様

`explanation` フィールド向けの軽量自前実装。

| 記法 | 出力 |
|---|---|
| `# ` / `## ` / `### ` | `<h2>` / `<h3>` / `<h4>` |
| `- ` / `* ` | `<ul><li>` |
| `1. ` | `<ol><li>` |
| `**text**` | `<strong>` |
| `*text*` | `<em>` |
| `` `code` `` | `<code>` |
| `[text](url)` | `<a target="_blank">` |
| 空行 | `<br>` |

---

## 技術スタック

- 純粋な HTML + CSS + Vanilla JS（フレームワーク・ライブラリなし）
- **File System Access API**（`showOpenFilePicker` / `showSaveFilePicker` / `createWritable`）
- ブラウザ要件：Chrome / Edge 最新版推奨（File System Access API 必須）
