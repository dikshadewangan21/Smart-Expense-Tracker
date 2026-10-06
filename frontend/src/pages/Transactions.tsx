import { Copy, Pencil, Plus, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { money } from '../lib/format'
import { PAYMENT_METHODS, pmLabel, type TxPage } from '../lib/types'
import { useLookups } from '../lib/useLookups'

const FILTER_KEYS = ['q', 'type', 'category_id', 'payment_method', 'date_from', 'date_to', 'min_amount', 'max_amount', 'tag', 'uncategorized', 'merchant_exact', 'sort', 'order', 'page']

export default function Transactions() {
  // Filters live in the URL so a chart click (later) or a shared link can open a pre-filtered list.
  const [params, setParams] = useSearchParams()
  const { categories } = useLookups()
  const [data, setData] = useState<TxPage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)

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

  const page = Number(params.get('page') ?? 1)
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const filtered = FILTER_KEYS.some((k) => k !== 'page' && k !== 'sort' && k !== 'order' && params.get(k))

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Transactions</h1>
        <div className="flex gap-2">
          <Link to="/add-expense" className="btn flex items-center gap-1"><Plus size={16} /> Expense</Link>
          <Link to="/add-income" className="btn flex items-center gap-1"><Plus size={16} /> Income</Link>
          <Link to="/add-transfer" className="btn flex items-center gap-1" style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }}><Plus size={16} /> Transfer</Link>
        </div>
      </div>

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
          <option value="">All methods</option>
          {PAYMENT_METHODS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <input className="input" type="date" aria-label="From date" value={params.get('date_from') ?? ''} onChange={(e) => set('date_from', e.target.value)} />
        <input className="input" type="date" aria-label="To date" value={params.get('date_to') ?? ''} onChange={(e) => set('date_to', e.target.value)} />
        <select className="input" aria-label="Sort" value={`${params.get('sort') ?? 'date'}:${params.get('order') ?? 'desc'}`}
          onChange={(e) => { const [s, o] = e.target.value.split(':'); const n = new URLSearchParams(params); n.set('sort', s); n.set('order', o); n.delete('page'); setParams(n, { replace: true }) }}>
          <option value="date:desc">Newest first</option><option value="date:asc">Oldest first</option>
          <option value="amount:desc">Largest first</option><option value="amount:asc">Smallest first</option>
        </select>
        {filtered && <button className="btn" style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }}
          onClick={() => setParams({}, { replace: true })}>Clear filters</button>}
      </div>

      {(params.get('uncategorized') || params.get('merchant_exact')) && (
        <div className="flex flex-wrap gap-2 text-sm" aria-label="Active drill-down filters">
          {params.get('uncategorized') && <button className="card py-1" onClick={() => set('uncategorized', '')}>Uncategorized only ✕</button>}
          {params.get('merchant_exact') && <button className="card py-1" onClick={() => set('merchant_exact', '')}>Merchant: {params.get('merchant_exact')} ✕</button>}
        </div>
      )}
      {error && <div className="card" role="alert">{error} <button className="btn ml-2" onClick={load}>Retry</button></div>}
      {!data && !error && <div className="skeleton h-48" aria-busy="true" />}
      {data && data.items.length === 0 && (
        <div className="card text-center muted py-8">
          {filtered ? 'No transactions match these filters.' : 'No transactions yet. Add your first expense or income to get started.'}
        </div>
      )}
      {data && data.items.length > 0 && (
        <div className="card p-0 relative overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="muted text-left"><tr><th className="p-3">Date</th><th>Merchant</th><th>Category</th><th>Method</th>
              <th className="text-right">Amount</th><th className="p-3"><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {data.items.map((t) => (
                <tr key={t.id} className="border-t" style={{ borderColor: 'var(--border)' }}>
                  <td className="p-3 whitespace-nowrap">{t.date}</td>
                  <td>{t.merchant ?? <span className="muted">—</span>}{t.tags.length > 0 && <span className="muted"> · {t.tags.join(', ')}</span>}</td>
                  <td>{t.type === 'transfer' ? <span className="muted">Transfer</span> : t.category ?? <span className="muted">Uncategorized</span>}</td>
                  <td>{pmLabel(t.payment_method)}</td>
                  <td className="text-right font-medium whitespace-nowrap" style={{ color: t.type === 'income' ? 'var(--good)' : undefined }}>
                    {t.type === 'income' ? '+' : t.type === 'expense' ? '−' : '⇄ '}{money(t.amount, t.currency)}</td>
                  <td className="p-3 whitespace-nowrap text-right">
                    {confirmId === t.id ? (
                      <span>Delete? <button className="underline mx-1" style={{ color: 'var(--bad)' }} onClick={() => { setConfirmId(null); act(() => api(`/transactions/${t.id}`, { method: 'DELETE' })) }}>Yes</button>
                        <button className="underline" onClick={() => setConfirmId(null)}>No</button></span>
                    ) : (<>
                      <Link to={`/transactions/${t.id}/edit`} aria-label="Edit" className="inline-block p-1"><Pencil size={16} /></Link>
                      <button aria-label="Duplicate" className="p-1" onClick={() => act(() => api(`/transactions/${t.id}/duplicate`, { method: 'POST' }))}><Copy size={16} /></button>
                      <button aria-label="Delete" className="p-1" onClick={() => setConfirmId(t.id)}><Trash2 size={16} /></button>
                    </>)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && data.total > data.page_size && (
        <div className="flex items-center justify-between text-sm">
          <span className="muted">{data.total} transactions</span>
          <div className="flex items-center gap-2">
            <button className="btn" disabled={page <= 1} onClick={() => set('page', String(page - 1))}>Previous</button>
            <span>Page {page} of {pages}</span>
            <button className="btn" disabled={page >= pages} onClick={() => set('page', String(page + 1))}>Next</button>
          </div>
        </div>
      )}
    </div>
  )
}
