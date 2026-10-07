import {
  Pause, Pencil, Play, Plus, Trash2, Calendar, Sparkles
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money } from '../lib/format'
import { FREQ_LABEL, num } from '../lib/types'
import { useLookups } from '../lib/useLookups'
import { Empty, ErrorBox, Modal, Skeleton, useLoad } from '../components/ui'
import { useToast } from '../components/Toast'

interface Sub {
  id: number
  merchant: string
  merchant_key: string
  amount: number | string
  frequency: string
  category_id: number | null
  category: string | null
  status: string
  reminder: boolean
  last_date: string | null
  next_expected: string | null
  days_until_next: number | null
  monthly_equivalent: number | string
  annual_cost: number | string
  confidence: number | null
  occurrences: number
  source: string
}

interface SubsResp {
  items: Sub[]
  totals: { count: number; monthly_cost: number; annual_cost: number }
  pending_review: number
}

interface Cand {
  merchant_key: string
  merchant: string
  amount: string
  frequency: string
  category_id: number | null
  category: string | null
  last_date: string
  next_expected: string
  occurrences: number
  confidence: number
  suggested: boolean
  amount_varies: boolean
  monthly_equivalent: string
  annual_cost: string
  reasons: string[]
}

const FREQS = ['weekly', 'biweekly', 'monthly', 'quarterly', 'yearly']
const SORTS = [
  ['monthly', 'Monthly cost'],
  ['cost', 'Charge amount'],
  ['renewal', 'Next renewal'],
  ['category', 'Category'],
]

type Form = { mode: 'edit'; sub: Sub } | { mode: 'confirm'; cand: Cand } | { mode: 'add' }

function CandRow({
  c,
  cur,
  onConfirm,
  onEdit,
  onIgnore,
}: {
  c: Cand
  cur: string
  onConfirm: () => void
  onEdit: () => void
  onIgnore: () => void
}) {
  return (
    <li className="py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
      <div>
        <div className="font-semibold text-sm flex items-center gap-2">
          <span>{c.merchant}</span>
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-accent/10 text-accent border border-accent/20">
            Detected
          </span>
        </div>
        <div className="text-xs muted mt-0.5">
          {money(num(c.amount), cur)} / {FREQ_LABEL[c.frequency] ?? c.frequency} · seen {c.occurrences} times
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button className="btn btn-secondary text-xs px-2.5 py-1.5" onClick={onIgnore}>
          Ignore
        </button>
        <button className="btn btn-secondary text-xs px-2.5 py-1.5" onClick={onEdit}>
          Edit details
        </button>
        <button className="btn btn-primary text-xs px-3 py-1.5 font-semibold" onClick={onConfirm}>
          Confirm
        </button>
      </div>
    </li>
  )
}

