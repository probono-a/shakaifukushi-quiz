import importlib.util
import json
import os
import shutil
import sqlite3

import pytest

from db import PROJECT_ROOT, open_initialized_db

_spec = importlib.util.spec_from_file_location(
    "import_json", os.path.join(PROJECT_ROOT, "converter", "import_json.py"))
ij = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ij)


@pytest.fixture
def env(tmp_path):
    src, dest, log = tmp_path / "src", tmp_path / "dest", tmp_path / "log"
    src.mkdir()
    conn = open_initialized_db()
    conn.row_factory = sqlite3.Row
    yield {"src": src, "dest": dest, "log": log, "conn": conn}
    conn.close()


def make_item(qid="35_1", **kw):
    edition, number = qid.split("_")
    item = {
        "id": qid, "edition": int(edition), "subject": "現代社会と福祉",
        "question_number": int(number), "question_type": "general",
        "case_text": None, "question_text": "問題文", "is_multiple_answers": False,
        "options": ["a", "b", "c"], "correct_options": [1], "explanation": "解説",
        "keywords": ["k"], "reference_links": [], "image_paths": [], "is_reviewed": False,
    }
    item.update(kw)
    return item


def write(env, name, items):
    path = env["src"] / name
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return path


def run(env):
    return ij.import_json_files(env["conn"], str(env["src"]), str(env["dest"]), str(env["log"]))


def row(env, qid):
    return env["conn"].execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()


def set_reviewed(env, qid, value):
    env["conn"].execute("UPDATE questions SET is_reviewed = ? WHERE id = ?", (value, qid))
    env["conn"].commit()


def log_text(result):
    with open(result["log_path"], encoding="utf-8") as f:
        return f.read()


def test_insert_uses_json_is_reviewed(env):
    write(env, "a.json", [make_item("35_1", is_reviewed=False), make_item("35_2", is_reviewed=True)])
    result = run(env)
    assert result["inserted"] == ["35_1", "35_2"]
    assert row(env, "35_1")["is_reviewed"] == 0
    assert row(env, "35_2")["is_reviewed"] == 1
    assert row(env, "35_1")["curriculum"] == "old"


def test_unreviewed_is_overwritten(env):
    write(env, "a.json", [make_item("35_1", explanation="古い")])
    run(env)
    write(env, "b.json", [make_item("35_1", explanation="新しい", is_reviewed=True)])
    result = run(env)
    assert [e[1] for e in result["overwritten"]] == ["35_1"]
    assert row(env, "35_1")["explanation"] == "新しい"
    assert row(env, "35_1")["is_reviewed"] == 1


def test_reviewed_is_skipped(env):
    write(env, "a.json", [make_item("35_1", explanation="古い")])
    run(env)
    set_reviewed(env, "35_1", 1)
    write(env, "b.json", [make_item("35_1", explanation="JSON の内容")])
    result = run(env)
    assert [e[1] for e in result["skipped"]] == ["35_1"]
    assert row(env, "35_1")["explanation"] == "古い"
    assert row(env, "35_1")["is_reviewed"] == 1


def test_files_are_moved_including_ones_with_skipped(env):
    write(env, "a.json", [make_item("35_1")])
    run(env)
    set_reviewed(env, "35_1", 1)
    write(env, "b.json", [make_item("35_1", explanation="違う"), make_item("35_2")])
    result = run(env)
    assert result["moved"] == ["b.json"]
    assert not (env["src"] / "b.json").exists()
    assert (env["dest"] / "b.json").exists()


def test_same_name_in_dest_is_kept_and_new_one_gets_timestamp(env):
    write(env, "a.json", [make_item("35_1")])
    run(env)
    first = (env["dest"] / "a.json").read_text(encoding="utf-8")
    write(env, "a.json", [make_item("35_1", explanation="再精査")])
    result = run(env)
    assert (env["dest"] / "a.json").read_text(encoding="utf-8") == first
    names = sorted(os.listdir(env["dest"]))
    assert len(names) == 2
    renamed = [n for n in names if n != "a.json"][0]
    assert renamed.startswith("a_") and renamed.endswith(".json")
    assert any("同じ名前" in w for w in result["warnings"])


