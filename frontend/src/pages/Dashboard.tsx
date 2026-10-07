import { useEffect, useState, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight,
  Wallet, PiggyBank, Target, Calendar, ArrowRight, PlusCircle,
  Sparkles, ChevronRight, RefreshCw, CreditCard
} from 'lucide-react'
import {
  Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis, CartesianGrid, Area, AreaChart
} from 'recharts'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money, pct } from '../lib/format'
import { pmLabel, type TxPage, type Transaction } from '../lib/types'
import { Empty, ErrorBox } from '../components/ui'
import type { WhatChangedData } from './WhatChanged'

interface UpItem {
  kind: string
  name: string
  amount: number
  due_date: string
  days_until: number
  group: string
}

interface Dash {
  currency: string
  cards: {
    total_balance: number
    month_income: number
    month_expenses: number
    savings: number
    budget_remaining: number | null
    net_worth: number
  }
  spending_by_category: { category: string; amount: number }[]
  monthly_trend: { month: string; income: number; expenses: number }[]
  budget_status: null | {
    total_limit: number
    remaining: number
    categories: { category: string; limit: number; used: number; remaining: number; percent_used: number | null }[]
  }
  upcoming_payments: {
    items: UpItem[]
    groups: Record<'overdue' | 'today' | 'tomorrow' | 'this_week' | 'later', UpItem[]>
    totals: { overdue: number; next_7_days: number; next_30_days: number }
  }
  recurring_summary: {
    subscriptions_count: number
    subscriptions_monthly: number
    subscriptions_annual: number
    bills_monthly: number
    total_monthly: number
    total_annual: number
    pending_review: number
  }
  analytics_summary: {
    savings_rate: number | null
    average_daily_spending: number
    highest_category: { category: string; amount: number; share: number } | null
    month_over_month: { change: number; change_pct: number | null; current_label: string; previous_label: string }
  }
  what_changed: WhatChangedData
  goals: {
    id: number
    name: string
    target: number
    current: number
    remaining: number
    percent: number | null
    target_date: string | null
    status?: string
    required_monthly?: number | null
    on_track?: boolean | null
  }[]
  insights: string[]
  financial_health: {
    score: number | null
    score_change: number | null
    note: string | null
    components: { key: string; label: string; points: number; max: number; reason: string; change_points: number | null }[]
  }
}

const CHART_COLORS = ['#0f766e', '#2563eb', '#d97706', '#7c3aed', '#be123c', '#16a34a', '#0891b2', '#ca8a04']

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

