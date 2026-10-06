import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { api, type AssistantResponse, type AssistantStatus } from '../api'
import '../assistant.css'

const statusLabels: Record<AssistantStatus, string> = {
  answered: 'Answer', ambiguous: 'Choose a matching record', not_found: 'Not found in this DBLP dataset',
  insufficient_evidence: 'Insufficient DBLP evidence', outside_scope: 'Outside the assistant’s scope', unavailable: 'Information unavailable'
}

function renderAnswerLine(line: string) {
  return line.split(/(\*\*[^*]+\*\*)/g).map((part, index) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={index}>{part.slice(2, -2)}</strong>
      : part
  )
}

export default function Assistant() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<AssistantResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const [error, setError] = useState('')
  const [downloadingFormat, setDownloadingFormat] = useState<'xlsx' | 'csv' | null>(null)
  const sourceByRef = useMemo(() => new Map((result?.sources ?? []).map(source => [`${source.kind}:${source.id}`, source])), [result])

  async function downloadCatalog(format: 'xlsx' | 'csv') {
    const q = result?.export_query || query
    if (!q || downloadingFormat) return
    setDownloadingFormat(format)
    try {
      await api.exportAssistantCatalog(q, format)
    } catch (err) {
      console.error(err)
      alert(`Failed to generate ${format.toUpperCase()} catalog. Please retry.`)
    } finally {
      setDownloadingFormat(null)
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const question = query.trim()
    if (!question || loading) return
    setLoading(true)
    setStatusMessage('Analyzing question…')
    setError('')
    setResult(null)
    try {
      await api.assistantQueryStream(
        question,
        (init) => {
          setLoading(false)
          setResult({
            status: init.status,
            answer: '',
            request_id: init.request_id,
            sources: init.sources,
            calculations: init.calculations,
            claims: [],
            is_all_papers: init.is_all_papers,
            export_query: init.export_query,
          })
        },
        (token) => {
          setResult((prev) => (prev ? { ...prev, answer: prev.answer + token } : prev))
        },
        (status) => {
          setStatusMessage(status)
        }
      )
    } catch (cause) {
      try {
        const response = await api.assistantQuery(question)
        setResult(response)
      } catch {
        setError(cause instanceof Error ? cause.message : 'The assistant request failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return <div className="assistant-page">
    <header className="page-heading assistant-heading">
      <div><span className="eyebrow">DBLP research data</span><h1>Research assistant</h1>
        <p>Ask in your own words about publications, authors, venues, collaborations, and trends. Answers use fields stored in DBLP.</p>
      </div>
    </header>
    <form className="assistant-form" onSubmit={submit}>
      <label htmlFor="assistant-question">Your question</label>
      <textarea id="assistant-question" value={query} onChange={event => setQuery(event.target.value)}
        placeholder="Which authors published the most papers between 2020 and 2024?" maxLength={1000} minLength={3} required rows={3}
        disabled={loading} />
      <div className="assistant-form-footer"><span>{query.length}/1000</span>
        <button type="submit" disabled={loading || query.trim().length < 3}>{loading ? 'Checking DBLP…' : 'Ask'}</button>
      </div>
    </form>

    {loading && <div className="assistant-state" role="status" aria-live="polite"><span className="assistant-spinner" />{statusMessage || 'Reading approved DBLP evidence…'}</div>}
    {error && <div className="assistant-state assistant-error" role="alert"><strong>Request failed</strong><p>{error}</p></div>}
    {result && <section className={`assistant-result status-${result.status}`} aria-live="polite" aria-labelledby="assistant-result-title">
      <div className="assistant-result-top"><span className="assistant-status">{statusLabels[result.status]}</span>
        <span className="assistant-request-id">Request {result.request_id}</span></div>
      {result.is_all_papers && (
        <div className="assistant-catalog-actions">
          <div>
            <strong className="assistant-catalog-title">Complete Research Catalog ({result.sources.length} publications)</strong>
            <span className="assistant-catalog-description">Includes verified DBLP titles, publication years, venues, and available abstracts.</span>
          </div>
          <div className="assistant-download-actions">
            <button className="assistant-download-button" type="button" onClick={() => downloadCatalog('xlsx')} disabled={downloadingFormat !== null}>
              {downloadingFormat === 'xlsx' ? 'Generating Excel...' : 'Download Excel (.xlsx)'}
            </button>
            <button className="assistant-download-button" type="button" onClick={() => downloadCatalog('csv')} disabled={downloadingFormat !== null}>
              {downloadingFormat === 'csv' ? 'Generating CSV...' : 'Download CSV (.csv)'}
            </button>
          </div>
        </div>
      )}
      <h2 id="assistant-result-title">Response</h2>
      <div className="assistant-answer">{result.answer.split('\n').map((line, index) => <p key={`${index}-${line}`}>{line ? renderAnswerLine(line) : '\u00a0'}</p>)}</div>

      {result.claims.length > 0 && <div className="assistant-claims"><h3>Evidence for each statement</h3>
        {result.claims.map(claim => <article className="assistant-claim" key={claim.claim_id}>
          <p>{claim.text}</p>
          <div className="assistant-nearby-sources">
            {claim.source_refs.map(ref => { const source = sourceByRef.get(ref); return source ? <a key={ref} href={source.href}>{source.title}<span> ↗</span></a> : null })}
            {claim.calculation_refs.map(index => result.calculations[index] ? <span className="calculation-cite" key={index}>Calculation {index + 1}</span> : null)}
          </div>
        </article>)}
      </div>}

      {result.sources.length > 0 && <div className="assistant-source-list"><h3>DBLP records</h3><ul>{result.sources.map(source => <li key={`${source.kind}:${source.id}`}>
        <a href={source.href}>{source.title}<span aria-hidden="true"> ↗</span></a><span className="source-kind">{source.kind}</span>{source.detail && <p>{source.detail}</p>}
      </li>)}</ul></div>}

      {result.calculations.length > 0 && <details className="assistant-provenance"><summary>How numeric results were calculated</summary>
        {result.calculations.map((calculation, index) => <section key={`${calculation.database_version}:${index}`}>
          <h4>{calculation.description}</h4><p>Database version: <code>{calculation.database_version}</code></p>
          <dl><dt>Filters</dt><dd><pre>{JSON.stringify(calculation.filters, null, 2)}</pre></dd><dt>Result</dt><dd><pre>{JSON.stringify(calculation.result, null, 2)}</pre></dd></dl>
        </section>)}
      </details>}
      <p className="assistant-boundary">Answers use approved DBLP bibliographic fields. A title match alone does not establish a paper’s methods or findings.</p>
    </section>}
  </div>
}
