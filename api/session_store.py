import uuid
from typing import Optional


def _default_state() -> dict:
    return {
        "city": "",
        "country": "",
        "pincode": "",
        "location_resolved": False,
        "weather": {},
        "tariff": {},
        "home_type": "Apartment",
        "members": "2",
        "mode": "Quick Mode",
        "usage_level": "Medium",
        "appliances": [],
        "calculation_results": {},
        "feedback_status": None,
    }


class SessionStore:
    """In-memory session state, keyed by session id. Dev/single-instance only —
    mirrors the fields app.py used to keep in st.session_state."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def create(self) -> str:
        session_id = uuid.uuid4().hex
        self._sessions[session_id] = _default_state()
        return session_id

    def get(self, session_id: str) -> Optional[dict]:
        return self._sessions.get(session_id)


store = SessionStore()
