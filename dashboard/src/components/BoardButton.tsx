import { useEffect, useState } from 'react'
import { BOARD_EVENT, isBoardItem, toggleBoardItem, type BoardItem } from '../lib/researchBoard'

export function BoardButton({ item }: { item: Omit<BoardItem, 'addedAt'> }) {
  const [saved, setSaved] = useState(() => isBoardItem(item.key))

  useEffect(() => {
    const refresh = () => setSaved(isBoardItem(item.key))
    window.addEventListener(BOARD_EVENT, refresh)
    return () => window.removeEventListener(BOARD_EVENT, refresh)
  }, [item.key])

  return (
    <button className="button-link" type="button" onClick={() => { const next = toggleBoardItem(item); setSaved(next.some(entry => entry.key === item.key)) }}>
      {saved ? 'Remove from board' : 'Save to board'}
    </button>
  )
}