def test_unique_dest_adds_counter_when_timestamp_name_taken(tmp_path):
    (tmp_path / "a.json").write_text("x")
    first, renamed = ij._unique_dest(str(tmp_path), "a.json")
    assert renamed
    open(first, "w").close()
    second, _ = ij._unique_dest(str(tmp_path), "a.json")
    assert second != first and not os.path.exists(second)


def test_broken_json_is_left_and_others_processed(env):
    (env["src"] / "bad.json").write_text("{ broken", encoding="utf-8")
    write(env, "ok.json", [make_item("35_1")])
    result = run(env)
    assert (env["src"] / "bad.json").exists()
    assert result["moved"] == ["ok.json"]
    assert "bad.json" in result["kept"]
    assert row(env, "35_1") is not None


def test_record_without_id_is_not_imported_and_file_stays(env):
    no_id = make_item("35_2")
    del no_id["id"]
    write(env, "a.json", [make_item("35_1"), no_id])
    result = run(env)
    assert (env["src"] / "a.json").exists()
    assert result["moved"] == []
    assert row(env, "35_1") is not None  # id のあるレコードは入る
    assert env["conn"].execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 1
    assert any("id のない" in w for w in result["warnings"])


def test_failure_in_file_rolls_back_that_file_only(env):
    # question_number がリストだと、SQLite に渡せず 2 件目で失敗する
    write(env, "a_bad.json", [make_item("35_1"), make_item("35_2", question_number=[1])])
    write(env, "b_ok.json", [make_item("35_3")])
    result = run(env)
    assert row(env, "35_1") is None  # 1 件目も rollback される
    assert row(env, "35_3") is not None
    assert (env["src"] / "a_bad.json").exists()
    assert result["moved"] == ["b_ok.json"]
    assert any("途中で失敗" in w for w in result["warnings"])


def test_move_failure_keeps_db_and_warns(env, monkeypatch):
    write(env, "a.json", [make_item("35_1")])

    def boom(*a, **k):
        raise PermissionError("使用中")

    monkeypatch.setattr(ij.shutil, "move", boom)
    result = run(env)
    assert row(env, "35_1") is not None
    assert (env["src"] / "a.json").exists()
    assert result["moved"] == []
    assert "移動に失敗" in log_text(result)


def test_duplicate_id_across_files_writes_nothing(env):
    write(env, "a.json", [make_item("35_1"), make_item("35_5")])
    write(env, "b.json", [make_item("35_1")])
    result = run(env)
    assert result["aborted"]
    assert result["duplicates"] == {"35_1": ["a.json", "b.json"]}
    assert env["conn"].execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0
    assert (env["src"] / "a.json").exists() and (env["src"] / "b.json").exists()
    assert "35_1" in log_text(result)


def test_main_uses_env_db(env, monkeypatch, tmp_path):
    src, dest, log = tmp_path / "m_src", tmp_path / "m_dest", tmp_path / "m_log"
    src.mkdir()
    (src / "a.json").write_text(json.dumps([make_item("36_1")]), encoding="utf-8")
    monkeypatch.setattr(ij, "JSON_DIR", str(src))
    monkeypatch.setattr(ij, "IMPORTED_DIR", str(dest))
    monkeypatch.setattr(ij, "LOG_DIR", str(log))
    assert ij.main() == 0
    assert row(env, "36_1") is not None  # QUIZ_DB_PATH の DB に入る
    assert (dest / "a.json").exists()


