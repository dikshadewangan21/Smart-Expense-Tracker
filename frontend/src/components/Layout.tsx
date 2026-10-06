import {
  BarChart3, Landmark, Scale, Target, CalendarDays, FileText,
  LayoutDashboard, LogOut, MoreHorizontal, Moon, PiggyBank,
  Receipt, Repeat, Settings, Sun, Bot, UploadCloud, Users,
  FolderTree, ShieldCheck, Bell, CheckCheck
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { api } from '../lib/api'
import OnboardingModal from '../pages/OnboardingModal'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/transactions', label: 'Transactions', icon: Receipt },
  { to: '/coach', label: 'AI Coach', icon: Bot },
  { to: '/imports', label: 'Import Center', icon: UploadCloud },
  { to: '/budgets', label: 'Budgets', icon: PiggyBank },
  { to: '/goals', label: 'Goals', icon: Target },
  { to: '/debts', label: 'Debts', icon: Landmark },
  { to: '/net-worth', label: 'Net worth', icon: Scale },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/shared', label: 'Shared', icon: Users },
  { to: '/categories', label: 'Categories', icon: FolderTree },
  { to: '/subscriptions', label: 'Subscriptions', icon: Repeat },
  { to: '/bills', label: 'Bills', icon: FileText },
  { to: '/calendar', label: 'Calendar', icon: CalendarDays },
  { to: '/privacy', label: 'Privacy', icon: ShieldCheck },
  { to: '/settings', label: 'Settings', icon: Settings },
]

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

interface NotificationItem {
  id: number
  kind: string
  message: string
  read: boolean
  created_at: string
}

export default function Layout() {
  const { user, logout } = useAuth()
  const [dark, setDark] = useTheme()
  const [more, setMore] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)
  const [notifications, setNotifications] = useState<{ unread_count: number; items: NotificationItem[] }>({ unread_count: 0, items: [] })
  const [showOnboarding, setShowOnboarding] = useState(false)

  const loc = useLocation()
  useEffect(() => setMore(false), [loc.pathname])

  // Check onboarding status
  useEffect(() => {
    if (user && !user.onboarded && !user.is_demo) {
      setShowOnboarding(true)
    }
  }, [user])

  // Poll / fetch notifications
  async function fetchNotifications() {
    try {
      const data = await api<{ unread_count: number; items: NotificationItem[] }>('/notifications')
      setNotifications(data)
    } catch {
      // silently ignore if unauthorized
    }
  }

  useEffect(() => {
    fetchNotifications()
    const timer = setInterval(fetchNotifications, 60000)
    return () => clearInterval(timer)
  }, [])

  async function markAllRead() {
    try {
      await api('/notifications/read-all', { method: 'POST' })
      fetchNotifications()
    } catch {
      // ignore
    }
  }

  return (
    <div className="min-h-screen md:flex">
      <aside className="hidden md:flex md:w-60 flex-col gap-1 p-4 border-r shrink-0 overflow-y-auto" style={{ borderColor: 'var(--border)' }}>
        <div className="font-bold text-lg mb-4 flex items-center gap-2">Smart Expense Tracker</div>
        <nav className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
              style={({ isActive }) => (isActive ? { background: 'var(--card)', fontWeight: 600 } : {})}>
              <Icon size={17} aria-hidden /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto pt-4 text-xs muted truncate">{user?.email}</div>
      </aside>

      <div className="flex-1 min-w-0 pb-16 md:pb-0">
        <header className="flex items-center justify-end gap-2 p-3 border-b" style={{ borderColor: 'var(--border)' }}>
          {/* Notifications button */}
          <div className="relative">
            <button
              className="btn relative p-2"
              style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }}
              onClick={() => setShowNotifications(!showNotifications)}
              aria-label="Notifications"
            >
              <Bell size={16} />
              {notifications.unread_count > 0 && (
                <span className="absolute -top-1 -right-1 bg-bad text-white text-[10px] font-bold px-1.5 py-0.2 rounded-full">
                  {notifications.unread_count}
                </span>
              )}
            </button>

            {/* Notification dropdown */}
            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 sm:w-96 card p-3 z-50 shadow-lg flex flex-col gap-2">
                <div className="flex items-center justify-between pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
                  <span className="font-semibold text-sm">Notifications &amp; Alerts</span>
                  {notifications.unread_count > 0 && (
                    <button className="text-xs muted hover:underline flex items-center gap-1" onClick={markAllRead}>
                      <CheckCheck size={13} /> Mark all read
                    </button>
                  )}
                </div>

                <div className="max-h-80 overflow-y-auto flex flex-col gap-2 text-xs">
                  {notifications.items.length === 0 ? (
                    <p className="muted py-4 text-center">No alerts at the moment. All caught up!</p>
                  ) : (
                    notifications.items.slice(0, 10).map((n) => (
                      <div
                        key={n.id}
                        className={`p-2 rounded border flex flex-col gap-1 ${!n.read ? 'bg-card font-medium' : 'muted opacity-80'}`}
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <p>{n.message}</p>
                        <span className="text-[10px] muted">{new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          <button className="btn p-2" style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }}
            onClick={() => setDark(!dark)} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}>
            {dark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <button className="btn p-2" style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }}
            onClick={logout} aria-label="Sign out"><LogOut size={16} /></button>
        </header>

        {user?.is_demo && (
          <div className="mx-4 my-3 max-w-6xl md:mx-auto rounded-lg px-3 py-2 text-sm" role="status"
            style={{ background: 'var(--card)', border: '1px solid var(--warn)', color: 'var(--warn)' }}>
            Demo mode: sample data for presentation.
          </div>
        )}

        <main className="p-4 md:p-6 max-w-6xl mx-auto"><Outlet /></main>
      </div>

      {/* Onboarding Wizard Modal */}
      {showOnboarding && <OnboardingModal onClose={() => setShowOnboarding(false)} />}

      {/* Mobile Drawer */}
      {more && (
        <div className="md:hidden fixed bottom-16 right-2 z-40 card flex flex-col gap-1 p-2 max-h-96 overflow-y-auto shadow-xl" role="menu">
          {MORE.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} role="menuitem" className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm">
              <Icon size={17} aria-hidden /> {label}
            </NavLink>
          ))}
        </div>
      )}

      {/* Mobile bottom navigation */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 flex justify-around p-2 border-t z-30"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }} aria-label="Primary">
        {PRIMARY.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className="flex flex-col items-center text-[10px] gap-1 px-2 py-1">
            <Icon size={18} aria-hidden /> {label}
          </NavLink>
        ))}
        <button className="flex flex-col items-center text-[10px] gap-1 px-2 py-1" aria-expanded={more} aria-haspopup="menu" onClick={() => setMore(!more)}>
          <MoreHorizontal size={18} aria-hidden /> More
        </button>
      </nav>
    </div>
  )
}
