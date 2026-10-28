"""Pure analysis functions. Error convention: error = forecast - actual (MW).

Positive error = wind over-forecast = shortfall the desk must cover by buying more power.
"""
import math
import statistics
from bisect import bisect_right
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")
JAN_DAYS = [date(2026, 1, d) for d in range(1, 32)]
HORIZON_BUCKET_H = 6
MAX_HORIZON_H = 48


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Dataset:
    """Indexed view over raw rows: actuals {start: MW}, forecast runs {publish: {start: MW}}."""

    def __init__(self, actuals: list, forecasts: list):
        self.actuals = {ts(s): g for s, g in actuals}
        self.runs: dict[datetime, dict[datetime, float]] = {}
        for p, s, g in forecasts:
            self.runs.setdefault(ts(p), {})[ts(s)] = g
        self.publish_times = sorted(self.runs)

    def latest_run_at(self, cutoff: datetime) -> datetime | None:
        i = bisect_right(self.publish_times, cutoff)
        return self.publish_times[i - 1] if i else None


def delivery_window(day: date) -> tuple[datetime, datetime]:
    """UK-local calendar day as a UTC [start, end) interval (handles 23/25h clock-change days)."""
    start = datetime.combine(day, time(0), UK)
    end = datetime.combine(day + timedelta(days=1), time(0), UK)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def decision_cutoff(day: date, cutoff: time) -> datetime:
    """Decision for delivery day D is taken on D-1 at `cutoff` UK local time."""
    return datetime.combine(day - timedelta(days=1), cutoff, UK).astimezone(timezone.utc)


def summarize(errors: list[float], actuals: list[float]) -> dict | None:
    if len(errors) < 2:
        return None
    q = statistics.quantiles(errors, n=10, method="inclusive")
    mae = sum(abs(e) for e in errors) / len(errors)
    bias = sum(errors) / len(errors)
    mean_actual = sum(actuals) / len(actuals)
    return {
        "n": len(errors),
        "mae": mae,
        "rmse": math.sqrt(sum(e * e for e in errors) / len(errors)),
        "bias": bias,
        # In-sample: MAE if the period's mean bias were subtracted from every forecast.
        "mae_debiased": sum(abs(e - bias) for e in errors) / len(errors),
        "p10": q[0],
        "p50": q[4],
        "p90": q[8],
        "max_over": max(errors),
        "max_under": min(errors),
        "mean_actual": mean_actual,
        "nmae_pct": 100 * mae / mean_actual if mean_actual else None,
    }


def day_view(ds: Dataset, day: date, cutoff: time) -> dict:
    """Actuals vs the latest forecast that was available at the decision cutoff for one delivery day."""
    start, end = delivery_window(day)
    cut = decision_cutoff(day, cutoff)
    pub = ds.latest_run_at(cut)
    run = ds.runs.get(pub, {})
    points, errors, matched_actuals = [], [], []
    t = start
    while t < end:  # half-hourly grid; forecast exists only on the hour
        a, f = ds.actuals.get(t), run.get(t)
        points.append({"time": iso(t), "actual": a, "forecast": f})
        if a is not None and f is not None:
            errors.append(f - a)
            matched_actuals.append(a)
        t += timedelta(minutes=30)
    return {
        "date": day.isoformat(),
        "decision_cutoff": iso(cut),
        "forecast_publish_time": iso(pub) if pub else None,
        "forecast_age_hours": (cut - pub).total_seconds() / 3600 if pub else None,
        "points": points,
        "stats": summarize(errors, matched_actuals),
    }


def accuracy(ds: Dataset, cutoff: time) -> dict:
    """Month-level accuracy of the forecast the desk would actually have used (latest at D-1 cutoff)."""
    rows = []  # (day, uk_hour, error, actual)
    for day in JAN_DAYS:
        pub = ds.latest_run_at(decision_cutoff(day, cutoff))
        if pub is None:
            continue
        start, end = delivery_window(day)
        for t, f in ds.runs[pub].items():
            a = ds.actuals.get(t)
            if start <= t < end and a is not None:
                rows.append((day, t.astimezone(UK).hour, f - a, a))

    by_day = []
    for day in JAN_DAYS:
        e = [r[2] for r in rows if r[0] == day]
        if e:
            by_day.append({"date": day.isoformat(), "mae": sum(map(abs, e)) / len(e), "bias": sum(e) / len(e)})

    by_hour = []
    for h in range(24):
        e = [r[2] for r in rows if r[1] == h]
        if e:
            by_hour.append({"hour": h, "mae": sum(map(abs, e)) / len(e), "bias": sum(e) / len(e)})

    # Histogram of errors in 1 GW bins, for the distribution chart.
    hist: dict[int, int] = {}
    for r in rows:
        b = math.floor(r[2] / 1000)
        hist[b] = hist.get(b, 0) + 1
    histogram = [{"bin_mw": b * 1000, "count": hist[b]} for b in sorted(hist)]

    return {
        "cutoff": cutoff.strftime("%H:%M"),
        "overall": summarize([r[2] for r in rows], [r[3] for r in rows]),
        "by_day": by_day,
        "by_hour": by_hour,
        "histogram": histogram,
        "by_horizon": by_horizon(ds),
    }


def by_horizon(ds: Dataset) -> list[dict]:
    """MAE by forecast lead time (target - publish) across every Jan-2026 forecast point, all runs."""
    jan_start, _ = delivery_window(JAN_DAYS[0])
    _, jan_end = delivery_window(JAN_DAYS[-1])
    buckets: dict[int, list[float]] = {}
    for pub, run in ds.runs.items():
        for t, f in run.items():
            a = ds.actuals.get(t)
            h = (t - pub).total_seconds() / 3600
            if a is None or not (jan_start <= t < jan_end) or not (0 <= h < MAX_HORIZON_H):
                continue
            buckets.setdefault(int(h // HORIZON_BUCKET_H), []).append(f - a)
    return [
        {
            "horizon": f"{b * HORIZON_BUCKET_H}-{(b + 1) * HORIZON_BUCKET_H}h",
            "n": len(e),
            "mae": sum(map(abs, e)) / len(e),
            "bias": sum(e) / len(e),
        }
        for b, e in sorted(buckets.items())
    ]
