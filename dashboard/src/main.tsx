import { Component, StrictMode, type ErrorInfo, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import './styles/tokens.css'
import './intelligence.css'
import App from './App'

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('Dashboard render failed', error, info) }
  render() { return this.state.error ? <main className="error-screen"><h1>Dashboard could not render.</h1><p>{this.state.error.message}</p><button onClick={() => location.reload()}>Reload dashboard</button></main> : this.props.children }
}

createRoot(document.getElementById('root')!).render(<StrictMode><ErrorBoundary><App /></ErrorBoundary></StrictMode>)

