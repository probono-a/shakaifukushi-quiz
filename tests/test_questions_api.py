import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:  # with を使わないと lifespan が走らず、init_db() が呼ばれない
        yield c


def body(**kw):
    b = {
        "edition": 35, "question_number": 1, "subject": "現代社会と福祉", "question_type": "general",
        "question_text": "問題", "options": ["a", "b"], "correct_options": [1],
        "explanation": "解説", "keywords": [], "reference_links": [], "curriculum": "old",
    }
    b.update(kw)
    return b


def create(client, **kw):
    r = client.post("/api/questions", json=body(**kw))
    assert r.status_code == 200, r.text
    return r.json()["id"]


def reviewed(client, qid):
    return client.get(f"/api/questions/{qid}").json()["is_reviewed"]


def test_get_includes_is_reviewed(client):
    qid = create(client, is_reviewed=True)
    assert client.get(f"/api/questions/{qid}").json()["is_reviewed"] == 1
    listed = client.get("/api/questions", params={"mode": "subject"}).json()
    assert [q["is_reviewed"] for q in listed] == [1]


def test_patch_toggles(client):
    qid = create(client, is_reviewed=False)
    assert reviewed(client, qid) == 0
    r = client.patch(f"/api/questions/{qid}/review", json={"is_reviewed": True})
    assert r.status_code == 200 and reviewed(client, qid) == 1
    r = client.patch(f"/api/questions/{qid}/review", json={"is_reviewed": False})
    assert r.status_code == 200 and reviewed(client, qid) == 0


def test_patch_errors(client):
    qid = create(client)
    assert client.patch("/api/questions/99_99/review", json={"is_reviewed": True}).status_code == 404
    for bad in ({"is_reviewed": 1}, {"is_reviewed": "true"}, {}):
        assert client.patch(f"/api/questions/{qid}/review", json=bad).status_code == 422, bad
    assert reviewed(client, qid) == 0


@pytest.mark.parametrize("initial", [True, False])
def test_put_without_is_reviewed_keeps_state(client, initial):
    qid = create(client, is_reviewed=initial)
    r = client.put(f"/api/questions/{qid}", json=body(explanation="直した"))
    assert r.status_code == 200
    assert reviewed(client, qid) == (1 if initial else 0)
    assert client.get(f"/api/questions/{qid}").json()["explanation"] == "直した"


def test_put_with_is_reviewed_updates(client):
    qid = create(client, is_reviewed=False)
    client.put(f"/api/questions/{qid}", json=body(is_reviewed=True))
    assert reviewed(client, qid) == 1
    client.put(f"/api/questions/{qid}", json=body(is_reviewed=False))
    assert reviewed(client, qid) == 0


@pytest.mark.parametrize("bad", ["false", 1, 0, None])
def test_put_rejects_non_bool(client, bad):
    qid = create(client, is_reviewed=True)
    r = client.put(f"/api/questions/{qid}", json=body(is_reviewed=bad, explanation="変わらない"))
    assert r.status_code == 422
    assert reviewed(client, qid) == 1
    assert client.get(f"/api/questions/{qid}").json()["explanation"] == "解説"


def test_put_unknown_id_is_404(client):
    assert client.put("/api/questions/99_99", json=body(is_reviewed=True)).status_code == 404


def test_post_respects_is_reviewed(client):
    assert reviewed(client, create(client, question_number=1, is_reviewed=True)) == 1
    assert reviewed(client, create(client, question_number=2, is_reviewed=False)) == 0
    assert reviewed(client, create(client, question_number=3)) == 0  # 送らなければ既定値


@pytest.mark.parametrize("bad", ["true", 1])
def test_post_rejects_non_bool(client, bad):
    r = client.post("/api/questions", json=body(is_reviewed=bad))
    assert r.status_code == 422
    assert client.get("/api/questions/35_1").status_code == 404


def check(client, qid):
    q = client.get(f"/api/questions/{qid}").json()
    return q["needs_check"], q["check_note"]


def patch_check(client, qid, **kw):
    return client.patch(f"/api/questions/{qid}/check", json=kw)


def test_get_includes_needs_check(client):
    qid = create(client, needs_check=True, check_note="理由")
    assert check(client, qid) == (1, "理由")
    listed = client.get("/api/questions", params={"mode": "subject"}).json()
    assert [(q["needs_check"], q["check_note"]) for q in listed] == [(1, "理由")]


def test_patch_check_toggles_and_returns_values(client):
    qid = create(client)
    assert check(client, qid) == (0, None)
    r = patch_check(client, qid, needs_check=True, check_note="正答は 3 では？")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "needs_check": 1, "check_note": "正答は 3 では？"}
    assert check(client, qid) == (1, "正答は 3 では？")


def test_patch_check_omitted_note_is_kept(client):
    qid = create(client, needs_check=True, check_note="理由")
    patch_check(client, qid, needs_check=False)  # 外しても理由は残る
    assert check(client, qid) == (0, "理由")
    patch_check(client, qid, needs_check=True)
    assert check(client, qid) == (1, "理由")


