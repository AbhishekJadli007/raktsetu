from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_and_meta():
    assert client.get("/api/health").json() == {"ok": True}
    m = client.get("/api/meta").json()
    assert len(m["banks"]) == 18


def test_plan_with_typed_in_stock():
    r = client.post("/api/plan", json={"date": "2024-09-20", "overrides": {"SMS": {"PLT": 0}}})
    assert r.status_code == 200
    sms = next(b for b in r.json()["banks"] if b["bank"] == "SMS")
    assert sms["plt_stock"] == 0


def test_bad_inputs_are_rejected_clearly():
    assert client.get("/api/plan?date=2031-01-01").status_code == 400
    r = client.post("/api/simulate", json={"start": "2024-09-01", "end": "2024-09-20",
                                            "scenario": {"surge": [{"bank": "NOPE", "date": "2024-09-05", "units": 10}]}})
    assert r.status_code == 400 and "Unknown bank" in r.json()["detail"]
