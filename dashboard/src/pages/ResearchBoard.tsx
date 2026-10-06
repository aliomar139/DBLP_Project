import { useEffect, useMemo, useState } from 'react'
import { ChartCard, PageHeader } from '../components/ChartCard'
import { clearBoard, readBoard, removeBoardItem, BOARD_EVENT, type BoardItem, type BoardItemType } from '../lib/researchBoard'

const labels: Record<BoardItemType, string> = {
  paper: 'Papers', researcher: 'Researchers', venue: 'Venues', topic: 'Topics'
}

export default function ResearchBoard() {
  const [items, setItems] = useState<BoardItem[]>(readBoard)
  const [filter, setFilter] = useState<'all' | BoardItemType>('all')

  useEffect(() => {
    const refresh = () => setItems(readBoard())
    window.addEventListener(BOARD_EVENT, refresh)
    return () => window.removeEventListener(BOARD_EVENT, refresh)
  }, [])

  const grouped = useMemo(() => {
    const visible = filter === 'all' ? items : items.filter(item => item.type === filter)
    return visible.reduce<Record<string, BoardItem[]>>((groups, item) => {
      ;(groups[item.type] ||= []).push(item)
      return groups
    }, {})
  }, [items, filter])

  return (
    <>
      <PageHeader title="Research board" description="Keep a short list of records you want to revisit.">
        {items.length > 0 && <button className="button-link" type="button" onClick={() => { clearBoard(); setItems([]) }}>Clear board</button>}
      </PageHeader>

      <div className="board-filter-row" role="group" aria-label="Filter saved records">
        {(['all', 'paper', 'researcher', 'venue', 'topic'] as const).map(type => (
          <button key={type} className={`segmented-button ${filter === type ? 'active' : ''}`} type="button" aria-pressed={filter === type} onClick={() => setFilter(type)}>
            {type === 'all' ? 'Everything' : labels[type]}
          </button>
        ))}
      </div>

      {!items.length ? (
        <div className="resource-state">
          <h2>Your board is empty</h2>
          <p>Save papers, researchers, venues, or topics as you browse.</p>
        </div>
      ) : !Object.keys(grouped).length ? (
        <div className="resource-state"><p>No saved records match this filter.</p></div>
      ) : (
        Object.entries(grouped).map(([type, records]) => (
          <ChartCard key={type} title={labels[type as BoardItemType]} description={`${records.length} saved record${records.length === 1 ? '' : 's'}.`}>
            <div className="research-board-grid">
              {records.map(item => (
                <article className="research-board-card" key={item.key}>
                  <span className="data-label">{labels[item.type]}</span>
                  <h3><a href={item.href}>{item.title}</a></h3>
                  {item.subtitle && <p>{item.subtitle}</p>}
                  <button className="text-button" type="button" onClick={() => setItems(removeBoardItem(item.key))}>Remove</button>
                </article>
              ))}
            </div>
          </ChartCard>
        ))
      )}
    </>
  )
}
