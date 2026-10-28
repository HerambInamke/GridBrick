# Plan: Wind Forecast Monitor (Elexon, Jan 2026)

## Domain decisions
- Purchase decisions made in Jan 2026 (on D-1) -> delivery days D = 2 Jan .. 1 Feb 2026 (Europe/London calendar days).
- Default decision time 09:00 UK: just before GB day-ahead gate closures (EPEX 09:20, N2EX 09:50).
- "Forecast available at decision time" = latest WINDFOR run with `publishTime <= D-1 cutoff` (default 09:00 UK, user-adjustable).
- WINDFOR is hourly, FUELHH (WIND) is half-hourly -> errors are computed on hourly points where both exist.
- Error = forecast - actual (positive = over-forecast = wind shortfall = must buy more).
- Accuracy metrics over the month: MAE, RMSE, bias, P10/P50/P90 error, error by hour-of-day, MAE vs forecast horizon.

## Architecture
- `backend/` FastAPI. `elexon.py` (fetch + snapshot fallback), `analysis.py` (pure functions, unit-tested), `main.py` (routes + serves built SPA).
- `frontend/` Vite + React + Recharts. Two views: Decision view (one delivery day), Accuracy view (whole month).
- `api/index.py` Vercel Python entrypoint re-exporting the FastAPI app. `vercel.json` builds the SPA.
- `Dockerfile` multi-stage (node build -> python runtime), `docker-compose.yml`.

## Dependency graph
elexon fetch -> analysis -> API routes -> frontend views -> Docker/Vercel -> README

## Tasks
1. Backend data layer + analysis (+ tests). Verify: pytest green; real-data smoke script.
2. API routes. Verify: uvicorn + curl both endpoints with real data.
   -- Checkpoint A: numbers sane (MAE in the hundreds-to-low-thousands MW range).
3. Frontend decision view. Verify: `npm run build` OK, page renders chart in browser.
4. Frontend accuracy view. Verify: build OK, metrics match API.
   -- Checkpoint B: full local flow works.
5. Docker + Vercel config. Verify: `docker build` + run, curl /api/health.
6. README (files, how to run, deploy link, AI-tool disclosure). Commit.
