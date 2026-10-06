import { useState } from 'react'
import { useInteraction } from './InteractionContext'
import type { InsightItem } from '../api'

export function InsightExplorer({ item, index }: { item: InsightItem; index: number }) {
  const [open, setOpen] = useState(false)
  const { shareView, notify } = useInteraction()
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`${item.title}\n\n${item.observation}\n\nMethodology: ${item.methodology}`)
      notify('Insight copied')
    } catch { notify('Copy unavailable') }
  }
  return <article className={`insight ${open ? 'is-expanded' : ''}`}>
    <div>
      <span className="insight-index">0{index + 1}</span>
      <h2>{item.title}</h2>
      <p className="observation">{item.observation}</p>
      {open && <div className="insight-evidence"><span className="narrative-label">Evidence path</span><p className="method-note">{item.methodology}</p><a className="button-link" href={item.href}>Open the underlying evidence →</a></div>}
      <div className="insight-actions">
        <button type="button" className="text-button" onClick={() => setOpen(!open)}>{open ? 'Hide evidence' : 'Inspect evidence'}</button>
        <button type="button" className="text-button" onClick={copy}>Copy insight</button>
        <button type="button" className="text-button" onClick={shareView}>Share view</button>
      </div>
    </div>
  </article>
}

