import { useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Modal } from '../components/ui'
import { TIMEZONES } from '../lib/types'

const CURRENCIES = ['INR', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'SGD', 'AED']
const STYLES = [
  { id: 'conservative', label: 'Conservative', desc: 'Focus heavily on building savings & emergency funds.' },
  { id: 'balanced', label: 'Balanced (50/30/20)', desc: '50% needs, 30% wants, 20% savings.' },
  { id: 'aggressive', label: 'Growth / Aggressive', desc: 'Maximize investments and debt pay-down.' },
]

export default function OnboardingModal({ onClose }: { onClose: () => void }) {
  const { user } = useAuth()
  const [step, setStep] = useState(1)

  const [name, setName] = useState(user?.name || '')
  const [currency, setCurrency] = useState(user?.currency || 'INR')
  const [timezone, setTimezone] = useState(user?.timezone || 'Asia/Kolkata')
  const [income, setIncome] = useState('60000')
  const [savingsTarget, setSavingsTarget] = useState('15000')
  const [style, setStyle] = useState('balanced')
  const [accountName, setAccountName] = useState('Main Bank Account')
  const [accountKind, setAccountKind] = useState('bank')
  const [accountBalance, setAccountBalance] = useState('25000')

  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function finish() {
    setBusy(true)
    setErr(null)
    try {
      await api('/auth/onboarding', {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim() || undefined,
          currency,
          timezone,
          monthly_income: Number(income) || null,
          monthly_savings_target: Number(savingsTarget) || null,
          budgeting_style: style,
          initial_account_name: accountName.trim() || undefined,
          initial_account_kind: accountKind,
          initial_account_balance: Number(accountBalance) || 0,
        }),
      })
      window.location.reload()
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Could not complete onboarding.')
      setBusy(false)
    }
  }

  return (
    <Modal title="Welcome! Let's set up your tracker" onClose={onClose}>
      <div className="flex flex-col gap-4">
        {step === 1 && (
          <div className="flex flex-col gap-3">
            <h3 className="font-semibold text-sm">Step 1 of 3: Your Profile & Currency</h3>
            <label className="text-sm">
              Your name
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Alex" />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm">
                Default Currency
                <select className="input" value={currency} onChange={(e) => setCurrency(e.target.value)}>
                  {CURRENCIES.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                Timezone
                <select className="input" value={timezone} onChange={(e) => setTimezone(e.target.value)}>
                  {TIMEZONES.map((tz) => (
                    <option key={tz} value={tz}>{tz}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="flex justify-end mt-2">
              <button className="btn" onClick={() => setStep(2)}>Next: Income & Savings →</button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col gap-3">
            <h3 className="font-semibold text-sm">Step 2 of 3: Income & Budgeting Goals</h3>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm">
                Typical Monthly Income ({currency})
                <input className="input" inputMode="decimal" value={income} onChange={(e) => setIncome(e.target.value)} />
              </label>
              <label className="text-sm">
                Monthly Savings Target ({currency})
                <input className="input" inputMode="decimal" value={savingsTarget} onChange={(e) => setSavingsTarget(e.target.value)} />
              </label>
            </div>
            <label className="text-sm">Budgeting Style</label>
            <div className="flex flex-col gap-2">
              {STYLES.map((s) => (
                <label key={s.id} className="card p-2 flex items-start gap-2 cursor-pointer text-sm" style={style === s.id ? { borderColor: 'var(--accent)' } : {}}>
                  <input type="radio" name="style" checked={style === s.id} onChange={() => setStyle(s.id)} className="mt-1" />
                  <div>
                    <div className="font-medium">{s.label}</div>
                    <div className="muted text-xs">{s.desc}</div>
                  </div>
                </label>
              ))}
            </div>
            <div className="flex justify-between mt-2">
              <button className="btn" style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }} onClick={() => setStep(1)}>← Back</button>
              <button className="btn" onClick={() => setStep(3)}>Next: Starting Account →</button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="flex flex-col gap-3">
            <h3 className="font-semibold text-sm">Step 3 of 3: Primary Account</h3>
            <p className="muted text-xs">Add your main bank account or wallet to calculate your net worth and safe-to-spend allowance.</p>
            <label className="text-sm">
              Account Name
              <input className="input" value={accountName} onChange={(e) => setAccountName(e.target.value)} placeholder="e.g. HDFC Salary Account" />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm">
                Account Type
                <select className="input" value={accountKind} onChange={(e) => setAccountKind(e.target.value)}>
                  <option value="bank">Bank Account</option>
                  <option value="cash">Cash Wallet</option>
                  <option value="wallet">Digital Wallet</option>
                  <option value="credit_card">Credit Card</option>
                </select>
              </label>
              <label className="text-sm">
                Starting Balance ({currency})
                <input className="input" inputMode="decimal" value={accountBalance} onChange={(e) => setAccountBalance(e.target.value)} />
              </label>
            </div>

            {err && <p role="alert" style={{ color: 'var(--bad)' }} className="text-sm">{err}</p>}

            <div className="flex justify-between mt-2">
              <button className="btn" style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }} onClick={() => setStep(2)}>← Back</button>
              <button className="btn" disabled={busy} onClick={finish}>{busy ? 'Saving...' : 'Finish & Go to Dashboard 🚀'}</button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}
