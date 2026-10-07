import { useState, useEffect } from 'react'
import { Sparkles, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useLookups } from '../lib/useLookups'
import { PAYMENT_METHODS } from '../lib/types'
import { useToast } from './Toast'
import { Modal } from './ui'

interface QuickAddModalProps {
  isOpen: boolean
  onClose: () => void
  initialKind?: 'expense' | 'income' | 'transfer'
  onSuccess?: () => void
}

export default function QuickAddModal({
  isOpen,
  onClose,
  initialKind = 'expense',
  onSuccess,
}: QuickAddModalProps) {
  const { user } = useAuth()
  const { categories, accounts } = useLookups()
  const { toast } = useToast()
  const cur = user?.currency ?? 'INR'

  const [type, setType] = useState<'expense' | 'income' | 'transfer'>(initialKind)
  const [amount, setAmount] = useState('')
  const [merchant, setMerchant] = useState('')
  const [categoryId, setCategoryId] = useState<string>('')
  const [date, setDate] = useState(() => new Date().toISOString().split('T')[0])
  const [paymentMethod, setPaymentMethod] = useState('upi')
  const [accountId, setAccountId] = useState<string>('')
  const [toAccountId, setToAccountId] = useState<string>('')
  const [notes, setNotes] = useState('')

  const [nlText, setNlText] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) {
      setType(initialKind)
      setAmount('')
      setMerchant('')
      setCategoryId('')
      setDate(new Date().toISOString().split('T')[0])
      setPaymentMethod('upi')
      setAccountId('')
      setToAccountId('')
      setNotes('')
      setNlText('')
      setErr(null)
      setShowAdvanced(false)
    }
  }, [isOpen, initialKind])

  async function handleNlParse() {
    if (!nlText.trim()) return
    setBusy(true)
    setErr(null)
    try {
      const parsed = await api<{
        type: 'expense' | 'income' | 'transfer'
        amount: number
        merchant: string
        date: string
        payment_method: string
        category_id: number | null
        notes: string
      }>('/coach/quick-add', {
        method: 'POST',
        body: JSON.stringify({ text: nlText.trim() }),
      })

      if (parsed.amount) setAmount(String(parsed.amount))
      if (parsed.merchant) setMerchant(parsed.merchant)
      if (parsed.type) setType(parsed.type)
      if (parsed.date) setDate(parsed.date)
      if (parsed.payment_method) setPaymentMethod(parsed.payment_method)
      if (parsed.category_id) setCategoryId(String(parsed.category_id))
      if (parsed.notes) setNotes(parsed.notes)
      toast.info('Parsed details from natural language!')
    } catch {
      setErr('Could not parse sentence automatically. Enter details below.')
    } finally {
      setBusy(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)

    const numAmt = Number(amount)
    if (!amount || Number.isNaN(numAmt) || numAmt <= 0) {
      setErr('Please enter a valid amount greater than 0.')
      return
    }

    setBusy(true)
    try {
      await api('/transactions', {
        method: 'POST',
        body: JSON.stringify({
          type,
          amount: numAmt,
          currency: cur,
          merchant: type === 'transfer' ? null : merchant.trim() || null,
          category_id: type === 'transfer' ? null : categoryId ? Number(categoryId) : null,
          date,
          payment_method: paymentMethod,
          account_id: accountId ? Number(accountId) : null,
          to_account_id: type === 'transfer' && toAccountId ? Number(toAccountId) : null,
          notes: notes.trim() || null,
        }),
      })

      toast.success(
        type === 'expense'
          ? 'Expense added successfully'
          : type === 'income'
          ? 'Income added successfully'
          : 'Transfer recorded successfully'
      )

      onClose()
      if (onSuccess) onSuccess()
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Could not save transaction.')
    } finally {
      setBusy(false)
    }
  }

  if (!isOpen) return null

  const filteredCategories = categories.filter((c) => c.kind === (type === 'income' ? 'income' : 'expense'))

  return (
    <Modal title="New Transaction" onClose={onClose}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {/* Type toggle */}
        <div className="grid grid-cols-3 gap-1 p-1 bg-border-subtle rounded-xl text-xs font-semibold" role="group">
          {(['expense', 'income', 'transfer'] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setType(t)}
              className={`py-1.5 rounded-lg capitalize transition-all ${
                type === t ? 'bg-card text-fg shadow-sm' : 'muted hover:text-fg'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Natural Language Quick Input Bar */}
        <div className="flex gap-2 items-center p-2 rounded-xl bg-border-subtle border" style={{ borderColor: 'var(--border)' }}>
          <Sparkles size={16} className="text-accent shrink-0" />
          <input
            className="flex-1 bg-transparent border-0 text-xs focus:outline-none placeholder:text-muted"
            placeholder="Quick phrase (e.g. ₹350 dinner Zomato yesterday)"
            value={nlText}
            onChange={(e) => setNlText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleNlParse())}
          />
          <button
            type="button"
            className="btn text-xs py-1 px-2 btn-secondary"
            disabled={busy || !nlText.trim()}
            onClick={handleNlParse}
          >
            Auto Fill
          </button>
        </div>

        {/* Amount Input - Primary & Prominent */}
        <div className="flex flex-col items-center justify-center py-2">
          <label className="text-xs muted mb-1 font-medium">AMOUNT ({cur})</label>
          <div className="relative flex items-center justify-center w-full">
            <span className="text-3xl sm:text-4xl font-semibold muted mr-1 select-none">
              {cur === 'INR' ? '₹' : '$'}
            </span>
            <input
              type="number"
              step="any"
              inputMode="decimal"
              className="text-3xl sm:text-4xl font-bold bg-transparent border-0 text-center focus:outline-none w-48 text-fg"
              placeholder="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              autoFocus
              required
            />
          </div>
        </div>

        {/* Category & Merchant (or Accounts for Transfer) */}
        {type !== 'transfer' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="text-xs font-medium">
              Category
              <select
                className="input mt-1"
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
              >
                <option value="">-- Uncategorized --</option>
                {filteredCategories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </label>

            <label className="text-xs font-medium">
              {type === 'income' ? 'Source / Payer' : 'Merchant / Payee'}
              <input
                className="input mt-1"
                placeholder={type === 'income' ? 'e.g. Salary, Client' : 'e.g. Swiggy, Netflix, Uber'}
                value={merchant}
                onChange={(e) => setMerchant(e.target.value)}
              />
            </label>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-center">
            <label className="text-xs font-medium">
              From Account
              <select className="input mt-1" value={accountId} onChange={(e) => setAccountId(e.target.value)} required>
                <option value="">-- Select Source --</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </label>

            <label className="text-xs font-medium">
              To Account
              <select className="input mt-1" value={toAccountId} onChange={(e) => setToAccountId(e.target.value)} required>
                <option value="">-- Select Destination --</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </label>
          </div>
        )}

        {/* Date */}
        <label className="text-xs font-medium">
          Date
          <input
            type="date"
            className="input mt-1"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </label>

        {/* Collapsible Advanced Options */}
        <div>
          <button
            type="button"
            className="flex items-center gap-1.5 text-xs text-accent font-medium hover:underline py-1"
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {showAdvanced ? 'Hide additional options' : 'More options (Payment method, Account, Notes)'}
          </button>

          {showAdvanced && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
              <label className="text-xs font-medium">
                Payment Method
                <select
                  className="input mt-1"
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                >
                  {PAYMENT_METHODS.map(([k, l]) => (
                    <option key={k} value={k}>{l}</option>
                  ))}
                </select>
              </label>

              {type !== 'transfer' && (
                <label className="text-xs font-medium">
                  Account
                  <select
                    className="input mt-1"
                    value={accountId}
                    onChange={(e) => setAccountId(e.target.value)}
                  >
                    <option value="">-- None / Default --</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                </label>
              )}

              <label className="text-xs font-medium sm:col-span-2">
                Notes
                <input
                  className="input mt-1"
                  placeholder="Optional memo or description"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  maxLength={500}
                />
              </label>
            </div>
          )}
        </div>

        {err && (
          <p role="alert" className="text-xs font-medium" style={{ color: 'var(--bad)' }}>
            {err}
          </p>
        )}

        {/* Action Buttons */}
        <div className="flex justify-end gap-2 mt-2 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn" disabled={busy || !amount}>
            {busy ? 'Saving...' : `Save ${type === 'expense' ? 'Expense' : type === 'income' ? 'Income' : 'Transfer'}`}
          </button>
        </div>
      </form>
    </Modal>
  )
}
