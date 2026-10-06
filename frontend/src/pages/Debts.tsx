import { ChevronDown, ChevronUp, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money, pct } from '../lib/format'
import { PAYMENT_METHODS, num } from '../lib/types'
import { useLookups } from '../lib/useLookups'
import { Empty, ErrorBox, Modal, Skeleton, Stat, ghost, useLoad } from '../components/ui'

interface Payment { id: number; date: string; amount: number; principal_paid: number; interest_paid: number; transaction_id: number | null }
interface Debt {
  id: number; name: string; kind: string; direction: 'owed' | 'lent'; principal: number; remaining: number; interest_rate: string | number | null
  emi: number | null; due_day: number | null; start_date: string | null; bill_id: number | null; bill_name: string | null; paid_off: boolean
  progress_percent: number | null; principal_paid_total: number; interest_paid_total: number; payments_count: number; last_payment_date: string | null
  next_due_date: string | null; days_until_due: number | null
  payoff: null | { months?: number; payoff_date?: string | null; total_interest?: number; total_paid?: number; reason?: string }
  payments?: Payment[]
}
interface DebtsResp {
  items: Debt[]
  summary: { total_owed: number; total_lent: number; monthly_emi: number; debt_to_income_percent: number | null; interest_paid_total: number; active: number; paid_off: number }
}
interface BillLite { id: number; name: string }

const KINDS: [string, string][] = [['personal', 'Personal loan'], ['education', 'Education loan'], ['credit_card', 'Credit card debt'],
  ['borrowed', 'Borrowed money'], ['lent', 'Money lent to others']]
const kindLabel = (k: string) => KINDS.find(([v]) => v === k)?.[1] ?? k
const todayStr = (tz?: string) => { try { return new Date().toLocaleDateString('en-CA', { timeZone: tz }) } catch { return new Date().toLocaleDateString('en-CA') } }

function DebtForm({ debt, onClose, onDone }: { debt: Debt | null; onClose: () => void; onDone: () => void }) {
  const { user } = useAuth()
  const bills = useLoad(() => api<{ items: BillLite[] }>('/bills'), [])
  const [name, setName] = useState(debt?.name ?? '')
  const [kind, setKind] = useState(debt?.kind ?? 'personal')
  const [principal, setPrincipal] = useState(debt ? String(debt.principal) : '')
  const [remaining, setRemaining] = useState(debt ? String(debt.remaining) : '')
  const [rate, setRate] = useState(debt?.interest_rate != null ? String(num(debt.interest_rate)) : '')
  const [emi, setEmi] = useState(debt?.emi ? String(debt.emi) : '')
  const [dueDay, setDueDay] = useState(debt?.due_day ? String(debt.due_day) : '')
  const [start, setStart] = useState(debt?.start_date ?? '')
  const [billId, setBillId] = useState(debt?.bill_id ? String(debt.bill_id) : '')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const lent = kind === 'lent'

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    if (!name.trim()) return setErr('Enter a name.')
    if (!(Number(principal) > 0)) return setErr('Enter the original amount, greater than zero.')
    if (debt && !(Number(remaining) >= 0 && remaining !== '')) return setErr('Enter what is left (0 if fully paid).')
    if (rate !== '' && !(Number(rate) >= 0 && Number(rate) <= 100)) return setErr('Interest rate must be between 0 and 100.')
    if (dueDay !== '' && !(Number.isInteger(Number(dueDay)) && Number(dueDay) >= 1 && Number(dueDay) <= 31)) return setErr('Due day must be 1 to 31.')
    setBusy(true)
    const body: Record<string, unknown> = {
      name, kind, principal, interest_rate: rate || null, emi: emi || null, due_day: dueDay ? Number(dueDay) : null,
      start_date: start || null, bill_id: !lent && billId ? Number(billId) : null,
    }
    if (debt) body.remaining = remaining
    else if (remaining !== '') body.remaining = remaining
    try {
      await api(debt ? `/debts/${debt.id}` : '/debts', { method: debt ? 'PUT' : 'POST', body: JSON.stringify(body) })
      onDone()
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : 'Could not save.'); setBusy(false) }
  }

  return (
    <Modal title={debt ? `Edit ${debt.name}` : 'Add a debt or loan'} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="text-sm">Name<input className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} /></label>
        <label className="text-sm">Type<select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-sm">Original amount ({user?.currency})<input className="input" inputMode="decimal" value={principal} onChange={(e) => setPrincipal(e.target.value)} /></label>
          <label className="text-sm">{lent ? 'Still owed to you' : 'Remaining'}<input className="input" inputMode="decimal" value={remaining} placeholder={debt ? '' : 'Same as original'} onChange={(e) => setRemaining(e.target.value)} /></label>
          {!lent && <label className="text-sm">Interest rate (% a year)<input className="input" inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} /></label>}
          {!lent && <label className="text-sm">EMI / monthly payment<input className="input" inputMode="decimal" value={emi} onChange={(e) => setEmi(e.target.value)} /></label>}
          <label className="text-sm">Due day of month<input className="input" inputMode="numeric" value={dueDay} onChange={(e) => setDueDay(e.target.value)} /></label>
          <label className="text-sm">Started on<input className="input" type="date" value={start} max={todayStr(user?.timezone)} onChange={(e) => setStart(e.target.value)} /></label>
        </div>
        {!lent && (
          <label className="text-sm">Linked bill (optional)
            <select className="input" value={billId} onChange={(e) => setBillId(e.target.value)}>
              <option value="">None</option>{(bills.data?.items ?? []).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select>
            <span className="muted text-xs">Paying that bill will also record a payment here, and the EMI is counted once in your health score.</span>
          </label>
        )}
        {kind === 'credit_card' && <p className="muted text-xs">If you also track this card as an account, its balance is already counted in net worth. Track it in one place only, or it counts twice.</p>}
        {err && <p role="alert" style={{ color: 'var(--bad)' }} className="text-sm">{err}</p>}
        <div className="flex gap-2 justify-end"><button type="button" className="btn" style={ghost} onClick={onClose}>Cancel</button><button className="btn" disabled={busy}>Save</button></div>
      </form>
    </Modal>
  )
}