def test_patch_check_null_clears_note(client):
    qid = create(client, needs_check=True, check_note="理由")
    patch_check(client, qid, needs_check=True, check_note=None)
    assert check(client, qid) == (1, None)


@pytest.mark.parametrize("note, expected", [("  理由  ", "理由"), ("   ", None), ("", None), ("1 行目\n2 行目", "1 行目\n2 行目")])
def test_patch_check_normalizes_note(client, note, expected):
    qid = create(client)
    r = patch_check(client, qid, needs_check=True, check_note=note)
    assert r.json()["check_note"] == expected
    assert check(client, qid) == (1, expected)


def test_patch_check_errors(client):
    qid = create(client)
    assert patch_check(client, "99_99", needs_check=True).status_code == 404
    for bad in ({"needs_check": 1}, {"needs_check": "true"}, {}, {"needs_check": True, "check_note": 1}):
        assert client.patch(f"/api/questions/{qid}/check", json=bad).status_code == 422, bad
    assert check(client, qid) == (0, None)


def test_put_without_needs_check_keeps_it(client):
    qid = create(client, needs_check=True, check_note="理由")
    client.put(f"/api/questions/{qid}", json=body(explanation="直した"))
    assert check(client, qid) == (1, "理由")


def test_put_with_needs_check_updates_and_normalizes(client):
    qid = create(client)
    client.put(f"/api/questions/{qid}", json=body(needs_check=True, check_note="  理由 "))
    assert check(client, qid) == (1, "理由")
    client.put(f"/api/questions/{qid}", json=body(needs_check=False, check_note=""))
    assert check(client, qid) == (0, None)


@pytest.mark.parametrize("bad", [{"needs_check": "true"}, {"needs_check": 1}, {"check_note": 1}])
def test_put_rejects_bad_check_fields(client, bad):
    qid = create(client)
    r = client.put(f"/api/questions/{qid}", json=body(explanation="変わらない", **bad))
    assert r.status_code == 422
    assert client.get(f"/api/questions/{qid}").json()["explanation"] == "解説"


def test_post_respects_needs_check(client):
    assert check(client, create(client, question_number=1, needs_check=True, check_note=" 理由 ")) == (1, "理由")
    assert check(client, create(client, question_number=2)) == (0, None)  # 送らなければ既定値


@pytest.mark.parametrize("bad", [{"needs_check": "true"}, {"check_note": 1}])
def test_post_rejects_bad_check_fields(client, bad):
    r = client.post("/api/questions", json=body(**bad))
    assert r.status_code == 422
    assert client.get("/api/questions/35_1").status_code == 404


def ids_of(client, mode, **params):
    return [q["id"] for q in client.get("/api/questions", params={"mode": mode, **params}).json()]


def test_mode_needs_check(client):
    assert ids_of(client, "needs_check") == []
    create(client, edition=36, question_number=2, needs_check=True)
    create(client, edition=35, question_number=9, needs_check=True)
    create(client, edition=35, question_number=1)
    create(client, edition=35, question_number=5, needs_check=True, question_type="事例")
    assert ids_of(client, "needs_check") == ["35_5", "35_9", "36_2"]
    assert ids_of(client, "needs_check", question_type="事例") == ["35_5"]
    patch_check(client, "35_9", needs_check=False)
    assert ids_of(client, "needs_check") == ["35_5", "36_2"]


def test_mode_unreviewed(client):
    create(client, edition=36, question_number=2)
    create(client, edition=35, question_number=9, is_reviewed=True)
    create(client, edition=35, question_number=1, correct_options=[1, 2])
    assert ids_of(client, "unreviewed") == ["35_1", "36_2"]
    assert ids_of(client, "unreviewed", multiple_only="true") == ["35_1"]
    client.patch("/api/questions/36_2/review", json={"is_reviewed": True})
    assert ids_of(client, "unreviewed") == ["35_1"]
    client.patch("/api/questions/35_1/review", json={"is_reviewed": True})
    assert ids_of(client, "unreviewed") == []


def test_check_modes_ignore_other_conditions(client):
    """要確認・未確認のモードは、科目・回・件数を使わない"""
    create(client, edition=35, question_number=1, needs_check=True)
    create(client, edition=36, question_number=1, needs_check=True, subject="社会保障")
    for mode in ("needs_check", "unreviewed"):
        got = ids_of(client, mode, subjects="社会保障", edition=36, count=1)
        assert got == ["35_1", "36_1"], mode


def test_check_modes_apply_filters(client):
    create(client, edition=35, question_number=1, needs_check=True, correct_options=[1, 2])
    create(client, edition=35, question_number=2, needs_check=True, question_type="事例")
    assert ids_of(client, "needs_check", multiple_only="true") == ["35_1"]
    assert ids_of(client, "unreviewed", question_type="事例") == ["35_2"]


def test_post_rejects_int_needs_check(client):
    assert client.post("/api/questions", json=body(needs_check=1)).status_code == 422


def test_put_null_clears_note(client):
    qid = create(client, needs_check=True, check_note="理由")
    client.put(f"/api/questions/{qid}", json=body(check_note=None))
    assert check(client, qid) == (1, None)
