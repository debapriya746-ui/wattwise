# Combined image for the Hugging Face Space live demo.
# Runs the FastAPI backend internally and serves the Streamlit app on 7860.
# The per-service Dockerfile.api / Dockerfile.frontend are still used by CI.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# app.py reads API_BASE_URL to reach the backend (default is this same value).
ENV API_BASE_URL=http://localhost:8001

# Hugging Face Spaces (Docker) expects the app on port 7860.
EXPOSE 7860

CMD ["bash", "start.sh"]