function FormModal({ form, onClose, onDone }: { form: Form; onClose: () => void; onDone: () => void }) {
  const { categories } = useLookups()
  const { user } = useAuth()
  const init = form.mode === 'edit' ? form.sub : form.mode === 'confirm' ? form.cand : null
  const [merchant, setMerchant] = useState(init?.merchant ?? '')
  const [amount, setAmount] = useState(init ? String(num(init.amount)) : '')
  const [frequency, setFrequency] = useState(init?.frequency ?? 'monthly')
  const [categoryId, setCategoryId] = useState(init?.category_id ? String(init.category_id) : '')
  const [nextDate, setNextDate] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const cats = categories.filter((c) => c.kind === 'expense')
  const title =
    form.mode === 'add'
      ? 'Add a recurring subscription'
      : form.mode === 'confirm'
      ? `Confirm ${form.cand.merchant}`
      : `Edit ${form.sub.merchant}`

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    if (!(Number(amount) > 0)) return setErr('Enter an amount greater than zero.')
    if (!merchant.trim()) return setErr('Enter a name.')
    if (form.mode === 'add' && !nextDate) return setErr('Enter the next payment date.')
    setBusy(true)
    try {
      const cat = categoryId ? Number(categoryId) : null
      if (form.mode === 'add') {
        await api('/recurring', {
          method: 'POST',
          body: JSON.stringify({ type: 'expense', merchant, amount, frequency, next_date: nextDate, category_id: cat }),
        })
      } else if (form.mode === 'confirm') {
        await api('/recurring/confirm', {
          method: 'POST',
          body: JSON.stringify({
            merchant_key: form.cand.merchant_key,
            type: 'expense',
            merchant,
            amount,
            frequency,
            category_id: cat,
          }),
        })
      } else {
        await api(`/recurring/${form.sub.id}`, {
          method: 'PUT',
          body: JSON.stringify({ merchant, amount, frequency, category_id: cat }),
        })
      }
      onDone()
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Could not save.')
      setBusy(false)
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="text-xs font-semibold flex flex-col gap-1">
          Service or Merchant Name
          <input
            className="input text-sm"
            placeholder="e.g. Netflix, Spotify, AWS"
            value={merchant}
            onChange={(e) => setMerchant(e.target.value)}
            maxLength={160}
            required
          />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs font-semibold flex flex-col gap-1">
            Amount ({user?.currency})
            <input
              className="input text-sm font-mono"
              inputMode="decimal"
              placeholder="e.g. 649"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
            />
          </label>
          <label className="text-xs font-semibold flex flex-col gap-1">
            Billing Frequency
            <select
              className="input text-sm"
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
            >
              {FREQS.map((f) => (
                <option key={f} value={f}>
                  {FREQ_LABEL[f]}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="text-xs font-semibold flex flex-col gap-1">
          Category
          <select
            className="input text-sm"
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
          >
            <option value="">Uncategorized</option>
            {cats.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        {form.mode === 'add' && (
          <label className="text-xs font-semibold flex flex-col gap-1">
            Next Payment Date
            <input
              className="input text-sm"
              type="date"
              value={nextDate}
              onChange={(e) => setNextDate(e.target.value)}
              required
            />
          </label>
        )}
        {err && <p role="alert" className="text-xs text-bad">{err}</p>}
        <div className="flex gap-2 justify-end pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
          <button type="button" className="btn btn-secondary text-xs px-3 py-2" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary text-xs px-4 py-2 font-semibold" disabled={busy}>
            {form.mode === 'confirm' ? 'Confirm Subscription' : 'Save Subscription'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export default function Subscriptions() {
  const { user } = useAuth()
  const cur = user?.currency ?? 'INR'
  const { toast } = useToast()
  const [sort, setSort] = useState('monthly')
  const [uncertain] = useState(false)
  const [form, setForm] = useState<Form | null>(null)
  const [delId, setDelId] = useState<number | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  const subs = useLoad(
    () => api<SubsResp>(`/subscriptions?sort=${sort}&order=${sort === 'renewal' || sort === 'category' ? 'asc' : 'desc'}`),
    [sort]
  )
  const cands = useLoad(() => api<Cand[]>(`/recurring/candidates?include_uncertain=${uncertain}`), [uncertain])
  const ignored = useLoad(() => api<Sub[]>('/recurring/ignored'), [])

  const refresh = () => {
    subs.reload()
    cands.reload()
    ignored.reload()
  }

  async function act(fn: () => Promise<unknown>, successMsg?: string) {
    setActionErr(null)
    try {
      await fn()
      if (successMsg) toast.success(successMsg)
      refresh()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Action failed.'
      setActionErr(msg)
      toast.error(msg)
    }
  }

  const suggested = (cands.data ?? []).filter((c) => c.suggested)

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Subscriptions</h1>
          <p className="text-xs sm:text-sm muted mt-0.5">
            Monitor and manage your recurring memberships and services
          </p>
        </div>

        <button
          className="btn btn-primary flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl self-start sm:self-auto"
          onClick={() => setForm({ mode: 'add' })}
        >
          <Plus size={16} />
          <span>Add Subscription</span>
        </button>
      </div>

      {subs.error && <ErrorBox message={subs.error} onRetry={subs.reload} />}
      {actionErr && <ErrorBox message={actionErr} />}

      {/* Top Cost Overview Cards */}
      {subs.data && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="card p-4 sm:p-5 rounded-2xl border flex flex-col justify-between" style={{ borderColor: 'var(--border)' }}>
            <span className="text-xs font-bold uppercase tracking-wider text-muted">Monthly Recurring</span>
            <div className="mt-2">
              <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                {money(subs.data.totals.monthly_cost, cur)}
                <span className="text-xs font-normal muted ml-1">/month</span>
              </div>
              <div className="text-xs muted mt-1">
                Across {subs.data.totals.count} active subscription(s)
              </div>
            </div>
          </div>

          <div className="card p-4 sm:p-5 rounded-2xl border flex flex-col justify-between" style={{ borderColor: 'var(--border)' }}>
            <span className="text-xs font-bold uppercase tracking-wider text-muted">Annual Estimate</span>
            <div className="mt-2">
              <div className="text-2xl sm:text-3xl font-extrabold tracking-tight text-accent">
                {money(subs.data.totals.annual_cost, cur)}
                <span className="text-xs font-normal muted ml-1">/year</span>
              </div>
              <div className="text-xs muted mt-1">
                Projected total annual outflow
              </div>
            </div>
          </div>

          <div className="card p-4 sm:p-5 rounded-2xl border flex flex-col justify-between sm:col-span-2 lg:col-span-1" style={{ borderColor: 'var(--border)' }}>
            <span className="text-xs font-bold uppercase tracking-wider text-muted">Bills &amp; Utilities</span>
            <div className="mt-2">
              <div className="text-sm font-semibold">Separate from fixed bills</div>
              <div className="text-xs muted mt-1">
                Rent, utilities, and EMIs are managed under{' '}
                <Link to="/bills" className="text-accent underline font-semibold">
                  Bills →
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Detected Repeating Payments Section */}
      {cands.data && suggested.length > 0 && (
        <section className="card p-4 sm:p-5 rounded-2xl border shadow-xs" style={{ borderColor: 'var(--border)' }}>
          <div className="pb-3 border-b" style={{ borderColor: 'var(--border)' }}>
            <h2 className="font-bold text-sm tracking-tight flex items-center gap-1.5">
              <Sparkles size={16} className="text-accent" />
              <span>Detected from your transactions ({suggested.length})</span>
            </h2>
            <p className="text-xs muted mt-0.5">
              We detected repeating payments. Confirm them to track recurring spend.
            </p>
          </div>
          <ul className="divide-y divide-[var(--border)]">
            {suggested.map((c) => (
              <CandRow
                key={c.merchant_key}
                c={c}
                cur={cur}
                onConfirm={() =>
                  act(
                    () =>
                      api('/recurring/confirm', {
                        method: 'POST',
                        body: JSON.stringify({ merchant_key: c.merchant_key, type: 'expense' }),
                      }),
                    `Confirmed ${c.merchant}`
                  )
                }
                onEdit={() => setForm({ mode: 'confirm', cand: c })}
                onIgnore={() =>
                  act(
                    () =>
                      api('/recurring/ignore', {
                        method: 'POST',
                        body: JSON.stringify({ merchant_key: c.merchant_key, type: 'expense' }),
                      }),
                    `Ignored ${c.merchant}`
                  )
                }
              />
            ))}
          </ul>
        </section>
      )}

      {/* Confirmed Subscriptions List */}
      <section className="card p-4 sm:p-5 rounded-2xl border shadow-xs" style={{ borderColor: 'var(--border)' }}>
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <div>
            <h2 className="font-bold text-sm tracking-tight">Active &amp; Tracked Subscriptions</h2>
            <p className="text-xs muted">Sorted and managed directly</p>
          </div>

          <label className="text-xs flex items-center gap-2">
            <span className="muted font-medium">Sort by:</span>
            <select
              className="input text-xs py-1 px-2 rounded-lg"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              {SORTS.map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </select>
          </label>
        </div>

        {!subs.data && !subs.error && <Skeleton rows={3} label="Loading subscriptions" />}

        {subs.data && subs.data.items.length === 0 && (
          <div className="py-8 text-center">
            <Empty title="No active subscriptions tracked">
              {(subs.data.pending_review ?? 0) > 0
                ? 'Confirm detected payments above to start tracking.'
                : 'Add recurring services like Netflix, Spotify, or gym memberships.'}
              <div className="mt-3">
                <button
                  onClick={() => setForm({ mode: 'add' })}
                  className="btn btn-primary text-xs px-3.5 py-1.5 font-semibold"
                >
                  + Add Subscription
                </button>
              </div>
            </Empty>
          </div>
        )}

        {subs.data && subs.data.items.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 mt-4">
            {subs.data.items.map((s) => {
              const isPaused = s.status === 'paused'
              const days = s.days_until_next

              return (
                <div
                  key={s.id}
                  className={`card-interactive p-4 rounded-2xl border flex flex-col justify-between gap-3 transition ${
                    isPaused ? 'opacity-60 bg-[var(--bg)]' : 'bg-[var(--card)]'
                  }`}
                  style={{ borderColor: 'var(--border)' }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-bold text-sm flex items-center gap-2 truncate">
                        <span>{s.merchant}</span>
                        {isPaused && (
                          <span className="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-amber-500/10 text-warn border border-amber-500/20">
                            Paused
                          </span>
                        )}
                      </div>
                      <div className="text-xs muted mt-0.5">
                        {s.category || 'General'} · {FREQ_LABEL[s.frequency] ?? s.frequency}
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <div className="text-base font-bold font-mono">
                        {money(num(s.amount), cur)}
                        <span className="text-xs font-normal muted">
                          /{s.frequency === 'monthly' ? 'mo' : s.frequency}
                        </span>
                      </div>
                      <div className="text-[11px] muted font-mono">
                        ~{money(num(s.monthly_equivalent), cur)}/mo
                      </div>
                    </div>
                  </div>

                  {/* Payment timing & actions */}
                  <div
                    className="flex items-center justify-between pt-2 border-t text-xs"
                    style={{ borderColor: 'var(--border)' }}
                  >
                    <div className="text-xs muted flex items-center gap-1">
                      <Calendar size={13} />
                      {isPaused ? (
                        <span>Payments paused</span>
                      ) : days !== null ? (
                        <span className="font-medium text-[var(--fg)]">
                          {days < 0
                            ? `${Math.abs(days)}d past expected`
                            : days === 0
                            ? 'Next payment today'
                            : days === 1
                            ? 'Next payment tomorrow'
                            : `Next payment in ${days} days`}
                        </span>
                      ) : (
                        <span>Next: {s.next_expected ?? '—'}</span>
                      )}
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-1.5">
                      <button
                        className="p-1.5 rounded-lg muted hover:text-accent hover:bg-[var(--bg)] transition"
                        title="Edit subscription"
                        onClick={() => setForm({ mode: 'edit', sub: s })}
                      >
                        <Pencil size={14} />
                      </button>

                      <button
                        className="p-1.5 rounded-lg muted hover:text-warn hover:bg-[var(--bg)] transition"
                        title={isPaused ? 'Resume tracking' : 'Pause subscription'}
                        onClick={() =>
                          act(
                            () =>
                              api(`/recurring/${s.id}`, {
                                method: 'PUT',
                                body: JSON.stringify({ status: isPaused ? 'confirmed' : 'paused' }),
                              }),
                            isPaused ? `Resumed ${s.merchant}` : `Paused ${s.merchant}`
                          )
                        }
                      >
                        {isPaused ? <Play size={14} /> : <Pause size={14} />}
                      </button>

                      {delId === s.id ? (
                        <span className="flex items-center gap-1 text-xs">
                          <button
                            className="text-bad font-semibold underline"
                            onClick={() => {
                              setDelId(null)
                              act(() => api(`/recurring/${s.id}`, { method: 'DELETE' }), `Deleted ${s.merchant}`)
                            }}
                          >
                            Yes
                          </button>
                          <button className="muted underline" onClick={() => setDelId(null)}>
                            No
                          </button>
                        </span>
                      ) : (
                        <button
                          className="p-1.5 rounded-lg muted hover:text-bad hover:bg-red-500/10 transition"
                          title="Delete subscription"
                          onClick={() => setDelId(s.id)}
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* Add / Edit Form Modal */}
      {form && (
        <FormModal
          form={form}
          onClose={() => setForm(null)}
          onDone={() => {
            setForm(null)
            refresh()
          }}
        />
      )}
    </div>
  )
}
