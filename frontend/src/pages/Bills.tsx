import { Check, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money } from '../lib/format'
import { FREQ_LABEL, PAYMENT_METHODS, num } from '../lib/types'
import { useLookups } from '../lib/useLookups'
import { Empty, ErrorBox, Modal, Skeleton, Stat, ghost, useLoad } from '../components/ui'

export interface Bill {
  id: number; name: string; kind: string; amount: string | number; category_id: number | null; category: string | null; due_date: string
  frequency: string; auto_repeat: boolean; notes: string | null; reminder_days: number[]; active: boolean; paid: boolean; last_paid: string | null
  status: string; days_until: number; monthly_equivalent: string | number | null
}
interface BillsResp { items: Bill[]; summary: { overdue_count: number; overdue_total: string; due_next_7_days_total: string; monthly_commitment: string } }

const KINDS = ['rent', 'electricity', 'internet', 'phone', 'insurance', 'emi', 'credit_card', 'custom']
const BILL_FREQS = ['once', 'weekly', 'monthly', 'quarterly', 'yearly']
const TABS = [['', 'Active'], ['paid', 'Paid'], ['inactive', 'Inactive']] as const
const label = (s: string) => s.replace('_', ' ').replace(/^./, (c) => c.toUpperCase())

export const STATUS_STYLE: Record<string, { text: string; color?: string }> = {
  overdue: { text: 'Overdue', color: 'var(--bad)' }, due_today: { text: 'Due today', color: 'var(--warn)' },
  upcoming: { text: 'Upcoming' }, paid: { text: 'Paid', color: 'var(--good)' }, inactive: { text: 'Inactive' },
}

function dueText(b: Bill) {
  if (b.status === 'paid') return `Paid${b.last_paid ? ` on ${b.last_paid}` : ''}`
  if (b.status === 'inactive') return 'Inactive'
  if (b.days_until < 0) return `${-b.days_until} day(s) overdue`
  if (b.days_until === 0) return 'Due today'
  return `Due in ${b.days_until} day(s)`
}

function today(tz?: string) {
  try { return new Date().toLocaleDateString('en-CA', { timeZone: tz }) } catch { return new Date().toLocaleDateString('en-CA') }
}

function BillForm({ bill, onClose, onDone }: { bill: Bill | null; onClose: () => void; onDone: () => void }) {
  const { categories } = useLookups()
  const { user } = useAuth()
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
    const body = JSON.stringify({ name, kind, amount, due_date: due, frequency, category_id: categoryId ? Number(categoryId) : null,
      auto_repeat: autoRepeat, active, notes: notes || null, reminder_days: bill ? bill.reminder_days : null })
    try {
      await api(bill ? `/bills/${bill.id}` : '/bills', { method: bill ? 'PUT' : 'POST', body })
      onDone()
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : 'Could not save.'); setBusy(false) }
  }

  return (
    <Modal title={bill ? `Edit ${bill.name}` : 'Add a bill'} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="text-sm">Name<input className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} /></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-sm">Type<select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map((k) => <option key={k} value={k}>{label(k)}</option>)}</select></label>
          <label className="text-sm">Amount ({user?.currency})<input className="input" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
          <label className="text-sm">{bill ? 'Next due date' : 'Due date'}<input className="input" type="date" value={due} onChange={(e) => setDue(e.target.value)} /></label>
          <label className="text-sm">Repeats<select className="input" value={frequency} onChange={(e) => setFrequency(e.target.value)}>{BILL_FREQS.map((f) => <option key={f} value={f}>{FREQ_LABEL[f]}</option>)}</select></label>
        </div>
        <label className="text-sm">Category<select className="input" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
          <option value="">None</option>{categories.filter((c) => c.kind === 'expense').map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <label className="text-sm">Notes<input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} /></label>
        <label className="text-sm flex gap-2 items-center"><input type="checkbox" checked={autoRepeat} onChange={(e) => setAutoRepeat(e.target.checked)} /> Move to the next due date after payment</label>
        {bill && <label className="text-sm flex gap-2 items-center"><input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active</label>}
        {err && <p role="alert" style={{ color: 'var(--bad)' }} className="text-sm">{err}</p>}
        <div className="flex gap-2 justify-end"><button type="button" className="btn" style={ghost} onClick={onClose}>Cancel</button><button className="btn" disabled={busy}>Save</button></div>
      </form>
    </Modal>
  )
}

