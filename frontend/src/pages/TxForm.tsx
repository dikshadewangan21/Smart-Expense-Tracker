import { useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useEffect } from 'react'
import { api } from '../lib/api'
import { PAYMENT_METHODS, type Tx } from '../lib/types'
import { useLookups } from '../lib/useLookups'

const today = () => new Date().toLocaleDateString('en-CA') // YYYY-MM-DD in the browser's local timezone

interface Props { kind: 'expense' | 'income' | 'transfer' }

/** One form for add expense, add income and edit (route /transactions/:id/edit). */
export default function TxForm({ kind }: Props) {
  const { id } = useParams()
  const editing = id !== undefined
  const nav = useNavigate()
  const { categories, accounts, ready } = useLookups()
  const [type, setType] = useState<'income' | 'expense' | 'transfer'>(kind)
  const [amount, setAmount] = useState('')
  const [merchant, setMerchant] = useState('')
  const [date, setDate] = useState(today())
  const [categoryId, setCategoryId] = useState('')
  const [originalCategory, setOriginalCategory] = useState('')
  const [pm, setPm] = useState('upi')
  const [accountId, setAccountId] = useState('')
  const [toAccountId, setToAccountId] = useState('')
  const [notes, setNotes] = useState('')
  const [tags, setTags] = useState('')
  const [always, setAlways] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState(!editing)

  useEffect(() => {
    if (!editing) return
    api<Tx>(`/transactions/${id}`).then((t) => {
      setType(t.type); setAmount(String(t.amount)); setMerchant(t.merchant ?? ''); setDate(t.date)
      setCategoryId(t.category_id ? String(t.category_id) : ''); setOriginalCategory(t.category_id ? String(t.category_id) : '')
      setPm(t.payment_method); setAccountId(t.account_id ? String(t.account_id) : ''); setToAccountId(t.to_account_id ? String(t.to_account_id) : ''); setNotes(t.notes ?? '')
      setTags(t.tags.join(', '))
      setLoaded(true)
    }).catch((e) => setError(e.message))
  }, [editing, id])

  const amountNum = Number(amount)
  const amountBad = amount !== '' && (!Number.isFinite(amountNum) || amountNum <= 0 || !/^\d+(\.\d{1,2})?$/.test(amount))
  const cats = categories.filter((c) => c.kind === (type === 'income' ? 'income' : 'expense'))
  const categoryChanged = editing && categoryId !== '' && categoryId !== originalCategory

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (amountBad || !amount) return
    if (type === 'transfer' && (!accountId || !toAccountId || accountId === toAccountId)) {
      setError('Pick two different accounts: one the money leaves and one it goes into.'); return
    }
    setBusy(true); setError(null)
    const body = {
      type, amount, date, merchant: merchant || null, payment_method: pm, notes: notes || null,
      category_id: type !== 'transfer' && categoryId ? Number(categoryId) : null, account_id: accountId ? Number(accountId) : null,
      to_account_id: type === 'transfer' ? Number(toAccountId) : null,
      tags: type === 'transfer' ? [] : tags.split(',').map((t) => t.trim()).filter(Boolean), always_categorize: always && categoryChanged,
    }
    try {
      await api(editing ? `/transactions/${id}` : '/transactions', { method: editing ? 'PUT' : 'POST', body: JSON.stringify(body) })
      nav('/transactions')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save.')
    } finally { setBusy(false) }
  }

  if (!ready || !loaded) return <div className="skeleton h-64 max-w-lg" aria-busy="true" />

  return (
    <form onSubmit={submit} className="card max-w-lg flex flex-col gap-3" noValidate>
      <h1 className="text-xl font-bold">{editing ? (type === 'transfer' ? 'Edit transfer' : 'Edit transaction') : type === 'income' ? 'Add income' : type === 'transfer' ? 'Transfer between accounts' : 'Add expense'}</h1>
      <label className="text-sm">Amount ({'₹'})
        <input className="input" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} required aria-invalid={amountBad} />
        {amountBad && <span role="alert" className="text-xs" style={{ color: 'var(--bad)' }}>Enter a positive amount with up to 2 decimals.</span>}
      </label>
      <label className="text-sm">{type === 'income' ? 'Source' : type === 'transfer' ? 'Label (optional)' : 'Merchant'}
        <input className="input" value={merchant} onChange={(e) => setMerchant(e.target.value)} maxLength={160} />
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="text-sm">Date
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
        <label className="text-sm">Payment method
          <select className="input" value={pm} onChange={(e) => setPm(e.target.value)}>
            {PAYMENT_METHODS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </label>
      </div>
      {type === 'transfer' ? (
        <div className="grid grid-cols-2 gap-3">
          <label className="text-sm">From account
            <select className="input" value={accountId} onChange={(e) => setAccountId(e.target.value)} required>
              <option value="">Choose…</option>{accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
          <label className="text-sm">To account
            <select className="input" value={toAccountId} onChange={(e) => setToAccountId(e.target.value)} required>
              <option value="">Choose…</option>{accounts.filter((a) => String(a.id) !== accountId).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
          <p className="muted text-xs col-span-2">A transfer moves money between your own accounts. It is not spending and does not change your net worth. Paying a credit-card bill from your bank is a transfer.</p>
        </div>
      ) : (
      <div className="grid grid-cols-2 gap-3">
        <label className="text-sm">Category
          <select className="input" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">{type === 'expense' && !editing ? 'Auto-detect from merchant' : 'Uncategorized'}</option>
            {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="text-sm">Account
          <select className="input" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
            <option value="">None</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </label>
      </div>
      )}
      {categoryChanged && type === 'expense' && merchant && (
        <label className="text-sm flex gap-2 items-center">
          <input type="checkbox" checked={always} onChange={(e) => setAlways(e.target.checked)} />
          Always categorize “{merchant}” this way
        </label>
      )}
      {type !== 'transfer' && <label className="text-sm">Tags (comma separated)
        <input className="input" value={tags} onChange={(e) => setTags(e.target.value)} />
      </label>}
      <label className="text-sm">Notes
        <textarea className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} />
      </label>
      {error && <p role="alert" className="text-sm" style={{ color: 'var(--bad)' }}>{error}</p>}
      <div className="flex gap-2">
        <button className="btn" disabled={busy || amountBad || !amount}>{busy ? 'Saving…' : 'Save'}</button>
        <button type="button" className="btn" style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }}
          onClick={() => nav(-1)}>Cancel</button>
      </div>
    </form>
  )
}
