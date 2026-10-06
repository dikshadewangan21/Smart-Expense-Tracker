import { Copy, Pencil, Plus, Trash2, Zap, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { money } from '../lib/format'
import { PAYMENT_METHODS, pmLabel, type TxPage } from '../lib/types'
import { useLookups } from '../lib/useLookups'
import { Modal, ghost } from '../components/ui'

const FILTER_KEYS = ['q', 'type', 'category_id', 'payment_method', 'date_from', 'date_to', 'min_amount', 'max_amount', 'tag', 'uncategorized', 'merchant_exact', 'sort', 'order', 'page']

export default function Transactions() {
  const [params, setParams] = useSearchParams()
  const { categories } = useLookups()
  const nav = useNavigate()
  const [data, setData] = useState<TxPage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)

  // Quick Add state
  const [quickAddModal, setQuickAddModal] = useState(false)
  const [quickAddText, setQuickAddText] = useState('')
  const [quickAddBusy, setQuickAddBusy] = useState(false)
  const [quickAddErr, setQuickAddErr] = useState<string | null>(null)

  // NL Search state
  const [nlSearchText, setNlSearchText] = useState('')
  const [nlBusy, setNlBusy] = useState(false)

  const query = FILTER_KEYS.filter((k) => params.get(k)).map((k) => `${k}=${encodeURIComponent(params.get(k)!)}`).join('&')

  const load = useCallback(() => {
    setError(null)
    api<TxPage>(`/transactions?page_size=25${query ? '&' + query : ''}`).then(setData).catch((e) => setError(e.message))
  }, [query])
  useEffect(load, [load])

  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params)
    if (v) next.set(k, v); else next.delete(k)
    if (k !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  async function act(fn: () => Promise<unknown>) {
    try { await fn(); load() } catch (e) { setError(e instanceof Error ? e.message : 'Action failed.') }
  }

  async function handleQuickAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!quickAddText.trim()) return
    setQuickAddBusy(true)
    setQuickAddErr(null)
    try {
      const parsed = await api<{
        type: string
        amount: number
        merchant: string
        date: string
        payment_method: string
        category_id: number | null
        notes: string
      }>('/coach/quick-add', {
        method: 'POST',
        body: JSON.stringify({ text: quickAddText.trim() }),
      })

      // Directly create transaction
      await api('/transactions', {
        method: 'POST',
        body: JSON.stringify({
          type: parsed.type,
          amount: parsed.amount,
          merchant: parsed.merchant,
          date: parsed.date,
          payment_method: parsed.payment_method,
          category_id: parsed.category_id,
          notes: parsed.notes,
        }),
      })

      setQuickAddModal(false)
      setQuickAddText('')
      load()
    } catch (e2) {
      setQuickAddErr(e2 instanceof Error ? e2.message : 'Could not parse quick add.')
    } finally {
      setQuickAddBusy(false)
    }
  }

  async function handleNlSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!nlSearchText.trim()) return
    setNlBusy(true)
    try {
      const filters = await api<Record<string, string | number>>(`/coach/nl-search?q=${encodeURIComponent(nlSearchText)}`)
      const next = new URLSearchParams()
      for (const [k, v] of Object.entries(filters)) {
        if (v !== undefined && v !== null) {
          next.set(k, String(v))
        }
      }
      setParams(next, { replace: true })
    } catch {
      // fallback to regular q param
      set('q', nlSearchText)
    } finally {
      setNlBusy(false)
    }
  }

  const page = Number(params.get('page') ?? 1)
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const filtered = FILTER_KEYS.some((k) => k !== 'page' && k !== 'sort' && k !== 'order' && params.get(k))

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold">Transactions</h1>
        <div className="flex gap-2 flex-wrap">
          <button className="btn flex items-center gap-1 bg-accent" onClick={() => setQuickAddModal(true)}>
            <Zap size={16} /> Quick Add
          </button>
          <Link to="/add-expense" className="btn flex items-center gap-1"><Plus size={16} /> Expense</Link>
          <Link to="/add-income" className="btn flex items-center gap-1"><Plus size={16} /> Income</Link>
          <Link to="/add-transfer" className="btn flex items-center gap-1" style={ghost}><Plus size={16} /> Transfer</Link>
        </div>
      </div>

      {/* Smart search bar */}
      <form onSubmit={handleNlSearch} className="card flex gap-2 items-center">
        <Sparkles size={18} className="text-accent shrink-0" />
        <input
          className="input flex-1 border-0 shadow-none focus:outline-none"
          placeholder="Natural language search (e.g. 'uber over 500 last month' or 'swiggy upi')..."
          value={nlSearchText}
          onChange={(e) => setNlSearchText(e.target.value)}
        />
        <button type="submit" className="btn text-xs" style={ghost} disabled={nlBusy || !nlSearchText.trim()}>
          {nlBusy ? 'Searching...' : 'Smart Filter'}
        </button>
      </form>

      {/* Standard filters */}
      <div className="card grid gap-2 grid-cols-2 md:grid-cols-4">
        <input className="input col-span-2" placeholder="Search merchant or notes" aria-label="Search" defaultValue={params.get('q') ?? ''}
          onKeyDown={(e) => e.key === 'Enter' && set('q', e.currentTarget.value)} onBlur={(e) => e.currentTarget.value !== (params.get('q') ?? '') && set('q', e.currentTarget.value)} />
        <select className="input" aria-label="Type" value={params.get('type') ?? ''} onChange={(e) => set('type', e.target.value)}>
          <option value="">All types</option><option value="expense">Expenses</option><option value="income">Income</option><option value="transfer">Transfers</option>
        </select>
        <select className="input" aria-label="Category" value={params.get('category_id') ?? ''} onChange={(e) => set('category_id', e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select className="input" aria-label="Payment method" value={params.get('payment_method') ?? ''} onChange={(e) => set('payment_method', e.target.value)}>
          <option value="">All payment methods</option>
          {PAYMENT_METHODS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <input className="input" type="date" aria-label="From date" value={params.get('date_from') ?? ''} onChange={(e) => set('date_from', e.target.value)} />
        <input className="input" type="date" aria-label="To date" value={params.get('date_to') ?? ''} onChange={(e) => set('date_to', e.target.value)} />
        <div className="flex gap-2 items-center">
          {filtered && <button className="btn text-xs" style={ghost} onClick={() => setParams(new URLSearchParams())}>Clear filters</button>}
        </div>
      </div>

      {error && <div className="card text-bad" role="alert">{error}</div>}

      <div className="card overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b muted text-xs bg-card" style={{ borderColor: 'var(--border)' }}>
              <th className="p-3">Date</th>
              <th className="p-3">Merchant / Payee</th>
              <th className="p-3">Category</th>
              <th className="p-3">Method</th>
              <th className="p-3 text-right">Amount</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {!data || data.items.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center muted">No transactions match your query.</td>
              </tr>
            ) : (
              data.items.map((t) => (
                <tr key={t.id} className="border-b hover:bg-card/40" style={{ borderColor: 'var(--border)' }}>
                  <td className="p-3 text-xs muted whitespace-nowrap">{t.date}</td>
                  <td className="p-3 font-medium">
                    {t.merchant || <span className="muted">No merchant</span>}
                    {t.notes && <div className="muted text-xs truncate max-w-xs">{t.notes}</div>}
                  </td>
                  <td className="p-3 text-xs">
                    <span className="px-2 py-0.5 rounded bg-card border" style={{ borderColor: 'var(--border)' }}>
                      {t.category || 'Uncategorized'}
                    </span>
                  </td>
                  <td className="p-3 text-xs muted">{pmLabel(t.payment_method)}</td>
                  <td className="p-3 text-right font-semibold whitespace-nowrap" style={{ color: t.type === 'income' ? 'var(--good)' : undefined }}>
                    {t.type === 'income' ? '+' : '−'}{money(Number(t.amount), t.currency)}
                  </td>
                  <td className="p-3 text-right whitespace-nowrap">
                    <div className="flex justify-end gap-1">
                      <button className="p-1 muted hover:text-fg" title="Duplicate" onClick={() => act(() => api(`/transactions/${t.id}/duplicate`, { method: 'POST' }))}>
                        <Copy size={15} />
                      </button>
                      <button className="p-1 muted hover:text-fg" title="Edit" onClick={() => nav(`/transactions/${t.id}/edit`)}>
                        <Pencil size={15} />
                      </button>
                      {confirmId === t.id ? (
                        <span className="text-xs">
                          Del? <button className="text-bad underline mx-0.5" onClick={() => act(() => api(`/transactions/${t.id}`, { method: 'DELETE' }))}>Yes</button>
                          <button className="underline" onClick={() => setConfirmId(null)}>No</button>
                        </span>
                      ) : (
                        <button className="p-1 muted hover:text-bad" title="Delete" onClick={() => setConfirmId(t.id)}>
                          <Trash2 size={15} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex justify-between items-center text-xs">
          <span className="muted">Page {page} of {pages} ({data?.total} total)</span>
          <div className="flex gap-2">
            <button className="btn text-xs" style={ghost} disabled={page <= 1} onClick={() => set('page', String(page - 1))}>Previous</button>
            <button className="btn text-xs" style={ghost} disabled={page >= pages} onClick={() => set('page', String(page + 1))}>Next</button>
          </div>
        </div>
      )}

      {/* Quick Add Modal */}
      {quickAddModal && (
        <Modal title="⚡ Quick Add Transaction" onClose={() => setQuickAddModal(false)}>
          <form onSubmit={handleQuickAdd} className="flex flex-col gap-3">
            <p className="text-xs muted">
              Type naturally like: &quot;spent 250 on lunch yesterday at Swiggy using upi&quot; or &quot;received 50000 salary today&quot;.
            </p>
            <textarea
              className="input h-24"
              placeholder="e.g. 450 grocery at Blinkit yesterday via upi"
              value={quickAddText}
              onChange={(e) => setQuickAddText(e.target.value)}
              required
              autoFocus
            />
            {quickAddErr && <p className="text-xs text-bad">{quickAddErr}</p>}
            <div className="flex justify-end gap-2 mt-2">
              <button type="button" className="btn" style={ghost} onClick={() => setQuickAddModal(false)}>Cancel</button>
              <button type="submit" className="btn bg-accent" disabled={quickAddBusy || !quickAddText.trim()}>
                {quickAddBusy ? 'Parsing...' : 'Add Transaction'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
