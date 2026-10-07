import { useNavigate, Link } from 'react-router-dom'
import { Sparkles, TrendingUp, TrendingDown, ArrowRight } from 'lucide-react'
import { money } from '../lib/format'

export interface Mover {
  category_id: number | null
  category: string
  current: number
  previous: number
  change: number
  change_pct: number | null
  is_new: boolean
  stopped: boolean
}

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
      <button
        className="w-full flex justify-between items-center text-left py-2 px-2 rounded-xl hover:bg-[var(--bg)] transition group cursor-pointer"
        onClick={onClick}
        aria-label={`Show ${m.category} transactions`}
      >
        <span className="text-xs font-medium text-[var(--fg)] truncate">
          {m.category}
          {m.is_new && <span className="muted font-normal text-[10px] ml-1.5 px-1.5 py-0.2 rounded bg-[var(--bg)] border">new</span>}
          {m.stopped && <span className="muted font-normal text-[10px] ml-1.5 px-1.5 py-0.2 rounded bg-[var(--bg)] border">none this time</span>}
        </span>
        <span
          style={{ color: up ? 'var(--bad)' : 'var(--good)' }}
          className="text-xs font-bold font-mono whitespace-nowrap ml-2"
        >
          {up ? '↑ +' : '↓ −'}
          {money(Math.abs(m.change), cur)}
          {m.change_pct !== null && (
            <span className="text-[10px] opacity-80 ml-1">
              ({m.change_pct > 0 ? '+' : ''}{Math.round(m.change_pct)}%)
            </span>
          )}
        </span>
      </button>
    </li>
  )
}

/** Every sentence here comes from the backend; this only lays it out cleanly. */
export default function WhatChanged({ data, currency }: { data: WhatChangedData; currency: string }) {
  const nav = useNavigate()
  const open = (m: Mover) => {
    const q = new URLSearchParams({ type: 'expense', date_from: data.period.start, date_to: data.period.end })
    if (m.category_id === null) q.set('uncategorized', 'true')
    else q.set('category_id', String(m.category_id))
    nav(`/transactions?${q}`)
  }

  return (
    <section
      className="card p-4 sm:p-5 rounded-2xl border shadow-xs"
      style={{ borderColor: 'var(--border)' }}
      aria-label="What changed"
    >
      <div className="flex items-center justify-between pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
        <div>
          <h2 className="font-bold text-sm tracking-tight flex items-center gap-1.5">
            <Sparkles size={16} className="text-accent" />
            <span>What changed this month?</span>
          </h2>
          <p className="text-xs muted mt-0.5">{data.comparison_note}</p>
        </div>
        <Link
          to="/analytics"
          className="text-xs font-semibold text-accent hover:underline flex items-center gap-1"
        >
          <span>See details</span>
          <ArrowRight size={13} />
        </Link>
      </div>

      {!data.comparable ? (
        <div className="py-4 text-center">
          <p className="text-xs muted">{data.headline}</p>
        </div>
      ) : (
        <div className="mt-3 flex flex-col gap-3">
          <div>
            <p className="text-sm font-semibold text-[var(--fg)]">{data.headline}</p>
            {data.drivers_sentence && (
              <p className="text-xs muted mt-0.5 leading-relaxed">{data.drivers_sentence}</p>
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2 pt-1">
            <div className="flex flex-col gap-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-bad flex items-center gap-1 px-1">
                <TrendingUp size={13} /> Spending Increased
              </span>
              {data.increases.length === 0 ? (
                <p className="muted text-xs p-2">No categories increased.</p>
              ) : (
                <ul className="flex flex-col divide-y divide-[var(--border)]/40">
                  {data.increases.slice(0, 5).map((m) => (
                    <Row key={`u${m.category_id}${m.category}`} m={m} cur={currency} onClick={() => open(m)} />
                  ))}
                </ul>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-good flex items-center gap-1 px-1">
                <TrendingDown size={13} /> Spending Decreased
              </span>
              {data.decreases.length === 0 ? (
                <p className="muted text-xs p-2">No categories decreased.</p>
              ) : (
                <ul className="flex flex-col divide-y divide-[var(--border)]/40">
                  {data.decreases.slice(0, 5).map((m) => (
                    <Row key={`d${m.category_id}${m.category}`} m={m} cur={currency} onClick={() => open(m)} />
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
