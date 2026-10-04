# 実装計画: 未確認の問題も DB に入れ、アプリで確認する (Issue #6)

## 目的

AI 精査 (`/check_explanations`) が終わった問題を、人の確認を待たずに DB に入れて、アプリで解けるようにする。
人の確認はアプリ上で行う。

- AI 精査でも誤りが残ることがあるので、未確認の問題はアプリで分かるようにする
- 人が確認・修正した内容は DB にだけ残る。確認済みにした問題は、再インポートで消えないようにする
  - 確認済みにせずエディタで直した内容は、再インポートで JSON の内容に戻る (しかたないものとする。差分はインポートのログに残る)

## パイプラインの変化

変更前:

```
check_explanations → ai_reviewed/ → quiz_editor で目視 → checked/ → import_json.py → imported_to_db/
```

変更後:

```
check_explanations → ai_reviewed/ → import_json.py → imported_to_db/
                                         ↓
                                  アプリで解きながら確認・修正し、確認済みにする
```

- `checked/` フォルダと、`tools/quiz_editor.html` でのレビュー手順は使わなくなる
- 確認状態の正は、インポート後は DB の `questions.is_reviewed` になる (JSON の `is_reviewed` はインポート時に一度だけ読む)

## 方針

- DB 上で確認済み (`is_reviewed = 1`) の問題は、インポート時に上書きしない
- DB 上で未確認の問題は、JSON の内容で上書きする (AI 精査のやり直しを反映できるように)
- インポートのたびに、ログファイルを出力する
  - 上書きしなかった問題と上書きした問題について、JSON と DB の差分をレポートとして出す

## 0. DB のパスと初期化を db.py にまとめる

対象: [db.py](../../../db.py)、[main.py](../../../main.py)、[converter/import_json.py](../../../converter/import_json.py)

### DB のパスを環境変数で渡せるようにする

自動テストと手動確認で、本番の `data/quiz.db` を使わずに済むようにする。

- `db.py` に、DB のパスを返す関数 (`get_db_path()`) を作る
  - 環境変数 `QUIZ_DB_PATH` があればそのパスを、なければ今と同じ `data/quiz.db` を返す
  - 空の文字列は、設定されていないものとして扱う
  - 相対パスは、実行したフォルダではなく、プロジェクトのルートを基準に絶対パスにする
  - 呼ばれるたびに環境変数を読む (読み込んだ時点の値で固定しない)
- 環境変数を読むのは `db.py` の 1 か所だけにする
  - `get_db()`、`main.py`、`import_json.py` は、どれも `get_db_path()` でパスを決める
- `main.py` の `from db import DB_PATH` をやめる
  - 今は読み込んだ時点の値をコピーして持っているので、あとから環境変数を変えても効かないため
- アプリの起動時とインポートの実行時に、使う DB のパスを表示する
  - `sqlite3.connect` は、ファイルがないと空の DB を黙って作る。パスを打ち間違えたときに気づけるように

環境変数は手動確認にも使う。
本番 DB のコピーを指定してアプリを起動すれば、確認状態を切り替える操作を本番 DB を汚さずに試せる。

```bash
cp data/quiz.db data/quiz_test.db
QUIZ_DB_PATH=data/quiz_test.db .venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000
```

(PowerShell では `$env:QUIZ_DB_PATH = "data/quiz_test.db"` を先に実行する。そのウィンドウを閉じるまで設定が残るので、本番 DB に戻すときは `Remove-Item Env:QUIZ_DB_PATH` する)

`data/*.db` は `.gitignore` に入っているので、`quiz_test.db` もコミットされない。

### DB の初期化を 1 つの関数にまとめる

今はテーブルを作る処理と移行処理が `main.py` (`_init_db()`) と `import_json.py` (`init_db()`) の 2 か所にあり、すでに中身がずれている。

- `history.time_sec` の移行は `main.py` にしかない
- `subject_mapping` の初期データは `import_json.py` にしかない

これを `db.py` の `init_db(conn)` 1 つにまとめ、`main.py` と `import_json.py` の両方から呼ぶ。

