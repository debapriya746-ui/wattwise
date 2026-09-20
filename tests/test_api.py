"""
Tier 3: FastAPI TestClient smoke tests for the API layer added in Phase 1.
No network calls, no LLM — just verifies the HTTP contract routes correctly
to the existing agents/*.py business logic.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def _new_session() -> str:
    resp = client.post("/sessions")
    assert resp.status_code == 200
    return resp.json()["session_id"]


def test_create_and_fetch_session():
    sid = _new_session()
    resp = client.get(f"/sessions/{sid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "Quick Mode"
    assert body["appliances"] == []


def test_unknown_session_is_404():
    resp = client.get("/sessions/does-not-exist")
    assert resp.status_code == 404


def test_profile_and_quick_appliances():
    sid = _new_session()
    resp = client.post(f"/sessions/{sid}/profile", json={"home_type": "House", "members": "3", "mode": "Quick Mode"})
    assert resp.status_code == 200

    resp = client.post(f"/sessions/{sid}/appliances/quick", json={"usage_level": "Medium"})
    assert resp.status_code == 200
    appliances = resp.json()["appliances"]
    assert len(appliances) > 0
    assert all("watts" in a and "hours" in a for a in appliances)


def test_calculate_never_returns_a_single_number():
    sid = _new_session()
    client.post(f"/sessions/{sid}/profile", json={"home_type": "Apartment", "members": "2", "mode": "Quick Mode"})
    client.post(f"/sessions/{sid}/appliances/quick", json={"usage_level": "Medium"})
    # Set weather/tariff directly to avoid live network calls in this test.
    client.patch(f"/sessions/{sid}", json={
        "temp": 90.0, "humidity": 40.0, "cdd": 20.0, "hdd": 0.0,
        "rate": 8.0, "fixed_charge": 50.0,
    })

    resp = client.post(f"/sessions/{sid}/calculate")
    assert resp.status_code == 200
    result = resp.json()

    # The whole point of the calculator's safety rule: a range, never one number.
    assert "low_bill" in result and "high_bill" in result and "total_expected" in result
    assert result["low_bill"] < result["total_expected"] < result["high_bill"]
    assert "disclaimer" in result


def test_tips_require_calculation_first():
    sid = _new_session()
    resp = client.get(f"/sessions/{sid}/tips")
    assert resp.status_code == 400
