import os
import sqlite3

from db import DEFAULT_DB_PATH, PROJECT_ROOT, SUBJECT_MAPPINGS, get_db_path, init_db, open_initialized_db


def test_path_default(monkeypatch):
    monkeypatch.delenv("QUIZ_DB_PATH")
    assert get_db_path() == os.path.join(PROJECT_ROOT, "data", "quiz.db")
    assert get_db_path() == DEFAULT_DB_PATH
    assert os.path.isabs(get_db_path())


def test_path_empty_string_is_unset(monkeypatch):
    monkeypatch.setenv("QUIZ_DB_PATH", "")
    assert get_db_path() == DEFAULT_DB_PATH


def test_path_relative_is_based_on_project_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUIZ_DB_PATH", "data/quiz_test.db")
    assert get_db_path() == os.path.join(PROJECT_ROOT, "data", "quiz_test.db")


def test_path_is_read_on_every_call(monkeypatch, tmp_path):
    monkeypatch.setenv("QUIZ_DB_PATH", str(tmp_path / "a.db"))
    first = get_db_path()
    monkeypatch.setenv("QUIZ_DB_PATH", str(tmp_path / "b.db"))
    assert get_db_path() != first


def test_init_db_on_empty_db(tmp_path):
    conn = sqlite3.connect(tmp_path / "new.db")
    init_db(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"questions", "sessions", "history", "subject_mapping"} <= tables
    assert conn.execute("SELECT COUNT(*) FROM subject_mapping").fetchone()[0] == len(SUBJECT_MAPPINGS)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(history)")}
    assert {"session_id", "edition", "time_sec"} <= cols
    init_db(conn)  # 2 回呼んでも初期データが増えない
    assert conn.execute("SELECT COUNT(*) FROM subject_mapping").fetchone()[0] == len(SUBJECT_MAPPINGS)


def test_open_initialized_db_creates_parent_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("QUIZ_DB_PATH", str(tmp_path / "sub" / "dir" / "q.db"))
    open_initialized_db().close()
    assert (tmp_path / "sub" / "dir" / "q.db").exists()
