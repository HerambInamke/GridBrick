const UK = 'Europe/London'

export const gw = (mw, digits = 1) => (mw == null ? '–' : (mw / 1000).toFixed(digits))
export const signedGw = (mw) => (mw == null ? '–' : `${mw > 0 ? '+' : ''}${gw(mw)}`)

export const ukTime = (iso) =>
  new Date(iso).toLocaleTimeString('en-GB', { timeZone: UK, hour: '2-digit', minute: '2-digit' })

export const ukDateTime = (iso) =>
  new Date(iso).toLocaleString('en-GB', {
    timeZone: UK, weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })

// Delivery days are plain YYYY-MM-DD strings; format at noon UTC so the weekday never shifts.
export const longDay = (d) =>
  new Date(`${d}T12:00:00Z`).toLocaleDateString('en-GB', { timeZone: UK, weekday: 'long', day: 'numeric', month: 'long' })

export const shortDay = (d) =>
  new Date(`${d}T12:00:00Z`).toLocaleDateString('en-GB', { timeZone: UK, weekday: 'short', day: 'numeric', month: 'short' })

export const prevDay = (d) => {
  const t = new Date(`${d}T12:00:00Z`)
  t.setUTCDate(t.getUTCDate() - 1)
  return t.toISOString().slice(0, 10)
}

export async function getJson(url) {
  // Empty by default (same-origin /api); set VITE_API_URL only if the API is hosted on another domain.
  const r = await fetch(`${import.meta.env.VITE_API_URL ?? ''}${url}`)
  if (!r.ok) throw new Error(`${url} failed: ${r.status} ${(await r.text()).slice(0, 200)}`)
  return r.json()
}
