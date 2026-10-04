import os

import pytest

from db import PROJECT_ROOT, get_db_path


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """すべてのテストで、一時フォルダの DB を使う (本番の data/quiz.db に触らない)"""
    monkeypatch.setenv("QUIZ_DB_PATH", str(tmp_path / "quiz.db"))
    path = os.path.abspath(get_db_path())
    assert path.startswith(os.path.abspath(str(tmp_path))), f"本番 DB を指している: {path}"
    assert not path.startswith(os.path.join(PROJECT_ROOT, "data"))
    yield path
