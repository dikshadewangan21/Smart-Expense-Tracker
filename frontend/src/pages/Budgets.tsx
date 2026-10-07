import { useCallback, useEffect, useState } from 'react'
import {
  PiggyBank, ChevronLeft, ChevronRight, Plus, Sliders, Calendar
} from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money, pct } from '../lib/format'
import { useLookups } from '../lib/useLookups'
import { useToast } from '../components/Toast'
import { ErrorBox } from '../components/ui'

interface Line {
  category: string
  limit: number
  used: number
  remaining: number
  percent_used: number | null
}

interface Status {
  total_limit: number
  total_used: number
  remaining: number
  categories: Line[]
}

const thisMonth = () => new Date().toLocaleDateString('en-CA').slice(0, 7)

function getFriendlyBudgetCopy(l: Line, daysLeft: number, cur: string): { message: string; tone: 'good' | 'warn' | 'bad' } {
  const p = l.percent_used ?? 0
  if (p >= 100) {
    const overAmt = Math.abs(l.remaining)
    return {
      message: `You've exceeded your ${l.category} budget by ${money(overAmt, cur)}. You can adjust your limit or pause spending for the rest of the month.`,
      tone: 'bad',
    }
  }
  if (p >= 90) {
    return {
      message: `Heads up: You're close to your ${l.category} limit with ${money(l.remaining, cur)} left for ${daysLeft} days.`,
      tone: 'warn',
    }
  }
  if (p >= 70) {
    const dailyPace = daysLeft > 0 ? l.remaining / daysLeft : l.remaining
    return {
      message: `You're getting close to your ${l.category} budget. Spending about ${money(dailyPace, cur)}/day keeps you on track.`,
      tone: 'warn',
    }
  }
  return {
    message: `${money(l.remaining, cur)} available for the remaining ${daysLeft} days. Looking healthy!`,
    tone: 'good',
  }
}

