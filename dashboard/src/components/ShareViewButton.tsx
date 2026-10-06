import { useState } from 'react'

export function ShareViewButton() {
  const [status, setStatus] = useState('')

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setStatus('Link copied')
      window.setTimeout(() => setStatus(''), 1800)
    } catch {
      setStatus('Copy unavailable')
    }
  }

  return (
    <button className="button-link" type="button" onClick={copyLink} aria-label="Copy link to this view">
      {status || 'Copy view link'}
    </button>
  )
}
