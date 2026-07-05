# 問題編集の一本化計画

## 背景・方針転換の経緯

当初は「ID指定編集（quiz.js の編集モーダル）」に AI 解説依頼文コピー機能を追加し、裏でクイズ画面が描画されてしまう不具合を個別に直す計画だった。

しかし、そもそも「新規問題入力（editor.html）」と「既存問題の編集（quiz.js の編集モーダル）」で似たようなフォームのコードが二重に存在しているのが根本の分かりにくさであり、両者を **editor.html に一本化** する方が良いという判断に至った。

editor.html はセッションやクイズ進行のロジックを一切持たない、ただのフォーム画面である。ID指定編集をこの画面で行うようにすれば、「裏でクイズ画面が動いてセッションが残ってしまう」問題は個別に直すまでもなく、構造的に発生しなくなる。AI 解説依頼文コピー機能も editor.html にしか実装しないため、統合すれば自動的に編集画面でも使えるようになる。

編集の呼び出し口は 2 か所ある。

1. **ダッシュボードの「ID で編集」欄** — 同じタブ内で遷移して問題ない（クイズの進行状態が存在しないため）。
2. **クイズ回答直後の「✏️ 編集」ボタン** — クイズのセッション状態（残り問題・現在の正答数・セッションID）が JS のメモリ上にしか無いため、そのままページ遷移すると失われてしまう。検討の結果、**editor.html を別タブで開く**方式を採用する。元のクイズタブは触らないため進行状態は無傷で、実装もシンプルになる。トレードオフとして、編集後に元のクイズタブのフィードバック表示（解説など）は自動更新されない（次にその問題が出題されたときには反映される）。

---

## 変更内容

### Task 1: `buildExplanationPrompt()` の共通化

**ファイル**: `static/js/markdown.js`（`editor.js` から移設）— 着手済み

AI 依頼文の組み立てロジックを `markdown.js` に共通化する。`editor.js` にある重複定義を削除し、共通関数を呼ぶだけにする。

### Task 2: `editor.html` / `editor.js` に「参考リンク」欄を追加

**ファイル**: `static/editor.html`, `static/js/editor.js`

現状の新規作成フォームには参考リンクの入力欄が無い。既存の quiz.js 編集モーダルには実装済みなので、そのまま移植する。

- `draft.reference_links = []` を状態に追加
- キーワード欄の下に「参考リンク」セクションを追加（URL 入力欄の追加・削除、`edit-link-row` / `edit-link-del-btn` / `edit-add-btn` は既存 CSS をそのまま流用）
- 保存時の body に `reference_links: draft.reference_links.filter(l => l.trim())` を含める（空欄のまま保存されるのを防ぐ）

これを先に対応しておかないと、後述の Task 4 で統合した瞬間に「参考リンク付きの問題を編集して保存したらリンクが消える」というデータ損失が起きる。

### Task 3: 科目プルダウンをカリキュラム連動にする（新規作成フォームの既存バグ修正）

**ファイル**: `routers/questions.py`, `static/js/editor.js`

現状の `editor.html` は、カリキュラムで「旧」を選んでも科目プルダウンが `GET /api/subjects`（新カリキュラムに統一された科目名）しか出さない。そのため今日時点でも、旧カリキュラムの過去問を新規登録すると、`curriculum='old'` のレコードに新カリキュラム名の `subject` が保存されてしまうという矛盾が起こり得る（Task 4 で編集機能を統合する前から存在する既存のギャップ）。ここで先に直しておく。

- **バックエンド**: `GET /api/subjects/old` を新設し、`subject_mapping` テーブルの `subject_old` 列（旧カリキュラムの生の科目名一覧）を返す。
  ```python
  @router.get("/subjects/old")
  def get_old_subjects():
      with get_db() as conn:
          rows = conn.execute(
              "SELECT DISTINCT subject_old FROM subject_mapping ORDER BY subject_old"
          ).fetchall()
      return [r["subject_old"] for r in rows]
  ```
  既存の `GET /api/subjects`（ダッシュボードの絞り込み・クイズ設定画面などが使う統一済みリスト）はそのまま変更しない。
- **フロントエンド**: `editor.js` で新カリ・旧カリそれぞれの科目リストを起動時に取得しておき、`f-curriculum` の値に応じて `f-subject` の選択肢を出し分ける（`change` イベントで再描画）。

### Task 4: `editor.html` に編集モードを追加