function PayForm({ bill, onClose, onDone }: { bill: Bill; onClose: () => void; onDone: () => void }) {
  const { accounts } = useLookups()
  const { user } = useAuth()
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
    setBusy(true); setErr(null)
    try {
      await api(`/bills/${bill.id}/pay`, { method: 'POST', body: JSON.stringify({ paid_on: paidOn, amount, create_transaction: create, payment_method: pm, account_id: accountId ? Number(accountId) : null }) })
      onDone()
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : 'Could not record payment.'); setBusy(false) }
  }

  return (
    <Modal title={`Mark ${bill.name} as paid`} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="text-sm">Paid on<input className="input" type="date" value={paidOn} onChange={(e) => setPaidOn(e.target.value)} /></label>
          <label className="text-sm">Amount ({user?.currency})<input className="input" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
        </div>
        <label className="text-sm flex gap-2 items-center"><input type="checkbox" checked={create} onChange={(e) => setCreate(e.target.checked)} /> Also record as an expense</label>
        {create && (
          <div className="grid grid-cols-2 gap-3">
            <label className="text-sm">Method<select className="input" value={pm} onChange={(e) => setPm(e.target.value)}>{PAYMENT_METHODS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
            <label className="text-sm">Account<select className="input" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              <option value="">None</option>{accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
          </div>
        )}
        <p className="muted text-xs">{bill.frequency !== 'once' && bill.auto_repeat ? 'The due date moves to the next cycle.' : 'This bill will be marked as paid.'}
          {bill.kind === 'credit_card' && create ? ' Card purchases are already counted as expenses; recording the bill payment too counts them twice.' : ''}</p>
        {err && <p role="alert" style={{ color: 'var(--bad)' }} className="text-sm">{err}</p>}
        <div className="flex gap-2 justify-end"><button type="button" className="btn" style={ghost} onClick={onClose}>Cancel</button><button className="btn" disabled={busy}>Record payment</button></div>
      </form>
    </Modal>
  )
}

export default function Bills() {
  const { user } = useAuth()
  const cur = user?.currency ?? 'INR'
  const [tab, setTab] = useState('')
  const [sort, setSort] = useState('due')
  const [editing, setEditing] = useState<Bill | 'new' | null>(null)
  const [paying, setPaying] = useState<Bill | null>(null)
  const [delId, setDelId] = useState<number | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  const { data, error, reload } = useLoad(() => api<BillsResp>(`/bills?sort=${sort}${tab ? `&status=${tab}` : ''}`), [tab, sort])

  async function del(id: number) {
    setDelId(null); setActionErr(null)
    try { await api(`/bills/${id}`, { method: 'DELETE' }); reload() } catch (e) { setActionErr(e instanceof Error ? e.message : 'Could not delete.') }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Bills</h1>
        <button className="btn flex items-center gap-1" onClick={() => setEditing('new')}><Plus size={16} /> Add bill</button>
      </div>

      {error && <ErrorBox message={error} onRetry={reload} />}
      {actionErr && <ErrorBox message={actionErr} />}
      {!data && !error && <Skeleton rows={4} label="Loading bills" />}

      {data && (
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
          <Stat label="Overdue" value={money(num(data.summary.overdue_total), cur)} sub={`${data.summary.overdue_count} bill(s)`} tone={data.summary.overdue_count > 0 ? 'bad' : undefined} />
          <Stat label="Due in next 7 days" value={money(num(data.summary.due_next_7_days_total), cur)} />
          <Stat label="Monthly commitment" value={money(num(data.summary.monthly_commitment), cur)} sub="Bills only, averaged per month" />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 justify-between">
        <div className="flex gap-2" role="group" aria-label="Bill status">
          {TABS.map(([k, l]) => <button key={k} className="btn" style={tab === k ? {} : ghost} aria-pressed={tab === k} onClick={() => setTab(k)}>{l}</button>)}
        </div>
        <label className="text-sm flex items-center gap-2">Sort by
          <select className="input" style={{ width: 'auto' }} value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="due">Due date</option><option value="amount">Amount</option><option value="name">Name</option></select></label>
      </div>

      {data && data.items.length === 0 && (
        <div className="card"><Empty>{tab === 'paid' ? 'No paid one-time bills.' : tab === 'inactive' ? 'No inactive bills.' : 'No bills yet. Add rent, electricity, EMIs and anything else that comes due.'}</Empty></div>
      )}
      {data && data.items.length > 0 && (
        <ul className="flex flex-col gap-2">
          {data.items.map((b) => {
            const st = STATUS_STYLE[b.status] ?? { text: b.status }
            return (
              <li key={b.id} className="card flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="font-medium">{b.name} <span className="muted font-normal text-sm">· {label(b.kind)} · {FREQ_LABEL[b.frequency]}</span></div>
                  <div className="text-sm"><span style={{ color: st.color, fontWeight: st.color ? 600 : 400 }}>{st.text}</span>
                    <span className="muted"> · {dueText(b)}{b.status !== 'paid' && b.status !== 'inactive' ? ` · ${b.due_date}` : ''}</span></div>
                  {b.notes && <div className="muted text-xs">{b.notes}</div>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold mr-2">{money(num(b.amount), cur)}</span>
                  {delId === b.id ? (
                    <span className="text-sm">Delete? <button className="underline mx-1" style={{ color: 'var(--bad)' }} onClick={() => del(b.id)}>Yes</button><button className="underline" onClick={() => setDelId(null)}>No</button></span>
                  ) : (<>
                    {(b.status === 'overdue' || b.status === 'due_today' || b.status === 'upcoming') &&
                      <button className="btn flex items-center gap-1" onClick={() => setPaying(b)}><Check size={16} /> Paid</button>}
                    <button aria-label={`Edit ${b.name}`} className="p-1" onClick={() => setEditing(b)}><Pencil size={16} /></button>
                    <button aria-label={`Delete ${b.name}`} className="p-1" onClick={() => setDelId(b.id)}><Trash2 size={16} /></button>
                  </>)}
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {editing && <BillForm bill={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onDone={() => { setEditing(null); reload() }} />}
      {paying && <PayForm bill={paying} onClose={() => setPaying(null)} onDone={() => { setPaying(null); reload() }} />}
    </div>
  )
}
