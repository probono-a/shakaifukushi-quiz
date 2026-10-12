# 実装計画: 解く時間を計るかどうかを、セッションの初めに選べるようにする (Issue #3)

## 目的

じっくり解くときは、時間を計る意味がない。
計った値が入ると、ダッシュボードの平均の解答時間 (と、それを使う試験時間の見込み) がゆがむ。
そこで、セッションの初めに時間を計るかどうかを選べるようにし、計らないときは解答時間を記録しない。

## 今回やること・やらないこと

やること:

- クイズのセットアップ画面に「時間を計る」のチェックを足す
- URL から始めるセッションでも選べるようにする (下の「決めること」)
- 計らないときは、解答履歴の `time_sec` を `null` で送る
- セッションの `config` に、計ったかどうかを残す

やらないこと (必要になったら別 Issue にする):

- 解いている途中で、計る・計らないを切り替えること
- 選んだ値を次のセッションに引き継ぐこと (`localStorage` に覚えるなど)
- 画面に経過時間を出すこと (今も出していない)
- これまでの解答履歴の `time_sec` を直すこと

## 決めること

URL から始めるセッションは、セットアップ画面を通らない。
問題を指定する URL (`quiz.html?ids=...`) と、ダッシュボードのおすすめカード (`quiz.html?mode=...`) がこれにあたる。
ここでどう選ぶかを決める。

案 A (おすすめ): URL に `timed=0` があれば計らない。なければ今までどおり計る

- 今までの URL の動きが変わらない
- 問題を指定する URL は、作るときに付けるかを決められる

案 B: URL から始めるときも、始める前に「時間を計りますか」と聞く

- 毎回 1 クリック増えるので、おすすめしない

## 1. バックエンド

直すところは無い見込み。

- `POST /api/history` の `time_sec` は、もとから `float | None` で `null` を受け取れる ([routers/history.py](../../../routers/history.py))
- ダッシュボードの平均 (全体・科目別) は SQL の `AVG(time_sec)` なので、`null` の行は平均から外れる ([routers/stats.py](../../../routers/stats.py))
- セッションの `config` は `dict` をそのまま JSON で保存するので、`timed` を足しても API は変わらない ([routers/sessions.py](../../../routers/sessions.py))

## 2. クイズ画面

対象: [static/quiz.html](../../../static/quiz.html)、[static/js/quiz.js](../../../static/js/quiz.js)

### セットアップ画面

- 「フィルター (任意)」の下に、項目を 1 つ足す
  - 「⏱️ 解く時間を計る」のチェックボックス (`id="opt-timed"`)
  - 初期値はオン (今までどおり)
  - 下に 1 行の説明: 「じっくり解くときはオフに。オフのときは、平均の解答時間に入りません」
- どのモードでも出す (`updateSetupOptions()` では隠さない)

### セッションの開始

- `startSession()` で、`config.timed` に計るかどうか (`true` / `false`) を入れる
  - セットアップ画面から: チェックボックスの値
  - URL から: `timed=0` なら `false`、それ以外は `true` (案 A の場合)
- `config` はセッション作成の `POST /api/sessions` にそのまま送られるので、記録に残る
- 0 問で戻ったときに前の `config` が残る件 (#12) とは別に扱う。今回は `timed` もほかの項目と同じ扱いにする

### 解答の記録

- `judgeAnswer()` で、`state.config.timed === false` なら `time_sec` を `null` にする
  - `undefined` (今までのセッション) は計るとみなす
- 問題の表示時刻 (`state.questionStartTime`) は、計らないときもそのまま取る (使わないだけ)

## 3. ドキュメント

- [README.md](../../../README.md): 画面の使い方に「時間を計る」の選択と、URL の `timed=0` を足す
- [CHANGELOG.md](../../../CHANGELOG.md): 追記する
- [CLAUDE.md](../../../CLAUDE.md): `history` の `time_sec` の説明に「計らないセッションでは `null`」を足す

## 4. テスト

### 自動テスト

フロントの変更が中心で、JS のテストの仕組みは無い。バックエンドの動きを押さえるテストを足す。

`tests/test_history_api.py` (新規):

| テスト | 確かめること |
|---|---|
| `time_sec` が `null` | `POST /api/history` に `time_sec: null` を送ると、`null` のまま保存される |
| 平均から外れる | `time_sec` が 10・20・`null` の 3 件で、`GET /api/stats` の平均が 15.0 になる (科目別も同じ) |
| すべて `null` | 平均が `null` になり、エラーにならない |

### 画面の確認 (手動)

DB のコピー (`QUIZ_DB_PATH`) で起動して確かめる。

- セットアップ画面: チェックが出る。初期値はオン
- オンで解く: 履歴に `time_sec` が入る
- オフで解く: 履歴の `time_sec` が `null`。セッションの `config` に `"timed": false`
- URL `?ids=...&timed=0`: `time_sec` が `null`
- URL `?ids=...` (`timed` なし): 今までどおり `time_sec` が入る
- ダッシュボード: 平均の解答時間・試験時間の見込みが、計った分だけで出る
