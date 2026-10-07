#!/usr/bin/env bash
# Boot the FastAPI backend in the background, then serve the Streamlit UI.
set -e

# Backend on 8001 (matches app.py's default API_BASE_URL).
uvicorn api.main:app --host 0.0.0.0 --port 8001 &

# Give the backend a moment to import and start before the UI accepts clicks.
sleep 5

# Streamlit on the public Hugging Face port. Headless avoids the email prompt;
# CORS/XSRF are relaxed because the Space serves the app behind a proxy.
exec streamlit run app.py \
  --server.port 7860 \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --browser.gatherUsageStats false