- 中身は、今の 2 か所を合わせたもの (テーブル作成、`history` の移行、`subject_mapping` の初期データ) と、1 で足す移行
- DB の親フォルダがなければ作る (今は `import_json.py` だけが作っている)
- `init_db()` は最後に自分で commit してから戻る (呼び出し側の rollback に巻き込まれないように)
- `import_json.py` は `converter/` から直接実行するスクリプトなので、先頭でプロジェクトのルートを `sys.path` に足してから `db` を読み込む

## 1. DB に確認状態の列を足す

対象: [db.py](../../../db.py) の `init_db()`

- `questions` に `is_reviewed INTEGER NOT NULL DEFAULT 0` を足す
  - `PRAGMA table_info(questions)` に `is_reviewed` がないときだけ `ALTER TABLE ... ADD COLUMN` する (既存の `history` の移行と同じ書き方)
  - 列を足した直後に一度だけ `UPDATE questions SET is_reviewed = 1` を実行する
  - 列の追加と `UPDATE` は、明示した `BEGIN` 〜 `COMMIT` で囲む
    - Python の sqlite3 は、既定では `ALTER TABLE` をその場で確定させる。囲まないと、`UPDATE` の確定前に落ちたとき列だけが残る
    - 次の起動では「列がある」と判断されて `UPDATE` が二度と走らず、確認済みの 283 問がすべて未確認に見えてしまう
  - いま DB にある問題は、すべて人が確認したうえで入れたものなので
  - 2026-10-05 に確かめた: `imported_to_db/` の JSON は 283 問すべて `is_reviewed: true` で、DB の 283 問と ID が過不足なく一致した
- `CREATE TABLE IF NOT EXISTS questions` の定義にも `is_reviewed` を足す (新規 DB 用)

## 2. インポートを変える

対象: [converter/import_json.py](../../../converter/import_json.py)

### 読み込み元と振り分け

- 読み込み元を `data/json/checked/` から `data/json/ai_reviewed/` に変える
  - `ai_reviewed/log/` には `.md` しかないので、`**/*.json` の走査に影響はない
- `is_reviewed: false` の問題も飛ばさずに入れる
- 処理が終わったファイルは、すべて `imported_to_db/` に移す
  - 確認済みのために飛ばした問題を含むファイルも移す。内容は DB 側が正なので
- JSON として読めないファイルは、今と同じく飛ばして元の場所に残す
- `id` がないレコードは入れずにログに出す。そのレコードを含むファイルは元の場所に残す

### ファイルごとに commit してから移す

今の `import_json.py` は、1 ファイルずつ `shutil.move` し、`conn.commit()` は全部のファイルが終わったあとに 1 回だけしている。
途中で失敗すると、ファイルは `imported_to_db/` に移ったのに DB には入っていない状態になる。

- 1 ファイル分を書き込んだら commit し、それからファイルを移す
- 1 ファイルの途中で失敗したら、そのファイル分を rollback し、ファイルは元の場所に残して、次のファイルへ進む
- commit のあとでファイルの移動に失敗したら (Windows でほかのアプリがファイルを開いているときなど)、警告に出して次のファイルへ進む
  - DB には入っているので、元の場所に残っても害はない (再インポートしても、未確認の行を同じ内容で上書きするだけ)
- ログは、途中で何が起きても最後に書き出す (`try`/`finally`)

### 移動先に同じ名前のファイルがあるとき

AI 精査をやり直したファイルを再インポートすると、`imported_to_db/` に同じ名前のファイルがある。
そのまま移すと、前のファイルが黙って消える。

- 移動先に同じ名前があるときは、新しいほうのファイル名の末尾に日時を付けて移す (例: `34th_14_相談援助の理論と方法_20261005-153000.json`)
  - 日時を付けた名前も使われていたら、さらに連番を付ける。移す前に、その名前が空いていることを必ず確かめる
  - Windows の `shutil.move` は、移動先に同じ名前があると黙って上書きすることがあるため
- ログにその旨を出す

### 1 問ごとの処理

| DB の状態 | 処理 | ログ |
|---|---|---|
| 未登録 | INSERT (`is_reviewed` は JSON の値) | ID の一覧 |
| 登録済み・未確認 | 上書き (`is_reviewed` は JSON の値) | 差分のある項目。差分がなければ ID の一覧 |
| 登録済み・確認済み | 何もしない | 差分のある項目 (JSON 側の内容を参考として出す)。差分がなければ ID の一覧 |

