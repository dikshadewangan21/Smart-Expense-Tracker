import {
  BarChart3, Landmark, Scale, Target, CalendarDays, FileText,
  LayoutDashboard, LogOut, MoreHorizontal, Moon, PiggyBank,
  Receipt, Repeat, Settings, Sun, Bot, UploadCloud, Users,
  FolderTree, ShieldCheck, Bell, CheckCheck, Plus, Search, X
} from 'lucide-react'
import { useEffect, useState, useCallback } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { api } from '../lib/api'
import OnboardingModal from '../pages/OnboardingModal'
import CommandPalette from './CommandPalette'
import QuickAddModal from './QuickAddModal'

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  badge?: string
}

const MAIN_NAV: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/transactions', label: 'Transactions', icon: Receipt },
  { to: '/budgets', label: 'Budgets', icon: PiggyBank },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/subscriptions', label: 'Subscriptions', icon: Repeat },
  { to: '/bills', label: 'Bills', icon: FileText },
  { to: '/goals', label: 'Goals', icon: Target },
  { to: '/debts', label: 'Debts', icon: Landmark },
  { to: '/net-worth', label: 'Net Worth', icon: Scale },
  { to: '/ai-coach', label: 'AI Coach', icon: Bot },
  { to: '/settings', label: 'Settings', icon: Settings },
]