export default function Budgets() {
  const { user } = useAuth()
  const cur = user?.currency ?? 'INR'
  const { toast } = useToast()
  const { categories, ready } = useLookups()

  const [month, setMonth] = useState(thisMonth())
  const [status, setStatus] = useState<Status | null | undefined>(undefined)
  const [total, setTotal] = useState('')
  const [limits, setLimits] = useState<Record<number, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [showEditor, setShowEditor] = useState(false)

  const load = useCallback(() => {
    setError(null)
    api<{ budget: Status | null }>(`/budgets?month=${month}-01`)
      .then((r) => {
        setStatus(r.budget)
        if (r.budget) {
          setTotal(String(r.budget.total_limit))
        } else {
          setTotal('')
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load budget.'))
  }, [month])

  useEffect(() => {
    load()
  }, [load])

  // Pre-fill editor from existing budget
  useEffect(() => {
    if (!status) {
      setLimits({})
      return
    }
    const byName = new Map(categories.map((c) => [c.name, c.id]))
    const next: Record<number, string> = {}
    for (const l of status.categories) {
      const id = byName.get(l.category)
      if (id) next[id] = String(l.limit)
    }
    setLimits(next)
  }, [status, categories])

  const expenseCats = categories.filter((c) => c.kind === 'expense')
  const sum = Object.values(limits).reduce((a, v) => a + (Number(v) || 0), 0)
  const overTotal = sum > Number(total || 0)

  const [y, m] = month.split('-').map(Number)
  const now = new Date()
  const daysInMonth = new Date(y, m, 0).getDate()
  const daysLeft =
    y === now.getFullYear() && m === now.getMonth() + 1
      ? Math.max(0, daysInMonth - now.getDate())
      : 0

  async function save() {
    setError(null)
    setSaving(true)
    const lines = Object.entries(limits)
      .filter(([, v]) => Number(v) > 0)
      .map(([id, v]) => ({ category_id: Number(id), limit_amount: v }))

    try {
      await api('/budgets', {
        method: 'POST',
        body: JSON.stringify({
          month: `${month}-01`,
          total_limit: total || '0',
          categories: lines,
        }),
      })
      toast.success('Budget saved successfully!')
      setShowEditor(false)
      load()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Could not save budget.'
      setError(msg)
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  // Quick navigation between months
  const shiftMonth = (offset: number) => {
    const [currY, currM] = month.split('-').map(Number)
    const d = new Date(currY, currM - 1 + offset, 1)
    setMonth(d.toLocaleDateString('en-CA').slice(0, 7))
  }

  if (!ready || status === undefined) {
    return (
      <div className="flex flex-col gap-4 max-w-4xl" aria-busy="true">
        <div className="skeleton h-8 w-48 rounded-lg" />
        <div className="skeleton h-44 rounded-2xl" />
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="skeleton h-36 rounded-2xl" />
          <div className="skeleton h-36 rounded-2xl" />
        </div>
      </div>
    )
  }

  const overallPct = status && status.total_limit > 0 ? (status.total_used / status.total_limit) * 100 : 0
  const isOverallOver = status && status.remaining < 0

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      {/* Page Header & Month Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Budgets</h1>
          <p className="text-xs sm:text-sm muted mt-0.5">
            Set guardrails and stay intentional with your spending
          </p>
        </div>

        {/* Month Selector Bar */}
        <div className="flex items-center gap-1.5 self-start sm:self-auto bg-[var(--card)] p-1 rounded-xl border" style={{ borderColor: 'var(--border)' }}>
          <button
            onClick={() => shiftMonth(-1)}
            className="p-1.5 rounded-lg hover:bg-[var(--bg)] muted hover:text-[var(--fg)]"
            title="Previous month"
            aria-label="Previous month"
          >
            <ChevronLeft size={16} />
          </button>
          <input
            type="month"
            className="input bg-transparent border-0 text-xs font-semibold py-1 px-2 focus:ring-0 shadow-none cursor-pointer"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            aria-label="Select month"
          />
          <button
            onClick={() => shiftMonth(1)}
            className="p-1.5 rounded-lg hover:bg-[var(--bg)] muted hover:text-[var(--fg)]"
            title="Next month"
            aria-label="Next month"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {error && <ErrorBox message={error} onRetry={load} />}

      {/* Main Budget Visual Status (When budget exists) */}
      {status ? (
        <div className="flex flex-col gap-5">
          {/* Overall Month Summary Card */}
          <div
            className="card p-5 sm:p-6 rounded-2xl border shadow-sm flex flex-col gap-4"
            style={{ borderColor: 'var(--border)' }}
          >
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-muted">
                  Overall Monthly Spending
                </span>
                <div className="text-2xl sm:text-3xl font-extrabold tracking-tight mt-1">
                  {money(status.total_used, cur)}{' '}
                  <span className="text-sm sm:text-base font-normal muted">
                    of {money(status.total_limit, cur)}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowEditor(!showEditor)}
                  className="btn btn-secondary text-xs px-3 py-2 rounded-xl flex items-center gap-1.5 font-semibold"
                >
                  <Sliders size={14} />
                  <span>{showEditor ? 'Close Editor' : 'Edit Limits'}</span>
                </button>
              </div>
            </div>

            {/* Overall Progress Bar */}
            <div className="flex flex-col gap-1.5">
              <div
                className="h-3 rounded-full overflow-hidden bg-[var(--border)]"
                role="progressbar"
                aria-valuenow={Math.round(overallPct)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Overall budget usage"
              >
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(overallPct, 100)}%`,
                    backgroundColor:
                      overallPct >= 100 ? 'var(--bad)' : overallPct >= 90 ? 'var(--warn)' : 'var(--accent)',
                  }}
                />
              </div>

              <div className="flex items-center justify-between text-xs font-medium pt-1">
                <span style={{ color: isOverallOver ? 'var(--bad)' : 'var(--good)' }}>
                  {isOverallOver
                    ? `${money(Math.abs(status.remaining), cur)} over budget`
                    : `${money(status.remaining, cur)} remaining`}
                </span>
                <span className="muted font-mono">{pct(overallPct)} used</span>
                <span className="muted flex items-center gap-1">
                  <Calendar size={13} />
                  {daysLeft} days remaining
                </span>
              </div>
            </div>
          </div>

          {/* Category Budgets Grid */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-bold tracking-tight">Category Breakdown</h2>
              <span className="text-xs muted">{status.categories.length} category budgets active</span>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {status.categories.map((l) => {
                const p = l.percent_used ?? 0
                const isOver = p >= 100
                const isWarn = p >= 70 && !isOver
                const feedback = getFriendlyBudgetCopy(l, daysLeft, cur)

                return (
                  <div
                    key={l.category}
                    className="card p-4 rounded-2xl border flex flex-col justify-between gap-3 shadow-xs"
                    style={{ borderColor: 'var(--border)' }}
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-sm tracking-tight">{l.category}</span>
                        <span
                          className="text-xs font-bold font-mono px-2 py-0.5 rounded-full"
                          style={{
                            backgroundColor: isOver
                              ? 'rgba(239, 68, 68, 0.1)'
                              : isWarn
                              ? 'rgba(217, 119, 6, 0.1)'
                              : 'rgba(15, 118, 110, 0.1)',
                            color: isOver ? 'var(--bad)' : isWarn ? 'var(--warn)' : 'var(--accent)',
                          }}
                        >
                          {pct(l.percent_used)}
                        </span>
                      </div>

                      <div className="text-xs muted mt-1 font-mono">
                        <strong className="text-[var(--fg)]">{money(l.used, cur)}</strong> spent of{' '}
                        {money(l.limit, cur)}
                      </div>
                    </div>

                    {/* Progress Bar */}
                    <div className="flex flex-col gap-1.5">
                      <div
                        className="h-2 rounded-full overflow-hidden bg-[var(--border)]"
                        role="progressbar"
                        aria-valuenow={Math.round(p)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${l.category} budget progress`}
                      >
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.min(p, 100)}%`,
                            backgroundColor: isOver ? 'var(--bad)' : isWarn ? 'var(--warn)' : 'var(--accent)',
                          }}
                        />
                      </div>

                      {/* Friendly Non-shaming copy */}
                      <p
                        className="text-[11px] leading-relaxed mt-1"
                        style={{
                          color:
                            feedback.tone === 'bad'
                              ? 'var(--bad)'
                              : feedback.tone === 'warn'
                              ? 'var(--warn)'
                              : 'var(--muted)',
                        }}
                      >
                        {feedback.message}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      ) : (
        /* Empty State */
        <div className="card p-8 text-center rounded-2xl border shadow-sm flex flex-col items-center gap-3" style={{ borderColor: 'var(--border)' }}>
          <div className="w-14 h-14 rounded-2xl bg-accent/10 text-accent flex items-center justify-center font-bold text-2xl">
            <PiggyBank size={28} />
          </div>
          <div>
            <h2 className="text-xl font-bold">Create your first budget</h2>
            <p className="muted text-xs sm:text-sm max-w-md mx-auto mt-1">
              Set a monthly spending limit and category caps to keep your finances balanced and stress-free.
            </p>
          </div>
          <button
            onClick={() => setShowEditor(true)}
            className="btn btn-primary text-xs px-4 py-2 mt-2 flex items-center gap-1.5 font-semibold"
          >
            <Plus size={15} /> Set Budget for {month}
          </button>
        </div>
      )}

      {/* Budget Editor (Collapsible or visible when requested) */}
      {(showEditor || !status) && (
        <section
          className="card p-5 sm:p-6 rounded-2xl border shadow-md flex flex-col gap-4 animate-fade-in"
          style={{ borderColor: 'var(--border)', background: 'var(--card)' }}
          aria-label="Budget editor"
        >
          <div className="flex items-center justify-between pb-3 border-b" style={{ borderColor: 'var(--border)' }}>
            <div>
              <h2 className="font-bold text-base tracking-tight">
                {status ? `Edit Budget for ${month}` : `Set Budget for ${month}`}
              </h2>
              <p className="text-xs muted">Adjust total limit and specific category spending limits</p>
            </div>
            {status && (
              <button
                onClick={() => setShowEditor(false)}
                className="text-xs muted hover:underline"
              >
                Cancel
              </button>
            )}
          </div>

          <div className="flex flex-col gap-4">
            {/* Total Monthly Limit */}
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold">Total Monthly Spending Limit ({cur})</span>
              <input
                type="number"
                inputMode="decimal"
                className="input text-base font-bold font-mono py-2.5 rounded-xl max-w-sm"
                placeholder="e.g. 50000"
                value={total}
                onChange={(e) => setTotal(e.target.value)}
                required
              />
            </label>

            {/* Category limits */}
            <div>
              <span className="text-xs font-semibold block mb-2">Category Spending Limits</span>
              <div className="grid gap-3 sm:grid-cols-2">
                {expenseCats.map((c) => (
                  <label key={c.id} className="flex flex-col gap-1 text-xs">
                    <span className="font-medium text-[var(--fg)]">{c.name}</span>
                    <input
                      type="number"
                      inputMode="decimal"
                      className="input py-2 text-xs font-mono rounded-lg"
                      placeholder="No limit"
                      value={limits[c.id] ?? ''}
                      onChange={(e) => setLimits({ ...limits, [c.id]: e.target.value })}
                    />
                  </label>
                ))}
              </div>
            </div>

            {/* Category sum warning */}
            <div className="pt-2 text-xs flex items-center gap-2">
              <span className="muted font-mono">
                Category limits total: <strong>{money(sum, cur)}</strong>
              </span>
              {overTotal && (
                <span className="text-bad font-semibold">
                  (Category limits exceed overall total by {money(sum - Number(total || 0), cur)})
                </span>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
              {status && (
                <button
                  type="button"
                  onClick={() => setShowEditor(false)}
                  className="btn btn-secondary text-xs px-4 py-2"
                >
                  Cancel
                </button>
              )}
              <button
                type="button"
                disabled={saving || !total || Number(total) <= 0}
                onClick={save}
                className="btn btn-primary text-xs px-5 py-2.5 font-semibold"
              >
                {saving ? 'Saving…' : 'Save Budget'}
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
