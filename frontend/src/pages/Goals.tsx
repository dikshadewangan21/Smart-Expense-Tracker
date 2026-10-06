import { ChevronDown, ChevronUp, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money, pct } from '../lib/format'
import { Empty, ErrorBox, Modal, Skeleton, Stat, ghost, useLoad } from '../components/ui'

interface Contribution { id: number; amount: number; date: string; note: string | null }
interface Goal {
  id: number; name: string; kind: string; target_amount: number; current_amount: number; remaining: number; percent: number | null
  target_date: string | null; status: 'active' | 'overdue' | 'completed'; months_left: number | null; required_monthly: number | null
  pace_monthly: number | null; estimated_completion: string | null; on_track: boolean | null; extra_needed_monthly: number | null
  notes: string[]; contributions?: Contribution[]
}
interface GoalsResp {
  items: Goal[]
  summary: { count: number; active: number; completed: number; total_target: number; total_saved: number; percent: number | null; required_monthly_total: number }
}

const KINDS: [string, string][] = [['emergency_fund', 'Emergency fund'], ['laptop', 'New laptop'], ['travel', 'Travel'], ['education', 'Education'],
  ['phone', 'Phone'], ['car', 'Car'], ['wedding', 'Wedding'], ['custom', 'Custom']]
const kindLabel = (k: string) => KINDS.find(([v]) => v === k)?.[1] ?? k
const todayStr = (tz?: string) => { try { return new Date().toLocaleDateString('en-CA', { timeZone: tz }) } catch { return new Date().toLocaleDateString('en-CA') } }

function GoalForm({ goal, onClose, onDone }: { goal: Goal | null; onClose: () => void; onDone: () => void }) {
  const { user } = useAuth()
  const [name, setName] = useState(goal?.name ?? '')
  const [kind, setKind] = useState(goal?.kind ?? 'custom')
  const [target, setTarget] = useState(goal ? String(goal.target_amount) : '')
  const [saved, setSaved] = useState('0')
  const [date, setDate] = useState(goal?.target_date ?? '')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    if (!name.trim()) return setErr('Enter a name.')
    if (!(Number(target) > 0)) return setErr('Enter a target greater than zero.')
    if (!goal && !(Number(saved) >= 0)) return setErr('Amount already saved can\'t be negative.')
    setBusy(true)
    try {
      if (goal) {
        await api(`/goals/${goal.id}`, { method: 'PUT', body: JSON.stringify({ name, kind, target_amount: target, target_date: date || null, clear_target_date: !date }) })
      } else {
        await api('/goals', { method: 'POST', body: JSON.stringify({ name, kind, target_amount: target, current_amount: saved || '0', target_date: date || null }) })
      }
      onDone()
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : 'Could not save.'); setBusy(false) }
  }

  return (
    <Modal title={goal ? `Edit ${goal.name}` : 'New goal'} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="text-sm">Name<input className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} /></label>
        <label className="text-sm">Type<select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-sm">Target ({user?.currency})<input className="input" inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} /></label>
          {!goal && <label className="text-sm">Already saved<input className="input" inputMode="decimal" value={saved} onChange={(e) => setSaved(e.target.value)} /></label>}
        </div>
        <label className="text-sm">Target date (optional)<input className="input" type="date" value={date} min={goal ? undefined : todayStr(user?.timezone)} onChange={(e) => setDate(e.target.value)} /></label>
        {goal && <p className="muted text-xs">To change the saved amount, add or withdraw money on the goal so the history explains the number.</p>}
        {err && <p role="alert" style={{ color: 'var(--bad)' }} className="text-sm">{err}</p>}
        <div className="flex gap-2 justify-end"><button type="button" className="btn" style={ghost} onClick={onClose}>Cancel</button><button className="btn" disabled={busy}>Save</button></div>
      </form>
    </Modal>
  )
}

