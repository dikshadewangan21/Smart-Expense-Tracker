import { useNavigate } from 'react-router-dom'
import { money } from '../lib/format'
import { Empty } from '../components/ui'

export interface Mover { category_id: number | null; category: string; current: number; previous: number; change: number; change_pct: number | null; is_new: boolean; stopped: boolean }
export interface WhatChangedData {
  period: { start: string; end: string; label: string }
  comparison_note: string
  comparable: boolean
  spending: { current: number; previous: number; change: number; change_pct: number | null }
  income: { current: number; previous: number; change: number; change_pct: number | null }
  increases: Mover[]
  decreases: Mover[]
  headline: string
  drivers_sentence: string | null
}

function Row({ m, cur, onClick }: { m: Mover; cur: string; onClick: () => void }) {
  const up = m.change > 0
  return (
    <li>
      <button className="w-full flex justify-between gap-2 text-left text-sm py-1 hover:underline" onClick={onClick}
        aria-label={`Show ${m.category} transactions`}>
        <span>{m.category}{m.is_new && <span className="muted"> · new</span>}{m.stopped && <span className="muted"> · none this time</span>}</span>
        <span style={{ color: up ? 'var(--bad)' : 'var(--good)' }} className="whitespace-nowrap">
          {up ? '+' : '−'}{money(Math.abs(m.change), cur)}{m.change_pct !== null && ` (${m.change_pct > 0 ? '+' : ''}${Math.round(m.change_pct)}%)`}
        </span>
      </button>
    </li>
  )
}

/** Every sentence here comes from the backend; this only lays it out. */
export default function WhatChanged({ data, currency }: { data: WhatChangedData; currency: string }) {
  const nav = useNavigate()
  const open = (m: Mover) => {
    const q = new URLSearchParams({ type: 'expense', date_from: data.period.start, date_to: data.period.end })
    if (m.category_id === null) q.set('uncategorized', 'true'); else q.set('category_id', String(m.category_id))
    nav(`/transactions?${q}`)
  }
  return (
    <section className="card" aria-label="What changed">
      <h2 className="font-semibold">What changed?</h2>
      <p className="muted text-xs mb-2">{data.comparison_note}</p>
      {!data.comparable ? <Empty>{data.headline}</Empty> : (
        <>
          <p className="text-sm font-medium">{data.headline}</p>
          {data.drivers_sentence && <p className="text-sm muted">{data.drivers_sentence}</p>}
          <div className="grid gap-4 md:grid-cols-2 mt-3">
            <div>
              <h3 className="text-xs uppercase muted mb-1">Went up</h3>
              {data.increases.length === 0 ? <p className="muted text-sm">Nothing went up.</p> :
                <ul>{data.increases.slice(0, 5).map((m) => <Row key={`u${m.category_id}${m.category}`} m={m} cur={currency} onClick={() => open(m)} />)}</ul>}
            </div>
            <div>
              <h3 className="text-xs uppercase muted mb-1">Went down</h3>
              {data.decreases.length === 0 ? <p className="muted text-sm">Nothing went down.</p> :
                <ul>{data.decreases.slice(0, 5).map((m) => <Row key={`d${m.category_id}${m.category}`} m={m} cur={currency} onClick={() => open(m)} />)}</ul>}
            </div>
          </div>
        </>
      )}
    </section>
  )
}
