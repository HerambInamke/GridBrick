from datetime import date, time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import analysis, elexon

app = FastAPI(title="Wind Forecast Monitor")
# Same-origin in Docker and on Vercel; CORS only matters if the SPA is hosted elsewhere. Public read-only data.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])


@app.middleware("http")
async def cache_api(request: Request, call_next):
    # January 2026 is historical, so successful API responses can sit on the CDN for an hour.
    response = await call_next(request)
    if request.url.path.startswith("/api/") and response.status_code == 200:
        response.headers["Cache-Control"] = "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400"
    return response
DEFAULT_CUTOFF = "09:00"
_ds: dict = {}


def dataset() -> tuple[analysis.Dataset, dict]:
    raw = elexon.load()
    if _ds.get("raw") is not raw:  # rebuild the index only when the cache refreshed
        _ds.update(raw=raw, ds=analysis.Dataset(raw["actuals"], raw["forecasts"]))
    return _ds["ds"], raw


def parse_cutoff(cutoff: str) -> time:
    try:
        return time.fromisoformat(cutoff)
    except ValueError:
        raise HTTPException(422, "cutoff must be HH:MM")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    _, raw = dataset()
    return {
        "days": [d.isoformat() for d in analysis.DELIVERY_DAYS],
        "default_cutoff": DEFAULT_CUTOFF,
        "source": raw["source"],
        "fetched_at": raw["fetched_at"],
    }


@app.get("/api/forecast")
def forecast(date_: date = Query(..., alias="date"), cutoff: str = DEFAULT_CUTOFF):
    if date_ not in analysis.DELIVERY_DAYS:
        raise HTTPException(422, "date must be a delivery day for a January 2026 decision (2026-01-02 to 2026-02-01)")
    ds, _ = dataset()
    return analysis.day_view(ds, date_, parse_cutoff(cutoff))


@app.get("/api/accuracy")
def accuracy(cutoff: str = DEFAULT_CUTOFF):
    ds, _ = dataset()
    return analysis.accuracy(ds, parse_cutoff(cutoff))


# In Docker the built SPA is served by FastAPI; on Vercel the platform serves it.
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="spa")
