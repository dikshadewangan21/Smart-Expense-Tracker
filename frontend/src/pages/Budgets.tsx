import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { money, pct } from '../lib/format'
import { useLookups } from '../lib/useLookups'

interface Line { category: string; limit: number; used: number; remaining: number; percent_used: number | null }
interface Status { total_limit: number; total_used: number; remaining: number; categories: Line[] }

const thisMonth = () => new Date().toLocaleDateString('en-CA').slice(0, 7)

function guidance(l: Line, daysLeft: number): string | null {
  const p = l.percent_used ?? 0
  if (p >= 100) return `${money(-l.remaining)} over. Pausing ${l.category.toLowerCase()} spending for the rest of the month would bring it back in line, or you can raise this limit.`
  if (p >= 90) return `${money(l.remaining)} left for ${daysLeft} days.`
  if (p >= 70) return `About ${money(l.remaining)} left, ${money(l.remaining / Math.max(daysLeft, 1))}/day for the remaining ${daysLeft} days.`
  return null
}

export default function Budgets() {
  const { categories, ready } = useLookups()
  const [month, setMonth] = useState(thisMonth())
  const [status, setStatus] = useState<Status | null | undefined>(undefined)
  const [total, setTotal] = useState('')
  const [limits, setLimits] = useState<Record<number, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const load = useCallback(() => {
    setError(null)
    api<{ budget: Status | null }>(`/budgets?month=${month}-01`).then((r) => {
      setStatus(r.budget)
      if (r.budget) setTotal(String(r.budget.total_limit))
    }).catch((e) => setError(e.message))
  }, [month])
  useEffect(load, [load])

  // Pre-fill the editor from the existing budget once both lookups and status are in.
  useEffect(() => {
    if (!status) { setLimits({}); return }
    const byName = new Map(categories.map((c) => [c.name, c.id]))
    const next: Record<number, string> = {}
    for (const l of status.categories) { const id = byName.get(l.category); if (id) next[id] = String(l.limit) }
    setLimits(next)
  }, [status, categories])

  const expenseCats = categories.filter((c) => c.kind === 'expense')
  const sum = Object.values(limits).reduce((a, v) => a + (Number(v) || 0), 0)
  const overTotal = sum > Number(total || 0)
  const [y, m] = month.split('-').map(Number)
  const now = new Date()
  const daysLeft = y === now.getFullYear() && m === now.getMonth() + 1 ? new Date(y, m, 0).getDate() - now.getDate() : 0

  async function save() {
    setError(null); setSaved(false)
    const lines = Object.entries(limits).filter(([, v]) => Number(v) > 0).map(([id, v]) => ({ category_id: Number(id), limit_amount: v }))
    try {
      await api('/budgets', { method: 'POST', body: JSON.stringify({ month: `${month}-01`, total_limit: total || '0', categories: lines }) })
      setSaved(true); load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save budget.') }
  }

  if (!ready || status === undefined) return <div className="skeleton h-64" aria-busy="true" />

  return (
    <div className="flex flex-col gap-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Budgets</h1>
        <input type="month" className="input w-auto" value={month} onChange={(e) => setMonth(e.target.value)} aria-label="Month" />
      </div>

      {status && (
        <section className="card">
          <div className="flex justify-between"><span>Overall</span>
            <span>{money(status.total_used)} of {money(status.total_limit)} · {money(status.remaining)} left</span></div>
          <ul className="flex flex-col gap-3 mt-3">
            {status.categories.map((l) => {
              const g = guidance(l, daysLeft)
              return (
                <li key={l.category}>
                  <div className="flex justify-between text-sm"><span>{l.category}</span><span className="muted">{money(l.used)} / {money(l.limit)} · {pct(l.percent_used)}</span></div>
                  <div className="h-2 rounded" style={{ background: 'var(--border)' }}>
                    <div className="h-2 rounded" style={{ width: `${Math.min(l.percent_used ?? 0, 100)}%`,
                      background: (l.percent_used ?? 0) >= 100 ? 'var(--bad)' : (l.percent_used ?? 0) >= 90 ? 'var(--warn)' : 'var(--accent)' }} />
                  </div>
                  {g && <p className="text-xs muted mt-1">{g}</p>}
                </li>
              )
            })}
          </ul>
        </section>
      )}

      <section className="card flex flex-col gap-3">
        <h2 className="font-semibold">{status ? 'Edit budget' : 'Create a budget for this month'}</h2>
        <p className="muted text-sm">Your plan is based on the numbers you enter and can be changed anytime.</p>
        <label className="text-sm">Total monthly budget
          <input className="input" inputMode="decimal" value={total} onChange={(e) => setTotal(e.target.value)} />
        </label>
        <div className="grid gap-2 sm:grid-cols-2">
          {expenseCats.map((c) => (
            <label key={c.id} className="text-sm">{c.name}
              <input className="input" inputMode="decimal" placeholder="No limit" value={limits[c.id] ?? ''}
                onChange={(e) => setLimits({ ...limits, [c.id]: e.target.value })} />
            </label>
          ))}
        </div>
        <p className="text-sm" style={{ color: overTotal ? 'var(--bad)' : 'var(--muted)' }}>
          Category limits total {money(sum)}{overTotal ? ' — more than the overall budget' : ''}.</p>
        {error && <p role="alert" className="text-sm" style={{ color: 'var(--bad)' }}>{error}</p>}
        {saved && <p role="status" className="text-sm" style={{ color: 'var(--good)' }}>Budget saved.</p>}
        <button className="btn self-start" disabled={!total || overTotal} onClick={save}>Save budget</button>
      </section>
    </div>
  )
}