const SECONDARY_NAV: NavItem[] = [
  { to: '/calendar', label: 'Calendar', icon: CalendarDays },
  { to: '/imports', label: 'Import Center', icon: UploadCloud },
  { to: '/shared', label: 'Shared Finances', icon: Users },
  { to: '/categories', label: 'Categories', icon: FolderTree },
  { to: '/privacy', label: 'Privacy & Security', icon: ShieldCheck },
]

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
  const [moreDrawer, setMoreDrawer] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)
  const [notifications, setNotifications] = useState<{ unread_count: number; items: NotificationItem[] }>({ unread_count: 0, items: [] })
  const [showOnboarding, setShowOnboarding] = useState(false)

  // Command Palette & Quick Add states
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [quickAddOpen, setQuickAddOpen] = useState(false)
  const [quickAddKind, setQuickAddKind] = useState<'expense' | 'income' | 'transfer'>('expense')

  const loc = useLocation()
  const nav = useNavigate()

  useEffect(() => setMoreDrawer(false), [loc.pathname])

  // Global keyboard shortcuts
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const target = e.target as HTMLElement | null
    const isEditing = target && (
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.tagName === 'SELECT' ||
      target.isContentEditable
    )

    // Palette: '/' or Cmd+K / Ctrl+K
    if ((e.key === '/' && !isEditing) || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k')) {
      e.preventDefault()
      setPaletteOpen((prev) => !prev)
      return
    }

    if (isEditing || paletteOpen || quickAddOpen) return

    // Quick keys when not editing
    if (e.key === 'n' || e.key === 'N') {
      e.preventDefault()
      setQuickAddKind('expense')
      setQuickAddOpen(true)
    } else if (e.key === 'b' || e.key === 'B') {
      e.preventDefault()
      nav('/budgets')
    } else if (e.key === 'a' || e.key === 'A') {
      e.preventDefault()
      nav('/analytics')
    } else if (e.key === 'd' || e.key === 'D') {
      e.preventDefault()
      nav('/dashboard')
    } else if (e.key === 't' || e.key === 'T') {
      e.preventDefault()
      nav('/transactions')
    }
  }, [paletteOpen, quickAddOpen, nav])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

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

  const openQuickAdd = (kind: 'expense' | 'income' | 'transfer' = 'expense') => {
    setQuickAddKind(kind)
    setQuickAddOpen(true)
  }

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg)] text-[var(--fg)]">
      {/* Desktop Sidebar */}
      <aside
        className="hidden md:flex md:w-64 flex-col border-r shrink-0 h-screen sticky top-0 overflow-y-auto z-20"
        style={{ borderColor: 'var(--border)', background: 'var(--card)' }}
      >
        {/* Brand */}
        <div className="p-4 pb-3 flex items-center justify-between border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-accent text-white flex items-center justify-center font-bold text-base shadow-sm">
              ₹
            </div>
            <div>
              <div className="font-bold text-sm tracking-tight leading-tight">Smart Expense</div>
              <div className="text-[10px] muted font-medium">Fintech 2026</div>
            </div>
          </div>
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-[var(--bg)] border text-muted" style={{ borderColor: 'var(--border)' }}>
            v2.6
          </span>
        </div>

        {/* Global Quick Action & Search Trigger */}
        <div className="p-3 flex flex-col gap-2 border-b" style={{ borderColor: 'var(--border)' }}>
          <button
            onClick={() => openQuickAdd('expense')}
            className="w-full btn flex items-center justify-center gap-2 font-semibold shadow-sm py-2 px-3 text-sm rounded-lg"
            style={{ background: 'var(--accent)', color: '#ffffff' }}
          >
            <Plus size={16} strokeWidth={2.5} />
            <span>+ Add Transaction</span>
            <kbd className="ml-auto text-[10px] opacity-80 bg-white/20 px-1.5 py-0.5 rounded font-mono">N</kbd>
          </button>

          <button
            onClick={() => setPaletteOpen(true)}
            className="w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs muted border bg-[var(--bg)] hover:text-[var(--fg)] transition"
            style={{ borderColor: 'var(--border)' }}
            title="Press / anywhere to search"
          >
            <span className="flex items-center gap-2">
              <Search size={13} />
              <span>Search or jump to…</span>
            </span>
            <kbd className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--card)] border" style={{ borderColor: 'var(--border)' }}>
              /
            </kbd>
          </button>
        </div>

        {/* Navigation links */}
        <nav className="flex-1 p-2 flex flex-col gap-0.5 overflow-y-auto" aria-label="Main navigation">
          <div className="text-[10px] uppercase font-bold tracking-wider px-3 py-1.5 text-muted">
            Menu
          </div>
          {MAIN_NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition ${
                  isActive
                    ? 'bg-accent/10 text-accent font-semibold'
                    : 'text-[var(--fg)] hover:bg-[var(--bg)]'
                }`
              }
            >
              <div className="flex items-center gap-2.5">
                <Icon size={17} className="shrink-0" />
                <span>{label}</span>
              </div>
            </NavLink>
          ))}

          {/* Secondary Tools section */}
          <div className="mt-3 pt-3 border-t text-[10px] uppercase font-bold tracking-wider px-3 py-1 text-muted" style={{ borderColor: 'var(--border)' }}>
            Tools &amp; Settings
          </div>
          {SECONDARY_NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  isActive
                    ? 'bg-accent/10 text-accent font-semibold'
                    : 'muted hover:text-[var(--fg)] hover:bg-[var(--bg)]'
                }`
              }
            >
              <Icon size={15} className="shrink-0" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* User bar & footer */}
        <div className="p-3 border-t flex items-center justify-between gap-2 mt-auto" style={{ borderColor: 'var(--border)', background: 'var(--card)' }}>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold truncate">{user?.name || 'My Account'}</div>
            <div className="text-[11px] muted truncate">{user?.email}</div>
          </div>
          <button
            className="btn p-2 rounded-lg"
            style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }}
            onClick={() => setDark(!dark)}
            aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            title="Toggle theme"
          >
            {dark ? <Sun size={15} /> : <Moon size={15} />}
          </button>
          <button
            className="btn p-2 rounded-lg"
            style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }}
            onClick={logout}
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut size={15} />
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 min-w-0 flex flex-col pb-20 md:pb-6">
        {/* Top Navbar */}
        <header
          className="sticky top-0 z-10 flex items-center justify-between px-4 py-2.5 border-b backdrop-blur-md bg-[var(--bg)]/90"
          style={{ borderColor: 'var(--border)' }}
        >
          {/* Mobile brand / search trigger */}
          <div className="flex items-center gap-2">
            <div className="md:hidden flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-accent text-white flex items-center justify-center font-bold text-xs">
                ₹
              </div>
              <span className="font-bold text-sm tracking-tight">Smart Expense</span>
            </div>

            {/* Global search trigger on mobile */}
            <button
              onClick={() => setPaletteOpen(true)}
              className="md:hidden flex items-center gap-1.5 px-2.5 py-1 text-xs muted rounded-full border bg-[var(--card)]"
              style={{ borderColor: 'var(--border)' }}
              aria-label="Open search palette"
            >
              <Search size={13} />
              <span>/</span>
            </button>
          </div>

          {/* Right Header items */}
          <div className="flex items-center gap-2 ml-auto">
            {/* Quick palette button on desktop header */}
            <button
              onClick={() => setPaletteOpen(true)}
              className="hidden sm:flex items-center gap-2 text-xs muted px-2.5 py-1.5 rounded-lg border bg-[var(--card)] hover:text-[var(--fg)] transition"
              style={{ borderColor: 'var(--border)' }}
            >
              <Search size={13} />
              <span>Jump to…</span>
              <kbd className="font-mono text-[10px] bg-[var(--bg)] px-1 rounded border" style={{ borderColor: 'var(--border)' }}>/</kbd>
            </button>

            {/* Notifications button */}
            <div className="relative">
              <button
                className="btn relative p-2 rounded-lg"
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
                <div
                  className="absolute right-0 mt-2 w-80 sm:w-96 card p-3 z-50 shadow-2xl flex flex-col gap-2 rounded-xl"
                  style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
                >
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
                          className={`p-2.5 rounded-lg border flex flex-col gap-1 transition ${
                            !n.read ? 'bg-accent/5 font-medium border-accent/30' : 'muted opacity-80'
                          }`}
                          style={{ borderColor: !n.read ? undefined : 'var(--border)' }}
                        >
                          <p className="text-xs">{n.message}</p>
                          <span className="text-[10px] muted">
                            {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Mobile dark toggle */}
            <button
              className="md:hidden btn p-2 rounded-lg"
              style={{ background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' }}
              onClick={() => setDark(!dark)}
              aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {dark ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
        </header>

        {/* Demo mode banner */}
        {user?.is_demo && (
          <div
            className="mx-4 my-3 max-w-6xl md:mx-auto rounded-lg px-3 py-2 text-xs flex items-center justify-between"
            role="status"
            style={{ background: 'rgba(217, 119, 6, 0.1)', border: '1px solid var(--warn)', color: 'var(--warn)' }}
          >
            <span>✨ <strong>Demo mode</strong>: Sample fintech data for presentation &amp; exploration.</span>
          </div>
        )}

        {/* Page Content */}
        <main className="p-3 sm:p-5 md:p-6 max-w-6xl w-full mx-auto animate-fade-in">
          <Outlet />
        </main>
      </div>

      {/* Onboarding Wizard Modal */}
      {showOnboarding && <OnboardingModal onClose={() => setShowOnboarding(false)} />}

      {/* Command Palette Modal */}
      <CommandPalette
        isOpen={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onOpenQuickAdd={(kind) => openQuickAdd(kind ?? 'expense')}
      />

      {/* Quick Add Modal */}
      <QuickAddModal
        isOpen={quickAddOpen}
        onClose={() => setQuickAddOpen(false)}
        initialKind={quickAddKind}
        onSuccess={() => {
          // Trigger a custom event so open pages can refresh data
          window.dispatchEvent(new CustomEvent('expense-tracker:tx-updated'))
        }}
      />

      {/* Mobile Drawer (More links) */}
      {moreDrawer && (
        <>
          <div
            className="md:hidden fixed inset-0 bg-black/40 z-40 backdrop-blur-xs animate-fade-in"
            onClick={() => setMoreDrawer(false)}
          />
          <div
            className="md:hidden fixed bottom-16 inset-x-3 z-50 card flex flex-col gap-1 p-3 max-h-[75vh] overflow-y-auto shadow-2xl rounded-2xl border"
            style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
            role="menu"
          >
            <div className="flex items-center justify-between pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
              <span className="font-semibold text-xs uppercase tracking-wider text-muted">More Pages &amp; Tools</span>
              <button onClick={() => setMoreDrawer(false)} className="p-1 rounded-full text-muted">
                <X size={16} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-1 py-1">
              {[...MAIN_NAV.slice(4), ...SECONDARY_NAV].map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  role="menuitem"
                  className={({ isActive }) =>
                    `flex items-center gap-2 rounded-lg p-2 text-xs font-medium transition ${
                      isActive ? 'bg-accent/10 text-accent font-semibold' : 'hover:bg-[var(--bg)]'
                    }`
                  }
                  onClick={() => setMoreDrawer(false)}
                >
                  <Icon size={15} />
                  <span className="truncate">{label}</span>
                </NavLink>
              ))}
            </div>
            <div className="pt-2 border-t mt-1 flex items-center justify-between text-xs muted" style={{ borderColor: 'var(--border)' }}>
              <span className="truncate">{user?.email}</span>
              <button onClick={logout} className="text-bad hover:underline font-medium">Sign out</button>
            </div>
          </div>
        </>
      )}

      {/* Mobile Bottom Navigation Bar (Thumb friendly, modern fintech style) */}
      <nav
        className="md:hidden fixed bottom-0 inset-x-0 h-16 flex items-center justify-around px-2 border-t z-30 shadow-lg"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
        aria-label="Mobile Navigation"
      >
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            `flex flex-col items-center justify-center flex-1 py-1 text-[10px] font-medium transition ${
              isActive ? 'text-accent font-semibold' : 'muted hover:text-[var(--fg)]'
            }`
          }
        >
          <LayoutDashboard size={20} />
          <span className="mt-1">Dashboard</span>
        </NavLink>

        <NavLink
          to="/transactions"
          className={({ isActive }) =>
            `flex flex-col items-center justify-center flex-1 py-1 text-[10px] font-medium transition ${
              isActive ? 'text-accent font-semibold' : 'muted hover:text-[var(--fg)]'
            }`
          }
        >
          <Receipt size={20} />
          <span className="mt-1">Transactions</span>
        </NavLink>

        {/* Center Prominent + Add Transaction Button */}
        <div className="flex flex-col items-center justify-center flex-1 -mt-5">
          <button
            onClick={() => openQuickAdd('expense')}
            className="w-12 h-12 rounded-full bg-accent text-white flex items-center justify-center shadow-lg active:scale-95 transition-transform"
            aria-label="Add transaction"
            title="Add transaction"
          >
            <Plus size={24} strokeWidth={2.5} />
          </button>
          <span className="text-[10px] mt-1 font-semibold text-accent">Add</span>
        </div>

        <NavLink
          to="/budgets"
          className={({ isActive }) =>
            `flex flex-col items-center justify-center flex-1 py-1 text-[10px] font-medium transition ${
              isActive ? 'text-accent font-semibold' : 'muted hover:text-[var(--fg)]'
            }`
          }
        >
          <PiggyBank size={20} />
          <span className="mt-1">Budgets</span>
        </NavLink>

        <button
          onClick={() => setMoreDrawer(!moreDrawer)}
          className={`flex flex-col items-center justify-center flex-1 py-1 text-[10px] font-medium transition ${
            moreDrawer ? 'text-accent font-semibold' : 'muted hover:text-[var(--fg)]'
          }`}
          aria-expanded={moreDrawer}
          aria-label="More navigation options"
        >
          <MoreHorizontal size={20} />
          <span className="mt-1">More</span>
        </button>
      </nav>
    </div>
  )
}
