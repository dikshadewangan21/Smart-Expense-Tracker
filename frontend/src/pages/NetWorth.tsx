import { Archive, ArchiveRestore, Pencil, Plus, TrendingUp, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money } from '../lib/format'
import { Empty, ErrorBox, Modal, Skeleton, Stat, ghost, useLoad } from '../components/ui'

interface Line { key: string; label: string; amount: number; items: { name: string; amount: number }[] }
interface NW {
  as_of: string; currency: string; assets: number; liabilities: number; net_worth: number
  assets_breakdown: Line[]; liabilities_breakdown: Line[]
  accounts: { id: number; name: string; kind: string; balance: number; valued_on: string | null; opening_balance: number }[]
  trend: { date: string; label: string; assets: number; liabilities: number; net_worth: number }[]
  change: { compared_to: string; net_worth: number; assets: number; liabilities: number }
  unassigned: { count: number; net: number }
  excluded_other_currency: number
  notes: string[]
}
interface Acc { id: number; name: string; kind: string; opening_balance: number | string; archived: boolean }
interface Val { id: number; date: string; value: number | string; note: string | null }

const KINDS: [string, string][] = [['bank', 'Bank account'], ['cash', 'Cash'], ['wallet', 'Wallet / UPI'], ['credit_card', 'Credit card'],
  ['investment', 'Investment'], ['property', 'Property'], ['other', 'Other']]
const kindLabel = (k: string) => KINDS.find(([v]) => v === k)?.[1] ?? k
const VALUED = ['investment', 'property', 'other']
const todayStr = (tz?: string) => { try { return new Date().toLocaleDateString('en-CA', { timeZone: tz }) } catch { return new Date().toLocaleDateString('en-CA') } }

function AccountForm({ acc, onClose, onDone }: { acc: Acc | null; onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState(acc?.name ?? '')
  const [kind, setKind] = useState(acc?.kind ?? 'bank')
  const [open, setOpen] = useState(acc ? String(acc.opening_balance) : '0')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(null)
    if (!name.trim()) return setErr('Enter a name.')
    if (open.trim() === '' || Number.isNaN(Number(open))) return setErr('Enter a valid opening balance (negative for a credit card you owe on).')
    setBusy(true)
    try {
      const body = JSON.stringify({ name, kind, opening_balance: open })
      if (acc) await api(`/accounts/${acc.id}`, { method: 'PUT', body })
      else await api('/accounts', { method: 'POST', body })
      onDone()
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : 'Could not save.'); setBusy(false) }
  }
  return (
    <Modal title={acc ? `Edit ${acc.name}` : 'New account'} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="text-sm">Name<input className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} /></label>
        <label className="text-sm">Type<select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label className="text-sm">Opening balance<input className="input" inputMode="decimal" value={open} onChange={(e) => setOpen(e.target.value)} /></label>
        <p className="muted text-xs">Balance = opening balance + your recorded transactions. Changing it restates history.</p>
        {err && <ErrorBox message={err} />}
        <button className="btn" disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
      </form>
    </Modal>
  )
}

