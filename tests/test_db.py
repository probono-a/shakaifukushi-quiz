import pytest
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


def _make_old_db(path, n=3):
    """is_reviewed 列のない旧形式の questions を持つ DB を作る"""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE questions (id TEXT PRIMARY KEY, edition INTEGER, subject TEXT)")
    conn.executemany("INSERT INTO questions VALUES (?, 35, 's')", [(f"35_{i}",) for i in range(1, n + 1)])
    conn.commit()
    return conn


def test_migration_marks_existing_questions_reviewed(tmp_path):
    conn = _make_old_db(tmp_path / "old.db")
    init_db(conn)
    assert conn.execute("SELECT COUNT(*) FROM questions WHERE is_reviewed = 1").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 3


def test_migration_runs_only_once(tmp_path):
    conn = _make_old_db(tmp_path / "old.db")
    init_db(conn)
    conn.execute("UPDATE questions SET is_reviewed = 0 WHERE id = '35_1'")
    conn.commit()
    init_db(conn)
    assert conn.execute("SELECT is_reviewed FROM questions WHERE id = '35_1'").fetchone()[0] == 0


class _FailOnUpdate:
    """UPDATE questions を実行しようとしたら例外を起こす接続のラッパー"""

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def execute(self, sql, *args):
        if sql.startswith("UPDATE questions SET is_reviewed"):
            raise RuntimeError("途中で落ちた")
        return self._conn.execute(sql, *args)


def test_migration_failure_leaves_no_column(tmp_path):
    conn = _make_old_db(tmp_path / "old.db")
    with pytest.raises(RuntimeError):
        init_db(_FailOnUpdate(conn))
    assert "is_reviewed" not in {r[1] for r in conn.execute("PRAGMA table_info(questions)")}
    init_db(conn)  # やり直すと、全件 1 になる
    assert conn.execute("SELECT COUNT(*) FROM questions WHERE is_reviewed = 1").fetchone()[0] == 3


def test_new_db_has_is_reviewed_default_0(tmp_path):
    conn = sqlite3.connect(tmp_path / "new.db")
    init_db(conn)
    conn.execute("INSERT INTO questions (id) VALUES ('x')")
    assert conn.execute("SELECT is_reviewed FROM questions").fetchone()[0] == 0
