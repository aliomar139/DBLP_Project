import { useState } from 'react'

export function exportTableToCSV<T extends Record<string, unknown>>(
  filename: string,
  rows: T[],
  columns: { key: string; label: string; value?: (r: T) => unknown }[]
) {
  if (!rows || rows.length === 0) return

  const header = columns.map(c => `"${c.label.replace(/"/g, '""')}"`).join(',')
  const body = rows.map(r => {
    return columns.map(c => {
      const val = c.value ? c.value(r) : r[c.key]
      const str = val === null || val === undefined ? '' : String(val)
      return `"${str.replace(/"/g, '""')}"`
    }).join(',')
  }).join('\n')

  const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + encodeURIComponent(header + '\n' + body)
  const link = document.createElement('a')
  link.setAttribute('href', csvContent)
  link.setAttribute('download', `${filename}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

export function ExportToolbar<T extends Record<string, unknown>>({
  title,
  data,
  columns,
  showPrint = true
}: {
  title: string
  data?: T[]
  columns?: { key: string; label: string; value?: (r: T) => unknown }[]
  showPrint?: boolean
}) {
  const [downloading, setDownloading] = useState(false)

  const handleExportCSV = () => {
    if (!data || !columns) return
    setDownloading(true)
    try {
      const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
      exportTableToCSV(slug, data, columns)
    } finally {
      setTimeout(() => setDownloading(false), 500)
    }
  }

  const handlePrint = () => {
    window.print()
  }

  return (
    <div className="export-toolbar" role="toolbar" aria-label="Export tools">
      {data && columns && (
        <button
          type="button"
          className="export-btn export-csv"
          onClick={handleExportCSV}
          disabled={downloading || !data.length}
          title="Export current table to CSV"
        >
          <span aria-hidden="true">↓</span>
          <span>{downloading ? 'Exporting...' : 'Export CSV'}</span>
        </button>
      )}

      {showPrint && (
        <button
          type="button"
          className="export-btn export-print"
          onClick={handlePrint}
          title="Print or save landscape report as PDF"
        >
          <span aria-hidden="true">⎙</span>
          <span>Print / Save PDF</span>
        </button>
      )}
    </div>
  )
}

