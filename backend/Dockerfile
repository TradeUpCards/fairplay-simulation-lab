# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install API runtime dependencies first for Docker layer caching.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Run from the repo-shaped /app so backend/app/room.py can resolve data/ and scoring/,
# and backend/play/session.py can put the sibling `playsim/` package on sys.path.
COPY backend ./backend
COPY data ./data
COPY playsim ./playsim

EXPOSE 8000

# Bind the platform-provided $PORT (Render/Fly set it); fall back to 8000 locally.
# Shell form so the env var expands.
CMD uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
