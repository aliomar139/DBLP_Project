import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

export function QuickPreview({ href, kind, detail, children }: { href: string; kind: string; detail?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState({ left: 0, top: 0 })
  const timer = useRef<number | undefined>(undefined)
  const closeTimer = useRef<number | undefined>(undefined)
  const anchor = useRef<HTMLSpanElement>(null)

  const show = () => {
    window.clearTimeout(closeTimer.current)
    const rect = anchor.current?.getBoundingClientRect()
    if (!rect) return
    setPosition({ left: Math.min(Math.max(12, rect.left), window.innerWidth - 332), top: Math.min(rect.bottom + 10, window.innerHeight - 145) })
    timer.current = window.setTimeout(() => setOpen(true), 420)
  }
  const hide = () => {
    window.clearTimeout(timer.current)
    closeTimer.current = window.setTimeout(() => setOpen(false), 160)
  }

  useEffect(() => () => { window.clearTimeout(timer.current); window.clearTimeout(closeTimer.current) }, [])

  return <span className="preview-anchor" ref={anchor} onMouseEnter={show} onMouseLeave={hide}>
    <a href={href} onFocus={show} onBlur={hide}>{children}</a>
    {open && createPortal(<div className="quick-preview" style={{ left: position.left, top: position.top }} onMouseEnter={() => window.clearTimeout(closeTimer.current)} onMouseLeave={hide}>
      <span className="quick-preview-kind">{kind}</span>
      <strong>{children}</strong>
      {detail && <span>{detail}</span>}
      <a href={href}>Open {kind.toLowerCase()} →</a>
    </div>, document.body)}
  </span>
}
