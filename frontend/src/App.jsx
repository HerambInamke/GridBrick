import { useEffect, useMemo, useState } from 'react'
import { DayChart, HorizonChart, HourChart, HistogramChart, DailyChart } from './charts.jsx'
import { getJson, gw, signedGw, longDay, prevDay, shortDay, ukDateTime, ukTime } from './format.js'

export default function App() {
  const [meta, setMeta] = useState(null)
  const [day, setDay] = useState('2026-01-15')
  const [cutoff, setCutoff] = useState('09:00')
  const [view, setView] = useState(null)
  const [acc, setAcc] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getJson('/api/meta').then(setMeta).catch((e) => setError(e.message))
  }, [])

  // `stale` drops responses that arrive after the user has already moved on.
  useEffect(() => {
    if (!/^\d{2}:\d{2}$/.test(cutoff)) return
    let stale = false
    setError(null)
    getJson(`/api/forecast?date=${day}&cutoff=${cutoff}`)
      .then((v) => !stale && setView(v))
      .catch((e) => !stale && setError(e.message))
    return () => { stale = true }
  }, [day, cutoff])

  useEffect(() => {
    if (!/^\d{2}:\d{2}$/.test(cutoff)) return
    let stale = false
    getJson(`/api/accuracy?cutoff=${cutoff}`)
      .then((a) => !stale && setAcc(a))
      .catch((e) => !stale && setError(e.message))
    return () => { stale = true }
  }, [cutoff])

  const days = meta?.days ?? []
  const idx = days.indexOf(day)
  const o = acc?.overall
  const loading = !error && (!view || !acc)

  // Uncertainty band from the period's error quantiles: actual = forecast - error.
  const plan = useMemo(() => {
    if (!view || !o) return null
    // Energy over hours with both a forecast and an actual, so the three figures compare like for like.
    const hourly = view.points.filter((p) => p.forecast != null && p.actual != null)
    if (!hourly.length) return null
    const sum = (f) => hourly.reduce((s, p) => s + f(p), 0) // hourly MW x 1h = MWh
    return {
      hours: hourly.length,
      expected: sum((p) => p.forecast),
      low: sum((p) => Math.max(0, p.forecast - o.p90)),
      actual: sum((p) => p.actual),
      points: view.points.map((p) => ({
        ...p,
        band: p.forecast == null ? null : [Math.max(0, p.forecast - o.p90), Math.max(0, p.forecast - o.p10)],
      })),
    }
  }, [view, o])

  return (
    <div className="page">
      <header className="masthead">
        <div>
          <h1>Wind forecast monitor</h1>
          <p className="sub">GB national wind generation for day-ahead purchase decisions made in January 2026</p>
        </div>
        <div className="controls">
          <label>
            Delivery day
            <span className="stepper">
              <button aria-label="Previous day" disabled={idx <= 0} onClick={() => setDay(days[idx - 1])}>‹</button>
              <select name="day" value={day} onChange={(e) => setDay(e.target.value)}>
                {days.map((d) => <option key={d} value={d}>{shortDay(d)}, decided {shortDay(prevDay(d))}</option>)}
              </select>
              <button aria-label="Next day" disabled={idx < 0 || idx >= days.length - 1} onClick={() => setDay(days[idx + 1])}>›</button>
            </span>
          </label>
          <label>
            Decision time on the day before (UK)
            <input name="cutoff" type="time" step="1800" value={cutoff} onChange={(e) => setCutoff(e.target.value)} />
          </label>
        </div>
      </header>

      {error && <p className="error" role="alert">Could not load data: {error}. Check the backend is running, then reload.</p>}

      {loading && <p className="loading">Loading Elexon data…</p>}

      <section className="hero" aria-live="polite">
        {view && !view.forecast_publish_time && (
          <p className="lede">No forecast had been published by {ukDateTime(view.decision_cutoff)}. Pick a later decision time.</p>
        )}
        {view?.forecast_publish_time && o && !plan && (
          <p className="lede">
            The latest forecast at {ukDateTime(view.decision_cutoff)} (published {ukDateTime(view.forecast_publish_time)})
            does not cover {longDay(view.date)}. Pick a later decision time.
          </p>
        )}
        {view?.forecast_publish_time && plan && (
          <>
            <p className="lede">
              For <strong>{longDay(view.date)}</strong>, the forecast you would have had at {ukTime(view.decision_cutoff)} expects{' '}
              <strong className="num">{gw(plan.expected, 0)} GWh</strong> of wind. On this period's track record,
              plan for at least <strong className="num shortfall">{gw(plan.low, 0)} GWh</strong>; the actual was{' '}
              <strong className="num">{gw(plan.actual, 0)} GWh</strong>.
            </p>
            <p className="provenance">
              Latest forecast before the decision: published {ukDateTime(view.forecast_publish_time)},{' '}
              {view.forecast_age_hours.toFixed(1)} h before your decision time.
              {plan.hours < 24 && ` It covers only ${plan.hours} hours of this day, so the energy figures are for those hours.`}
              {' '}The shaded band is where actual wind fell 80% of the time across all delivery days, for forecasts taken
              at this decision time (forecast minus the 10th–90th percentile error).
            </p>
            <DayChart points={plan.points} />
            {view.stats && (
              <dl className="figures">
                <div><dt>Mean error this day</dt><dd>{gw(view.stats.mae, 2)} GW</dd></div>
                <div><dt>Bias this day</dt><dd>{signedGw(view.stats.bias)} GW</dd></div>
                <div><dt>Largest shortfall</dt><dd>{view.stats.max_over > 0 ? `${gw(view.stats.max_over)} GW` : 'None'}</dd></div>
                <div><dt>Largest surplus</dt><dd>{view.stats.max_under < 0 ? `${gw(-view.stats.max_under)} GW` : 'None'}</dd></div>
              </dl>
            )}
          </>
        )}
      </section>

      {o && (
        <section className="accuracy">
          <h2>How far to trust the forecast</h2>
          <p className="lede-small">
            All 31 delivery days (2 Jan to 1 Feb), each scored against the forecast available at {acc.cutoff} the day before.
            Error is forecast minus actual, so a positive error means less wind arrived than forecast and you had to buy more.
          </p>

          <dl className="figures big">
            <div><dt>Typical error (MAE)</dt><dd>{gw(o.mae, 2)} GW</dd><span>{o.nmae_pct.toFixed(0)}% of mean output</span></div>
            <div><dt>Bias</dt><dd className={o.bias > 0 ? 'shortfall' : 'surplus'}>{signedGw(o.bias)} GW</dd><span>{o.bias > 0 ? 'forecast runs high' : 'forecast runs low'}</span></div>
            <div><dt>90% of hours, shortfall below</dt><dd className="shortfall">{gw(o.p90, 2)} GW</dd><span>P90 of error</span></div>
            <div><dt>MAE after removing bias</dt><dd>{gw(o.mae_debiased, 2)} GW</dd><span>in-sample, for reference</span></div>
          </dl>

          <div className="grid">
            <figure>
              <figcaption>Error grows with lead time</figcaption>
              <HorizonChart data={acc.by_horizon} />
              <p className="note">MAE by hours between publication and delivery, all forecast runs.</p>
            </figure>
            <figure>
              <figcaption>Error by hour of delivery</figcaption>
              <HourChart data={acc.by_hour} />
              <p className="note">MAE and bias by UK clock hour.</p>
            </figure>
            <figure>
              <figcaption>How errors are distributed</figcaption>
              <HistogramChart data={acc.histogram} />
              <p className="note">Hours per 1 GW error band. Red: wind came in below forecast.</p>
            </figure>
            <figure>
              <figcaption>Error by delivery day</figcaption>
              <DailyChart data={acc.by_day} selected={day} onSelect={setDay} />
              <p className="note">Select a bar to open that day above.</p>
            </figure>
          </div>
        </section>
      )}

      <footer>
        Data: Elexon BMRS, FUELHH (wind outturn) and WINDFOR (wind forecast).{' '}
        {meta && (meta.source === 'live'
          ? `Fetched live ${ukDateTime(meta.fetched_at)}.`
          : 'Elexon was unreachable, so a bundled snapshot is shown.')}
      </footer>
    </div>
  )
}
