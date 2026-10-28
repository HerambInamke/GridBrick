# Demo video talk track (max 10 min)

## Part 1: client pitch (about 5 min)
1. **The problem (30 s).** "You buy tomorrow's power today. The wind you can count on decides how much you buy.
   Too little and you pay imbalance prices; too much and you overpay. This pilot answers two questions:
   what did the forecast say when you had to decide, and how far can you trust it?"
2. **Decision view (90 s).** Open 15 January. Read the sentence: expected GWh, the plan-for-at-least figure, the actual.
   Point at the provenance line: the app picks the latest forecast published before your decision time, never one published after.
   Change the decision time from 09:00 to 16:00 and show the forecast run update.
3. **Likely range (45 s).** The shaded band is January's track record, applied to the day: in 8 hours out of 10, wind landed inside it.
4. **Trust (90 s).** Scroll down. MAE 2.1 GW (18% of output). The forecast ran about 1.9 GW high on average, so
   wind usually under-delivered. Plan for a shortfall of up to 4.3 GW to be covered 9 hours in 10. Error grows with lead time.
5. **Find the bad days (30 s).** Click the tallest bar in the per-day chart: the page jumps to that day.
6. **Next steps (15 s).** Solar, demand, and price data; alerts when a new forecast run moves materially; a bias-corrected forecast.

## Part 2: tech lead review (about 5 min)
1. **Architecture (60 s).** Repo layout from the README: FastAPI backend, React + Recharts frontend; Docker serves both,
   Vercel serves the SPA statically with `/api/*` going to `api/index.py`.
2. **Data layer (45 s).** `backend/app/elexon.py`: two Elexon calls for the whole month, 6 h cache, bundled snapshot fallback;
   `/api/meta` reports which source is live.
3. **Analysis (90 s).** `backend/app/analysis.py`: `Dataset` indexes runs by publish time; `latest_run_at` uses bisect;
   UK-local delivery windows via `zoneinfo`; error sign convention; hourly vs half-hourly matching; quantiles via `statistics`.
4. **Validation (45 s).** `backend/tests/test_analysis.py`: forecast selection before vs after the decision time, clock-change days,
   lead-time buckets, API validation (422s). Mention the alignment check that ruled out a timestamp bug behind the bias.
5. **Practices (60 s).** Pure functions with no I/O in analysis, stdlib only to keep cold starts small, pinned dependencies,
   multi-stage Docker build, accessible UI (labelled controls, keyboard focus, colour plus line style for series).
