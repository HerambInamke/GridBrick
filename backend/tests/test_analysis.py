from datetime import date, time

import pytest
from fastapi.testclient import TestClient

from app import analysis, elexon, main
from app.analysis import Dataset, accuracy, by_horizon, day_view, decision_cutoff, delivery_window, summarize


def make_ds():
    # Actuals: 1000 MW every half hour on 15 Jan.
    actuals = [[f"2026-01-15T{h:02d}:{m:02d}:00Z", 1000] for h in range(24) for m in (0, 30)]
    forecasts = []
    # Run published 14 Jan 07:30 (before 09:00 cutoff): over-forecasts by 200 MW.
    forecasts += [["2026-01-14T07:30:00Z", f"2026-01-15T{h:02d}:00:00Z", 1200] for h in range(24)]
    # Run published 14 Jan 09:30 (after cutoff): must be ignored with the 09:00 cutoff.
    forecasts += [["2026-01-14T09:30:00Z", f"2026-01-15T{h:02d}:00:00Z", 500] for h in range(24)]
    return Dataset(actuals, forecasts)


def test_picks_latest_run_before_cutoff_not_after():
    v = day_view(make_ds(), date(2026, 1, 15), time(9, 0))
    assert v["forecast_publish_time"] == "2026-01-14T07:30:00Z"
    assert v["decision_cutoff"] == "2026-01-14T09:00:00Z"
    assert v["forecast_age_hours"] == 1.5
    assert v["stats"]["bias"] == 200 and v["stats"]["mae"] == 200  # error = forecast - actual


def test_later_cutoff_picks_later_run():
    v = day_view(make_ds(), date(2026, 1, 15), time(10, 0))
    assert v["forecast_publish_time"] == "2026-01-14T09:30:00Z"
    assert v["stats"]["bias"] == -500


def test_day_view_grid_is_half_hourly_with_hourly_forecast():
    pts = day_view(make_ds(), date(2026, 1, 15), time(9, 0))["points"]
    assert len(pts) == 48
    assert pts[0]["forecast"] == 1200 and pts[1]["forecast"] is None and pts[1]["actual"] == 1000


def test_no_run_available_is_handled():
    v = day_view(make_ds(), date(2026, 1, 14), time(9, 0))  # no run published by 13 Jan 09:00
    assert v["forecast_publish_time"] is None and v["stats"] is None


def test_stale_run_that_does_not_cover_the_day():
    v = day_view(make_ds(), date(2026, 1, 20), time(9, 0))  # latest run is from 14 Jan, covers only 15 Jan
    assert v["forecast_publish_time"] == "2026-01-14T09:30:00Z"
    assert all(p["forecast"] is None for p in v["points"]) and v["stats"] is None


def test_delivery_window_uses_uk_local_time():
    s, e = delivery_window(date(2026, 3, 29))  # spring clock change: 23-hour day
    assert (e - s).total_seconds() == 23 * 3600
    assert decision_cutoff(date(2026, 7, 2), time(9)).isoformat() == "2026-07-01T08:00:00+00:00"  # BST


def test_delivery_days_match_january_decisions():
    days = analysis.DELIVERY_DAYS
    assert days[0] == date(2026, 1, 2) and days[-1] == date(2026, 2, 1) and len(days) == 31
    assert decision_cutoff(days[0], time(9)).date() == date(2026, 1, 1)
    assert decision_cutoff(days[-1], time(9)).date() == date(2026, 1, 31)


def test_summarize():
    s = summarize([-100, 0, 100, 200], [1000, 1000, 1000, 1000])
    assert s["mae"] == 100 and s["bias"] == 50 and s["nmae_pct"] == 10
    assert s["mae_debiased"] == 100  # |-150|,|-50|,|50|,|150| -> 100
    assert summarize([1], [1]) is None


def test_accuracy_and_horizon():
    acc = accuracy(make_ds(), time(9, 0))
    assert acc["overall"]["n"] == 24 and acc["overall"]["bias"] == 200
    assert [d["date"] for d in acc["by_day"]] == ["2026-01-15"]
    assert len(acc["by_hour"]) == 24
    hz = {b["horizon"]: b for b in by_horizon(make_ds())}
    # 07:30 run -> targets 15 Jan 00:00..23:00 are 16.5..39.5h ahead.
    assert hz["12-18h"]["n"] == 2 + 4  # 07:30 run: 16.5h, 17.5h; 09:30 run: 14.5h..17.5h
    assert sum(b["n"] for b in hz.values()) == 48


@pytest.fixture
def client(monkeypatch):
    raw = {"actuals": [], "forecasts": [], "source": "test", "fetched_at": "x"}
    ds = make_ds()
    monkeypatch.setattr(elexon, "load", lambda: raw)
    monkeypatch.setattr(main, "_ds", {"raw": raw, "ds": ds})
    return TestClient(main.app)


def test_api(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert len(client.get("/api/meta").json()["days"]) == 31
    r = client.get("/api/forecast", params={"date": "2026-01-15", "cutoff": "09:00"})
    assert r.status_code == 200 and r.json()["stats"]["bias"] == 200
    assert client.get("/api/forecast", params={"date": "2026-01-01"}).status_code == 422  # decided 31 Dec: out of scope
    assert client.get("/api/forecast", params={"date": "2026-02-01"}).status_code == 200  # decided 31 Jan: in scope
    assert client.get("/api/forecast", params={"date": "2026-01-15", "cutoff": "bad"}).status_code == 422
    assert client.get("/api/accuracy").json()["overall"]["n"] == 24


def test_api_headers(client):
    r = client.get("/api/meta", headers={"Origin": "https://elsewhere.example"})
    assert r.headers["access-control-allow-origin"] == "*"
    assert "s-maxage" in r.headers["cache-control"]
    assert "cache-control" not in client.get("/api/forecast", params={"date": "2026-01-01"}).headers  # errors are not cached


def test_snapshot_fallback(monkeypatch):
    monkeypatch.setattr(elexon, "_cache", {})
    monkeypatch.setattr(elexon, "fetch_live", lambda: (_ for _ in ()).throw(OSError("down")))
    data = elexon.load()
    assert data["source"] == "snapshot" and data["actuals"] and data["forecasts"]
