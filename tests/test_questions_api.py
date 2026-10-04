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
