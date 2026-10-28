"""Fetch wind actuals (FUELHH) and forecasts (WINDFOR) from Elexon BMRS, with a bundled snapshot fallback."""
import json
import time
import urllib.request
from pathlib import Path

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
SNAPSHOT = Path(__file__).resolve().parent.parent / "data" / "snapshot.json"
CACHE_TTL_S = 6 * 3600

# Delivery days are Jan 2026. Forecasts are fetched from 3 days earlier so every
# Jan target time has its full 0-48h forecast history for the horizon analysis.
ACTUALS_URL = f"{BASE}/FUELHH/stream?settlementDateFrom=2026-01-01&settlementDateTo=2026-01-31&fuelType=WIND"
FORECASTS_URL = f"{BASE}/WINDFOR/stream?publishDateTimeFrom=2025-12-29T00:00:00Z&publishDateTimeTo=2026-02-01T00:00:00Z"

_cache: dict = {}


def _get(url: str) -> list:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_live() -> dict:
    actuals = [[r["startTime"], r["generation"]] for r in _get(ACTUALS_URL) if r.get("fuelType") == "WIND"]
    forecasts = [[r["publishTime"], r["startTime"], r["generation"]] for r in _get(FORECASTS_URL)]
    if not actuals or not forecasts:
        raise ValueError("Elexon returned no data")
    return {"actuals": actuals, "forecasts": forecasts}


def load() -> dict:
    """Return {"actuals", "forecasts", "source", "fetched_at"}; live data cached, snapshot if Elexon is unreachable."""
    if _cache and time.time() - _cache["ts"] < CACHE_TTL_S:
        return _cache["data"]
    try:
        data = {**fetch_live(), "source": "live"}
    except Exception:
        if _cache:  # keep serving the last good live data rather than downgrading
            return _cache["data"]
        data = {**json.loads(SNAPSHOT.read_text()), "source": "snapshot"}
    data["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _cache.update(ts=time.time(), data=data)
    return data


if __name__ == "__main__":
    # Refresh the bundled snapshot: python -m app.elexon (from backend/)
    SNAPSHOT.write_text(json.dumps(fetch_live(), separators=(",", ":")))
    print(f"wrote {SNAPSHOT} ({SNAPSHOT.stat().st_size // 1024} KB)")
