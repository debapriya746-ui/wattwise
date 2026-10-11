"""Run the WattWise FastAPI backend in-process.

Single-process hosts like Streamlit Community Cloud run only one app, so there
is nowhere to stand up a separate FastAPI service. `ensure_backend` starts the
same `api.main:app` in a daemon thread inside the Streamlit process and the
frontend talks to it over localhost exactly as it would a separate service.

On a two-process host (the Docker image / Render), the backend is already
running separately; `ensure_backend` detects it listening on the URL and does
nothing, so the same app.py works in both setups.
"""
import os
import threading
import time

import httpx

_started = False
_lock = threading.Lock()


def _backend_ready(base_url: str, timeout: float = 1.0) -> bool:
    try:
        return httpx.get(f"{base_url}/health", timeout=timeout).status_code == 200
    except Exception:
        return False


def _serve(host: str, port: int):
    import uvicorn

    # Imported here, not at module top, so the env vars ensure_backend() sets
    # (WATTWISE_ENABLE_ADK, GROQ_API_KEY) are already in place when api.main —
    # and, through it, the ADK agent — is first imported.
    from api.main import app

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    # Signal handlers can only be installed on the main thread; we are not it.
    server.install_signal_handlers = lambda: None
    server.run()


def ensure_backend(base_url: str, host: str, port: int, groq_api_key: str | None = None) -> bool:
    """Guarantee a backend is reachable at base_url, starting one if needed.

    Returns True once the backend answers /health, False if it never came up.
    """
    global _started

    if _backend_ready(base_url):
        return True

    with _lock:
        if not _started:
            # Configure the agent BEFORE the backend thread imports api.main.
            if groq_api_key:
                os.environ["GROQ_API_KEY"] = groq_api_key
                os.environ["WATTWISE_ENABLE_ADK"] = "1"
            else:
                # No key -> run the guided wizard only; don't try to load the agent.
                os.environ.setdefault("WATTWISE_ENABLE_ADK", "0")
            threading.Thread(target=_serve, args=(host, port), daemon=True).start()
            _started = True

    for _ in range(60):  # up to ~30s for first import (ADK is heavy)
        if _backend_ready(base_url):
            return True
        time.sleep(0.5)
    return False
