import { useState } from 'react'
import {
  User, Moon, Sun, Shield, UploadCloud, Users,
  LogOut, Sliders
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { TIMEZONES } from '../lib/types'
import { useToast } from '../components/Toast'

export default function Settings() {
  const { user, updateProfile, logout } = useAuth()
  const { toast } = useToast()

  const [name, setName] = useState(user?.name ?? '')
  const [tz, setTz] = useState(user?.timezone ?? 'Asia/Kolkata')
  const [busy, setBusy] = useState(false)

  const isDark = document.documentElement.classList.contains('dark')
  const [darkTheme, setDarkTheme] = useState(isDark)

  const toggleTheme = () => {
    const next = !darkTheme
    setDarkTheme(next)
    document.documentElement.classList.toggle('dark', next)
    localStorage.setItem('theme', next ? 'dark' : 'light')
    toast.info(`Switched to ${next ? 'Dark' : 'Light'} theme`)
  }

  const zones = TIMEZONES.includes(tz) ? TIMEZONES : [tz, ...TIMEZONES]

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      await updateProfile({ name, timezone: tz })
      toast.success('Settings saved successfully!')
    } catch (e2) {
      toast.error(e2 instanceof Error ? e2.message : 'Could not save profile settings.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-xs sm:text-sm muted mt-0.5">
          Manage your account profile, preferences, and data options
        </p>
      </div>

      {/* Section 1: Profile & Timezone */}
      <form
        onSubmit={save}
        className="card p-5 sm:p-6 rounded-2xl border shadow-xs flex flex-col gap-4"
        style={{ borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-2 pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
          <User size={18} className="text-accent" />
          <h2 className="font-bold text-sm tracking-tight">Profile &amp; Regional Settings</h2>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-xs font-semibold flex flex-col gap-1.5">
            <span>Email Address</span>
            <input
              className="input text-xs muted bg-[var(--bg)] cursor-not-allowed"
              value={user?.email ?? ''}
              disabled
              title="Email cannot be edited"
            />
          </label>

          <label className="text-xs font-semibold flex flex-col gap-1.5">
            <span>Full Name</span>
            <input
              className="input text-xs"
              placeholder="Your full name"
              value={name}
              maxLength={120}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-xs font-semibold flex flex-col gap-1.5">
            <span>Account Currency</span>
            <input
              className="input text-xs muted bg-[var(--bg)] cursor-not-allowed font-mono font-semibold"
              value={user?.currency ?? 'INR'}
              disabled
              title="Currency configured during signup"
            />
          </label>

          <label className="text-xs font-semibold flex flex-col gap-1.5">
            <span>Timezone</span>
            <select
              className="input text-xs"
              value={tz}
              onChange={(e) => setTz(e.target.value)}
            >
              {zones.map((z) => (
                <option key={z} value={z}>
                  {z}
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className="text-[11px] muted leading-relaxed">
          Your timezone calibrates "Today" for upcoming and overdue bills, recurring transactions, and month-to-date budgeting.
        </p>

        <div className="pt-2 border-t flex justify-end" style={{ borderColor: 'var(--border)' }}>
          <button
            type="submit"
            disabled={busy}
            className="btn btn-primary text-xs px-5 py-2 font-semibold"
          >
            {busy ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </form>

      {/* Section 2: Appearance & Interactions */}
      <section
        className="card p-5 sm:p-6 rounded-2xl border shadow-xs flex flex-col gap-4"
        style={{ borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-2 pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
          <Sliders size={18} className="text-accent" />
          <h2 className="font-bold text-sm tracking-tight">Appearance &amp; Navigation</h2>
        </div>

        <div className="flex items-center justify-between py-1">
          <div>
            <div className="text-xs font-semibold">Theme Mode</div>
            <div className="text-[11px] muted">Toggle between light and dark fintech mode</div>
          </div>
          <button
            onClick={toggleTheme}
            className="btn btn-secondary text-xs px-3 py-1.5 rounded-xl flex items-center gap-1.5 font-medium"
          >
            {darkTheme ? <Sun size={14} className="text-amber-400" /> : <Moon size={14} />}
            <span>{darkTheme ? 'Dark Mode' : 'Light Mode'}</span>
          </button>
        </div>

        <div className="flex items-center justify-between py-1 border-t" style={{ borderColor: 'var(--border)' }}>
          <div>
            <div className="text-xs font-semibold">Global Command Palette</div>
            <div className="text-[11px] muted">Press <kbd className="px-1 py-0.5 rounded border bg-[var(--bg)] font-mono text-[10px]">/</kbd> anywhere to trigger quick search and navigation</div>
          </div>
          <kbd className="text-xs font-mono px-2 py-1 rounded-lg border bg-[var(--bg)]" style={{ borderColor: 'var(--border)' }}>
            / or Cmd+K
          </kbd>
        </div>
      </section>

      {/* Section 3: Data & Integrations */}
      <section
        className="card p-5 sm:p-6 rounded-2xl border shadow-xs flex flex-col gap-3"
        style={{ borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-2 pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
          <UploadCloud size={18} className="text-accent" />
          <h2 className="font-bold text-sm tracking-tight">Data, Imports &amp; Security</h2>
        </div>

        <div className="grid gap-2 sm:grid-cols-3 pt-1">
          <Link
            to="/imports"
            className="card-interactive p-3 rounded-xl border flex flex-col gap-1 text-left"
            style={{ borderColor: 'var(--border)' }}
          >
            <div className="flex items-center gap-2 font-semibold text-xs">
              <UploadCloud size={15} className="text-accent" />
              <span>Import Center</span>
            </div>
            <div className="text-[11px] muted">Upload bank CSVs and statements</div>
          </Link>

          <Link
            to="/privacy"
            className="card-interactive p-3 rounded-xl border flex flex-col gap-1 text-left"
            style={{ borderColor: 'var(--border)' }}
          >
            <div className="flex items-center gap-2 font-semibold text-xs">
              <Shield size={15} className="text-accent" />
              <span>Privacy &amp; Security</span>
            </div>
            <div className="text-[11px] muted">Audit logs and data controls</div>
          </Link>

          <Link
            to="/shared"
            className="card-interactive p-3 rounded-xl border flex flex-col gap-1 text-left"
            style={{ borderColor: 'var(--border)' }}
          >
            <div className="flex items-center gap-2 font-semibold text-xs">
              <Users size={15} className="text-accent" />
              <span>Shared Finances</span>
            </div>
            <div className="text-[11px] muted">Household and partner budgets</div>
          </Link>
        </div>
      </section>

      {/* Section 4: Account Session */}
      <section
        className="card p-4 rounded-2xl border flex items-center justify-between"
        style={{ borderColor: 'var(--border)' }}
      >
        <div>
          <div className="text-xs font-semibold">Active Session</div>
          <div className="text-[11px] muted">Signed in as {user?.email}</div>
        </div>

        <button
          onClick={logout}
          className="btn text-xs px-3.5 py-1.5 rounded-xl border flex items-center gap-1.5 text-bad hover:bg-red-500/10 transition"
          style={{ borderColor: 'rgba(239, 68, 68, 0.2)' }}
        >
          <LogOut size={14} />
          <span>Sign Out</span>
        </button>
      </section>
    </div>
  )
}
