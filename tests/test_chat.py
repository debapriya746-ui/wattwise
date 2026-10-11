"""Tests for the AI Assistant wiring.

No LLM key and no network: these verify the health probe and that the chat
routes are correctly gated on WATTWISE_ENABLE_ADK, which is what the Streamlit
frontend relies on to decide whether to offer the chat tab.
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient


def _load_app(enable_adk: str):
    """Import api.main fresh with WATTWISE_ENABLE_ADK set to the given value."""
    os.environ["WATTWISE_ENABLE_ADK"] = enable_adk
    import api.main as main
    return importlib.reload(main)


def test_health_reports_adk_disabled():
    main = _load_app("0")
    client = TestClient(main.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "adk_enabled": False}


def test_chat_routes_absent_when_disabled():
    main = _load_app("0")
    client = TestClient(main.app)
    # v2 agent routes are only registered when ADK is enabled.
    assert client.post("/v2/sessions").status_code == 404
