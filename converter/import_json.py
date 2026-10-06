"""data/json/ai_reviewed/ の JSON を data/quiz.db に取り込む。

- DB に未登録の問題は INSERT する
- DB で未確認 (is_reviewed = 0) の問題は、JSON の内容で UPDATE する
- DB で確認済み (is_reviewed = 1) の問題は、何もしない (人が確認した内容を守る)
- 要確認の印 (needs_check) と理由 (check_note) は、JSON に項目があるときだけ読む
  (項目のない JSON を入れ直しても、アプリで付けた印が消えないように)
- 1 ファイルずつ commit してから imported_to_db/ に移す
- 実行のたびに、JSON と DB の差分をログファイルに出す
"""
import difflib
import glob
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime

# プロジェクトルートを基準にパスを解決 (実行場所に依存しない)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from db import get_db_path, open_initialized_db  # noqa: E402

JSON_DIR = os.path.join(PROJECT_ROOT, "data", "json", "ai_reviewed")
IMPORTED_DIR = os.path.join(PROJECT_ROOT, "data", "json", "imported_to_db")
LOG_DIR = os.path.join(IMPORTED_DIR, "log")

# 差分を比べる項目 (edition・question_number・is_multiple・curriculum は比べない。理由は計画書を参照)
LIST_FIELDS = ("options", "correct_options", "keywords", "reference_links", "image_paths")
COMPARE_FIELDS = (
    "subject", "question_type", "case_text", "question_text", "options",
    "correct_options", "explanation", "keywords", "reference_links", "image_paths",
)
# ログに unified diff で出す長い項目
LONG_FIELDS = ("case_text", "question_text", "options", "explanation")
# JSON に項目があるときだけ読み、比べる項目 (要確認の印と理由)
CHECK_FIELDS = ("needs_check", "check_note")


def get_curriculum(edition):
    """回数からカリキュラム区分を判定"""
    # 第 37 回（2025 年 2 月）から新カリキュラム
    if edition >= 37:
        return "new"
    else:
        return "old"


def _norm_text(value):
    """None と空文字を同じにし、前後の空白を取る"""
    if value is None:
        return ""
    return str(value).strip()


def _norm_list(value):
    """None を空リストにし、空の要素を除く"""
    if value is None:
        return []
    if not isinstance(value, list):
        return [value]
    return [v for v in value if not (v is None or (isinstance(v, str) and not v.strip()))]


def _normalize(record):
    """比べる項目だけを、見た目の違いをならした形にして返す"""
    return {
        f: _norm_list(record.get(f)) if f in LIST_FIELDS else _norm_text(record.get(f))
        for f in COMPARE_FIELDS
    }


def _db_record(row):
    """DB の行 (dict) を、JSON と同じ形 (リスト項目は list) にする"""
    rec = dict(row)
    for f in LIST_FIELDS:
        raw = rec.get(f)
        try:
            rec[f] = json.loads(raw) if raw else []
        except (TypeError, ValueError):
            rec[f] = [raw]
    return rec


def _dumps(value):
    return json.dumps(value, ensure_ascii=False)


def normalize_check_note(value):
    """理由の前後の空白を取り、空なら None にする (API と同じ扱い)"""
    if value is None:
        return None
    return str(value).strip() or None


def _check_values(record):
    """要確認の印と理由を、DB に入れる形 (0 / 1、文字列か None) にして返す"""
    return {
        "needs_check": 1 if record.get("needs_check") else 0,
        "check_note": normalize_check_note(record.get("check_note")),
    }


def drop_bad_check_fields(items, name, warnings):
    """型の違う needs_check・check_note を読まないように、項目を除いたコピーを返す。

    API と同じく、needs_check は true / false、check_note は文字列か null だけを受け付ける。
    (例えば "false" という文字列を印ありとして入れないように)
    """
    out = []
    for item in items:
        bad = []
        if "needs_check" in item and not isinstance(item["needs_check"], bool):
            bad.append("needs_check")
        if "check_note" in item and not (item["check_note"] is None or isinstance(item["check_note"], str)):
            bad.append("check_note")
        if bad:
            item = {k: v for k, v in item.items() if k not in bad}
            warnings.append(f"{name}: {item['id']} の {'・'.join(bad)} は型が違うので読まなかった")
        out.append(item)
    return out


