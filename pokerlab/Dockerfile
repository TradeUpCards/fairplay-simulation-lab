# pokerlab — single-service deploy: FastAPI serves the built React UI *and* the API.
#
# IMPORTANT: build context must be the REPO ROOT (so the sibling `playsim/` package is
# available). On Railway set:  Dockerfile Path = pokerlab/Dockerfile  (Root Directory = /).
#
# This is the LEAN image — no PyTorch — so heuristic bots + EV/equity coaching + history
# + the optional LLM narrator all work. Trained / self-play bots need torch + a committed
# checkpoint (see README.md); add them in a follow-up if wanted.

# --- 1) build the React UI ---
FROM node:20-slim AS web
WORKDIR /web
COPY pokerlab/web/package.json ./
RUN npm install
COPY pokerlab/web/ ./
RUN npx vite build                 # transpile-only build (no tsc gate) -> /web/dist

# --- 2) python runtime ---
FROM python:3.12-slim AS app
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Shared bots/seam (playsim) + game-spine deps. No torch in this image.
COPY playsim/ ./playsim/
COPY pokerlab/requirements.txt ./pokerlab/requirements.txt
RUN pip install --no-cache-dir numpy \
 && pip install --no-cache-dir -r pokerlab/requirements.txt \
 && pip install --no-cache-dir ./playsim

# app code + the built UI (overlays the empty web/dist with the real build)
COPY pokerlab/ ./pokerlab/
COPY --from=web /web/dist ./pokerlab/web/dist

EXPOSE 8000
CMD ["sh", "-c", "uvicorn pokerlab.server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
