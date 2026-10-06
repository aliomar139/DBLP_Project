import type { ReactNode } from 'react'
type Entry = { name?: string | number; value?: unknown; color?: string; dataKey?: unknown; payload?: Record<string, unknown> }
export function ChartTooltip({ active, payload, label, formatter, labelFormatter, shares = false }: {
 active?: boolean; payload?: readonly Entry[]; label?: ReactNode; shares?: boolean;
 formatter?: (value: any, name: any, entry: any, index: number, payload: any) => ReactNode;
 labelFormatter?: (label: any, payload: any) => ReactNode;
}) {
 if (!active || !payload?.length) return null
 const total = payload.reduce((sum, p) => sum + (typeof p.value === 'number' ? p.value : 0), 0)
 return <div className="chart-tooltip">
  {label != null && <strong>{labelFormatter ? labelFormatter(label, payload) : label}</strong>}
  {payload.map((p, i) => {
   const formatted = formatter?.(p.value, p.name, p, i, payload)
   const value = Array.isArray(formatted) ? formatted[0] : formatted ?? (typeof p.value === 'number' ? p.value.toLocaleString('en-US', {maximumFractionDigits:2}) : String(p.value ?? 'N/A'))
   const name = Array.isArray(formatted) ? formatted[1] : p.name
   return <div key={`${p.dataKey}-${i}`}><span><i style={{background:p.color ?? 'var(--accent)'}} />{name}</span><b>{value}{shares && total > 0 && typeof p.value === 'number' ? ` · ${(100*p.value/total).toFixed(1)}%` : ''}</b></div>
  })}
 </div>
}
