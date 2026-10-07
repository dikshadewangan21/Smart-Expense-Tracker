import { Check, Pencil, Plus, Trash2, Calendar } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money } from '../lib/format'
import { FREQ_LABEL, PAYMENT_METHODS, num } from '../lib/types'
import { useLookups } from '../lib/useLookups'
import { Empty, ErrorBox, Modal, Skeleton, Stat, useLoad } from '../components/ui'
import { useToast } from '../components/Toast'

export interface Bill {
  id: number
  name: string
  kind: string
  amount: string | number
  category_id: number | null
  category: string | null
  due_date: string
  frequency: string
  auto_repeat: boolean
  notes: string | null
  reminder_days: number[]
  active: boolean
  paid: boolean
  last_paid: string | null
  status: string
  days_until: number
  monthly_equivalent: string | number | null
}

interface BillsResp {
  items: Bill[]
  summary: {
    overdue_count: number
    overdue_total: string
    due_next_7_days_total: string
    monthly_commitment: string
  }
}

const KINDS = ['rent', 'electricity', 'internet', 'phone', 'insurance', 'emi', 'credit_card', 'custom']
const BILL_FREQS = ['once', 'weekly', 'monthly', 'quarterly', 'yearly']

// Tabs: Upcoming, Paid, Overdue, or All Active
const TABS = [
  ['upcoming', 'Upcoming'],
  ['overdue', 'Overdue'],
  ['paid', 'Paid'],
  ['', 'All Active'],
] as const

const label = (s: string) => s.replace('_', ' ').replace(/^./, (c) => c.toUpperCase())

export function getStatusBadge(b: Bill): { text: string; bg: string; textCol: string; border: string } {
  if (b.status === 'paid') {
    return {
      text: 'Paid',
      bg: 'bg-green-500/10',
      textCol: 'text-good',
      border: 'border-green-500/20',
    }
  }
  if (b.status === 'overdue' || b.days_until < 0) {
    return {
      text: `${Math.abs(b.days_until)}d Overdue`,
      bg: 'bg-red-500/10',
      textCol: 'text-bad',
      border: 'border-red-500/20',
    }
  }
  if (b.status === 'due_today' || b.days_until === 0) {
    return {
      text: 'Due Today',
      bg: 'bg-amber-500/10',
      textCol: 'text-warn',
      border: 'border-amber-500/20',
    }
  }
  if (b.days_until === 1) {
    return {
      text: 'Due Tomorrow',
      bg: 'bg-blue-500/10',
      textCol: 'text-accent',
      border: 'border-blue-500/20',
    }
  }
  if (b.days_until <= 7) {
    return {
      text: `In ${b.days_until} days`,
      bg: 'bg-blue-500/5',
      textCol: 'text-accent',
      border: 'border-blue-500/20',
    }
  }
  return {
    text: `Due in ${b.days_until}d`,
    bg: 'bg-[var(--card)]',
    textCol: 'text-muted',
    border: 'border-[var(--border)]',
  }
}

function today(tz?: string) {
  try {
    return new Date().toLocaleDateString('en-CA', { timeZone: tz })
  } catch {
    return new Date().toLocaleDateString('en-CA')
  }
}

