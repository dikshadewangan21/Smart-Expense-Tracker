import { Pause, Pencil, Play, Plus, Trash2, Undo2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money } from '../lib/format'
import { FREQ_LABEL, num } from '../lib/types'
import { useLookups } from '../lib/useLookups'
import { Empty, ErrorBox, Modal, Skeleton, ghost, useLoad } from '../components/ui'

interface Sub {
  id: number; merchant: string; merchant_key: string; amount: number | string; frequency: string; category_id: number | null; category: string | null
  status: string; reminder: boolean; last_date: string | null; next_expected: string | null; days_until_next: number | null
  monthly_equivalent: number | string; annual_cost: number | string; confidence: number | null; occurrences: number; source: string
}
interface SubsResp { items: Sub[]; totals: { count: number; monthly_cost: number; annual_cost: number }; pending_review: number }
interface Cand {
  merchant_key: string; merchant: string; amount: string; frequency: string; category_id: number | null; category: string | null
  last_date: string; next_expected: string; occurrences: number; confidence: number; suggested: boolean; amount_varies: boolean
  monthly_equivalent: string; annual_cost: string; reasons: string[]
}

const FREQS = ['weekly', 'biweekly', 'monthly', 'quarterly', 'yearly']
const SORTS = [['monthly', 'Monthly cost'], ['cost', 'Charge amount'], ['renewal', 'Next renewal'], ['category', 'Category']]

type Form = { mode: 'edit'; sub: Sub } | { mode: 'confirm'; cand: Cand } | { mode: 'add' }

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
  const title = form.mode === 'add' ? 'Add a recurring payment' : form.mode === 'confirm' ? `Confirm ${form.cand.merchant}` : `Edit ${form.sub.merchant}`

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
        await api('/recurring', { method: 'POST', body: JSON.stringify({ type: 'expense', merchant, amount, frequency, next_date: nextDate, category_id: cat }) })
      } else if (form.mode === 'confirm') {
        await api('/recurring/confirm', { method: 'POST', body: JSON.stringify({ merchant_key: form.cand.merchant_key, type: 'expense', merchant, amount, frequency, category_id: cat }) })
      } else {
        await api(`/recurring/${form.sub.id}`, { method: 'PUT', body: JSON.stringify({ merchant, amount, frequency, category_id: cat }) })
      }
      onDone()
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : 'Could not save.'); setBusy(false) }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="text-sm">Name<input className="input" value={merchant} onChange={(e) => setMerchant(e.target.value)} maxLength={160} /></label>
        <label className="text-sm">Amount ({user?.currency})<input className="input" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
        <label className="text-sm">How often
          <select className="input" value={frequency} onChange={(e) => setFrequency(e.target.value)}>{FREQS.map((f) => <option key={f} value={f}>{FREQ_LABEL[f]}</option>)}</select></label>
        <label className="text-sm">Category
          <select className="input" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">Uncategorized</option>{cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        {form.mode === 'add' && <label className="text-sm">Next payment date<input className="input" type="date" value={nextDate} onChange={(e) => setNextDate(e.target.value)} /></label>}
        {err && <p role="alert" style={{ color: 'var(--bad)' }} className="text-sm">{err}</p>}
        <div className="flex gap-2 justify-end">
          <button type="button" className="btn" style={ghost} onClick={onClose}>Cancel</button>
          <button className="btn" disabled={busy}>{form.mode === 'confirm' ? 'Confirm' : 'Save'}</button>
        </div>
      </form>
    </Modal>
  )
}

