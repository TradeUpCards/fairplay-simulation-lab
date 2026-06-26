# Deploy — FairPlay training table

Frontend on **Vercel** (static), API on **Render** (free Docker web service). The
training table needs the live API (poker engine + streaming coach); the API is stateful
(in-memory sessions), which is why it runs as a persistent server, not serverless.

## 1. API on Render

1. Push this branch to GitHub (already on `origin`).
2. Render → **New → Blueprint** → connect this repo. Render reads `render.yaml` and
   builds `backend/Dockerfile` (which now copies `playsim/` and binds `$PORT`).
3. When prompted, set the two env vars:
   - `ANTHROPIC_API_KEY` — your key (powers the live coach).
   - `CORS_ORIGINS` — leave blank for now; fill in after step 2 with the Vercel URL
     (comma-separated, no trailing slash), e.g. `https://fairplay.vercel.app`.
4. Deploy. Note the service URL, e.g. `https://fairplay-api.onrender.com`.
   Health check: `GET /docs` should return the FastAPI docs page.

> Free tier spins down after ~15 min idle; the first request then cold-starts in
> ~30–50s. Fine for a demo; mention it when presenting.

## 2. Frontend on Vercel

1. Vercel → **Add New → Project** → import this repo.
2. **Root Directory: `frontend`** (Vercel auto-detects Vite: build `vite build`,
   output `dist`). No SPA rewrite needed (the app switches views in state, no router).
3. Add env var **`VITE_API_BASE`** = the Render URL from step 1.4
   (e.g. `https://fairplay-api.onrender.com`).
4. Deploy. Note the Vercel URL.

## 3. Close the CORS loop

Back in Render, set `CORS_ORIGINS` to the Vercel URL and redeploy the API (or it
picks up on next deploy). The browser calls are then allowed.

## Verify

Open the Vercel URL → **Train** tab → seat bots → Deal → play a hand → confirm the
coach streams. (First coach call after idle eats the API cold-start.)

## Local dev (unchanged)

`npm run dev` runs both: Vite on :5173, API on :8000. The frontend falls back to
`http://localhost:8000` when `VITE_API_BASE` is unset.
