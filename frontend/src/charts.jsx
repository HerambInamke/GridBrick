import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { gw, shortDay, ukTime } from './format.js'

const C = { ink: '#14273A', forecast: '#2B7A99', band: '#2B7A99', short: '#C2364A', surplus: '#4F8A3B', grid: '#C9D3DA' }
const axis = { stroke: C.ink, fontSize: 12, tickLine: false }

// Ticks on whole 0.5 / 1 / 2 GW steps (data is in MW).
const gwTicks = (rows, ...keys) => {
  const vals = rows.flatMap((r) => keys.flatMap((k) => [r[k]].flat())).filter((v) => v != null)
  const lo = Math.min(0, ...vals), hi = Math.max(1, ...vals)
  const step = hi - lo > 8000 ? 2000 : hi - lo > 3000 ? 1000 : 500
  const first = Math.floor(lo / step)
  return Array.from({ length: Math.ceil(hi / step) - first + 1 }, (_, i) => (first + i) * step)
}

const tooltipFmt = (v, name) => {
  if (Array.isArray(v)) return [`${gw(v[0])}–${gw(v[1])} GW`, name]
  return [v == null ? '–' : `${gw(v, 2)} GW`, name]
}

export function DayChart({ points }) {
  const ticks = gwTicks(points, 'actual', 'forecast', 'band')
  return (
    <div className="chart hero-chart">
      <ResponsiveContainer width="100%" height={360}>
        <ComposedChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={C.grid} vertical={false} />
          <XAxis dataKey="time" tickFormatter={ukTime} interval={5} {...axis} />
          <YAxis tickFormatter={(v) => `${gw(v, 0)} GW`} ticks={ticks} domain={[ticks[0], ticks.at(-1)]} width={56} {...axis} />
          <Tooltip labelFormatter={ukTime} formatter={tooltipFmt} />
          <Legend verticalAlign="top" align="right" height={28} iconType="plainline" />
          <Area dataKey="band" name="Likely range (80%)" fill={C.band} fillOpacity={0.16} stroke="none" connectNulls isAnimationActive={false} />
          <Line dataKey="forecast" name="Forecast at decision time" stroke={C.forecast} strokeWidth={2.5} strokeDasharray="6 4" dot={false} connectNulls isAnimationActive={false} />
          <Line dataKey="actual" name="Actual" stroke={C.ink} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

export function HorizonChart({ data }) {
  const ticks = gwTicks(data, 'mae', 'bias')
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        <XAxis dataKey="horizon" {...axis} />
        <YAxis tickFormatter={(v) => gw(v, 1)} ticks={ticks} domain={[ticks[0], ticks.at(-1)]} width={40} {...axis} />
        <Tooltip formatter={tooltipFmt} />
        <Bar dataKey="mae" name="MAE" fill={C.forecast} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function HourChart({ data }) {
  const ticks = gwTicks(data, 'mae', 'bias')
  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        <XAxis dataKey="hour" tickFormatter={(h) => `${String(h).padStart(2, '0')}:00`} interval={5} {...axis} />
        <YAxis tickFormatter={(v) => gw(v, 1)} ticks={ticks} domain={[ticks[0], ticks.at(-1)]} width={40} {...axis} />
        <Tooltip labelFormatter={(h) => `${String(h).padStart(2, '0')}:00`} formatter={tooltipFmt} />
        <Legend verticalAlign="top" align="right" height={24} iconType="plainline" />
        <Bar dataKey="mae" name="MAE" fill={C.forecast} isAnimationActive={false} />
        <Line dataKey="bias" name="Bias" stroke={C.short} strokeWidth={2} dot={false} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

export function HistogramChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap={1}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        <XAxis dataKey="bin_mw" tickFormatter={(v) => `${v > 0 ? '+' : ''}${v / 1000}`} {...axis} />
        <YAxis width={40} {...axis} allowDecimals={false} />
        <Tooltip
          labelFormatter={(v) => `Error ${v / 1000} to ${v / 1000 + 1} GW`}
          formatter={(v) => [`${v} hours`, 'Count']}
        />
        <ReferenceLine x={0} stroke={C.ink} />
        <Bar dataKey="count" isAnimationActive={false}>
          {data.map((d) => <Cell key={d.bin_mw} fill={d.bin_mw >= 0 ? C.short : C.surplus} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function DailyChart({ data, selected, onSelect }) {
  const ticks = gwTicks(data, 'mae', 'bias')
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDay} interval={6} {...axis} />
        <YAxis tickFormatter={(v) => gw(v, 1)} ticks={ticks} domain={[ticks[0], ticks.at(-1)]} width={40} {...axis} />
        <Tooltip labelFormatter={shortDay} formatter={tooltipFmt} />
        <Bar dataKey="mae" name="MAE" cursor="pointer" isAnimationActive={false} onClick={(d) => onSelect(d.date)}>
          {data.map((d) => <Cell key={d.date} fill={d.date === selected ? C.ink : C.forecast} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
