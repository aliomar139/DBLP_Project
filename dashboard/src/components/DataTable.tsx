import { useMemo, useState, type ReactNode } from 'react'
export type Column<T> = {
  key: string
  label: string
  render: (row: T, index: number) => ReactNode
  value?: (row: T) => string | number | null
  numeric?: boolean
  width?: string | number
  minWidth?: string | number
  maxWidth?: string | number
  className?: string
  align?: 'left' | 'center' | 'right'
}
function renderHeaderLabel(label: string | ReactNode, sortIcon?: ReactNode) {
  if (typeof label === 'string') {
    const match = label.match(/^(.*?)\s*(\([^)]+\))\s*$/)
    if (match) {
      const [, main, paren] = match
      return (
        <span className="th-multiline">
          <span className="th-title">
            <span>{main}</span>
            {sortIcon}
          </span>
          <span className="th-sub">{paren}</span>
        </span>
      )
    }
  }
  return (
    <>
      {label}
      {sortIcon}
    </>
  )
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  caption,
  sort,
  onSort,
  pagination,
  actions,
  className,
  tableLayout
}: {
  rows: T[]
  columns: Column<T>[]
  rowKey: (row: T) => string | number
  caption: string
  sort?: { key: string; order: 'asc' | 'desc' }
  onSort?: (key: string) => void
  pagination?: false | { total: number; offset: number; limit: number; onChange: (offset: number, limit: number) => void }
  actions?: (row: T) => ReactNode
  className?: string
  tableLayout?: 'auto' | 'fixed'
}) {
  const [local, setLocal] = useState<{ key: string; order: 'asc' | 'desc' }>()
  const [page, setPage] = useState(0)
  const [size, setSize] = useState(20)
  const selected = sort ?? local
  const ordered = useMemo(() => {
    const col = columns.find(c => c.key === local?.key)
    if (onSort || !local || !col?.value) return rows
    return [...rows].sort((a, b) => {
      const x = col.value!(a), y = col.value!(b)
      if (x === null) return y === null ? 0 : 1
      if (y === null) return -1
      const result = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))
      return local.order === 'asc' ? result : -result
    })
  }, [rows, columns, local, onSort])
  const change = (key: string) => {
    setPage(0)
    onSort ? onSort(key) : setLocal({ key, order: local?.key === key && local.order === 'desc' ? 'asc' : 'desc' })
  }
  const remote = pagination || undefined
  const total = remote?.total ?? rows.length, limit = remote?.limit ?? size
  const offset = remote?.offset ?? Math.min(page * size, Math.max(0, Math.ceil(total / size) - 1) * size)
  const enabled = pagination !== false && (!!remote || total > 20)
  const visible = enabled && !remote ? ordered.slice(offset, offset + limit) : ordered
  const jump = (next: number, newSize = limit) => {
    if (remote) remote.onChange(next, newSize)
    else { setSize(newSize); setPage(Math.floor(next / newSize)) }
  }
  return (
    <>
      <div className={`table-scroll ${className ?? ''}`} tabIndex={0} role="region" aria-label={caption}>
        <table style={tableLayout ? { tableLayout } : undefined}>
          <caption className="sr-only">{caption}</caption>
          <colgroup>
            {columns.map(c => (
              <col
                key={c.key}
                style={{
                  width: typeof c.width === 'number' ? `${c.width}px` : c.width,
                  minWidth: typeof c.minWidth === 'number' ? `${c.minWidth}px` : c.minWidth,
                  maxWidth: typeof c.maxWidth === 'number' ? `${c.maxWidth}px` : c.maxWidth
                }}
              />
            ))}
            {actions && <col style={{ width: '120px' }} />}
          </colgroup>
          <thead>
            <tr>
              {columns.map(c => (
                <th
                  key={c.key}
                  className={`${c.numeric ? 'numeric' : ''} ${c.className ?? ''}`}
                  style={{
                    width: typeof c.width === 'number' ? `${c.width}px` : c.width,
                    minWidth: typeof c.minWidth === 'number' ? `${c.minWidth}px` : c.minWidth,
                    maxWidth: typeof c.maxWidth === 'number' ? `${c.maxWidth}px` : c.maxWidth,
                    textAlign: c.align
                  }}
                  aria-sort={selected?.key === c.key ? (selected.order === 'asc' ? 'ascending' : 'descending') : undefined}
                >
                  {c.value || onSort ? (
                    <button className="sort-button" onClick={() => change(c.key)}>
                      {renderHeaderLabel(
                        c.label,
                        <span aria-hidden="true">{selected?.key === c.key ? (selected.order === 'asc' ? ' ↑' : ' ↓') : ' ↕'}</span>
                      )}
                    </button>
                  ) : (
                    renderHeaderLabel(c.label)
                  )}
                </th>
              ))}
              {actions && <th>Quick actions</th>}
            </tr>
          </thead>
          <tbody>
            {visible.map((r, i) => (
              <tr key={rowKey(r)}>
                {columns.map(c => (
                  <td
                    key={c.key}
                    className={`${c.numeric ? 'numeric' : ''} ${c.className ?? ''}`}
                    style={{
                      width: typeof c.width === 'number' ? `${c.width}px` : c.width,
                      textAlign: c.align
                    }}
                  >
                    {c.render(r, i + (enabled && !remote ? offset : 0))}
                  </td>
                ))}
                {actions && <td className="row-action">{actions(r)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="empty-state">No records match this selection.</p>}
      </div>
      {enabled && (
        <nav className="table-pagination" aria-label={`${caption} pagination`}>
          <span aria-live="polite">Showing {total ? offset + 1 : 0}–{Math.min(offset + visible.length, total)} of {total.toLocaleString()} results</span>
          <label>Rows <select aria-label={`${caption} rows per page`} value={limit} onChange={e => jump(0, Number(e.target.value))}>{[10, 20, 50, 100].map(n => <option key={n}>{n}</option>)}</select></label>
          <button disabled={offset === 0} onClick={() => jump(Math.max(0, offset - limit))}>Previous</button>
          <label>Page <input key={`${offset}-${limit}`} type="number" min={1} max={Math.max(1, Math.ceil(total / limit))} defaultValue={Math.floor(offset / limit) + 1} aria-label={`${caption} page number`} onBlur={e => { const n = Number(e.target.value); if (Number.isInteger(n) && n >= 1 && n <= Math.ceil(total / limit)) jump((n - 1) * limit); else e.target.value = String(Math.floor(offset / limit) + 1) }} onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur() }} /></label>
          <span>of {Math.max(1, Math.ceil(total / limit)).toLocaleString()}</span>
          <button disabled={offset + limit >= total} onClick={() => jump(offset + limit)}>Next</button>
        </nav>
      )}
    </>
  )
}