- 上書きは `INSERT OR REPLACE` をやめて `UPDATE` にする
  - `REPLACE` は行を消して入れ直すので、今後列が増えたときに JSON にない列の値が消えるため
- 書き込む前に、すべてのファイルの ID を調べる。同じ ID が 2 つのファイルにあれば、何も書き込まずに止め、重複を報告する
  - 「あとから読んだほうを入れる」は、先に入れたほうが確認済みになるとスキップされてしまい、確認済みは上書きしないルールとぶつかるため

### 差分の比べ方

比べる項目: `subject`、`question_type`、`case_text`、`question_text`、`options`、`correct_options`、`explanation`、`keywords`、`reference_links`、`image_paths`

比べない項目:

- `edition`、`question_number`: ID の一部なので変わらない
- `is_multiple`: `correct_options` から決まる値なので、`correct_options` の差分で分かる
  - しかも決め方が経路で違う (インポートは JSON の `is_multiple_answers`、エディタは `correct_options` の数)
- `curriculum`: インポートは回から計算した値を入れ、JSON の値は使っていないため

見た目だけの違いを差分にしない。

- `None` と空文字は同じとみなす (エディタは空欄を空文字で保存し、JSON は `null` のことがあるため)
- 文字列は前後の空白を取ってから比べる。リストは空の要素を除いてから比べる
  - エディタは保存するときに、前後の空白・末尾の空の選択肢・空のリンクとキーワードを落とすため (DB `35_1` の `reference_links` は `[]`、JSON は `[""]` だった)
- リスト系の項目は、DB に入れるときと同じ `json.dumps(..., ensure_ascii=False)` の形にしてから比べる

### ログファイル

- 出力先: `data/json/imported_to_db/log/import_log_{YYYY-MM-DD_HHMMSS}.md`
  - `/check_explanations` のログ (`ai_reviewed/log/`) と同じ形で、`data/` 以下なので git 管理外
  - 文字コードは `encoding="utf-8"` を明示する (Windows の既定は cp932 のため)
- コンソールの Import Summary は今のまま出し、最後にログファイルのパスを出す

ログの構成:

1. 実行日時、使った DB のパス、読み込んだファイル一覧
2. 集計: 新規登録・上書き・スキップ (確認済み) の件数
3. スキップした問題 (確認済み): 差分があるものは差分を、差分がないものは ID だけを出す
4. 上書きした問題: 差分があるものは差分を、差分がないものは ID だけを出す
5. 新規登録した問題の ID 一覧
6. 警告: 元の場所に残したファイル (読めない JSON、`id` のないレコード、途中で失敗、移動に失敗)、名前を変えて移したファイル

差分の書き方:

- 短い項目 (`subject`、`correct_options` など) は「DB の値 → JSON の値」を 1 行で出す
- 長い項目 (`explanation`、`question_text`、`case_text`、`options`) は `difflib.unified_diff` の結果を ```` ```diff ```` のコードブロックで出す

## 3. API を変える

対象: [routers/questions.py](../../../routers/questions.py)

- GET (`/api/questions`、`/api/questions/{id}`): `q.*` で取っているので `is_reviewed` はそのまま返る。追加の変更はない見込み (テストで確かめる)
- 確認状態だけを変える API を足す
  - `PATCH /api/questions/{id}/review`、本文は `{"is_reviewed": true}` または `false`
  - 存在しない ID は 404、`is_reviewed` が真偽値 (`true`/`false`) でないときは 422
  - `1` や `"true"` も受け付けないよう、`StrictBool` で受ける
  - クイズ画面のボタンから使う
- PUT (`/api/questions/{id}`): 本文に `is_reviewed` があるときだけ更新する
  - 本文は `dict` で受けているので、`isinstance(v, bool)` で確かめ、真偽値でなければ 422
  - ないときは今の値を保つ。古い画面からの保存で確認状態が消えないように
- POST (`/api/questions`): 本文の `is_reviewed` をそのまま入れる (PUT と同じく、真偽値でなければ 422)
  - エディタは常に送るので、送られなかったときの既定値は決めない (列の既定値 0 になる)

## 4. アプリの画面

### クイズ画面

対象: [static/js/quiz.js](../../../static/js/quiz.js)、[static/quiz.html](../../../static/quiz.html)、[static/css/style.css](../../../static/css/style.css)

- 未確認の問題に「未確認」バッジを出す (`renderQuestion()` のバッジ列。目立つ色にする)
- 解答後の解説欄に「確認済みにする」ボタンを置く
  - 今ある「✏️ 編集」ボタン (`fb-actions`、エディタを別タブで開く) の隣に並べる
  - 押したら `PATCH` を呼び、手元の問題データとバッジを更新する
  - 確認済みの問題には出さない
- エディタで確認状態を変えて保存したら、クイズ画面の「未確認」バッジと「確認済みにする」ボタンだけを新しくする
  - エディタは保存後にタブを閉じる前に、開いた元のクイズ画面 (`window.opener`、同じオリジン) の関数を呼び、問題の ID と `is_reviewed` を渡す
  - クイズ画面は、手元の問題データの `is_reviewed` を書き換え、表示中の問題ならバッジとボタンだけを描き直す
  - `renderQuestion()` は呼ばない (解答の状態が「未解答」に戻り、解答履歴が二重に記録されるため)
- 問題文・解説など、中身の表示を新しくする仕組みは入れない
  - 表示が古いままなのは今も同じで、この Issue とは関係がないため
  - 入れるには、解説を描く処理と解答履歴を記録する処理 (`judgeAnswer()`) を分ける必要がある。別 Issue (#7) で扱う

### エディタ

対象: [static/editor.html](../../../static/editor.html)、[static/js/editor.js](../../../static/js/editor.js)

- 「確認済み」のチェックボックスを足し、保存時に PUT・POST の本文で常に送る
  - 既存の問題を開いたときは DB の値を表示する
  - 新規作成ではチェック済みを初期値にする。続けて新規作成するとき (`resetForm()`) もチェック済みに戻す

## 4.5. 古いインポートスクリプトを消す

対象: `tools/import_quiz.py`

- `import_json.py` の前身にあたる古い版で、`is_reviewed` を見ずに `INSERT OR REPLACE` で全部入れる
- 今回の変更のあとに使うと、確認済みの問題を黙って上書きし、確認済みの印も 0 に戻してしまう
- 最初のコミットから手が入っておらず、どこからも呼ばれていないので消す
- リポジトリ内のドキュメントに説明は残っていない (2026-10-05 に grep で確かめた)

## 5. ドキュメント

- [.claude/commands/import_to_db.md](../../../.claude/commands/import_to_db.md): 読み込み元を `ai_reviewed/` に変え、ログファイルの場所と、スキップした差分の報告を足す
- [.claude/commands/check_explanations.md](../../../.claude/commands/check_explanations.md): 「人間による最終チェック・DB 登録の前段」の説明、`data/json/checked/` に触れている箇所、ログの「次のステップ」の案内を、新しい流れに合わせる
- [CLAUDE.md](../../../CLAUDE.md)
  - 「ディレクトリ構成」に `tests/` を足す
  - データパイプラインの手順 6・7 と、その下の段落 (`checked/` を通る流れの説明) を書き換える
  - `questions` テーブルの説明に `is_reviewed` を足す
  - 「コマンド」に、テストの実行方法と `QUIZ_DB_PATH` を足す。「lint・テストコマンドは存在しない」を書き換える
- [docs/data-pipeline.md](../../data-pipeline.md): 流れの図、quiz_editor の節、`import_json.py` の説明、注意事項を書き換える
- [docs/dev/prompts/pdf_to_json.md](../prompts/pdf_to_json.md): 人の最終確認を quiz_editor で行う、という記述を直す
- [README.md](../../../README.md)
  - 「API エンドポイント一覧」に `PATCH /api/questions/{id}/review` を足す
  - プロジェクト構成の `quiz_editor.html` の説明 (JSON 確認・修正 GUI) を直す
  - 残すか消すかは「決めていないこと」の結論に合わせる
- [CHANGELOG.md](../../../CHANGELOG.md): 追記する
- `data/json/import-checklist-2026-08.md` (git 管理外): 作業手順の行を新しい流れに合わせる
- Claude のメモリ `project_data_status.md` (リポジトリ外): `checked/` を通る流れを前提にした記述を直す

`.claude/` は `.gitignore` に入っているので、`.claude/commands/` の変更はコミットされない (手元でだけ反映される)。

## 6. テスト

このリポジトリで初めて自動テストを入れる。
インポートは、間違えると人が確認した内容を黙って上書きしてしまうので、条件の組み合わせを自動テストで押さえる。
画面は手動で確認する。

### テストの仕組み

- `pytest` と `httpx` (FastAPI の `TestClient` が使う) を `requirements-dev.txt` に入れる
  - アプリを使うだけの人の `setup.bat` には入れない
  - 入れ方: `uv pip install -r requirements-dev.txt`
  - `setup.bat` は `uv venv` で環境を作るので、`.venv` に pip は入っていない
- `pytest.ini` を置き、`pythonpath = .` と `testpaths = tests` を指定する
  - どのフォルダから実行しても、`db`・`main`・`converter` を読み込めるように
  - `converter/` には `__init__.py` がないので、テストからは `converter/import_json.py` を `importlib` で読み込むか、`__init__.py` を足す (実装時に決める)
- 実行: `.venv\Scripts\python.exe -m pytest`
- テストは `tests/` に置く

### テスト用 DB

自動テストは、テストごとに pytest の一時フォルダ (`tmp_path`) に作る DB と JSON で行う。
本番の `data/quiz.db` と `data/json/` には触らない。

- `tests/conftest.py` に、すべてのテストで自動的に効く fixture (`autouse=True`) を置く
  - `monkeypatch.setenv("QUIZ_DB_PATH", ...)` で一時フォルダの DB を指す
  - `get_db_path()` が返すパスが `tmp_path` の下にあることを assert し、本番 DB を誤って使わないようにする
- `import_json.py` は、インポートの関数では読み込み元・移動先・ログのフォルダを必須の引数にする
  - 今と同じ固定パスを決めるのは、コマンドとして実行したとき (`if __name__ == "__main__":`) だけにする
  - テストで引数を渡し忘れても、本番の `data/json/` を動かさないように (引数がなければエラーになる)
  - DB のパスは引数にせず、`get_db_path()` で決める (関数を呼んだときに決める)
- API のテストでは `TestClient(app)` を `with` で使う
  - `with` を使わないと lifespan が走らず、`init_db()` が呼ばれないため

### 自動テスト

`tests/test_db.py`:

| テスト | 確かめること |
|---|---|
| パス: 環境変数なし | `data/quiz.db` の絶対パスになる |
| パス: 相対パス | プロジェクトのルートを基準にした絶対パスになる |
| 列の移行 | `is_reviewed` のない既存 DB で `init_db()` を呼ぶと、既存の問題がすべて 1 になる |
| 移行を 2 回 | 2 回目の `init_db()` で、0 に戻した問題が 1 に戻されない (UPDATE が 1 回しか走らない) |
| 移行の途中で失敗 | 列の追加の直後に例外を起こすと列は残らず、もう一度 `init_db()` を呼ぶと全件 1 になる |
| パス: 空の文字列 | `QUIZ_DB_PATH=""` は、設定されていないときと同じ `data/quiz.db` になる |
| 新規 DB | 空の DB で `init_db()` を呼ぶと、全テーブルと `subject_mapping` の初期データができる |

`tests/test_import_json.py`:

| テスト | 確かめること |
|---|---|
| 新規登録 | 未登録の問題が、JSON の `is_reviewed` で入る (false なら 0、true なら 1) |
| 未確認の上書き | DB で未確認の問題は、JSON の内容で上書きされる。JSON が `is_reviewed: true` なら 1 になる |
| 確認済みのスキップ | DB で確認済みの問題は、JSON が違っていても DB が変わらない |
| ファイルの移動 | スキップした問題を含むファイルも含め、処理したファイルがすべて移動先に移る |
| 移動先に同名 | 前のファイルは残り、新しいファイルは日時付きの名前で移る |
| 壊れた JSON | 元の場所に残り、ほかのファイルは処理される |
| `id` のないレコード | 入らず、そのファイルは元の場所に残る |
| 途中で失敗 | そのファイル分は DB に入らず (rollback)、ファイルは元の場所に残り、次のファイルは処理される |
| 移動に失敗 | DB には入り、ファイルは元の場所に残り、ログに警告が出る |
| 同じ ID が 2 ファイル | 何も書き込まれず、ファイルも移らず、重複が報告される |
| コマンドとして実行 | 引数なしで実行すると、`QUIZ_DB_PATH` の DB に入る |
| ログ: スキップの差分 | 確認済みでスキップした問題のうち、差分のある項目だけがログに出る |
| ログ: 上書きの差分 | 上書きした問題の、変わった項目だけがログに出る |
| ログ: 差分なし | 差分がない問題は、スキップ・上書きそれぞれの ID の一覧にだけ出る |
| ログ: 見た目だけの違い | `None` と空文字、前後の空白、リストの空の要素、`is_multiple`・`curriculum` の違いは差分に出ない |
| ログ: 文字コード | ログを `utf-8` で読み直すと、日本語が正しく読める |

`tests/test_questions_api.py`:

| テスト | 確かめること |
|---|---|
| GET (1 問) | `/api/questions/{id}` の結果に `is_reviewed` が入っている |
| GET (一覧) | `/api/questions` の結果にも `is_reviewed` が入っている |
| PATCH | `/api/questions/{id}/review` で 0 ↔ 1 が切り替わる |
| PATCH (異常) | 存在しない ID は 404。`is_reviewed` が `1`・`"true"`・なしの本文は 422 |
| PUT (`is_reviewed` なし) | 確認済みの問題も未確認の問題も、確認状態が保たれる |
| PUT (`is_reviewed` あり) | 確認状態が更新される |
| PUT (異常) | `is_reviewed` が `"false"` などの真偽値でない値なら 422 |
| POST | 本文の `is_reviewed` のとおりに登録される。真偽値でない値なら 422 |

### 手動確認

画面 (`QUIZ_DB_PATH` で本番 DB のコピーを指定して起動する):

- [x] 起動時に、使う DB のパス (`quiz_test.db`) が表示される
- [x] 未確認の問題に「未確認」バッジが出る。確認済みの問題には出ない
- [x] 解答後に「確認済みにする」を押すと、バッジが消え、ボタンも消える
- [x] 画面を再読み込みしても確認済みのまま (DB に保存されている)
- [x] エディタで既存の問題を開くと、確認状態がチェックボックスに出る
- [x] エディタでチェックを外して保存すると、クイズ画面で未確認に戻る
- [x] クイズ画面から「✏️ 編集」でエディタを開き、確認状態を変えて保存すると、クイズ画面に戻ったときにバッジとボタンが新しくなっている。解答済みの状態はそのまま
- [x] エディタで新規作成すると、チェック済みが初期値になる

本番データでの確認 (DB をバックアップしてから):

- [x] アプリを起動すると移行が走り、既存の問題がすべて確認済みになる (未確認バッジが出ない)
- [x] `ai_reviewed/` の Day 4 の 2 ファイル (`34th_14`、`34th_15`) をインポートすると、未確認として入る
- [x] ログファイルが `imported_to_db/log/` にでき、新規登録の件数と ID が合っている

## 進め方

1. ブランチ `feature/issue6-unreviewed-import` を切る
2. 実行前に `data/quiz.db` をバックアップする (`data/quiz-bak-YYYYMMDD.db`)
   - 拡張子を `.db` にして `.gitignore` の `data/*.db` に当てはまるようにする。`quiz.db.bak-...` だと当てはまらず、コミットされる恐れがある
   - 実装中は、本番 DB でアプリを起動しない (`run.bat` は `--reload` なので、`db.py` を保存した時点で本番 DB の移行が走る)。画面を見るときは `QUIZ_DB_PATH` でコピーを使う
3. テストの仕組み (`requirements-dev.txt`、`pytest.ini`、`tests/conftest.py`) を作る
4. 0 → 1 → 2 → 3 の順に、自動テストを書きながら実装する
5. 4 (画面) を実装し、手動確認のチェックリストを通す
6. 4.5 (`tools/import_quiz.py` の削除) と 5 (ドキュメント) を行う
7. 本番データでの確認をする

## 決めていないこと

- `tools/quiz_editor.html` と `data/json/checked/` を残すか消すか
  - 新しい流れでは使わない。消すなら README のプロジェクト構成も直す
- 「未確認の問題だけを出題する」モードと、ダッシュボードの未確認の問題数 (Issue の範囲外)
  - 確認を早く進めるには役立つ。入れるなら別 Issue にする