function MoneyForm({ goal, withdraw, onClose, onDone }: { goal: Goal; withdraw: boolean; onClose: () => void; onDone: () => void }) {
  const { user } = useAuth()
  const [amount, setAmount] = useState('')
  const [date, setDate] = useState(todayStr(user?.timezone))
  const [note, setNote] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!(Number(amount) > 0)) return setErr('Enter an amount greater than zero.')
    setBusy(true); setErr(null)
    try {
      await api(`/goals/${goal.id}/contributions`, { method: 'POST', body: JSON.stringify({ amount: withdraw ? `-${amount}` : amount, date, note: note || null }) })
      onDone()
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : 'Could not save.'); setBusy(false) }
  }

  return (
    <Modal title={`${withdraw ? 'Withdraw from' : 'Add money to'} ${goal.name}`} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="text-sm">Amount ({user?.currency})<input className="input" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus /></label>
          <label className="text-sm">Date<input className="input" type="date" value={date} max={todayStr(user?.timezone)} onChange={(e) => setDate(e.target.value)} /></label>
        </div>
        <label className="text-sm">Note (optional)<input className="input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} /></label>
        <p className="muted text-xs">This tracks money you set aside. It isn't a transaction, so it doesn't count as spending.</p>
        {err && <p role="alert" style={{ color: 'var(--bad)' }} className="text-sm">{err}</p>}
        <div className="flex gap-2 justify-end"><button type="button" className="btn" style={ghost} onClick={onClose}>Cancel</button><button className="btn" disabled={busy}>{withdraw ? 'Withdraw' : 'Add'}</button></div>
      </form>
    </Modal>
  )
}

function Verdict({ g, cur }: { g: Goal; cur: string }) {
  if (g.status === 'completed') return <span style={{ color: 'var(--good)' }}>Goal reached</span>
  if (g.on_track === true) return <span style={{ color: 'var(--good)' }}>On track{g.estimated_completion ? `: about ${g.estimated_completion}` : ''}</span>
  if (g.on_track === false) return <span style={{ color: 'var(--warn)' }}>Behind: about {g.estimated_completion}, after the target date. {g.extra_needed_monthly !== null && `Roughly ${money(g.extra_needed_monthly, cur)} more a month would catch up.`}</span>
  if (g.estimated_completion) return <span>At your pace: about {g.estimated_completion}</span>
  return <span className="muted">No estimate yet</span>
}

