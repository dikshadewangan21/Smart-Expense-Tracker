import {
  Copy, Pencil, Plus, Trash2, Zap, Sparkles, Search, X,
  ArrowDownLeft, ArrowUpRight, ArrowLeftRight, ChevronLeft,
  ChevronRight
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { money } from '../lib/format'
import { PAYMENT_METHODS, pmLabel, type TxPage, type Transaction } from '../lib/types'
import { useLookups } from '../lib/useLookups'
import { Empty, ErrorBox } from '../components/ui'
import { useToast } from '../components/Toast'
import QuickAddModal from '../components/QuickAddModal'

const FILTER_KEYS = [
  'q', 'type', 'category_id', 'payment_method', 'date_from', 'date_to',
  'min_amount', 'max_amount', 'tag', 'uncategorized', 'merchant_exact', 'sort', 'order', 'page'
]

export default function Transactions() {
  const [params, setParams] = useSearchParams()
  const { categories } = useLookups()
  const nav = useNavigate()
  const { toast } = useToast()

  const [data, setData] = useState<TxPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)

  // Quick Add state
  const [quickAddOpen, setQuickAddOpen] = useState(false)
  const [quickAddKind, setQuickAddKind] = useState<'expense' | 'income' | 'transfer'>('expense')

  // Natural Language Search state
  const [nlSearchText, setNlSearchText] = useState('')
  const [nlBusy, setNlBusy] = useState(false)

  const query = FILTER_KEYS
    .filter((k) => params.get(k))
    .map((k) => `${k}=${encodeURIComponent(params.get(k)!)}`)
    .join('&')

  const load = useCallback(() => {
    setError(null)
    setLoading(true)
    api<TxPage>(`/transactions?page_size=25${query ? '&' + query : ''}`)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load transactions.'))
      .finally(() => setLoading(false))
  }, [query])

  useEffect(() => {
    load()
  }, [load])

  // Listen to global custom events for tx changes
  useEffect(() => {
    const handleUpdate = () => load()
    window.addEventListener('expense-tracker:tx-updated', handleUpdate)
    return () => window.removeEventListener('expense-tracker:tx-updated', handleUpdate)
  }, [load])

  const setFilter = (k: string, v: string) => {
    const next = new URLSearchParams(params)
    if (v) next.set(k, v)
    else next.delete(k)
    if (k !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  const removeFilter = (k: string) => {
    const next = new URLSearchParams(params)
    next.delete(k)
    if (k !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  const clearAllFilters = () => {
    setParams(new URLSearchParams(), { replace: true })
  }

  async function handleDuplicate(t: Transaction) {
    try {
      await api(`/transactions/${t.id}/duplicate`, { method: 'POST' })
      toast.success(`Duplicated "${t.merchant || 'Transaction'}"`)
      load()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to duplicate transaction.')
    }
  }

  async function handleDelete(t: Transaction) {
    try {
      await api(`/transactions/${t.id}`, { method: 'DELETE' })
      setConfirmId(null)
      toast.success(`Deleted transaction`)
      load()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to delete transaction.')
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
        if (v !== undefined && v !== null && v !== '') {
          next.set(k, String(v))
        }
      }
      setParams(next, { replace: true })
      toast.info('Applied smart filters!')
    } catch {
      // fallback to regular q param
      setFilter('q', nlSearchText)
    } finally {
      setNlBusy(false)
    }
  }

  const page = Number(params.get('page') ?? 1)
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  // Extract active filter tags for chips
  const activeChips: { key: string; label: string }[] = []
  if (params.get('q')) activeChips.push({ key: 'q', label: `Search: "${params.get('q')}"` })
  if (params.get('type')) {
    const t = params.get('type')
    activeChips.push({ key: 'type', label: t === 'expense' ? 'Expenses' : t === 'income' ? 'Income' : 'Transfers' })
  }
  if (params.get('category_id')) {
    const catId = Number(params.get('category_id'))
    const cat = categories.find((c) => c.id === catId)
    activeChips.push({ key: 'category_id', label: cat ? cat.name : `Category #${catId}` })
  }
  if (params.get('payment_method')) {
    activeChips.push({ key: 'payment_method', label: pmLabel(params.get('payment_method')!) })
  }
  if (params.get('date_from')) activeChips.push({ key: 'date_from', label: `From: ${params.get('date_from')}` })
  if (params.get('date_to')) activeChips.push({ key: 'date_to', label: `To: ${params.get('date_to')}` })

  return (
    <div className="flex flex-col gap-5">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Transactions</h1>
          <p className="text-xs sm:text-sm muted mt-0.5">
            {data ? `${data.total} total transactions` : 'Track all inflows and outflows'}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => {
              setQuickAddKind('expense')
              setQuickAddOpen(true)
            }}
            className="btn flex items-center gap-1.5 px-3.5 py-2 font-semibold text-sm rounded-xl shadow-sm"
            style={{ background: 'var(--accent)', color: '#ffffff' }}
          >
            <Zap size={16} />
            <span>+ Quick Add</span>
          </button>

          <Link
            to="/add-expense"
            className="btn btn-secondary flex items-center gap-1 px-3 py-2 text-xs rounded-xl"
          >
            <Plus size={15} /> Expense
          </Link>

          <Link
            to="/add-income"
            className="btn btn-secondary flex items-center gap-1 px-3 py-2 text-xs rounded-xl"
          >
            <Plus size={15} /> Income
          </Link>
        </div>
      </div>

      {/* Sticky Search & Filter Bar */}
      <div
        className="sticky top-14 z-10 card p-3 rounded-2xl shadow-sm border flex flex-col gap-3 backdrop-blur-md bg-[var(--card)]/95"
        style={{ borderColor: 'var(--border)' }}
      >
        {/* Natural Language Search / Quick Search */}
        <form onSubmit={handleNlSearch} className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
            <input
              type="text"
              className="input pl-9 pr-8 text-sm w-full rounded-xl"
              placeholder="Search 'Swiggy', 'UPI', 'Food', '₹500', or 'last month'…"
              value={nlSearchText || (params.get('q') ?? '')}
              onChange={(e) => {
                setNlSearchText(e.target.value)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  setFilter('q', e.currentTarget.value)
                }
              }}
            />
            {(nlSearchText || params.get('q')) && (
              <button
                type="button"
                onClick={() => {
                  setNlSearchText('')
                  removeFilter('q')
                }}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-muted hover:text-[var(--fg)]"
              >
                <X size={14} />
              </button>
            )}
          </div>

          <button
            type="submit"
            disabled={nlBusy || !nlSearchText.trim()}
            className="btn btn-secondary text-xs px-3 py-2.5 rounded-xl shrink-0 flex items-center gap-1"
            title="Ask AI to parse filters"
          >
            <Sparkles size={14} className="text-accent" />
            <span className="hidden sm:inline">{nlBusy ? 'Filtering…' : 'Smart Filter'}</span>
          </button>
        </form>

        {/* Quick Filter dropdowns */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t" style={{ borderColor: 'var(--border)' }}>
          {/* Type */}
          <select
            className="input text-xs py-1.5 rounded-lg"
            value={params.get('type') ?? ''}
            onChange={(e) => setFilter('type', e.target.value)}
            aria-label="Filter by type"
          >
            <option value="">All Types</option>
            <option value="expense">Expenses</option>
            <option value="income">Income</option>
            <option value="transfer">Transfers</option>
          </select>

          {/* Category */}
          <select
            className="input text-xs py-1.5 rounded-lg"
            value={params.get('category_id') ?? ''}
            onChange={(e) => setFilter('category_id', e.target.value)}
            aria-label="Filter by category"
          >
            <option value="">All Categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>

          {/* Payment Method */}
          <select
            className="input text-xs py-1.5 rounded-lg"
            value={params.get('payment_method') ?? ''}
            onChange={(e) => setFilter('payment_method', e.target.value)}
            aria-label="Filter by payment method"
          >
            <option value="">All Payment Methods</option>
            {PAYMENT_METHODS.map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </select>

          {/* Date range picker trigger */}
          <div className="flex gap-1.5">
            <input
              type="date"
              className="input text-xs py-1.5 px-2 rounded-lg flex-1 min-w-0"
              value={params.get('date_from') ?? ''}
              onChange={(e) => setFilter('date_from', e.target.value)}
              title="From date"
            />
            <input
              type="date"
              className="input text-xs py-1.5 px-2 rounded-lg flex-1 min-w-0"
              value={params.get('date_to') ?? ''}
              onChange={(e) => setFilter('date_to', e.target.value)}
              title="To date"
            />
          </div>
        </div>

        {/* Removable Filter Chips */}
        {activeChips.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap pt-1">
            <span className="text-[11px] muted font-medium mr-1">Active filters:</span>
            {activeChips.map((chip) => (
              <button
                key={chip.key}
                onClick={() => removeFilter(chip.key)}
                className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/20 hover:bg-accent/20 transition"
              >
                <span>{chip.label}</span>
                <X size={12} />
              </button>
            ))}
            <button
              onClick={clearAllFilters}
              className="text-[11px] font-semibold text-bad hover:underline ml-2"
            >
              Clear all
            </button>
          </div>
        )}
      </div>

      {error && <ErrorBox message={error} onRetry={load} />}

      {/* Loading Skeleton */}
      {loading && !data && (
        <div className="card p-4 flex flex-col gap-3 rounded-2xl">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton h-14 rounded-xl" />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && data && data.items.length === 0 && (
        <div className="py-12 card p-8 text-center rounded-2xl border" style={{ borderColor: 'var(--border)' }}>
          <Empty title="No transactions match your query">
            {activeChips.length > 0
              ? 'Try removing one or more active filters to broaden your search.'
              : 'Add your first transaction to start tracking your spending.'}
            <div className="mt-4 flex justify-center gap-2">
              {activeChips.length > 0 ? (
                <button onClick={clearAllFilters} className="btn btn-secondary text-xs px-3 py-2">
                  Clear Filters
                </button>
              ) : (
                <button
                  onClick={() => {
                    setQuickAddKind('expense')
                    setQuickAddOpen(true)
                  }}
                  className="btn btn-primary text-xs px-4 py-2"
                >
                  + Add Expense
                </button>
              )}
            </div>
          </Empty>
        </div>
      )}

      {/* Transactions Display */}
      {data && data.items.length > 0 && (
        <>
          {/* Desktop Table View (Hidden on mobile) */}
          <div className="hidden md:block card p-0 overflow-hidden rounded-2xl border shadow-sm" style={{ borderColor: 'var(--border)' }}>
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b bg-[var(--card)] text-xs text-muted font-medium" style={{ borderColor: 'var(--border)' }}>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Merchant / Details</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Method</th>
                  <th className="py-3 px-4 text-right">Amount</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {data.items.map((t) => {
                  const isIncome = t.type === 'income'
                  const isTransfer = t.type === 'transfer'

                  return (
                    <tr
                      key={t.id}
                      className="hover:bg-[var(--card)]/60 transition group cursor-pointer"
                      onClick={() => nav(`/transactions/${t.id}/edit`)}
                    >
                      {/* Date */}
                      <td className="py-3 px-4 text-xs muted font-mono whitespace-nowrap">
                        {t.date}
                      </td>

                      {/* Merchant & Notes */}
                      <td className="py-3 px-4">
                        <div className="font-semibold text-xs text-[var(--fg)]">
                          {t.merchant || <span className="muted italic">No merchant</span>}
                        </div>
                        {t.notes && (
                          <div className="text-[11px] muted truncate max-w-xs mt-0.5">
                            {t.notes}
                          </div>
                        )}
                      </td>

                      {/* Category */}
                      <td className="py-3 px-4">
                        <span className="inline-block text-[11px] px-2 py-0.5 rounded-md bg-[var(--bg)] border text-muted font-medium" style={{ borderColor: 'var(--border)' }}>
                          {t.category || 'Uncategorized'}
                        </span>
                      </td>

                      {/* Method */}
                      <td className="py-3 px-4 text-xs muted whitespace-nowrap">
                        {pmLabel(t.payment_method)}
                      </td>

                      {/* Amount */}
                      <td className="py-3 px-4 text-right whitespace-nowrap">
                        <span
                          className="font-bold text-sm font-mono"
                          style={{
                            color: isIncome ? 'var(--good)' : isTransfer ? 'var(--accent)' : undefined,
                          }}
                        >
                          {isIncome ? '+' : isTransfer ? '' : '−'}
                          {money(Number(t.amount), t.currency)}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-4 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1 opacity-70 group-hover:opacity-100 transition">
                          <button
                            className="p-1.5 rounded-lg muted hover:text-accent hover:bg-[var(--card)]"
                            title="Duplicate transaction"
                            onClick={() => handleDuplicate(t)}
                          >
                            <Copy size={15} />
                          </button>
                          <button
                            className="p-1.5 rounded-lg muted hover:text-accent hover:bg-[var(--card)]"
                            title="Edit transaction"
                            onClick={() => nav(`/transactions/${t.id}/edit`)}
                          >
                            <Pencil size={15} />
                          </button>
                          {confirmId === t.id ? (
                            <div className="flex items-center gap-1 text-xs">
                              <button
                                className="text-bad font-semibold underline px-1 py-0.5 rounded hover:bg-red-500/10"
                                onClick={() => handleDelete(t)}
                              >
                                Delete
                              </button>
                              <button
                                className="muted underline px-1 py-0.5"
                                onClick={() => setConfirmId(null)}
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button
                              className="p-1.5 rounded-lg muted hover:text-bad hover:bg-red-500/10"
                              title="Delete transaction"
                              onClick={() => setConfirmId(t.id)}
                            >
                              <Trash2 size={15} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile Card List View (Shown only on small screens) */}
          <div className="md:hidden flex flex-col gap-2.5">
            {data.items.map((t) => {
              const isIncome = t.type === 'income'
              const isTransfer = t.type === 'transfer'

              return (
                <div
                  key={t.id}
                  onClick={() => nav(`/transactions/${t.id}/edit`)}
                  className="card-interactive p-3.5 rounded-2xl flex flex-col gap-2 border shadow-xs"
                  style={{ borderColor: 'var(--border)', background: 'var(--card)' }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div
                        className={`w-9 h-9 rounded-xl flex items-center justify-center font-bold text-sm shrink-0 ${
                          isIncome ? 'bg-green-500/10 text-good' : isTransfer ? 'bg-blue-500/10 text-accent' : 'bg-red-500/10 text-bad'
                        }`}
                      >
                        {isIncome ? <ArrowDownLeft size={16} /> : isTransfer ? <ArrowLeftRight size={16} /> : <ArrowUpRight size={16} />}
                      </div>

                      <div className="min-w-0 truncate">
                        <div className="text-sm font-bold truncate">
                          {t.merchant || t.category || 'Transaction'}
                        </div>
                        <div className="text-xs muted flex items-center gap-1.5 mt-0.5">
                          <span>{t.category || 'Uncategorized'}</span>
                          <span>•</span>
                          <span>{pmLabel(t.payment_method)}</span>
                        </div>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <div
                        className="text-base font-bold font-mono"
                        style={{ color: isIncome ? 'var(--good)' : undefined }}
                      >
                        {isIncome ? '+' : isTransfer ? '' : '−'}
                        {money(Number(t.amount), t.currency)}
                      </div>
                      <div className="text-[11px] muted font-mono mt-0.5">
                        {t.date}
                      </div>
                    </div>
                  </div>

                  {t.notes && (
                    <div className="text-xs muted bg-[var(--bg)] p-1.5 rounded-lg border text-ellipsis overflow-hidden" style={{ borderColor: 'var(--border)' }}>
                      {t.notes}
                    </div>
                  )}

                  {/* Mobile Actions Bar */}
                  <div
                    className="flex items-center justify-end gap-3 pt-2 border-t mt-0.5 text-xs muted"
                    style={{ borderColor: 'var(--border)' }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      className="flex items-center gap-1 hover:text-accent"
                      onClick={() => handleDuplicate(t)}
                    >
                      <Copy size={13} /> Duplicate
                    </button>
                    <button
                      className="flex items-center gap-1 hover:text-accent"
                      onClick={() => nav(`/transactions/${t.id}/edit`)}
                    >
                      <Pencil size={13} /> Edit
                    </button>
                    {confirmId === t.id ? (
                      <span className="flex items-center gap-1.5 text-bad font-semibold">
                        Delete?
                        <button className="underline" onClick={() => handleDelete(t)}>Yes</button>
                        <button className="underline muted" onClick={() => setConfirmId(null)}>No</button>
                      </span>
                    ) : (
                      <button
                        className="flex items-center gap-1 hover:text-bad"
                        onClick={() => setConfirmId(t.id)}
                      >
                        <Trash2 size={13} /> Delete
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-2 text-xs muted">
              <span>
                Showing page {page} of {pages} ({data.total} total)
              </span>
              <div className="flex items-center gap-2">
                <button
                  className="btn btn-secondary text-xs px-3 py-1.5 rounded-lg flex items-center gap-1"
                  disabled={page <= 1}
                  onClick={() => setFilter('page', String(page - 1))}
                >
                  <ChevronLeft size={14} /> Previous
                </button>
                <button
                  className="btn btn-secondary text-xs px-3 py-1.5 rounded-lg flex items-center gap-1"
                  disabled={page >= pages}
                  onClick={() => setFilter('page', String(page + 1))}
                >
                  Next <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Quick Add Modal */}
      <QuickAddModal
        isOpen={quickAddOpen}
        onClose={() => setQuickAddOpen(false)}
        initialKind={quickAddKind}
        onSuccess={() => load()}
      />
    </div>
  )
}
