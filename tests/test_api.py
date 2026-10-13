import pytest
from fastapi.testclient import TestClient

from t2s import api
from t2s.config import ArmConfig
from t2s.generate import LLMUnavailable


@pytest.fixture
def client(monkeypatch, school_db):
    monkeypatch.setattr(api, "API_CONFIG", ArmConfig("test", link_schema=False, shots=0, max_retries=2))
    monkeypatch.setattr(api, "allowlist", lambda: frozenset({"school"}))
    monkeypatch.setattr(api, "db_path", lambda db_id: __import__("pathlib").Path(school_db))
    return TestClient(api.app)


def _llm(monkeypatch, scripted_llm, replies):
    llm = scripted_llm(replies)
    monkeypatch.setattr(api, "get_llm", lambda: llm)
    return llm


def test_query_ok(client, monkeypatch, scripted_llm):
    _llm(monkeypatch, scripted_llm, ["```sql\nSELECT count(*) FROM students\n```"])
    r = client.post("/query", json={"db_id": "school", "question": "How many students?"})
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == [[3]] and body["attempts"] == 1
    assert {"sql", "rows", "attempts", "error_trace", "tokens_in", "tokens_out", "latency_ms"} <= body.keys()


def test_unknown_db_404(client):
    r = client.post("/query", json={"db_id": "../../etc/passwd", "question": "x"})
    assert r.status_code == 404


def test_guard_rejection_400(client, monkeypatch, scripted_llm):
    _llm(monkeypatch, scripted_llm, ["```sql\nDELETE FROM students\n```"])
    r = client.post("/query", json={"db_id": "school", "question": "delete all rows"})
    assert r.status_code == 400
    assert "forbidden" in r.json()["detail"]["reason"]


def test_ollama_down_503(client, monkeypatch):
    class Down:
        def chat(self, messages, **options):
            raise LLMUnavailable("connection refused")

        def healthy(self):
            return False

    monkeypatch.setattr(api, "get_llm", lambda: Down())
    assert client.post("/query", json={"db_id": "school", "question": "q"}).status_code == 503
    assert client.get("/health").status_code == 503


def test_health_ok(client, monkeypatch):
    class Up:
        def healthy(self):
            return True

    monkeypatch.setattr(api, "get_llm", lambda: Up())
    assert client.get("/health").json()["status"] == "ok"


def test_real_client_unreachable_raises_unavailable():
    from t2s.generate import OllamaChat

    llm = OllamaChat(url="http://127.0.0.1:9")  # discard port: nothing listens there
    assert not llm.healthy()
    with pytest.raises(LLMUnavailable):
        llm.chat([{"role": "user", "content": "hi"}])