def compute_diff(db_row, item):
    """DB の行と JSON のレコードの差分を、項目名 → (DB 側, JSON 側) で返す。差分がなければ空

    要確認の印と理由は、JSON に項目があるときだけ比べる。
    """
    a = _normalize(_db_record(db_row))
    b = _normalize(item)
    diff = {f: (a[f], b[f]) for f in COMPARE_FIELDS if _dumps(a[f]) != _dumps(b[f])}
    db_check, json_check = _check_values(dict(db_row)), _check_values(item)
    for f in CHECK_FIELDS:
        if f in item and db_check[f] != json_check[f]:
            diff[f] = (db_check[f], json_check[f])
    return diff


def _lines(field, value):
    if field == "options":
        return [_dumps(v) for v in value]
    return str(value).splitlines()


def _short(field, value):
    if field in LIST_FIELDS:
        return _dumps(value)
    if field == "needs_check":
        return "あり" if value else "なし"
    return f"`{value}`" if value else "(空)"


def format_diff(diff):
    """compute_diff の結果をログ用の Markdown にする"""
    out = []
    for field, (old, new) in diff.items():
        if field in LONG_FIELDS:
            body = "\n".join(difflib.unified_diff(
                _lines(field, old), _lines(field, new), "DB", "JSON", lineterm="", n=1))
            out.append(f"- `{field}`\n\n```diff\n{body}\n```")
        else:
            out.append(f"- `{field}`: {_short(field, old)} → {_short(field, new)}")
    return "\n".join(out)


def _unique_dest(directory, name):
    """移動先で名前が空いていればそのまま、使われていれば日時 (と連番) を付けた名前を返す。

    Windows の shutil.move は、同名のファイルがあると黙って上書きすることがあるため、
    移す前に必ず空いていることを確かめる。
    """
    dest = os.path.join(directory, name)
    if not os.path.exists(dest):
        return dest, False
    stem, ext = os.path.splitext(name)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = os.path.join(directory, f"{stem}_{stamp}{ext}")
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{stem}_{stamp}_{n}{ext}")
        n += 1
    return candidate, True


def _write_values(item):
    return (
        item.get("edition"),
        item.get("subject"),
        item.get("question_number"),
        item.get("question_type"),
        item.get("case_text"),
        item.get("question_text"),
        1 if item.get("is_multiple_answers") else 0,
        json.dumps(item.get("options", []), ensure_ascii=False),
        json.dumps(item.get("correct_options", []), ensure_ascii=False),
        item.get("explanation"),
        json.dumps(item.get("keywords", []), ensure_ascii=False),
        json.dumps(item.get("reference_links", []), ensure_ascii=False),
        json.dumps(item.get("image_paths", []), ensure_ascii=False),
        get_curriculum(item.get("edition")),
        1 if item.get("is_reviewed") else 0,
    )


