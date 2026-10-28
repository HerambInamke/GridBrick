from datetime import date, time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from . import analysis, elexon

app = FastAPI(title="Wind Forecast Monitor")
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
        "days": [d.isoformat() for d in analysis.JAN_DAYS],
        "default_cutoff": DEFAULT_CUTOFF,
        "source": raw["source"],
        "fetched_at": raw["fetched_at"],
    }


@app.get("/api/forecast")
def forecast(date_: date = Query(..., alias="date"), cutoff: str = DEFAULT_CUTOFF):
    if date_ not in analysis.JAN_DAYS:
        raise HTTPException(422, "date must be in January 2026")
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