function ValuationModal({ acc, onClose, onDone }: { acc: { id: number; name: string }; onClose: () => void; onDone: () => void }) {
  const { user } = useAuth()
  const [date, setDate] = useState(todayStr(user?.timezone))
  const [value, setValue] = useState('')
  const [note, setNote] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const { data, error, reload } = useLoad(() => api<Val[]>(`/accounts/${acc.id}/valuations`), [acc.id])
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(null)
    if (value.trim() === '' || Number.isNaN(Number(value))) return setErr('Enter the current value.')
    setBusy(true)
    try {
      await api(`/accounts/${acc.id}/valuations`, { method: 'POST', body: JSON.stringify({ date, value, note: note || null }) })
      setValue(''); setNote(''); reload(); onDone()
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : 'Could not save.') }
    setBusy(false)
  }
  async function del(id: number) {
    try { await api(`/accounts/${acc.id}/valuations/${id}`, { method: 'DELETE' }); reload(); onDone() }
    catch (e2) { setErr(e2 instanceof Error ? e2.message : 'Could not delete.') }
  }
  return (
    <Modal title={`Value of ${acc.name}`} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="text-sm">As of<input type="date" className="input" value={date} max={todayStr(user?.timezone)} onChange={(e) => setDate(e.target.value)} /></label>
          <label className="text-sm">Worth ({user?.currency})<input className="input" inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} /></label>
        </div>
        <label className="text-sm">Note (optional)<input className="input" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} /></label>
        <p className="muted text-xs">You enter this value yourself; it is not fetched from a broker. Transactions after this date adjust it.</p>
        {err && <ErrorBox message={err} />}
        <button className="btn" disabled={busy}>{busy ? 'Saving…' : 'Save value'}</button>
      </form>
      <h3 className="font-semibold text-sm mt-4 mb-1">History</h3>
      {error ? <ErrorBox message={error} onRetry={reload} /> : !data ? <Skeleton rows={2} /> : data.length === 0 ? <p className="muted text-sm">No values recorded yet.</p> : (
        <ul className="text-sm divide-y" style={{ borderColor: 'var(--border)' }}>
          {data.map((v) => (
            <li key={v.id} className="flex items-center justify-between py-1.5 gap-2">
              <span>{v.date}{v.note ? <span className="muted"> · {v.note}</span> : null}</span>
              <span className="flex items-center gap-2">{money(Number(v.value), user?.currency)}
                <button aria-label={`Delete value from ${v.date}`} onClick={() => del(v.id)} className="p-1"><Trash2 size={14} /></button></span>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  )
}

function Breakdown({ title, lines, cur, tone }: { title: string; lines: Line[]; cur: string; tone: 'good' | 'bad' }) {
  return (
    <section className="card" aria-label={title}>
      <h2 className="font-semibold mb-2">{title}</h2>
      {lines.length === 0 ? <p className="muted text-sm">Nothing here.</p> : lines.map((l) => (
        <div key={l.key} className="mb-3 last:mb-0">
          <div className="flex justify-between font-medium text-sm"><span>{l.label}</span><span style={{ color: `var(--${tone})` }}>{money(l.amount, cur)}</span></div>
          <ul className="muted text-xs mt-1">{l.items.map((it, i) => <li key={i} className="flex justify-between"><span className="truncate pr-2">{it.name}</span><span>{money(it.amount, cur)}</span></li>)}</ul>
        </div>
      ))}
    </section>
  )
}

export default function NetWorth() {
  const [months, setMonths] = useState(12)
  const nw = useLoad(() => api<NW>(`/net-worth?months=${months}`), [months])
  const accs = useLoad(() => api<Acc[]>('/accounts?include_archived=true'), [])
  const [edit, setEdit] = useState<Acc | 'new' | null>(null)
  const [val, setVal] = useState<{ id: number; name: string } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { document.title = 'Net worth · Smart Expense Tracker' }, [])
  const refresh = () => { nw.reload(); accs.reload() }

  async function archive(a: Acc, archived: boolean) {
    setErr(null)
    try { await api(`/accounts/${a.id}`, { method: 'PUT', body: JSON.stringify({ archived }) }); refresh() }
    catch (e) { setErr(e instanceof Error ? e.message : 'Could not update the account.') }
  }

  if (nw.error) return <ErrorBox message={nw.error} onRetry={nw.reload} />
  if (!nw.data) return <Skeleton rows={6} label="Loading net worth" />
  const d = nw.data
  const cur = d.currency
  const empty = d.accounts.length === 0 && d.liabilities_breakdown.length === 0 && d.assets_breakdown.length === 0
  const ch = d.change
  const balances = new Map(d.accounts.map((a) => [a.id, a]))
  const chartData = d.trend.map((t) => ({ ...t }))

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-bold">Net worth</h1>
        <button className="btn" onClick={() => setEdit('new')}><Plus size={16} aria-hidden /> Add account</button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Stat label="Net worth" value={money(d.net_worth, cur)} tone={d.net_worth < 0 ? 'bad' : undefined}
          sub={<>{ch.net_worth >= 0 ? '+' : '−'}{money(Math.abs(ch.net_worth), cur)} since {ch.compared_to}</>} />
        <Stat label="Assets" value={money(d.assets, cur)} tone="good" />
        <Stat label="Liabilities" value={money(d.liabilities, cur)} tone={d.liabilities > 0 ? 'bad' : undefined} />
      </div>

      {err && <ErrorBox message={err} />}
      {d.notes.length > 0 && (
        <ul className="card text-sm flex flex-col gap-1" style={{ borderColor: 'var(--warn)' }} aria-label="Notes">
          {d.notes.map((n, i) => <li key={i}>⚠ {n}</li>)}
        </ul>
      )}

      {empty ? <Empty>No accounts or debts yet. Add an account with its opening balance to start tracking net worth.</Empty> : (
        <>
          <section className="card" aria-label="Net worth trend">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-semibold flex items-center gap-2"><TrendingUp size={16} aria-hidden /> Trend</h2>
              <select className="input w-auto" aria-label="Trend length" value={months} onChange={(e) => setMonths(Number(e.target.value))}>
                <option value={6}>6 months</option><option value={12}>12 months</option><option value={24}>24 months</option>
              </select>
            </div>
            <div style={{ width: '100%', height: 240 }}>
              <ResponsiveContainer>
                <AreaChart data={chartData} margin={{ left: 0, right: 8, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 11 }} width={56} tickFormatter={(v: number) => Math.abs(v) >= 100000 ? `${(v / 100000).toFixed(1)}L` : `${Math.round(v / 1000)}k`} />
                  <Tooltip formatter={(v) => money(Number(v), cur)} />
                  <Area type="monotone" dataKey="net_worth" name="Net worth" stroke="var(--accent, #4f46e5)" fill="var(--accent, #4f46e5)" fillOpacity={0.15} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <p className="muted text-xs mt-1">History is rebuilt from your current opening balances, values and transactions. If those are wrong, so is the past.</p>
          </section>

          <div className="grid md:grid-cols-2 gap-3">
            <Breakdown title="Assets" lines={d.assets_breakdown} cur={cur} tone="good" />
            <Breakdown title="Liabilities" lines={d.liabilities_breakdown} cur={cur} tone="bad" />
          </div>
        </>
      )}

      <section className="card" aria-label="Accounts">
        <h2 className="font-semibold mb-2">Accounts</h2>
        {accs.error ? <ErrorBox message={accs.error} onRetry={accs.reload} /> : !accs.data ? <Skeleton rows={3} /> : accs.data.length === 0 ? (
          <p className="muted text-sm">No accounts yet.</p>
        ) : (
          <ul className="divide-y" style={{ borderColor: 'var(--border)' }}>
            {accs.data.map((a) => {
              const b = balances.get(a.id)
              return (
                <li key={a.id} className="py-2 flex items-center justify-between gap-2 flex-wrap" style={a.archived ? { opacity: 0.6 } : {}}>
                  <div className="min-w-0">
                    <div className="font-medium truncate">{a.name}{a.archived && <span className="muted text-xs"> (archived)</span>}</div>
                    <div className="muted text-xs">{kindLabel(a.kind)}{b?.valued_on ? ` · valued ${b.valued_on}` : ''}</div>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="font-semibold mr-2">{b ? money(b.balance, cur) : '—'}</span>
                    {VALUED.includes(a.kind) && !a.archived && <button className="btn" style={ghost} onClick={() => setVal({ id: a.id, name: a.name })}>Update value</button>}
                    <button className="p-2" aria-label={`Edit ${a.name}`} onClick={() => setEdit(a)}><Pencil size={16} /></button>
                    {a.archived
                      ? <button className="p-2" aria-label={`Restore ${a.name}`} onClick={() => archive(a, false)}><ArchiveRestore size={16} /></button>
                      : <button className="p-2" aria-label={`Archive ${a.name}`} onClick={() => archive(a, true)}><Archive size={16} /></button>}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
        <p className="muted text-xs mt-2">Archiving hides an account from pickers and net worth; its transactions stay. Goals are not counted in net worth.</p>
        {d.unassigned.count > 0 && <p className="muted text-xs mt-1">{d.unassigned.count} transactions have no account, so they are not in these balances.</p>}
        {d.excluded_other_currency > 0 && <p className="muted text-xs mt-1">{d.excluded_other_currency} records in another currency are excluded.</p>}
      </section>

      {edit && <AccountForm acc={edit === 'new' ? null : edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); refresh() }} />}
      {val && <ValuationModal acc={val} onClose={() => setVal(null)} onDone={refresh} />}
    </div>
  )
}