export default function Goals() {
  const { user } = useAuth()
  const cur = user?.currency ?? 'INR'
  const { data, error, reload } = useLoad(() => api<GoalsResp>('/goals'), [])
  const [form, setForm] = useState<Goal | 'new' | null>(null)
  const [money_, setMoney] = useState<{ goal: Goal; withdraw: boolean } | null>(null)
  const [open, setOpen] = useState<number | null>(null)
  const [detail, setDetail] = useState<Record<number, Contribution[]>>({})
  const [delId, setDelId] = useState<number | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  async function toggle(g: Goal) {
    if (open === g.id) return setOpen(null)
    try { setDetail({ ...detail, [g.id]: (await api<Goal>(`/goals/${g.id}`)).contributions ?? [] }); setOpen(g.id) }
    catch (e) { setActionErr(e instanceof Error ? e.message : 'Could not load history.') }
  }
  async function act(fn: () => Promise<unknown>) {
    setActionErr(null)
    try { await fn(); setOpen(null); setDetail({}); reload() } catch (e) { setActionErr(e instanceof Error ? e.message : 'Action failed.') }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Savings goals</h1>
        <button className="btn flex items-center gap-1" onClick={() => setForm('new')}><Plus size={16} /> New goal</button>
      </div>
      {error && <ErrorBox message={error} onRetry={reload} />}
      {actionErr && <ErrorBox message={actionErr} />}
      {!data && !error && <Skeleton rows={3} label="Loading goals" />}

      {data && data.items.length > 0 && (
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
          <Stat label="Saved so far" value={money(data.summary.total_saved, cur)} sub={`of ${money(data.summary.total_target, cur)}`} />
          <Stat label="Overall progress" value={pct(data.summary.percent)} />
          <Stat label="Needed per month" value={money(data.summary.required_monthly_total, cur)} sub="to hit every dated goal on time" />
          <Stat label="Goals" value={`${data.summary.active} active`} sub={`${data.summary.completed} completed`} />
        </div>
      )}
      {data && data.items.length === 0 && (
        <div className="card"><Empty>No goals yet. Set one (emergency fund, laptop, trip) and we'll work out what to save each month.</Empty></div>
      )}

      {data && data.items.map((g) => (
        <section key={g.id} className="card flex flex-col gap-2" aria-label={g.name}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="font-semibold">{g.name} <span className="muted font-normal text-sm">· {kindLabel(g.kind)}{g.status === 'overdue' && ' · date passed'}</span></h2>
              <div className="text-sm muted">{money(g.current_amount, cur)} of {money(g.target_amount, cur)}{g.target_date ? ` · by ${g.target_date}` : ' · no target date'}</div>
            </div>
            <div className="flex items-center gap-1">
              {g.status !== 'completed' && <button className="btn" onClick={() => setMoney({ goal: g, withdraw: false })}>Add money</button>}
              <button className="btn" style={ghost} onClick={() => setMoney({ goal: g, withdraw: true })} disabled={g.current_amount <= 0}>Withdraw</button>
              <button aria-label={`Edit ${g.name}`} className="p-1" onClick={() => setForm(g)}><Pencil size={16} /></button>
              {delId === g.id ? (
                <span className="text-sm">Delete? <button className="underline mx-1" style={{ color: 'var(--bad)' }} onClick={() => { setDelId(null); act(() => api(`/goals/${g.id}`, { method: 'DELETE' })) }}>Yes</button><button className="underline" onClick={() => setDelId(null)}>No</button></span>
              ) : <button aria-label={`Delete ${g.name}`} className="p-1" onClick={() => setDelId(g.id)}><Trash2 size={16} /></button>}
            </div>
          </div>
          <div className="h-2 rounded" style={{ background: 'var(--border)' }} role="progressbar" aria-label={`${g.name} progress`} aria-valuenow={Math.round(g.percent ?? 0)} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-2 rounded" style={{ width: `${g.percent ?? 0}%`, background: g.status === 'completed' ? 'var(--good)' : 'var(--accent)' }} />
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <span>{pct(g.percent)} · {money(g.remaining, cur)} to go</span>
            {g.required_monthly !== null && <span>Needs <strong>{money(g.required_monthly, cur)}</strong>/month for {g.months_left} month(s)</span>}
            {g.pace_monthly !== null && <span>Your recent pace: {money(g.pace_monthly, cur)}/month</span>}
          </div>
          <div className="text-sm"><Verdict g={g} cur={cur} /></div>
          {g.notes.map((n) => <p key={n} className="muted text-xs">{n}</p>)}
          <button className="text-sm flex items-center gap-1 underline self-start" onClick={() => toggle(g)} aria-expanded={open === g.id}>
            {open === g.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />} History
          </button>
          {open === g.id && (
            <ul className="text-sm border-t pt-2" style={{ borderColor: 'var(--border)' }}>
              {(detail[g.id] ?? []).length === 0 ? <li className="muted">No contributions recorded yet.</li> : (detail[g.id] ?? []).map((c) => (
                <li key={c.id} className="flex justify-between items-center py-0.5">
                  <span>{c.date} <span className="muted">{c.note ?? ''}</span></span>
                  <span style={{ color: c.amount < 0 ? 'var(--bad)' : 'var(--good)' }}>{c.amount < 0 ? '−' : '+'}{money(Math.abs(c.amount), cur)}
                    <button className="p-1 ml-1" aria-label="Remove contribution" onClick={() => act(() => api(`/goals/${g.id}/contributions/${c.id}`, { method: 'DELETE' }))}><Trash2 size={14} /></button></span>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}

      {form && <GoalForm goal={form === 'new' ? null : form} onClose={() => setForm(null)} onDone={() => { setForm(null); setOpen(null); setDetail({}); reload() }} />}
      {money_ && <MoneyForm goal={money_.goal} withdraw={money_.withdraw} onClose={() => setMoney(null)} onDone={() => { setMoney(null); setOpen(null); setDetail({}); reload() }} />}
    </div>
  )
}
