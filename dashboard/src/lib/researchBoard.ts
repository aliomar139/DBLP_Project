export type BoardItemType = 'paper' | 'researcher' | 'venue' | 'topic'

export type BoardItem = {
  key: string
  type: BoardItemType
  id: string | number
  title: string
  subtitle?: string
  href: string
  addedAt: number
}

const STORAGE_KEY = 'dblp-research-board'
const BOARD_EVENT = 'dblp-research-board-change'
let memoryBoard: BoardItem[] = []

function readStoredValue() {
  try {
    return sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function writeStoredValue(value: BoardItem[]) {
  memoryBoard = value
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value))
  } catch {
    // The in-memory copy keeps the board usable when storage is blocked.
  }
}

export function readBoard(): BoardItem[] {
  try {
    const raw = readStoredValue()
    if (!raw) return memoryBoard
    const value = JSON.parse(raw)
    return Array.isArray(value) ? value : memoryBoard
  } catch {
    return memoryBoard
  }
}

export function isBoardItem(key: string) {
  return readBoard().some(item => item.key === key)
}

export function toggleBoardItem(item: Omit<BoardItem, 'addedAt'>) {
  const board = readBoard()
  const next = board.some(existing => existing.key === item.key)
    ? board.filter(existing => existing.key !== item.key)
    : [...board, { ...item, addedAt: Date.now() }]
  writeStoredValue(next)
  window.dispatchEvent(new Event(BOARD_EVENT))
  return next
}

export function removeBoardItem(key: string) {
  const next = readBoard().filter(item => item.key !== key)
  writeStoredValue(next)
  window.dispatchEvent(new Event(BOARD_EVENT))
  return next
}

export function clearBoard() {
  memoryBoard = []
  try { sessionStorage.removeItem(STORAGE_KEY) } catch {}
  window.dispatchEvent(new Event(BOARD_EVENT))
}

export { BOARD_EVENT }