function BillForm({ bill, onClose, onDone }: { bill: Bill | null; onClose: () => void; onDone: () => void }) {
  const { categories } = useLookups()
  const { user } = useAuth()
  const { toast } = useToast()

  const [name, setName] = useState(bill?.name ?? '')
  const [kind, setKind] = useState(bill?.kind ?? 'custom')
  const [amount, setAmount] = useState(bill ? String(num(bill.amount)) : '')
  const [due, setDue] = useState(bill?.due_date ?? '')
  const [frequency, setFrequency] = useState(bill?.frequency ?? 'monthly')
  const [categoryId, setCategoryId] = useState(bill?.category_id ? String(bill.category_id) : '')
  const [autoRepeat, setAutoRepeat] = useState(bill?.auto_repeat ?? true)
  const [active, setActive] = useState(bill?.active ?? true)
  const [notes, setNotes] = useState(bill?.notes ?? '')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    if (!name.trim()) return setErr('Enter a name.')
    if (!(Number(amount) > 0)) return setErr('Enter an amount greater than zero.')
    if (!due) return setErr('Pick a due date.')
    setBusy(true)

    const body = JSON.stringify({
      name,
      kind,
      amount,
      due_date: due,
      frequency,
      category_id: categoryId ? Number(categoryId) : null,
      auto_repeat: autoRepeat,
      active,
      notes: notes || null,
      reminder_days: bill ? bill.reminder_days : null,
    })

    try {
      await api(bill ? `/bills/${bill.id}` : '/bills', { method: bill ? 'PUT' : 'POST', body })
      toast.success(bill ? `Updated ${name}` : `Added bill ${name}`)
      onDone()
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Could not save bill.')
      setBusy(false)
    }
  }

  return (
    <Modal title={bill ? `Edit ${bill.name}` : '+ Add a Bill'} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="text-xs font-semibold flex flex-col gap-1">
          Bill / Payee Name
          <input
            className="input text-sm"
            placeholder="e.g. Apartment Rent, Electricity, Broadband"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={120}
            required
          />
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs font-semibold flex flex-col gap-1">
            Bill Type
            <select className="input text-sm" value={kind} onChange={(e) => setKind(e.target.value)}>
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {label(k)}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-semibold flex flex-col gap-1">
            Amount ({user?.currency})
            <input
              className="input text-sm font-mono"
              inputMode="decimal"
              placeholder="e.g. 12000"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
            />
          </label>
          <label className="text-xs font-semibold flex flex-col gap-1">
            {bill ? 'Next Due Date' : 'Due Date'}
            <input className="input text-sm" type="date" value={due} onChange={(e) => setDue(e.target.value)} required />
          </label>
          <label className="text-xs font-semibold flex flex-col gap-1">
            Frequency
            <select className="input text-sm" value={frequency} onChange={(e) => setFrequency(e.target.value)}>
              {BILL_FREQS.map((f) => (
                <option key={f} value={f}>
                  {FREQ_LABEL[f]}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="text-xs font-semibold flex flex-col gap-1">
          Category
          <select className="input text-sm" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">None</option>
            {categories
              .filter((c) => c.kind === 'expense')
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
          </select>
        </label>

        <label className="text-xs font-semibold flex flex-col gap-1">
          Notes (optional)
          <input className="input text-sm" value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} />
        </label>

        <label className="text-xs flex items-center gap-2 mt-1">
          <input type="checkbox" checked={autoRepeat} onChange={(e) => setAutoRepeat(e.target.checked)} />
          <span>Automatically move to the next due date after payment</span>
        </label>

        {bill && (
          <label className="text-xs flex items-center gap-2">
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
            <span>Active bill</span>
          </label>
        )}

        {err && <p role="alert" className="text-xs text-bad">{err}</p>}

        <div className="flex gap-2 justify-end pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
          <button type="button" className="btn btn-secondary text-xs px-3 py-2" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary text-xs px-4 py-2 font-semibold" disabled={busy}>
            Save Bill
          </button>
        </div>
      </form>
    </Modal>
  )
}

function PayForm({ bill, onClose, onDone }: { bill: Bill; onClose: () => void; onDone: () => void }) {
  const { accounts } = useLookups()
  const { user } = useAuth()
  const { toast } = useToast()

  const [paidOn, setPaidOn] = useState(today(user?.timezone))
  const [amount, setAmount] = useState(String(num(bill.amount)))
  const [create, setCreate] = useState(true)
  const [pm, setPm] = useState('upi')
  const [accountId, setAccountId] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!(Number(amount) > 0)) return setErr('Enter an amount greater than zero.')
    setBusy(true)
    setErr(null)

    try {
      await api(`/bills/${bill.id}/pay`, {
        method: 'POST',
        body: JSON.stringify({
          paid_on: paidOn,
          amount,
          create_transaction: create,
          payment_method: pm,
          account_id: accountId ? Number(accountId) : null,
        }),
      })
      toast.success(`Recorded payment for ${bill.name}!`)
      onDone()
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Could not record payment.')
      setBusy(false)
    }
  }

  return (
    <Modal title={`Mark ${bill.name} as Paid`} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs font-semibold flex flex-col gap-1">
            Paid On
            <input className="input text-sm" type="date" value={paidOn} onChange={(e) => setPaidOn(e.target.value)} />
          </label>
          <label className="text-xs font-semibold flex flex-col gap-1">
            Amount Paid ({user?.currency})
            <input
              className="input text-sm font-mono"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </label>
        </div>

        <label className="text-xs flex items-center gap-2">
          <input type="checkbox" checked={create} onChange={(e) => setCreate(e.target.checked)} />
          <span>Also record as an expense transaction</span>
        </label>

        {create && (
          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs font-semibold flex flex-col gap-1">
              Payment Method
              <select className="input text-sm" value={pm} onChange={(e) => setPm(e.target.value)}>
                {PAYMENT_METHODS.map(([k, l]) => (
                  <option key={k} value={k}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs font-semibold flex flex-col gap-1">
              Account
              <select className="input text-sm" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                <option value="">None</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        {err && <p role="alert" className="text-xs text-bad">{err}</p>}

        <div className="flex gap-2 justify-end pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
          <button type="button" className="btn btn-secondary text-xs px-3 py-2" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary text-xs px-4 py-2 font-semibold" disabled={busy}>
            Record Payment
          </button>
        </div>
      </form>
    </Modal>
  )
}

export default function Bills() {
  const { user } = useAuth()
  const cur = user?.currency ?? 'INR'
  const { toast } = useToast()

  const [tab, setTab] = useState<'upcoming' | 'overdue' | 'paid' | ''>('upcoming')
  const [sort, setSort] = useState('due')
  const [editing, setEditing] = useState<Bill | 'new' | null>(null)
  const [paying, setPaying] = useState<Bill | null>(null)
  const [delId, setDelId] = useState<number | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  const { data, error, reload } = useLoad(
    () => api<BillsResp>(`/bills?sort=${sort}${tab ? `&status=${tab}` : ''}`),
    [tab, sort]
  )

  async function del(id: number, name: string) {
    setDelId(null)
    setActionErr(null)
    try {
      await api(`/bills/${id}`, { method: 'DELETE' })
      toast.success(`Deleted ${name}`)
      reload()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Could not delete.'
      setActionErr(msg)
      toast.error(msg)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Bills &amp; Payments</h1>
          <p className="text-xs sm:text-sm muted mt-0.5">
            Never miss a rent, utility, EMI, or credit card due date
          </p>
        </div>

        <button
          className="btn btn-primary flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl self-start sm:self-auto"
          onClick={() => setEditing('new')}
        >
          <Plus size={16} />
          <span>+ Add Bill</span>
        </button>
      </div>

      {error && <ErrorBox message={error} onRetry={reload} />}
      {actionErr && <ErrorBox message={actionErr} />}

      {/* Summary KPI Cards */}
      {data && (
        <div className="grid gap-3 sm:gap-4 grid-cols-2 lg:grid-cols-3">
          <Stat
            label="Overdue Bills"
            value={money(num(data.summary.overdue_total), cur)}
            sub={`${data.summary.overdue_count} bill(s) need attention`}
            tone={data.summary.overdue_count > 0 ? 'bad' : undefined}
          />
          <Stat
            label="Due in Next 7 Days"
            value={money(num(data.summary.due_next_7_days_total), cur)}
            sub="Upcoming commitments"
          />
          <Stat
            label="Monthly Commitment"
            value={money(num(data.summary.monthly_commitment), cur)}
            sub="Averaged total bill cost"
          />
        </div>
      )}

      {/* Tabs & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Tabs: Upcoming / Overdue / Paid / All Active */}
        <div
          className="flex items-center gap-1 bg-[var(--card)] p-1 rounded-xl border"
          style={{ borderColor: 'var(--border)' }}
          role="group"
          aria-label="Bill status tabs"
        >
          {TABS.map(([k, l]) => (
            <button
              key={k}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                tab === k
                  ? 'bg-accent text-white shadow-xs'
                  : 'muted hover:text-[var(--fg)] hover:bg-[var(--bg)]'
              }`}
              onClick={() => setTab(k)}
            >
              {l}
            </button>
          ))}
        </div>

        <label className="text-xs flex items-center gap-2">
          <span className="muted font-medium">Sort by:</span>
          <select
            className="input text-xs py-1 px-2 rounded-lg"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="due">Due date</option>
            <option value="amount">Amount</option>
            <option value="name">Name</option>
          </select>
        </label>
      </div>

      {/* Bill Items List */}
      {!data && !error && <Skeleton rows={4} label="Loading bills" />}

      {data && data.items.length === 0 && (
        <div className="card p-8 text-center rounded-2xl border shadow-xs" style={{ borderColor: 'var(--border)' }}>
          <Empty title="No bills found in this tab">
            {tab === 'overdue'
              ? 'Great job! You have zero overdue bills.'
              : tab === 'paid'
              ? 'No bills have been marked as paid yet.'
              : 'Add your recurring utilities, rent, and credit cards to stay organized.'}
            <div className="mt-3">
              <button
                onClick={() => setEditing('new')}
                className="btn btn-primary text-xs px-3.5 py-1.5 font-semibold"
              >
                + Add a Bill
              </button>
            </div>
          </Empty>
        </div>
      )}

      {data && data.items.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.items.map((b) => {
            const badge = getStatusBadge(b)

            return (
              <div
                key={b.id}
                className="card-interactive p-4 rounded-2xl border flex flex-col justify-between gap-3 shadow-xs"
                style={{ borderColor: 'var(--border)', background: 'var(--card)' }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-bold text-sm truncate flex items-center gap-2">
                      <span>{b.name}</span>
                      <span className="text-[10px] muted px-1.5 py-0.2 rounded bg-[var(--bg)] border font-normal" style={{ borderColor: 'var(--border)' }}>
                        {label(b.kind)}
                      </span>
                    </div>
                    <div className="text-xs muted mt-0.5 flex items-center gap-1.5">
                      <span>{FREQ_LABEL[b.frequency] ?? b.frequency}</span>
                      {b.category && <span>• {b.category}</span>}
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <div className="text-base font-bold font-mono">
                      {money(num(b.amount), cur)}
                    </div>
                    <span className={`inline-block text-[10px] font-bold px-2 py-0.5 rounded-full border mt-1 ${badge.bg} ${badge.textCol} ${badge.border}`}>
                      {badge.text}
                    </span>
                  </div>
                </div>

                {b.notes && (
                  <p className="text-xs muted bg-[var(--bg)] p-2 rounded-lg border text-ellipsis overflow-hidden" style={{ borderColor: 'var(--border)' }}>
                    {b.notes}
                  </p>
                )}

                {/* Footer with date & actions */}
                <div
                  className="flex items-center justify-between pt-2 border-t text-xs"
                  style={{ borderColor: 'var(--border)' }}
                >
                  <div className="text-xs muted flex items-center gap-1">
                    <Calendar size={13} />
                    <span>Due: <strong>{b.due_date}</strong></span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {delId === b.id ? (
                      <span className="flex items-center gap-1 text-xs">
                        <button className="text-bad font-semibold underline" onClick={() => del(b.id, b.name)}>
                          Yes
                        </button>
                        <button className="muted underline" onClick={() => setDelId(null)}>
                          No
                        </button>
                      </span>
                    ) : (
                      <>
                        {b.status !== 'paid' && b.status !== 'inactive' && (
                          <button
                            className="btn btn-secondary text-xs px-2.5 py-1 rounded-lg flex items-center gap-1 font-semibold"
                            onClick={() => setPaying(b)}
                          >
                            <Check size={14} className="text-good" />
                            <span>Mark Paid</span>
                          </button>
                        )}
                        <button
                          className="p-1.5 rounded-lg muted hover:text-accent hover:bg-[var(--bg)]"
                          title="Edit bill"
                          onClick={() => setEditing(b)}
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          className="p-1.5 rounded-lg muted hover:text-bad hover:bg-red-500/10"
                          title="Delete bill"
                          onClick={() => setDelId(b.id)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Bill Add / Edit Form Modal */}
      {editing && (
        <BillForm
          bill={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onDone={() => {
            setEditing(null)
            reload()
          }}
        />
      )}

      {/* Pay Modal */}
      {paying && (
        <PayForm
          bill={paying}
          onClose={() => setPaying(null)}
          onDone={() => {
            setPaying(null)
            reload()
          }}
        />
      )}
    </div>
  )
}
