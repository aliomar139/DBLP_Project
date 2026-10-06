import { useInteraction } from './InteractionContext'

export function FilterChips() {
  const { filters, removeFilter, clearFilters, shareView } = useInteraction()
  if (!filters.length) return null
  return <div className="exploration-bar" aria-label="Active exploration filters">
    <span className="exploration-label">Exploring</span>
    {filters.map(filter => <button key={filter.key} type="button" className="exploration-chip" onClick={() => removeFilter(filter.key)}>
      {filter.label}<span aria-hidden="true">×</span>
    </button>)}
    <button type="button" className="text-button" onClick={clearFilters}>Clear all</button>
    <button type="button" className="text-button" onClick={shareView}>Share view</button>
  </div>
}

