import csv
import io
import json

from db import get_db

# history にはほかの表への外部キーが無いので、セッションや問題を作らずに行を足せる


def answer(client, time_sec, subject="現代社会と福祉"):
    r = client.post("/api/history", json={
        "session_id": "s1", "question_id": "35_1", "is_correct": True,
        "subject": subject, "curriculum": "old", "edition": 35, "time_sec": time_sec,
    })
    assert r.status_code == 201, r.text


def test_time_sec_null_is_saved_as_null(client):
    answer(client, None)
    with get_db() as conn:
        assert conn.execute("SELECT time_sec FROM history").fetchone()["time_sec"] is None


def test_null_is_left_out_of_average(client):
    for t in (10, 20, None):
        answer(client, t)
    stats = client.get("/api/stats").json()
    assert stats["overall"]["total"] == 3  # 正答率・解いた数には入る
    assert stats["overall"]["avg_time_sec"] == 15.0
    assert [s["avg_time_sec"] for s in stats["by_subject"]] == [15.0]


def test_all_null_average_is_null(client):
    answer(client, None)
    answer(client, None)
    r = client.get("/api/stats")
    assert r.status_code == 200
    assert r.json()["overall"]["avg_time_sec"] is None
    assert [s["avg_time_sec"] for s in r.json()["by_subject"]] == [None]


def test_session_config_keeps_timed(client):
    r = client.post("/api/sessions", json={"mode": "random", "config": {"timed": False}})
    assert r.status_code == 201, r.text
    with get_db() as conn:
        row = conn.execute("SELECT config FROM sessions WHERE id = ?", (r.json()["id"],)).fetchone()
    assert json.loads(row["config"]) == {"timed": False}


def post_answer(client, **extra):
    r = client.post("/api/history", json={
        "session_id": "s1", "question_id": "35_1", "is_correct": False,
        "subject": "現代社会と福祉", "curriculum": "old", "edition": 35, **extra,
    })
    assert r.status_code == 201, r.text


def saved_selected_options(client):
    with get_db() as conn:
        return [r["selected_options"] for r in conn.execute("SELECT selected_options FROM history ORDER BY id")]


def test_selected_options_are_saved_sorted(client):
    post_answer(client, selected_options=[3, 1])
    post_answer(client, selected_options=[2])
    assert saved_selected_options(client) == ["1,3", "2"]


def test_selected_options_omitted_is_null(client):
    post_answer(client)
    post_answer(client, selected_options=None)
    assert saved_selected_options(client) == [None, None]


def test_export_has_selected_options_column(client):
    post_answer(client, selected_options=[3, 1])
    post_answer(client)
    r = client.get("/api/history/export")
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0][-1] == "選んだ選択肢"
    assert sorted(row[-1] for row in rows[1:]) == ["", "1,3"]