export default function Subscriptions() {
  const { user } = useAuth()
  const cur = user?.currency ?? 'INR'
  const [sort, setSort] = useState('monthly')
  const [uncertain, setUncertain] = useState(false)
  const [form, setForm] = useState<Form | null>(null)
  const [delId, setDelId] = useState<number | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  const subs = useLoad(() => api<SubsResp>(`/subscriptions?sort=${sort}&order=${sort === 'renewal' || sort === 'category' ? 'asc' : 'desc'}`), [sort])
  const cands = useLoad(() => api<Cand[]>(`/recurring/candidates?include_uncertain=${uncertain}`), [uncertain])
  const ignored = useLoad(() => api<Sub[]>('/recurring/ignored'), [])

  const refresh = () => { subs.reload(); cands.reload(); ignored.reload() }
  async function act(fn: () => Promise<unknown>) {
    setActionErr(null)
    try { await fn(); refresh() } catch (e) { setActionErr(e instanceof Error ? e.message : 'Action failed.') }
  }

  const suggested = (cands.data ?? []).filter((c) => c.suggested)
  const possible = (cands.data ?? []).filter((c) => !c.suggested)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-bold">Subscriptions</h1>
        <button className="btn flex items-center gap-1" onClick={() => setForm({ mode: 'add' })}><Plus size={16} /> Add</button>
      </div>

      {subs.error && <ErrorBox message={subs.error} onRetry={subs.reload} />}
      {actionErr && <ErrorBox message={actionErr} />}
      {!subs.data && !subs.error && <Skeleton rows={3} label="Loading subscriptions" />}

      {subs.data && (
        <section className="card" aria-label="Recurring cost summary">
          {subs.data.totals.count === 0 ? <p className="muted text-sm">No confirmed subscriptions yet.</p> : (
            <>
              <p className="text-lg">Your recurring payments cost approximately <strong>{money(subs.data.totals.monthly_cost, cur)}</strong>/month.</p>
              <p className="muted text-sm">Estimated annual recurring cost: {money(subs.data.totals.annual_cost, cur)}. Based on {subs.data.totals.count} confirmed payment(s); bills are on the <Link className="underline" to="/bills">Bills</Link> page.</p>
            </>
          )}
        </section>
      )}

      {cands.data && suggested.length > 0 && (
        <section className="card" aria-label="Detected subscriptions">
          <h2 className="font-semibold">Detected from your transactions</h2>
          <p className="muted text-xs mb-2">We found repeating payments. Nothing counts until you confirm it.</p>
          <ul className="flex flex-col divide-y" style={{ borderColor: 'var(--border)' }}>
            {suggested.map((c) => <CandRow key={c.merchant_key} c={c} cur={cur}
              onConfirm={() => act(() => api('/recurring/confirm', { method: 'POST', body: JSON.stringify({ merchant_key: c.merchant_key, type: 'expense' }) }))}
              onEdit={() => setForm({ mode: 'confirm', cand: c })}
              onIgnore={() => act(() => api('/recurring/ignore', { method: 'POST', body: JSON.stringify({ merchant_key: c.merchant_key, type: 'expense' }) }))} />)}
          </ul>
        </section>
      )}
      {cands.error && <ErrorBox message={cands.error} onRetry={cands.reload} />}

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <h2 className="font-semibold">Confirmed</h2>
          <label className="text-sm flex items-center gap-2">Sort by
            <select className="input" style={{ width: 'auto' }} value={sort} onChange={(e) => setSort(e.target.value)}>
              {SORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        </div>
        {subs.data && subs.data.items.length === 0 && (
          <Empty>{(subs.data.pending_review ?? 0) > 0 ? 'Confirm a detected payment above to see it here.' : 'Nothing here yet. Subscriptions are detected once a payment repeats at least three times, or add one yourself.'}</Empty>
        )}
        {subs.data && subs.data.items.length > 0 && (
          <div className="relative overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="muted text-left"><tr><th className="py-2">Name</th><th>Category</th><th>Frequency</th><th className="text-right">Amount</th>
                <th className="text-right">Per month</th><th>Next</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {subs.data.items.map((s) => (
                  <tr key={s.id} className="border-t" style={{ borderColor: 'var(--border)', opacity: s.status === 'paused' ? 0.6 : 1 }}>
                    <td className="py-2">{s.merchant}{s.status === 'paused' && <span className="muted"> · paused</span>}</td>
                    <td>{s.category ?? <span className="muted">—</span>}</td>
                    <td>{FREQ_LABEL[s.frequency] ?? s.frequency}</td>
                    <td className="text-right whitespace-nowrap">{money(num(s.amount), cur)}</td>
                    <td className="text-right whitespace-nowrap">{money(num(s.monthly_equivalent), cur)}</td>
                    <td className="whitespace-nowrap">{s.status === 'paused' ? '—' : s.next_expected ?? '—'}
                      {s.status !== 'paused' && s.days_until_next !== null && <span className="muted"> ({s.days_until_next < 0 ? `${-s.days_until_next}d late` : s.days_until_next === 0 ? 'today' : `in ${s.days_until_next}d`})</span>}</td>
                    <td className="whitespace-nowrap text-right">
                      {delId === s.id ? (
                        <span>Delete? <button className="underline mx-1" style={{ color: 'var(--bad)' }} onClick={() => { setDelId(null); act(() => api(`/recurring/${s.id}`, { method: 'DELETE' })) }}>Yes</button>
                          <button className="underline" onClick={() => setDelId(null)}>No</button></span>
                      ) : (<>
                        <button aria-label={`Edit ${s.merchant}`} className="p-1" onClick={() => setForm({ mode: 'edit', sub: s })}><Pencil size={16} /></button>
                        <button aria-label={s.status === 'paused' ? `Resume ${s.merchant}` : `Pause ${s.merchant}`} className="p-1"
                          onClick={() => act(() => api(`/recurring/${s.id}`, { method: 'PUT', body: JSON.stringify({ status: s.status === 'paused' ? 'confirmed' : 'paused' }) }))}>
                          {s.status === 'paused' ? <Play size={16} /> : <Pause size={16} />}</button>
                        <button aria-label={`Delete ${s.merchant}`} className="p-1" onClick={() => setDelId(s.id)}><Trash2 size={16} /></button>
                      </>)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={uncertain} onChange={(e) => setUncertain(e.target.checked)} />
          Show possible patterns (lower confidence)</label>
        {uncertain && cands.data && (possible.length === 0 ? <p className="muted text-sm mt-2">No weaker patterns found.</p> : (
          <ul className="flex flex-col divide-y mt-2">
            {possible.map((c) => <CandRow key={c.merchant_key} c={c} cur={cur}
              onConfirm={() => act(() => api('/recurring/confirm', { method: 'POST', body: JSON.stringify({ merchant_key: c.merchant_key, type: 'expense' }) }))}
              onEdit={() => setForm({ mode: 'confirm', cand: c })}
              onIgnore={() => act(() => api('/recurring/ignore', { method: 'POST', body: JSON.stringify({ merchant_key: c.merchant_key, type: 'expense' }) }))} />)}
          </ul>
        ))}
      </section>

      {ignored.data && ignored.data.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-1">Ignored</h2>
          <ul className="text-sm">
            {ignored.data.map((s) => (
              <li key={s.id} className="flex justify-between items-center py-1">
                <span>{s.merchant}</span>
                <button className="flex items-center gap-1 underline" onClick={() => act(() => api(`/recurring/${s.id}`, { method: 'DELETE' }))}><Undo2 size={14} /> Stop ignoring</button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {form && <FormModal form={form} onClose={() => setForm(null)} onDone={() => { setForm(null); refresh() }} />}
    </div>
  )
}

function CandRow({ c, cur, onConfirm, onEdit, onIgnore }: { c: Cand; cur: string; onConfirm: () => void; onEdit: () => void; onIgnore: () => void }) {
  return (
    <li className="py-3 flex flex-col gap-1 md:flex-row md:items-center md:justify-between" style={{ borderColor: 'var(--border)' }}>
      <div className="text-sm">
        <div className="font-medium">{c.merchant} <span className="muted font-normal">· {money(num(c.amount), cur)}{c.amount_varies ? ' (varies)' : ''} {FREQ_LABEL[c.frequency]?.toLowerCase()}</span></div>
        <div className="muted text-xs">{c.reasons.join('; ')}. Confidence {Math.round(c.confidence * 100)}%. Next expected {c.next_expected}. About {money(num(c.annual_cost), cur)}/year.</div>
      </div>
      <div className="flex gap-2 shrink-0">
        <button className="btn" onClick={onConfirm}>Confirm</button>
        <button className="btn" style={ghost} onClick={onEdit}>Edit</button>
        <button className="btn" style={ghost} onClick={onIgnore}>Ignore</button>
      </div>
    </li>
  )
}