def _import_file(conn, items):
    """1 ファイル分の問題を書き込む (commit はしない)。

    inserted は ID のリスト、overwritten / skipped は (ID, 差分) のリストで返す。
    """
    res = {"inserted": [], "overwritten": [], "skipped": []}
    for item in items:
        qid = item["id"]
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
        values = _write_values(item)
        if row is None:
            conn.execute("""
                INSERT INTO questions (
                    id, edition, subject, question_number, question_type,
                    case_text, question_text, is_multiple, options,
                    correct_options, explanation, keywords, reference_links,
                    image_paths, curriculum, is_reviewed, needs_check, check_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (qid,) + values + tuple(_check_values(item).values()))
            res["inserted"].append(qid)
            continue
        diff = compute_diff(dict(row), item)
        if row["is_reviewed"]:
            res["skipped"].append((qid, diff))
            continue
        # REPLACE は行を消して入れ直すので、JSON にない列の値が消える。UPDATE を使う
        conn.execute("""
            UPDATE questions SET
                edition = ?, subject = ?, question_number = ?, question_type = ?,
                case_text = ?, question_text = ?, is_multiple = ?, options = ?,
                correct_options = ?, explanation = ?, keywords = ?, reference_links = ?,
                image_paths = ?, curriculum = ?, is_reviewed = ?
            WHERE id = ?
        """, values + (qid,))
        # 要確認の印と理由は、JSON に項目があるときだけ上書きする
        check = _check_values(item)
        for f in CHECK_FIELDS:
            if f in item:
                conn.execute(f"UPDATE questions SET {f} = ? WHERE id = ?", (check[f], qid))
        res["overwritten"].append((qid, diff))
    return res


def import_json_files(conn, json_dir, imported_dir, log_dir):
    """json_dir の JSON を DB に取り込み、処理したファイルを imported_dir に移す。

    ログは途中で何が起きても log_dir に書き出す。結果を dict で返す。
    inserted は ID のリスト、overwritten / skipped は (ファイル名, ID, 差分) のリスト。
    """
    conn.row_factory = sqlite3.Row  # 列名でアクセスできるようにする
    started = datetime.now()
    result = {
        "inserted": [], "overwritten": [], "skipped": [],
        "moved": [], "kept": [], "warnings": [], "duplicates": {}, "aborted": False,
        "log_path": None,
    }
    files = []
    try:
        _run_import(conn, json_dir, imported_dir, result, files)
    except BaseException as e:
        result["warnings"].append(f"予期しないエラーで中断: {type(e).__name__}: {e}")
        raise
    finally:
        result["log_path"] = _write_log(log_dir, started, files, result)
    return result


def _run_import(conn, json_dir, imported_dir, result, files):
    paths = sorted(glob.glob(os.path.join(json_dir, "**", "*.json"), recursive=True))
    files.extend(os.path.basename(p) for p in paths)

    # 1. すべてのファイルを読む (読めないファイルは飛ばして元の場所に残す)
    loaded = []  # (path, items)
    for path in paths:
        name = os.path.basename(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list) or not all(isinstance(i, dict) for i in data):
                raise ValueError("トップレベルが問題 (オブジェクト) のリストではない")
        except (ValueError, OSError) as e:  # JSONDecodeError は ValueError の一種
            msg = f"{name}: 読み込めないので飛ばした ({e})"
            print(f"Error: {msg}")
            result["warnings"].append(msg)
            result["kept"].append(name)
            continue
        loaded.append((path, data))

    # 2. 同じ ID が複数の場所にあれば、何も書き込まずに止める
    seen = {}
    for path, data in loaded:
        for item in data:
            if item.get("id"):
                seen.setdefault(item["id"], []).append(os.path.basename(path))
    result["duplicates"] = {k: v for k, v in seen.items() if len(v) > 1}
    if result["duplicates"]:
        result["aborted"] = True
        result["kept"].extend(os.path.basename(p) for p, _ in loaded)
        print("Error: 同じ ID が複数ある。何も書き込まずに中止した")
        return

    # 3. ファイルごとに書き込み → commit → 移動
    for path, data in loaded:
        name = os.path.basename(path)
        print(f"Processing: {path}")
        valid = [i for i in data if i.get("id")]
        missing = len(data) - len(valid)
        valid = drop_bad_check_fields(valid, name, result["warnings"])
        try:
            res = _import_file(conn, valid)
            conn.commit()
        except Exception as e:
            conn.rollback()
            msg = f"{name}: 途中で失敗したので、このファイル分は DB に入れていない ({type(e).__name__}: {e})"
            print(f"Error: {msg}")
            result["warnings"].append(msg)
            result["kept"].append(name)
            continue
        result["inserted"].extend(res["inserted"])
        for key in ("overwritten", "skipped"):
            result[key].extend((name, qid, diff) for qid, diff in res[key])
        if missing:
            msg = f"{name}: id のないレコードが {missing} 件あった (入れていない)。ファイルは元の場所に残した"
            print(f"Warning: {msg}")
            result["warnings"].append(msg)
            result["kept"].append(name)
            continue
        # ファイルハンドルは閉じてある (Windows では開いたままだと移動できない)
        try:
            os.makedirs(imported_dir, exist_ok=True)
            dest, renamed = _unique_dest(imported_dir, name)
            shutil.move(path, dest)
        except OSError as e:
            msg = f"{name}: DB には入れたが、移動に失敗した ({e})。元の場所に残した"
            print(f"Warning: {msg}")
            result["warnings"].append(msg)
            result["kept"].append(name)
            continue
        result["moved"].append(name)
        if renamed:
            result["warnings"].append(
                f"{name}: 移動先に同じ名前があったので、{os.path.basename(dest)} の名前で移した")


def _write_log(log_dir, started, files, result):
    ts = started.strftime("%Y-%m-%d_%H%M%S")
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, f"import_log_{ts}.md")
    n = 2
    while os.path.exists(path):
        path = os.path.join(log_dir, f"import_log_{ts}_{n}.md")
        n += 1

    out = [f"# インポートログ {started.strftime('%Y-%m-%d %H:%M:%S')}", ""]
    out += [f"- DB: `{get_db_path()}`", f"- 読み込んだファイル: {len(files)} 件"]
    out += [f"  - {name}" for name in files]
    if result["aborted"]:
        out += ["", "**同じ ID が複数の場所にあったので、何も書き込まずに中止した。**", ""]
        out += [f"- `{k}`: {', '.join(v)}" for k, v in result["duplicates"].items()]

    out += ["", "## 集計", "",
            f"- 新規登録: {len(result['inserted'])} 件",
            f"- 上書き (未確認だった問題): {len(result['overwritten'])} 件",
            f"- スキップ (確認済み): {len(result['skipped'])} 件"]

    def section(title, entries):
        out.extend(["", f"## {title}", ""])
        if not entries:
            out.append("なし")
            return
        for fname, qid, diff in (e for e in entries if e[2]):
            out.extend([f"### {qid} ({fname})", "", format_diff(diff), ""])
        no_diff = [e[1] for e in entries if not e[2]]
        if no_diff:
            out.append(f"差分なし: {', '.join(no_diff)}")

    section("スキップした問題 (確認済み。DB の内容を残した)", result["skipped"])
    section("上書きした問題", result["overwritten"])

    out += ["", "## 新規登録した問題", ""]
    out.append(", ".join(result["inserted"]) if result["inserted"] else "なし")

    out += ["", "## 警告", ""]
    out += [f"- {w}" for w in result["warnings"]] if result["warnings"] else ["なし"]
    if result["kept"]:
        out += ["", "元の場所に残したファイル:"] + [f"- {k}" for k in result["kept"]]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return path


def print_summary(result):
    print("\nImport Summary:")
    print(f"- Inserted: {len(result['inserted'])}")
    print(f"- Overwritten (unreviewed): {len(result['overwritten'])}")
    print(f"- Skipped (reviewed): {len(result['skipped'])}")
    print(f"- Files moved to imported_to_db/: {len(result['moved'])}")
    for name in result["moved"]:
        print(f"    {name}")
    if result["kept"]:
        print(f"- Files kept in place: {len(result['kept'])}")
        for name in result["kept"]:
            print(f"    {name}")
    print(f"- Log: {result['log_path']}")


def main():
    """コマンドとして実行したときの入口。読み込み元・移動先・ログは固定のフォルダを使う"""
    connection = open_initialized_db()
    try:
        outcome = import_json_files(connection, JSON_DIR, IMPORTED_DIR, LOG_DIR)
    finally:
        connection.close()
    print_summary(outcome)
    return 1 if outcome["aborted"] else 0


if __name__ == "__main__":
    sys.exit(main())