function PayForm({ debt, onClose, onDone }: { debt: Debt; onClose: () => void; onDone: () => void }) {
  const { user } = useAuth()
  const { accounts } = useLookups()
  const lent = debt.direction === 'lent'
  const [amount, setAmount] = useState(debt.emi && !lent ? String(Math.min(debt.emi, debt.remaining + 0)) : '')
  const [date, setDate] = useState(todayStr(user?.timezone))
  const [principal, setPrincipal] = useState('')
  const [adv, setAdv] = useState(false)
  const [asExpense, setAsExpense] = useState(!lent)
  const [pm, setPm] = useState('bank_transfer')
  const [accountId, setAccountId] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!(Number(amount) > 0)) return setErr('Enter an amount greater than zero.')
    setBusy(true); setErr(null)
    const body: Record<string, unknown> = { amount, paid_on: date, create_transaction: lent ? false : asExpense, payment_method: pm, account_id: accountId ? Number(accountId) : null }
    if (adv && principal !== '') body.principal_paid = principal
    try { await api(`/debts/${debt.id}/payments`, { method: 'POST', body: JSON.stringify(body) }); onDone() }
    catch (e2) { setErr(e2 instanceof Error ? e2.message : 'Could not record.'); setBusy(false) }
  }

  return (
    <Modal title={lent ? `Repayment received: ${debt.name}` : `Payment: ${debt.name}`} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="text-sm">Amount ({user?.currency})<input className="input" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus /></label>
          <label className="text-sm">Date<input className="input" type="date" value={date} max={todayStr(user?.timezone)} onChange={(e) => setDate(e.target.value)} /></label>
        </div>
        {!lent && (
          <>
            <label className="text-sm flex gap-2 items-center"><input type="checkbox" checked={asExpense} onChange={(e) => setAsExpense(e.target.checked)} /> Also record as an expense</label>
            {asExpense && (
              <div className="grid grid-cols-2 gap-3">
                <label className="text-sm">Method<select className="input" value={pm} onChange={(e) => setPm(e.target.value)}>{PAYMENT_METHODS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
                <label className="text-sm">Account<select className="input" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                  <option value="">None</option>{accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
              </div>
            )}
            <label className="text-sm flex gap-2 items-center"><input type="checkbox" checked={adv} onChange={(e) => setAdv(e.target.checked)} /> I know how much of this was principal</label>
            {adv && <label className="text-sm">Principal part<input className="input" inputMode="decimal" value={principal} onChange={(e) => setPrincipal(e.target.value)} /></label>}
            <p className="muted text-xs">{adv ? 'The rest is recorded as interest or fees.' : debt.interest_rate && num(debt.interest_rate) > 0 ? 'Unless you say otherwise, one month of interest is estimated from the remaining balance and the rest reduces what you owe.' : 'The whole payment reduces what you owe.'}</p>
          </>
        )}
        {lent && <p className="muted text-xs">Money coming back from someone you lent to isn't income, so this is not added to your transactions.</p>}
        {err && <p role="alert" style={{ color: 'var(--bad)' }} className="text-sm">{err}</p>}
        <div className="flex gap-2 justify-end"><button type="button" className="btn" style={ghost} onClick={onClose}>Cancel</button><button className="btn" disabled={busy}>Record</button></div>
      </form>
    </Modal>
  )
}

function Payoff({ d, cur }: { d: Debt; cur: string }) {
  const p = d.payoff
  if (!p) return null
  if (p.reason) return <p className="muted text-xs">{p.reason}</p>
  return <p className="text-sm">Estimate: paid off in about <strong>{p.months} month(s)</strong>{p.payoff_date ? ` (${p.payoff_date})` : ''}, with roughly {money(num(p.total_interest), cur)} more interest, if you keep paying the EMI on time.</p>
}

export default function Debts() {
  const { user } = useAuth()
  const cur = user?.currency ?? 'INR'
  const [sort, setSort] = useState('due')
  const { data, error, reload } = useLoad(() => api<DebtsResp>(`/debts?sort=${sort}`), [sort])
  const [form, setForm] = useState<Debt | 'new' | null>(null)
  const [paying, setPaying] = useState<Debt | null>(null)
  const [open, setOpen] = useState<number | null>(null)
  const [detail, setDetail] = useState<Record<number, Payment[]>>({})
  const [delId, setDelId] = useState<number | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  const refresh = () => { setOpen(null); setDetail({}); reload() }
  async function toggle(d: Debt) {
    if (open === d.id) return setOpen(null)
    try { setDetail({ ...detail, [d.id]: (await api<Debt>(`/debts/${d.id}`)).payments ?? [] }); setOpen(d.id) }
    catch (e) { setActionErr(e instanceof Error ? e.message : 'Could not load payments.') }
  }
  async function act(fn: () => Promise<unknown>) {
    setActionErr(null)
    try { await fn(); refresh() } catch (e) { setActionErr(e instanceof Error ? e.message : 'Action failed.') }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Debts &amp; loans</h1>
        <button className="btn flex items-center gap-1" onClick={() => setForm('new')}><Plus size={16} /> Add</button>
      </div>
      {error && <ErrorBox message={error} onRetry={reload} />}
      {actionErr && <ErrorBox message={actionErr} />}
      {!data && !error && <Skeleton rows={3} label="Loading debts" />}

      {data && data.items.length > 0 && (
        <>
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            <Stat label="You owe" value={money(data.summary.total_owed, cur)} />
            <Stat label="Owed to you" value={money(data.summary.total_lent, cur)} />
            <Stat label="Monthly EMIs" value={money(data.summary.monthly_emi, cur)}
              sub={data.summary.debt_to_income_percent === null ? 'No income recorded to compare with' : `${pct(data.summary.debt_to_income_percent)} of typical monthly income`} />
            <Stat label="Interest paid so far" value={money(data.summary.interest_paid_total, cur)} sub="from payments you recorded" />
          </div>
          <div className="flex justify-end">
            <label className="text-sm flex items-center gap-2">Sort by
              <select className="input" style={{ width: 'auto' }} value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="due">Next due</option><option value="remaining">Amount left</option><option value="rate">Interest rate</option><option value="name">Name</option></select></label>
          </div>
        </>
      )}
      {data && data.items.length === 0 && <div className="card"><Empty>No debts or loans yet. Add a loan, a credit-card balance, or money you lent to someone.</Empty></div>}

      {data && data.items.map((d) => (
        <section key={d.id} className="card flex flex-col gap-2" aria-label={d.name} style={d.paid_off ? { opacity: 0.7 } : {}}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="font-semibold">{d.name} <span className="muted font-normal text-sm">· {kindLabel(d.kind)}{d.paid_off && ' · paid off'}</span></h2>
              <div className="text-sm muted">
                {money(d.remaining, cur)} {d.direction === 'lent' ? 'still owed to you' : 'left'} of {money(d.principal, cur)}
                {d.interest_rate != null && num(d.interest_rate) > 0 ? ` · ${num(d.interest_rate)}% a year` : ''}{d.emi ? ` · EMI ${money(d.emi, cur)}` : ''}
              </div>
            </div>
            <div className="flex items-center gap-1">
              {!d.paid_off && <button className="btn" onClick={() => setPaying(d)}>{d.direction === 'lent' ? 'Repayment' : 'Record payment'}</button>}
              <button aria-label={`Edit ${d.name}`} className="p-1" onClick={() => setForm(d)}><Pencil size={16} /></button>
              {delId === d.id ? (
                <span className="text-sm">Delete? <button className="underline mx-1" style={{ color: 'var(--bad)' }} onClick={() => { setDelId(null); act(() => api(`/debts/${d.id}`, { method: 'DELETE' })) }}>Yes</button><button className="underline" onClick={() => setDelId(null)}>No</button></span>
              ) : <button aria-label={`Delete ${d.name}`} className="p-1" onClick={() => setDelId(d.id)}><Trash2 size={16} /></button>}
            </div>
          </div>
          <div className="h-2 rounded" style={{ background: 'var(--border)' }} role="progressbar" aria-label={`${d.name} repaid`} aria-valuenow={Math.round(d.progress_percent ?? 0)} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-2 rounded" style={{ width: `${d.progress_percent ?? 0}%`, background: 'var(--good)' }} />
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <span>{pct(d.progress_percent)} {d.direction === 'lent' ? 'repaid to you' : 'repaid'}</span>
            {d.next_due_date && <span>Next due {d.next_due_date} ({d.days_until_due === 0 ? 'today' : `in ${d.days_until_due} day(s)`})</span>}
            {d.bill_name && <span className="muted">Linked bill: {d.bill_name}</span>}
            {d.payments_count > 0 && <span className="muted">{d.payments_count} payment(s) · {money(d.interest_paid_total, cur)} interest/fees</span>}
          </div>
          <Payoff d={d} cur={cur} />
          <button className="text-sm flex items-center gap-1 underline self-start" onClick={() => toggle(d)} aria-expanded={open === d.id}>
            {open === d.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />} Payment history
          </button>
          {open === d.id && (
            <ul className="text-sm border-t pt-2" style={{ borderColor: 'var(--border)' }}>
              {(detail[d.id] ?? []).length === 0 ? <li className="muted">No payments recorded yet.</li> : (detail[d.id] ?? []).map((p) => (
                <li key={p.id} className="flex justify-between items-center py-0.5">
                  <span>{p.date} <span className="muted">principal {money(p.principal_paid, cur)}{p.interest_paid > 0 ? ` · interest ${money(p.interest_paid, cur)}` : ''}{p.transaction_id ? ' · in transactions' : ''}</span></span>
                  <span>{money(p.amount, cur)}<button className="p-1 ml-1" aria-label="Undo payment" onClick={() => act(() => api(`/debts/${d.id}/payments/${p.id}`, { method: 'DELETE' }))}><Trash2 size={14} /></button></span>
                </li>
              ))}
              {(detail[d.id] ?? []).some((p) => p.transaction_id) && <li className="muted text-xs pt-1">Undoing a payment restores the balance but keeps its expense in Transactions; delete that there if it was a mistake.</li>}
            </ul>
          )}
        </section>
      ))}
      {data && data.items.length > 0 && <p className="muted text-xs">Figures come from what you entered. Payoff dates are estimates, not financial advice.</p>}

      {form && <DebtForm debt={form === 'new' ? null : form} onClose={() => setForm(null)} onDone={() => { setForm(null); refresh() }} />}
      {paying && <PayForm debt={paying} onClose={() => setPaying(null)} onDone={() => { setPaying(null); refresh() }} />}
    </div>
  )
}
