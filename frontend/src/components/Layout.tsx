import { BarChart3, Landmark, Scale, Target, CalendarDays, FileText, LayoutDashboard, LogOut, MoreHorizontal, Moon, PiggyBank, Receipt, Repeat, Settings, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'

// Only routes that exist are listed. Add entries as each phase ships.
const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/transactions', label: 'Transactions', icon: Receipt },
  { to: '/budgets', label: 'Budgets', icon: PiggyBank },
  { to: '/goals', label: 'Goals', icon: Target },
  { to: '/debts', label: 'Debts', icon: Landmark },
  { to: '/net-worth', label: 'Net worth', icon: Scale },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/subscriptions', label: 'Subscriptions', icon: Repeat },
  { to: '/bills', label: 'Bills', icon: FileText },
  { to: '/calendar', label: 'Calendar', icon: CalendarDays },
  { to: '/settings', label: 'Settings', icon: Settings },
]
// Phone bottom bar shows the first four; the rest live behind "More".
const PRIMARY = NAV.slice(0, 4)
const MORE = NAV.slice(4)

function useTheme() {
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark' ||
    (!localStorage.getItem('theme') && matchMedia('(prefers-color-scheme: dark)').matches))
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])
  return [dark, setDark] as const
}

export default function Layout() {
  const { user, logout } = useAuth()
  const [dark, setDark] = useTheme()
  const [more, setMore] = useState(false)
  const loc = useLocation()
  useEffect(() => setMore(false), [loc.pathname])

  return (
    <div className="min-h-screen md:flex">
      <aside className="hidden md:flex md:w-60 flex-col gap-1 p-4 border-r" style={{ borderColor: 'var(--border)' }}>
        <div className="font-bold text-lg mb-4">Smart Expense Tracker</div>
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className="flex items-center gap-2 rounded-lg px-3 py-2"
            style={({ isActive }) => (isActive ? { background: 'var(--card)', fontWeight: 600 } : {})}>
            <Icon size={18} aria-hidden /> {label}
          </NavLink>
        ))}
        <div className="mt-auto text-sm muted truncate">{user?.email}</div>
      </aside>

      <div className="flex-1 min-w-0 pb-16 md:pb-0">
        <header className="flex items-center justify-end gap-2 p-3">
          <button className="btn" style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }}
            onClick={() => setDark(!dark)} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}>
            {dark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <button className="btn" style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }}
            onClick={logout} aria-label="Sign out"><LogOut size={16} /></button>
        </header>
        {user?.is_demo && (
          <div className="mx-4 mb-3 max-w-6xl md:mx-auto rounded-lg px-3 py-2 text-sm" role="status"
            style={{ background: 'var(--card)', border: '1px solid var(--warn)', color: 'var(--warn)' }}>
            Demo mode: everything here is sample data, not your real finances.
          </div>
        )}
        <main className="px-4 pb-8 max-w-6xl mx-auto"><Outlet /></main>
      </div>

      {more && (
        <div className="md:hidden fixed bottom-16 right-2 z-40 card flex flex-col gap-1 p-2" role="menu">
          {MORE.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} role="menuitem" className="flex items-center gap-2 rounded-lg px-3 py-2"><Icon size={18} aria-hidden /> {label}</NavLink>
          ))}
        </div>
      )}
      <nav className="md:hidden fixed bottom-0 inset-x-0 flex justify-around p-2 border-t"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }} aria-label="Primary">
        {PRIMARY.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className="flex flex-col items-center text-xs gap-1 px-2 py-1">
            <Icon size={20} aria-hidden /> {label}
          </NavLink>
        ))}
        <button className="flex flex-col items-center text-xs gap-1 px-2 py-1" aria-expanded={more} aria-haspopup="menu" onClick={() => setMore(!more)}>
          <MoreHorizontal size={20} aria-hidden /> More
        </button>
      </nav>
    </div>
  )
}