function getRelativeDateBadge(days: number): { label: string; tone: string } {
  if (days < 0) return { label: `${Math.abs(days)}d overdue`, tone: 'bg-red-500/10 text-bad border-red-500/20' }
  if (days === 0) return { label: 'Today', tone: 'bg-amber-500/10 text-warn border-amber-500/20' }
  if (days === 1) return { label: 'Tomorrow', tone: 'bg-blue-500/10 text-accent border-blue-500/20' }
  if (days <= 7) return { label: `In ${days} days`, tone: 'bg-[var(--card)] text-muted border-[var(--border)]' }
  return { label: `In ${days} days`, tone: 'bg-[var(--card)] text-muted border-[var(--border)]' }
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading your financial dashboard">
      <div className="flex flex-col gap-2">
        <div className="skeleton h-8 w-64 rounded-lg" />
        <div className="skeleton h-4 w-40 rounded" />
      </div>

      <div className="grid gap-3 sm:gap-4 grid-cols-2 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton h-28 rounded-2xl" />
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="skeleton h-72 rounded-2xl" />
        <div className="skeleton h-72 rounded-2xl" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="skeleton h-60 rounded-2xl" />
        <div className="skeleton h-60 rounded-2xl" />
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [data, setData] = useState<Dash | null>(null)
  const [recentTx, setRecentTx] = useState<Transaction[]>([])
  const [error, setError] = useState<string | null>(null)
  const [safe, setSafe] = useState<{ safe_to_spend_daily: number; safe_to_spend_total: number; days_left_in_month: number } | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(() => {
    setError(null)
    setRefreshing(true)

    Promise.all([
      api<Dash>('/dashboard'),
      api<TxPage>('/transactions?page_size=5'),
      api<{ safe_to_spend_daily: number; safe_to_spend_total: number; days_left_in_month: number }>('/planning/safe-to-spend').catch(() => null),
    ])
      .then(([dashData, txData, safeData]) => {
        setData(dashData)
        if (txData && txData.items) setRecentTx(txData.items)
        if (safeData) setSafe(safeData)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load your dashboard.'))
      .finally(() => setRefreshing(false))
  }, [])

  useEffect(() => {
    load()
    const handleUpdate = () => load()
    window.addEventListener('expense-tracker:tx-updated', handleUpdate)
    return () => window.removeEventListener('expense-tracker:tx-updated', handleUpdate)
  }, [load])

  if (error) {
    return (
      <div className="py-12">
        <ErrorBox message="We could not load your dashboard overview right now." onRetry={load} />
      </div>
    )
  }

  if (!data) return <DashboardSkeleton />

  const c = data.cards
  const cur = data.currency
  const displayName = user?.name ? user.name.split(' ')[0] : 'there'
  const mom = data.analytics_summary.month_over_month
  const isMomHigher = mom && mom.change > 0

  // Check if totally empty state (new user)
  const hasNoData = c.month_income === 0 && c.month_expenses === 0 && c.total_balance === 0 && recentTx.length === 0

  if (hasNoData) {
    return (
      <div className="flex flex-col gap-6 max-w-2xl mx-auto py-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {getGreeting()}, {displayName} 👋
          </h1>
          <p className="text-sm muted mt-0.5">Welcome to your Smart Expense Tracker</p>
        </div>

        <div className="card p-8 text-center flex flex-col items-center gap-4 rounded-2xl shadow-sm border" style={{ borderColor: 'var(--border)' }}>
          <div className="w-16 h-16 rounded-2xl bg-accent/10 text-accent flex items-center justify-center font-bold text-2xl">
            ✨
          </div>
          <div>
            <h2 className="text-xl font-bold">Your money story starts here</h2>
            <p className="muted text-sm max-w-md mx-auto mt-1">
              Add your first transaction to start seeing your spending trends, budget tracking, and smart financial insights.
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-3 mt-2">
            <Link
              to="/add-expense"
              className="btn flex items-center gap-2 px-5 py-2.5 font-semibold text-sm shadow-md"
              style={{ background: 'var(--accent)', color: '#ffffff' }}
            >
              <PlusCircle size={17} /> Add your first expense
            </Link>
            <Link to="/imports" className="btn flex items-center gap-2 px-4 py-2 text-sm border" style={{ borderColor: 'var(--border)' }}>
              Import CSV / Statement
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Top Section: Greeting & Period Headline */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-1 border-b" style={{ borderColor: 'var(--border)' }}>
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            {getGreeting()}, {displayName} 👋
          </h1>
          <p className="text-xs sm:text-sm muted mt-0.5 flex items-center gap-2">
            <span>This month's financial pulse</span>
            <span>•</span>
            <span className="font-medium text-[var(--fg)]">
              {new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
            </span>
          </p>
        </div>

        <div className="flex items-center gap-2">
          {safe && (
            <div
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-medium"
              style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
              title="Safe to spend calculated after bills & budget limits"
            >
              <span className="text-muted">Safe/day:</span>
              <span className="font-bold text-accent">{money(safe.safe_to_spend_daily, cur)}</span>
            </div>
          )}
          <button
            onClick={load}
            disabled={refreshing}
            className="btn p-2 rounded-lg text-xs flex items-center gap-1.5"
            style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
            title="Refresh dashboard"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {/* Row 1: Balance / Income / Expenses / Savings / Budget remaining (Interactive Cards) */}
      <div className="grid gap-3 sm:gap-4 grid-cols-2 lg:grid-cols-5">
        {/* Balance Card */}
        <div
          onClick={() => nav('/transactions')}
          className="card-interactive p-4 rounded-2xl flex flex-col justify-between"
          role="button"
          tabIndex={0}
          aria-label="View account transactions"
        >
          <div className="flex items-center justify-between text-xs muted font-medium">
            <span>Total Balance</span>
            <Wallet size={16} className="text-accent" />
          </div>
          <div className="mt-2">
            <div className="text-xl sm:text-2xl font-bold tracking-tight">
              {money(c.total_balance, cur)}
            </div>
            <div className="text-[11px] muted mt-0.5 flex items-center gap-1">
              <span>Net worth:</span>
              <span className="font-semibold text-[var(--fg)]">{money(c.net_worth, cur)}</span>
            </div>
          </div>
        </div>

        {/* Income Card */}
        <div
          onClick={() => nav('/transactions?type=income')}
          className="card-interactive p-4 rounded-2xl flex flex-col justify-between"
          role="button"
          tabIndex={0}
          aria-label="View income transactions"
        >
          <div className="flex items-center justify-between text-xs muted font-medium">
            <span>Income</span>
            <TrendingUp size={16} className="text-good" />
          </div>
          <div className="mt-2">
            <div className="text-xl sm:text-2xl font-bold tracking-tight text-good">
              {money(c.month_income, cur)}
            </div>
            <div className="text-[11px] text-good mt-0.5 font-medium flex items-center gap-0.5">
              <ArrowDownRight size={13} />
              <span>Received this month</span>
            </div>
          </div>
        </div>

        {/* Expenses Card */}
        <div
          onClick={() => nav('/transactions?type=expense')}
          className="card-interactive p-4 rounded-2xl flex flex-col justify-between"
          role="button"
          tabIndex={0}
          aria-label="View expenses and trends"
        >
          <div className="flex items-center justify-between text-xs muted font-medium">
            <span>Expenses</span>
            <TrendingDown size={16} className="text-bad" />
          </div>
          <div className="mt-2">
            <div className="text-xl sm:text-2xl font-bold tracking-tight">
              {money(c.month_expenses, cur)}
            </div>
            {mom && mom.change_pct !== null ? (
              <div
                className="text-[11px] mt-0.5 font-medium flex items-center gap-0.5"
                style={{ color: isMomHigher ? 'var(--bad)' : 'var(--good)' }}
              >
                {isMomHigher ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
                <span>
                  {Math.abs(Math.round(mom.change_pct))}% vs last month
                </span>
              </div>
            ) : (
              <div className="text-[11px] muted mt-0.5">Outflows this month</div>
            )}
          </div>
        </div>

        {/* Savings Card */}
        <div
          onClick={() => nav('/goals')}
          className="card-interactive p-4 rounded-2xl flex flex-col justify-between"
          role="button"
          tabIndex={0}
          aria-label="View savings goals"
        >
          <div className="flex items-center justify-between text-xs muted font-medium">
            <span>Savings</span>
            <PiggyBank size={16} className="text-accent" />
          </div>
          <div className="mt-2">
            <div
              className="text-xl sm:text-2xl font-bold tracking-tight"
              style={{ color: c.savings >= 0 ? 'var(--good)' : 'var(--bad)' }}
            >
              {money(c.savings, cur)}
            </div>
            <div className="text-[11px] muted mt-0.5 font-medium">
              {data.analytics_summary.savings_rate !== null
                ? `${pct(data.analytics_summary.savings_rate)} savings rate`
                : 'Track toward goals'}
            </div>
          </div>
        </div>

        {/* Budget Remaining Card */}
        <div
          onClick={() => nav('/budgets')}
          className="card-interactive p-4 rounded-2xl flex flex-col justify-between col-span-2 sm:col-span-1"
          role="button"
          tabIndex={0}
          aria-label="View budgets"
        >
          <div className="flex items-center justify-between text-xs muted font-medium">
            <span>Budget Remaining</span>
            <Target size={16} className="text-accent" />
          </div>
          <div className="mt-2">
            {c.budget_remaining !== null ? (
              <>
                <div
                  className="text-xl sm:text-2xl font-bold tracking-tight"
                  style={{ color: c.budget_remaining < 0 ? 'var(--bad)' : undefined }}
                >
                  {money(c.budget_remaining, cur)}
                </div>
                <div className="text-[11px] muted mt-0.5 font-medium">
                  {c.budget_remaining < 0 ? 'Over limit' : 'Available this month'}
                </div>
              </>
            ) : (
              <>
                <div className="text-base font-bold text-accent">Set Budget</div>
                <div className="text-[11px] muted mt-0.5">Create your monthly plan →</div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Row 2: Spending trend + Budget progress */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Spending Trend (Last 6 months) */}
        <section className="card p-4 sm:p-5 rounded-2xl flex flex-col justify-between" aria-label="Monthly spending trend">
          <div className="flex items-center justify-between pb-3">
            <div>
              <h2 className="font-bold text-sm tracking-tight">Spending &amp; Income Trend</h2>
              <p className="text-xs muted">Past 6 months comparison</p>
            </div>
            <Link to="/analytics" className="text-xs font-semibold text-accent hover:underline flex items-center gap-0.5">
              Analytics <ChevronRight size={14} />
            </Link>
          </div>

          <div className="h-60 w-full mt-2">
            {data.monthly_trend.every((m) => m.income === 0 && m.expenses === 0) ? (
              <Empty title="No trend history yet">Keep logging transactions to visualize your progress over time.</Empty>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.monthly_trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="incomeGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#16a34a" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="expenseGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" opacity={0.6} />
                  <XAxis dataKey="month" stroke="var(--muted)" fontSize={11} tickLine={false} />
                  <YAxis stroke="var(--muted)" fontSize={11} tickLine={false} tickFormatter={(v) => money(v, cur)} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--card)',
                      borderColor: 'var(--border)',
                      borderRadius: '0.75rem',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                      fontSize: '12px',
                    }}
                    formatter={(v) => money(Number(v), cur)}
                  />
                  <Area type="monotone" dataKey="income" name="Income" stroke="#16a34a" strokeWidth={2} fill="url(#incomeGrad)" />
                  <Area type="monotone" dataKey="expenses" name="Expenses" stroke="#ef4444" strokeWidth={2} fill="url(#expenseGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        {/* Budget Progress */}
        <section className="card p-4 sm:p-5 rounded-2xl flex flex-col justify-between" aria-label="Budget status">
          <div className="flex items-center justify-between pb-3">
            <div>
              <h2 className="font-bold text-sm tracking-tight">Budget Progress</h2>
              <p className="text-xs muted">
                {data.budget_status
                  ? `${money(data.budget_status.remaining, cur)} remaining across categories`
                  : 'Monthly spending guardrails'}
              </p>
            </div>
            <Link to="/budgets" className="text-xs font-semibold text-accent hover:underline flex items-center gap-0.5">
              Manage <ChevronRight size={14} />
            </Link>
          </div>

          <div className="flex-1 flex flex-col justify-center">
            {!data.budget_status || data.budget_status.categories.length === 0 ? (
              <Empty title="No budgets active">
                Set category limits to track food, rent, shopping, and more.
                <div className="mt-3">
                  <Link to="/budgets" className="btn btn-secondary text-xs px-3 py-1.5">
                    + Set monthly budget
                  </Link>
                </div>
              </Empty>
            ) : (
              <div className="flex flex-col gap-3 py-1">
                {data.budget_status.categories.slice(0, 4).map((b) => {
                  const pctVal = b.percent_used ?? 0
                  const isOver = pctVal >= 100
                  const isWarn = pctVal >= 70 && !isOver

                  return (
                    <div key={b.category} className="flex flex-col gap-1.5">
                      <div className="flex justify-between items-baseline text-xs">
                        <span className="font-semibold">{b.category}</span>
                        <span className="muted font-mono">
                          {money(b.used, cur)} / {money(b.limit, cur)}
                          <span
                            className="ml-1.5 font-bold"
                            style={{ color: isOver ? 'var(--bad)' : isWarn ? 'var(--warn)' : 'var(--accent)' }}
                          >
                            ({pct(b.percent_used)})
                          </span>
                        </span>
                      </div>
                      <div className="h-2 rounded-full overflow-hidden bg-[var(--border)]" role="progressbar" aria-valuenow={Math.round(pctVal)}>
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.min(pctVal, 100)}%`,
                            backgroundColor: isOver ? 'var(--bad)' : isWarn ? 'var(--warn)' : 'var(--accent)',
                          }}
                        />
                      </div>
                      {isOver && (
                        <span className="text-[11px] text-bad font-medium">
                          You're {money(Math.abs(b.remaining), cur)} over your limit for {b.category}.
                        </span>
                      )}
                      {isWarn && (
                        <span className="text-[11px] text-warn font-medium">
                          Getting close: {money(b.remaining, cur)} left this month.
                        </span>
                      )}
                    </div>
                  )
                })}
                {data.budget_status.categories.length > 4 && (
                  <Link to="/budgets" className="text-xs text-accent hover:underline mt-1">
                    +{data.budget_status.categories.length - 4} more category budgets
                  </Link>
                )}
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Row 3: What Changed + Upcoming payments */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* What Changed This Month */}
        <section className="card p-4 sm:p-5 rounded-2xl" aria-label="What changed this month">
          <div className="flex items-center justify-between pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
            <div>
              <h2 className="font-bold text-sm tracking-tight flex items-center gap-1.5">
                <Sparkles size={16} className="text-accent" />
                <span>What changed this month?</span>
              </h2>
              <p className="text-xs muted">{data.what_changed.comparison_note}</p>
            </div>
            <Link to="/analytics" className="text-xs font-semibold text-accent hover:underline flex items-center gap-0.5">
              See details →
            </Link>
          </div>

          <div className="mt-3">
            {!data.what_changed.comparable ? (
              <p className="text-xs muted py-4 text-center">{data.what_changed.headline}</p>
            ) : (
              <div className="flex flex-col gap-3">
                <p className="text-sm font-semibold">{data.what_changed.headline}</p>
                {data.what_changed.drivers_sentence && (
                  <p className="text-xs muted">{data.what_changed.drivers_sentence}</p>
                )}

                <div className="grid gap-4 sm:grid-cols-2 mt-1">
                  {/* Increases */}
                  <div className="flex flex-col gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-bad flex items-center gap-1">
                      <TrendingUp size={13} /> Spending Up
                    </span>
                    {data.what_changed.increases.length === 0 ? (
                      <p className="text-xs muted">No notable increases.</p>
                    ) : (
                      <div className="flex flex-col gap-1.5 text-xs">
                        {data.what_changed.increases.slice(0, 3).map((m) => (
                          <div key={m.category} className="flex justify-between items-center py-1 border-b border-[var(--border)]/40">
                            <span className="truncate">{m.category}</span>
                            <span className="font-semibold text-bad font-mono whitespace-nowrap">
                              +{money(Math.abs(m.change), cur)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Decreases */}
                  <div className="flex flex-col gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-good flex items-center gap-1">
                      <TrendingDown size={13} /> Spending Down
                    </span>
                    {data.what_changed.decreases.length === 0 ? (
                      <p className="text-xs muted">No notable savings drops.</p>
                    ) : (
                      <div className="flex flex-col gap-1.5 text-xs">
                        {data.what_changed.decreases.slice(0, 3).map((m) => (
                          <div key={m.category} className="flex justify-between items-center py-1 border-b border-[var(--border)]/40">
                            <span className="truncate">{m.category}</span>
                            <span className="font-semibold text-good font-mono whitespace-nowrap">
                              −{money(Math.abs(m.change), cur)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Upcoming Payments (Timeline / Card Design) */}
        <section className="card p-4 sm:p-5 rounded-2xl flex flex-col justify-between" aria-label="Upcoming payments">
          <div className="flex items-center justify-between pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
            <div>
              <h2 className="font-bold text-sm tracking-tight flex items-center gap-1.5">
                <Calendar size={16} className="text-accent" />
                <span>Upcoming Payments</span>
              </h2>
              <p className="text-xs muted">Next 30 days commitments</p>
            </div>
            <Link to="/bills" className="text-xs font-semibold text-accent hover:underline flex items-center gap-0.5">
              All Bills <ChevronRight size={14} />
            </Link>
          </div>

          <div className="mt-3 flex-1">
            {data.upcoming_payments.items.length === 0 ? (
              <Empty title="All clear!">No bills or payments due in the next 30 days.</Empty>
            ) : (
              <div className="flex flex-col gap-2">
                {data.upcoming_payments.items.slice(0, 4).map((p) => {
                  const badge = getRelativeDateBadge(p.days_until)
                  return (
                    <div
                      key={`${p.kind}-${p.name}-${p.due_date}`}
                      className="card-interactive p-2.5 rounded-xl flex items-center justify-between border"
                      style={{ borderColor: 'var(--border)', background: 'var(--card)' }}
                      onClick={() => nav('/bills')}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-8 h-8 rounded-lg bg-[var(--bg)] border flex items-center justify-center shrink-0" style={{ borderColor: 'var(--border)' }}>
                          <CreditCard size={15} className="text-muted" />
                        </div>
                        <div className="truncate">
                          <div className="text-xs font-semibold truncate">{p.name}</div>
                          <div className="text-[11px] muted">{p.due_date}</div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2.5 text-right shrink-0">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${badge.tone}`}>
                          {badge.label}
                        </span>
                        <span className="text-sm font-bold font-mono">
                          {money(p.amount, cur)}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Row 4: Savings goals + Spending categories */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Savings Goals */}
        <section className="card p-4 sm:p-5 rounded-2xl flex flex-col justify-between" aria-label="Savings goals">
          <div className="flex items-center justify-between pb-3">
            <div>
              <h2 className="font-bold text-sm tracking-tight">Savings Goals</h2>
              <p className="text-xs muted">Progress toward targets</p>
            </div>
            <Link to="/goals" className="text-xs font-semibold text-accent hover:underline flex items-center gap-0.5">
              Goals <ChevronRight size={14} />
            </Link>
          </div>

          <div className="flex-1 flex flex-col justify-center">
            {data.goals.length === 0 ? (
              <Empty title="No goals yet">
                Create a savings goal for an emergency fund, gadget, or vacation.
                <div className="mt-3">
                  <Link to="/goals" className="btn btn-secondary text-xs px-3 py-1.5">
                    + Set a goal
                  </Link>
                </div>
              </Empty>
            ) : (
              <div className="flex flex-col gap-3 py-1">
                {data.goals.slice(0, 3).map((g) => (
                  <div key={g.id} className="flex flex-col gap-1.5">
                    <div className="flex justify-between items-baseline text-xs">
                      <span className="font-semibold">{g.name}</span>
                      <span className="muted font-mono">
                        {money(g.current, cur)} / {money(g.target, cur)} ({pct(g.percent)})
                      </span>
                    </div>
                    <div className="h-2 rounded-full overflow-hidden bg-[var(--border)]" role="progressbar" aria-valuenow={Math.round(g.percent ?? 0)}>
                      <div
                        className="h-full rounded-full bg-accent transition-all duration-500"
                        style={{ width: `${Math.min(g.percent ?? 0, 100)}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-[11px] muted">
                      <span>{money(g.remaining, cur)} left to reach goal</span>
                      {g.target_date && <span>Target: {g.target_date}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Spending Categories Breakdown */}
        <section className="card p-4 sm:p-5 rounded-2xl flex flex-col justify-between" aria-label="Spending by category">
          <div className="flex items-center justify-between pb-3">
            <div>
              <h2 className="font-bold text-sm tracking-tight">Top Categories</h2>
              <p className="text-xs muted">Where your money went this month</p>
            </div>
            <Link to="/analytics" className="text-xs font-semibold text-accent hover:underline flex items-center gap-0.5">
              Breakdown <ChevronRight size={14} />
            </Link>
          </div>

          <div className="h-56 w-full flex items-center justify-center">
            {data.spending_by_category.length === 0 ? (
              <Empty title="No expenses this month">Transactions you log will populate this breakdown.</Empty>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data.spending_by_category}
                    dataKey="amount"
                    nameKey="category"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={3}
                  >
                    {data.spending_by_category.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--card)',
                      borderColor: 'var(--border)',
                      borderRadius: '0.75rem',
                      fontSize: '12px',
                    }}
                    formatter={(v) => money(Number(v), cur)}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>
      </div>

      {/* Row 5: Recent Transactions (Easy to Scan) */}
      <section className="card p-4 sm:p-5 rounded-2xl" aria-label="Recent transactions">
        <div className="flex items-center justify-between pb-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <div>
            <h2 className="font-bold text-sm tracking-tight">Recent Transactions</h2>
            <p className="text-xs muted">Latest account activity</p>
          </div>
          <Link
            to="/transactions"
            className="btn btn-secondary text-xs px-3 py-1.5 flex items-center gap-1 font-semibold"
          >
            <span>View All Transactions</span>
            <ArrowRight size={13} />
          </Link>
        </div>

        <div className="mt-3">
          {recentTx.length === 0 ? (
            <Empty title="No transactions yet">
              Click the button below to add your first transaction.
              <div className="mt-3">
                <Link to="/add-expense" className="btn btn-primary text-xs px-4 py-2">
                  + Add Expense
                </Link>
              </div>
            </Empty>
          ) : (
            <div className="flex flex-col divide-y" style={{ borderColor: 'var(--border)' }}>
              {recentTx.map((t) => (
                <div
                  key={t.id}
                  onClick={() => nav(`/transactions/${t.id}/edit`)}
                  className="py-3 flex items-center justify-between gap-3 hover:bg-[var(--card)] px-2 rounded-xl transition cursor-pointer"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`w-9 h-9 rounded-xl flex items-center justify-center font-bold text-sm shrink-0 ${
                        t.type === 'income' ? 'bg-green-500/10 text-good' : t.type === 'transfer' ? 'bg-blue-500/10 text-accent' : 'bg-red-500/10 text-bad'
                      }`}
                    >
                      {t.type === 'income' ? '↓' : t.type === 'transfer' ? '⇄' : '↑'}
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-semibold truncate flex items-center gap-2">
                        <span>{t.merchant || t.category || 'Transaction'}</span>
                        {t.category && (
                          <span className="text-[10px] muted px-1.5 py-0.2 rounded bg-[var(--bg)] border font-normal" style={{ borderColor: 'var(--border)' }}>
                            {t.category}
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] muted flex items-center gap-1.5 mt-0.5">
                        <span>{t.date}</span>
                        <span>•</span>
                        <span>{pmLabel(t.payment_method)}</span>
                        {t.notes && <span className="truncate max-w-[150px]">• {t.notes}</span>}
                      </div>
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <span
                      className="text-sm font-bold font-mono"
                      style={{ color: t.type === 'income' ? 'var(--good)' : undefined }}
                    >
                      {t.type === 'income' ? '+' : t.type === 'transfer' ? '' : '−'}
                      {money(t.amount, cur)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