**ファイル**: `static/editor.html`, `static/js/editor.js`

`editor.html?id=38_1` のように `id` パラメータ付きで開いた場合、新規作成ではなく既存問題の編集として動作させる。

- `DOMContentLoaded` で `id` パラメータを確認し、あれば `GET /api/questions/{id}` で取得してフォームに反映する
  - 回次・問題番号は ID を構成するため **編集不可（disabled）** にする
  - カリキュラムをまず反映してから Task 3 の仕組みで科目プルダウンを出し分け、**`subject_display`（表示用に変換された名前）ではなく DB に格納されている生の `subject` 値**を選択済みにする。これにより、科目を触らずに保存すれば元の値がそのまま書き戻され、勝手な変換は起きない
  - 問題タイプ・事例文・問題文・選択肢・正答・解説・キーワード・参考リンクも編集可能
- 見出し（カードタイトル・`<title>`）と保存ボタンの文言を「問題編集」「更新する」に切り替える
- 保存時は `POST /api/questions` の代わりに `PUT /api/questions/{id}` を呼ぶ
- 保存成功後の挙動を編集モード用に変える（`resetForm()` は呼ばない）
  - トーストで「更新しました」と表示
  - `window.opener` があれば（＝別タブとして開かれた＝クイズ画面からの遷移）少し待ってから `window.close()` で自動的にタブを閉じ、元のクイズタブに戻す
  - `window.opener` が無ければ（＝ダッシュボードから同じタブで遷移）`location.href = '/'` でダッシュボードに戻る

### Task 5: 呼び出し元を editor.html に向ける

**ファイル**: `static/js/dashboard.js`, `static/js/quiz.js`

- `dashboard.js`: 「ID で編集」フォームの遷移先を `/quiz.html?editId=...` → `/editor.html?id=...` に変更
- `quiz.js`: 回答直後の「✏️ 編集」ボタンのクリックハンドラを、モーダルを開く処理から `window.open(\`/editor.html?id=${encodeURIComponent(q.id)}\`, '_blank')` に変更

### Task 6: quiz.js / quiz.html の重複コードを削除

**ファイル**: `static/js/quiz.js`, `static/quiz.html`

editor.html への一本化に伴い、quiz.js 内の編集モーダル関連コードが丸ごと不要になるため削除する。

- `quiz.js`: `openEditModal` / `buildEditModalBody` / `attachEditModalListeners` / `closeEditModal` / `saveEdit` / `reRenderFeedback` / `refreshEditKeywords` / `refreshEditLinks` / `editDraft` 変数、および `DOMContentLoaded` 内の `editId` URL パラメータ分岐（`ids` パラメータの分岐は別機能なので残す）
- `quiz.html`: `#edit-modal` の HTML と、対応する `.edit-modal` 系のインライン `<style>` を削除（`.edit-input` などの汎用フォーム部品スタイルは `style.css` 側に残っており editor.html が使い続けるので、`style.css` 側は変更しない）

---

## 対象外（スコープ外）

- ダッシュボードにトースト機構を追加すること（同一タブ遷移後は特に確認メッセージなしでダッシュボードへ戻る）
- `tools/quiz_editor.html` の改修

---

## 実装順序

1. Task 1（`buildExplanationPrompt` の共通化）
2. Task 2（参考リンク欄の追加）— データ損失防止のため Task 4 より先に対応
3. Task 3（科目プルダウンのカリキュラム連動化）— Task 4 の前提となるため先に対応
4. Task 4（editor.html の編集モード対応）
5. Task 5（呼び出し元の切り替え）— Task 4 と合わせて動作確認
6. Task 6（quiz.js / quiz.html の重複コード削除）— 最後にまとめて掃除

---

## 完了条件

- `editor.html` が新規作成・既存編集の両方で使える（`?id=` の有無で自動切り替え）
- カリキュラム（新／旧）に応じて科目プルダウンの選択肢が切り替わり、既存レコードの `subject` を触らずに保存しても値が変換されない
- 編集モードでも AI 解説依頼文コピー・参考リンク編集が使える
- ダッシュボードの「ID で編集」から editor.html に遷移し、保存後はダッシュボードに戻る
- クイズ回答後の「✏️ 編集」は別タブで editor.html を開き、保存すると自動でタブが閉じてクイズに戻れる。クイズの進行状態（残り問題・正答数・セッション）は一切失われない
- quiz.js / quiz.html から編集モーダル関連の重複コードが無くなっている
