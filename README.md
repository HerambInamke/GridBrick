# Wind Forecast Monitor

A web app for a UK utility's day-ahead purchasing desk. For every purchase decision made in January 2026
(delivery days **2 January to 1 February 2026**) it shows
the **latest national wind forecast that was available when the purchase decision had to be made**
(the day before), next to what actually happened, and it **quantifies how wrong that forecast tends
to be** so the desk can size how much extra power to buy.

**Live app:** _add the Vercel URL here after deploying (see [Deploy](#deploy-to-vercel))_

Data: Elexon BMRS only. Actuals come from [FUELHH](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream) (`fuelType=WIND`, half-hourly)
and forecasts from [WINDFOR](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream) (hourly, about 8 runs a day).

## What the app shows

**Decision view (top of page).** Pick a delivery day and the time you decide on the day before (default 09:00 UK,
just ahead of the GB day-ahead auction gate closures: [EPEX at 09:20](https://www.epexspot.com/en) and
[Nord Pool N2EX at 09:50](https://support.nordpoolgroup.com/support/solutions/articles/8000088463-about-the-day-ahead-gb-auction)).
The app selects the most recent WINDFOR run published **at or before** that time, then shows:
- expected wind energy for the day (GWh), a "plan for at least" low case, and the actual outturn
- the forecast, the actual, and a shaded 80% likely range built from the period's measured error quantiles
- a note when the chosen forecast run does not cover the whole day (e.g. very early decision times)
- that day's error figures (mean error, bias, largest shortfall and surplus)

**Accuracy view (bottom of page).** All 31 delivery days, each scored against the forecast you would have used at the chosen decision time:
- MAE, bias, P90 error (shortfall to plan for in 9 hours out of 10), and MAE after removing the bias
- error by forecast lead time (0–48 h, all runs), by hour of day, error distribution, and error per day (click a bar to open that day)

### Method and definitions
| Term | Definition |
|---|---|
| Scope | Decisions made 1–31 Jan 2026 (on D-1), so delivery days D = 2 Jan to 1 Feb 2026 |
| Delivery day D | UK-local calendar day (`Europe/London`, so 23/25-hour clock-change days are handled) |
| Decision time | D-1 at the chosen UK time. Forecast used = latest `publishTime <= decision time` |
| Error | `forecast − actual` in MW. **Positive means less wind than forecast, so the desk must buy more** |
| Matching | WINDFOR is hourly and FUELHH half-hourly, so errors are computed on the hourly points where both exist |
| Likely range | `forecast − P90 error` to `forecast − P10 error`: where actual fell 80% of the time over the period |
| Day energy (GWh) | Summed over hours with both a forecast and an actual, so expected, low case and actual compare like for like |
| Lead time | `startTime − publishTime`, bucketed in 6 h steps from 0 to 48 h |

### Key findings (decisions in January 2026, 09:00 decision time, 744 matched hours)
- Typical error (MAE) is **2.0 GW**, about **18%** of mean wind output.
- The forecast ran **high by about 1.75 GW on average**: wind outturn usually came in below forecast. This holds at
  every lead time, including 0–6 h, and doesn't change when actuals are shifted ±30/60 min, so it is not a
  timestamp-alignment artefact. A likely contributor is that FUELHH is metered outturn *after* curtailment
  (constraint actions), while the forecast is closer to unconstrained potential. The data alone can't confirm this.
- In 90% of hours, the shortfall was below **4.2 GW** (P90 of error).
- Error grows with lead time: MAE goes from about 1.65 GW at 0–6 h to about 2.3 GW at 42–48 h.
- Removing the average bias would cut MAE to about 1.4 GW (in-sample figure, for reference only).
- The likely range and the low case use the same period they are evaluated on (in-sample). In production they would come from a trailing window.

## Repository layout
```
backend/
  app/elexon.py        Fetches FUELHH + WINDFOR from Elexon; 6 h in-memory cache; falls back to the bundled snapshot
  app/analysis.py      Pure analysis functions (forecast selection, metrics, horizon analysis), no I/O
  app/main.py          FastAPI routes: /api/health, /api/meta, /api/forecast, /api/accuracy; serves the SPA in Docker
  data/snapshot.json   Bundled copy of the period's data (used only if Elexon is unreachable)
  tests/               pytest unit + API tests
  requirements-dev.txt Test dependencies
frontend/
  src/App.jsx          Page layout, data loading, decision sentence and figures
  src/charts.jsx       Recharts charts (day chart with likely range, accuracy charts)
  src/format.js        GW / UK-time formatting, fetch helper
  src/styles.css       Styles
api/index.py           Vercel serverless entrypoint (re-exports the FastAPI app)
vercel.json            Vercel build + routing config
Dockerfile             Multi-stage build: Node builds the SPA, Python serves API + SPA
docker-compose.yml     One-command local run
requirements.txt       Runtime Python dependencies (FastAPI, uvicorn, tzdata)
docs/demo-script.md    Talk track for the demo video
tasks/                 Build plan and task list
```

## Running it

### Docker (recommended)
```bash
docker compose up --build
# open http://localhost:8000
```

### Local development
```bash
# backend (Python 3.11+)
python -m venv .venv
.venv/Scripts/activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r backend/requirements-dev.txt
cd backend && uvicorn app.main:app --reload --port 8000

# frontend (Node 20+), in a second terminal; /api is proxied to :8000
cd frontend && npm install && npm run dev
# open http://localhost:5173
```

### Tests
```bash
cd backend && python -m pytest -q
```

### Refreshing the bundled snapshot
```bash
cd backend && python -m app.elexon
```

## API
| Endpoint | Returns |
|---|---|
| `GET /api/health` | `{"status": "ok"}` |
| `GET /api/meta` | Available delivery days, default decision time, data source (`live` or `snapshot`) |
| `GET /api/forecast?date=2026-01-15&cutoff=09:00` | Half-hourly actuals + hourly forecast for the day, the chosen run's publish time, day stats |
| `GET /api/accuracy?cutoff=09:00` | Month metrics, by day, by hour, histogram, by lead time |

Dates outside 2026-01-02 to 2026-02-01, or malformed decision times, return `422`.

## Design decisions
- **Stdlib-only analysis.** The data is about 20k rows, so pandas would add 100+ MB to the serverless bundle and slow cold starts for no gain.
- **Live data with a snapshot fallback.** January 2026 is historical, so the result is stable. If Elexon is down, the app still works and the footer says which source is in use.
- **Pure analysis module.** `analysis.py` has no I/O, so every rule (forecast selection at the decision time, error sign, clock-change days, lead-time buckets) is unit-tested on small synthetic data.
- **One deployable.** In Docker, FastAPI serves both API and SPA. On Vercel, the SPA is static and `/api/*` is rewritten to the Python function.

## Deploy to Vercel
```bash
npx vercel login
npx vercel --prod
```
`vercel.json` builds the frontend and deploys `api/index.py` as a Python function. No environment variables are needed.

## Use of AI tools
This project was built with the help of an AI coding assistant (Claude Code), used for scaffolding, writing code and
tests, and reviewing the UI. All analysis choices and results were checked against the live Elexon data.