def test_log_skip_diff_shows_only_changed_fields(env):
    write(env, "a.json", [make_item("35_1")])
    run(env)
    set_reviewed(env, "35_1", 1)
    write(env, "b.json", [make_item("35_1", subject="別の科目", explanation="新しい解説")])
    text = log_text(run(env))
    skipped = text.split("## スキップした問題")[1].split("## 上書きした問題")[0]
    assert "`subject`: `現代社会と福祉` → `別の科目`" in skipped
    assert "```diff" in skipped and "+新しい解説" in skipped and "-解説" in skipped
    assert "`question_text`" not in skipped
    assert "`options`" not in skipped


def test_log_overwrite_diff(env):
    write(env, "a.json", [make_item("35_1", correct_options=[1], options=["a", "b"])])
    run(env)
    write(env, "b.json", [make_item("35_1", correct_options=[2], options=["a", "c"])])
    text = log_text(run(env))
    over = text.split("## 上書きした問題")[1].split("## 新規登録")[0]
    assert "`correct_options`: [1] → [2]" in over
    assert '-"b"' in over and '+"c"' in over
    assert "`subject`" not in over


def test_log_no_diff_lists_ids_only(env):
    write(env, "a.json", [make_item("35_1"), make_item("35_2")])
    run(env)
    set_reviewed(env, "35_2", 1)
    write(env, "b.json", [make_item("35_1"), make_item("35_2")])
    text = log_text(run(env))
    assert "差分なし: 35_1" in text.split("## 上書きした問題")[1]
    assert "差分なし: 35_2" in text.split("## スキップした問題")[1].split("## 上書きした問題")[0]
    assert "###" not in text


def test_log_ignores_cosmetic_differences(env):
    write(env, "a.json", [make_item("35_1", case_text=None, reference_links=[], options=["a", "b"])])
    run(env)
    set_reviewed(env, "35_1", 1)
    # None と空文字、前後の空白、リストの空の要素。is_multiple と curriculum も差分にしない
    cosmetic = make_item("35_1", case_text="", reference_links=[""], options=["a", "b", ""],
                         question_text=" 問題文 \n", is_multiple_answers=True)
    cosmetic["curriculum"] = "new"
    write(env, "b.json", [cosmetic])
    text = log_text(run(env))
    assert "###" not in text
    assert "差分なし: 35_1" in text


def test_log_is_utf8(env):
    write(env, "a.json", [make_item("35_1", explanation="日本語の解説")])
    result = run(env)
    assert "新規登録" in log_text(result)
    assert os.path.dirname(result["log_path"]) == str(env["log"])
    assert os.path.basename(result["log_path"]).startswith("import_log_")


def test_update_keeps_other_columns(env):
    """UPDATE なので、JSON にない列 (将来足される列) は消えない"""
    write(env, "a.json", [make_item("35_1")])
    run(env)
    env["conn"].execute("ALTER TABLE questions ADD COLUMN memo TEXT")
    env["conn"].execute("UPDATE questions SET memo = 'メモ' WHERE id = '35_1'")
    env["conn"].commit()
    write(env, "b.json", [make_item("35_1", explanation="新しい")])
    run(env)
    assert row(env, "35_1")["memo"] == "メモ"


def test_log_written_even_when_unexpected_error(env, monkeypatch):
    write(env, "a.json", [make_item("35_1")])

    def boom(*a, **k):
        raise KeyboardInterrupt()

    monkeypatch.setattr(ij, "_import_file", boom)
    with pytest.raises(KeyboardInterrupt):
        run(env)
    assert len(os.listdir(env["log"])) == 1


def test_reimport_keeps_needs_check(env):
    """未確認の問題を上書きしても、要確認の印と理由は消えない"""
    write(env, "a.json", [make_item("35_1")])
    run(env)
    env["conn"].execute("UPDATE questions SET needs_check = 1, check_note = '理由' WHERE id = '35_1'")
    env["conn"].commit()
    write(env, "b.json", [make_item("35_1", explanation="新しい")])
    run(env)
    r = row(env, "35_1")
    assert r["explanation"] == "新しい"
    assert (r["needs_check"], r["check_note"]) == (1, "理由")
