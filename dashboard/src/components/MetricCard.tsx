export const floorNum = (n: number | null | undefined): number => {
  if (n === null || n === undefined || !Number.isFinite(Number(n))) return 0
  return Math.floor(Number(n))
}

export const cleanDisplay = (val: string | number | null | undefined): string => {
  if (val === null || val === undefined) return ''
  if (typeof val === 'number') return full(val)
  return String(val).replace(/([0-9])([A-Za-z])/g, (_m, p1, p2) => `${p1} ${p2}`)
}

export const full = (n: number | null | undefined) => new Intl.NumberFormat('en-US').format(floorNum(n))
export const compact = (n: number | null | undefined) => {
  if (n === null || n === undefined || !Number.isFinite(Number(n))) return '0'
  const val = floorNum(n)
  const formatted = new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1
  }).format(val)
  return formatted.replace(/([0-9])([A-Za-z])/g, (_m, p1, p2) => `${p1} ${p2}`)
}
export const percent = (n: number | null | undefined) => n === null || n === undefined ? 'No baseline' : `${n > 0 ? '+' : ''}${new Intl.NumberFormat('en-US').format(floorNum(n))}%`

export function MetricCard({ label, value, detail, history, delta, explanation }: { label: string; value: string | number; detail?: string; history?: number[]; delta?: string; explanation?: string }) {
  const series = history?.filter(Number.isFinite) ?? []
  const min = Math.min(...series), range = Math.max(...series) - min || 1
  const points = series.map((n, i) => `${i * 100 / Math.max(1, series.length - 1)},${26 - (n - min) / range * 22}`).join(' ')
  const formattedValue = typeof value === 'number' ? full(value) : cleanDisplay(value)
  const formattedDetail = detail ? cleanDisplay(detail) : undefined
  const formattedDelta = delta ? cleanDisplay(delta) : undefined

  return (
    <article className="metric-card">
      <span>{label}{(explanation || detail) && <abbr tabIndex={0} title={explanation || detail} aria-label={explanation || detail}>i</abbr>}</span>
      <strong className={typeof formattedValue === 'string' && /[a-z]{4}/i.test(formattedValue) ? 'metric-text' : undefined}>
        {formattedValue}
      </strong>
      {formattedDelta && <span className="metric-delta">{formattedDelta}</span>}
      {series.length > 1 && (
        <svg className="metric-sparkline" viewBox="0 0 100 30" role="img" aria-label={`${label}, recent series: ${series.join(', ')}`}>
          <polyline points={points} fill="none" stroke="var(--accent-dark)" strokeWidth="2" />
        </svg>
      )}
      {formattedDetail && <small>{formattedDetail}</small>}
    </article>
  )
}
