import {
  Bar, BarChart, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Area, AreaChart
} from 'recharts'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight,
  PieChart as PieIcon, Store, CreditCard, Layers
} from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money, pct } from '../lib/format'
import { pmLabel } from '../lib/types'
import { Empty, ErrorBox, Stat } from '../components/ui'
import WhatChanged, { type WhatChangedData } from './WhatChanged'
import { useEffect, useState } from 'react'

const PERIODS = [
  ['this_month', 'This month'],
  ['last_month', 'Last month'],
  ['last_3_months', '3 months'],
  ['last_6_months', '6 months'],
  ['this_year', 'This year'],
  ['custom', 'Custom'],
] as const

const COLORS = ['#0f766e', '#2563eb', '#d97706', '#7c3aed', '#be123c', '#16a34a', '#0891b2', '#ca8a04', '#64748b']

interface Cat {
  category_id: number | null
  category: string
  essential: boolean | null
  amount: number
  count: number
  share: number
}

interface Cmp {
  current: number
  previous: number
  change: number
  change_pct: number | null
  current_label: string
  previous_label: string
}

interface A {
  period: { kind: string; label: string; start: string; end: string; days: number; days_elapsed: number }
  previous_period: { label: string; start: string; end: string }
  totals: {
    income: number
    expenses: number
    net_savings: number
    savings_rate: number | null
    transaction_count: number
    average_daily_spending: number
  }
  previous_totals: { income: number; expenses: number; net_savings: number; savings_rate: number | null }
  by_category: Cat[]
  by_merchant: {
    top: { merchant_key: string; merchant: string; amount: number; count: number; share: number }[]
    other_total: number
    other_count: number
    no_merchant_total: number
  }
  by_payment_method: { payment_method: string; amount: number; count: number; share: number }[]
  income_vs_expenses: { granularity: string; points: { bucket: string; income: number; expenses: number; net: number }[] }
  monthly_trend: { month: string; income: number; expenses: number; savings: number; savings_rate: number | null }[]
  month_over_month: Cmp
  week_over_week: Cmp
  highest_category: Cat | null
  highest_spending_day: { date: string; amount: number } | null
  largest_transactions: { id: number; merchant: string | null; amount: number; date: string; category: string | null }[]
  essential_vs_discretionary: {
    essential: number
    discretionary: number
    unclassified: number
    essential_share: number | null
    coverage: number
    note: string | null
  }
  budget_performance: { month: string; limit: number; spent: number; percent_used: number | null; partial: boolean }[]
  excluded_other_currency: number
}

function ComparisonCard({ title, c, cur }: { title: string; c: Cmp; cur: string }) {
  const up = c.change > 0
  return (
    <div className="card p-4 rounded-2xl border" style={{ borderColor: 'var(--border)' }}>
      <div className="text-xs muted font-semibold uppercase tracking-wider">{title}</div>
      <div className="text-xl sm:text-2xl font-bold tracking-tight mt-1">{money(c.current, cur)}</div>
      <div
        className="text-xs font-semibold mt-1 flex items-center gap-1"
        style={{ color: c.change === 0 ? undefined : up ? 'var(--bad)' : 'var(--good)' }}
      >
        {up ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
        <span>
          {c.change === 0 ? 'No change' : `${up ? '+' : '−'}${money(Math.abs(c.change), cur)}`}
        </span>
        {c.change_pct !== null && c.change !== 0 && (
          <span>({c.change_pct > 0 ? '+' : ''}{Math.round(c.change_pct)}%)</span>
        )}
      </div>
      <div className="text-[11px] muted mt-1">
        {c.current_label} vs {c.previous_label}: {money(c.previous, cur)}
      </div>
    </div>
  )
}

export default function Analytics() {
  const { user } = useAuth()
  const cur = user?.currency ?? 'INR'
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()

  const period = params.get('period') ?? 'this_month'
  const from = params.get('date_from') ?? ''
  const to = params.get('date_to') ?? ''

  const customReady = period !== 'custom' || (from && to && from <= to)
  const qs = `period=${period}${period === 'custom' ? `&date_from=${from}&date_to=${to}` : ''}`

  const [data, setData] = useState<A | null>(null)
  const [whatChanged, setWhatChanged] = useState<WhatChangedData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    if (!customReady) return
    setLoading(true)
    setError(null)

    Promise.all([
      api<A>(`/analytics?${qs}`),
      api<WhatChangedData>(`/what-changed?${qs}`).catch(() => null),
    ])
      .then(([aData, wData]) => {
        setData(aData)
        if (wData) setWhatChanged(wData)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load analytics.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [qs, customReady])

  const setFilter = (k: string, v: string) => {
    const n = new URLSearchParams(params)
    if (v) n.set(k, v)
    else n.delete(k)
    setParams(n, { replace: true })
  }

  const drill = (extra: Record<string, string>) => {
    if (!data) return
    nav(
      `/transactions?${new URLSearchParams({
        date_from: data.period.start,
        date_to: data.period.end,
        ...extra,
      })}`
    )
  }

  const drillCat = (c: Cat) =>
    drill({
      type: 'expense',
      ...(c.category_id === null ? { uncategorized: 'true' } : { category_id: String(c.category_id) }),
    })

  return (
    <div className="flex flex-col gap-6">
      {/* Top Section */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Your spending overview</h1>
          <p className="text-xs sm:text-sm muted mt-0.5">
            Understand your cash flow, trends, top merchants, and savings rate
          </p>
        </div>

        {/* Time selector pills */}
        <div
          className="flex flex-wrap items-center gap-1 bg-[var(--card)] p-1 rounded-xl border self-start sm:self-auto"
          style={{ borderColor: 'var(--border)' }}
          role="group"
          aria-label="Time selector"
        >
          {PERIODS.map(([k, l]) => (
            <button
              key={k}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                period === k
                  ? 'bg-accent text-white shadow-xs'
                  : 'muted hover:text-[var(--fg)] hover:bg-[var(--bg)]'
              }`}
              onClick={() => setFilter('period', k === 'this_month' ? '' : k)}
            >
              {l}
            </button>
          ))}
        </div>
      </div>

      {/* Custom Date Pickers */}
      {period === 'custom' && (
        <div
          className="card p-3 rounded-2xl border flex items-center gap-3 flex-wrap text-xs"
          style={{ borderColor: 'var(--border)' }}
        >
          <span className="font-semibold text-muted">Date range:</span>
          <input
            type="date"
            className="input text-xs py-1.5 rounded-lg"
            value={from}
            max={to || undefined}
            onChange={(e) => setFilter('date_from', e.target.value)}
          />
          <span className="muted">to</span>
          <input
            type="date"
            className="input text-xs py-1.5 rounded-lg"
            value={to}
            min={from || undefined}
            onChange={(e) => setFilter('date_to', e.target.value)}
          />
          {!customReady && (
            <span className="text-bad font-medium">Please select a valid start and end date.</span>
          )}
        </div>
      )}

      {error && <ErrorBox message={error} onRetry={load} />}

      {/* Loading Skeleton */}
      {loading && !data && (
        <div className="flex flex-col gap-4">
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="skeleton h-24 rounded-2xl" />
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="skeleton h-72 rounded-2xl" />
            <div className="skeleton h-72 rounded-2xl" />
          </div>
        </div>
      )}

      {/* Data display */}
      {data && (
        <>
          {data.totals.transaction_count === 0 ? (
            <div className="card p-10 text-center rounded-2xl border shadow-sm" style={{ borderColor: 'var(--border)' }}>
              <Empty title="Nothing to analyze yet">
                Add a few transactions and we'll turn them into useful spending trends and breakdowns.
                <div className="mt-4">
                  <button
                    onClick={() => nav('/add-expense')}
                    className="btn btn-primary text-xs px-4 py-2 font-semibold"
                  >
                    + Add Transaction
                  </button>
                </div>
              </Empty>
            </div>
          ) : (
            <div className="flex flex-col gap-6">
              {/* Row 1: KPI Stat Cards */}
              <div className="grid gap-3 sm:gap-4 grid-cols-2 lg:grid-cols-4">
                <Stat label="Total Income" value={money(data.totals.income, cur)} tone="good" icon={<TrendingUp size={16} />} />
                <Stat label="Total Expenses" value={money(data.totals.expenses, cur)} tone="bad" icon={<TrendingDown size={16} />} />
                <Stat
                  label="Net Savings"
                  value={money(data.totals.net_savings, cur)}
                  tone={data.totals.net_savings < 0 ? 'bad' : 'good'}
                  sub={data.totals.savings_rate !== null ? `${pct(data.totals.savings_rate)} savings rate` : undefined}
                />
                <Stat
                  label="Avg Daily Spend"
                  value={money(data.totals.average_daily_spending, cur)}
                  sub={`over ${data.period.days_elapsed} days`}
                />
              </div>

              {/* Row 2: Comparisons */}
              <div className="grid gap-4 md:grid-cols-2">
                <ComparisonCard title="Month over Month Comparison" c={data.month_over_month} cur={cur} />
                <ComparisonCard title="Week over Week Comparison" c={data.week_over_week} cur={cur} />
              </div>

              {/* Row 3: What Changed section */}
              {whatChanged && <WhatChanged data={whatChanged} currency={cur} />}

              {/* Row 4: Spending by Category & Top Merchants */}
              <div className="grid gap-4 lg:grid-cols-2">
                {/* Category Breakdown */}
                <section className="card p-4 sm:p-5 rounded-2xl border shadow-xs" style={{ borderColor: 'var(--border)' }}>
                  <div className="flex items-center justify-between pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
                    <div>
                      <h2 className="font-bold text-sm tracking-tight flex items-center gap-1.5">
                        <PieIcon size={16} className="text-accent" />
                        <span>Category Breakdown</span>
                      </h2>
                      <p className="text-xs muted">Click a slice or category to filter</p>
                    </div>
                  </div>

                  <div className="mt-3">
                    {data.by_category.length === 0 ? (
                      <Empty title="No expenses recorded" />
                    ) : (
                      <>
                        <div className="h-56 w-full">
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                              <Pie
                                data={data.by_category}
                                dataKey="amount"
                                nameKey="category"
                                innerRadius={50}
                                outerRadius={85}
                                paddingAngle={2}
                                onClick={(_, i) => drillCat(data.by_category[i])}
                                style={{ cursor: 'pointer' }}
                              >
                                {data.by_category.map((_, i) => (
                                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
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
                        </div>

                        <div className="flex flex-col gap-1.5 mt-2 max-h-48 overflow-y-auto pr-1">
                          {data.by_category.map((c, i) => (
                            <button
                              key={c.category + i}
                              className="w-full flex items-center justify-between py-1.5 px-2 rounded-lg text-xs hover:bg-[var(--bg)] transition text-left"
                              onClick={() => drillCat(c)}
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                <span
                                  className="w-3 h-3 rounded-full shrink-0"
                                  style={{ background: COLORS[i % COLORS.length] }}
                                />
                                <span className="font-medium truncate">{c.category}</span>
                              </div>
                              <span className="muted font-mono whitespace-nowrap">
                                {money(c.amount, cur)}{' '}
                                <span className="font-bold text-[var(--fg)]">({pct(c.share)})</span>
                              </span>
                            </button>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                </section>

                {/* Top Merchants */}
                <section className="card p-4 sm:p-5 rounded-2xl border shadow-xs" style={{ borderColor: 'var(--border)' }}>
                  <div className="flex items-center justify-between pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
                    <div>
                      <h2 className="font-bold text-sm tracking-tight flex items-center gap-1.5">
                        <Store size={16} className="text-accent" />
                        <span>Top Merchants</span>
                      </h2>
                      <p className="text-xs muted">Click a bar to see transactions</p>
                    </div>
                  </div>

                  <div className="mt-3">
                    {data.by_merchant.top.length === 0 ? (
                      <Empty title="No merchant data found" />
                    ) : (
                      <div className="h-72 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={data.by_merchant.top} layout="vertical" margin={{ left: 0, right: 16 }}>
                            <XAxis type="number" stroke="var(--muted)" fontSize={11} tickFormatter={(v) => money(v, cur)} />
                            <YAxis type="category" dataKey="merchant" stroke="var(--muted)" fontSize={11} width={85} tickLine={false} />
                            <Tooltip
                              contentStyle={{
                                backgroundColor: 'var(--card)',
                                borderColor: 'var(--border)',
                                borderRadius: '0.75rem',
                                fontSize: '12px',
                              }}
                              formatter={(v) => money(Number(v), cur)}
                            />
                            <Bar
                              dataKey="amount"
                              fill="#0f766e"
                              radius={[0, 6, 6, 0]}
                              style={{ cursor: 'pointer' }}
                              onClick={(row) =>
                                drill({
                                  type: 'expense',
                                  merchant_exact: (row as unknown as { merchant_key: string }).merchant_key,
                                })
                              }
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                </section>
              </div>

              {/* Row 5: Income vs Expenses & Trend */}
              <div className="grid gap-4 lg:grid-cols-2">
                {/* Income vs Expenses */}
                <section className="card p-4 sm:p-5 rounded-2xl border shadow-xs" style={{ borderColor: 'var(--border)' }}>
                  <div className="pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
                    <h2 className="font-bold text-sm tracking-tight">Income vs Expenses</h2>
                    <p className="text-xs muted">Net balance over period</p>
                  </div>

                  <div className="h-60 w-full mt-3">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={data.income_vs_expenses.points}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" opacity={0.6} />
                        <XAxis dataKey="bucket" stroke="var(--muted)" fontSize={11} tickLine={false} />
                        <YAxis stroke="var(--muted)" fontSize={11} tickLine={false} tickFormatter={(v) => money(v, cur)} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: 'var(--card)',
                            borderColor: 'var(--border)',
                            borderRadius: '0.75rem',
                            fontSize: '12px',
                          }}
                          formatter={(v) => money(Number(v), cur)}
                        />
                        <Legend />
                        <Area type="monotone" dataKey="income" name="Income" stroke="#16a34a" fill="#16a34a" fillOpacity={0.2} />
                        <Area type="monotone" dataKey="expenses" name="Expenses" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </section>

                {/* Savings Rate & 6-month History */}
                <section className="card p-4 sm:p-5 rounded-2xl border shadow-xs" style={{ borderColor: 'var(--border)' }}>
                  <div className="pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
                    <h2 className="font-bold text-sm tracking-tight">Savings History</h2>
                    <p className="text-xs muted">Net positive savings trajectory</p>
                  </div>

                  <div className="h-60 w-full mt-3">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={data.monthly_trend}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" opacity={0.6} />
                        <XAxis dataKey="month" stroke="var(--muted)" fontSize={11} tickLine={false} />
                        <YAxis stroke="var(--muted)" fontSize={11} tickLine={false} tickFormatter={(v) => money(v, cur)} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: 'var(--card)',
                            borderColor: 'var(--border)',
                            borderRadius: '0.75rem',
                            fontSize: '12px',
                          }}
                          formatter={(v) => money(Number(v), cur)}
                        />
                        <Legend />
                        <Line type="monotone" dataKey="savings" name="Net Savings" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 3 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </section>
              </div>

              {/* Row 6: Payment Methods & Essential vs Discretionary */}
              <div className="grid gap-4 lg:grid-cols-2">
                {/* Payment Methods */}
                <section className="card p-4 sm:p-5 rounded-2xl border shadow-xs" style={{ borderColor: 'var(--border)' }}>
                  <div className="pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
                    <h2 className="font-bold text-sm tracking-tight flex items-center gap-1.5">
                      <CreditCard size={16} className="text-accent" />
                      <span>Payment Methods Breakdown</span>
                    </h2>
                  </div>

                  <div className="flex flex-col gap-3 mt-3">
                    {data.by_payment_method.map((p) => (
                      <button
                        key={p.payment_method}
                        className="w-full text-left flex flex-col gap-1 p-2 rounded-xl hover:bg-[var(--bg)] transition"
                        onClick={() => drill({ type: 'expense', payment_method: p.payment_method })}
                      >
                        <div className="flex justify-between text-xs">
                          <span className="font-semibold">{pmLabel(p.payment_method)}</span>
                          <span className="muted font-mono">
                            {money(p.amount, cur)} ({pct(p.share)})
                          </span>
                        </div>
                        <div className="h-2 rounded-full overflow-hidden bg-[var(--border)]">
                          <div
                            className="h-full rounded-full bg-accent"
                            style={{ width: `${Math.min(p.share, 100)}%` }}
                          />
                        </div>
                      </button>
                    ))}
                  </div>
                </section>

                {/* Essential vs Discretionary */}
                <section className="card p-4 sm:p-5 rounded-2xl border shadow-xs" style={{ borderColor: 'var(--border)' }}>
                  <div className="pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
                    <h2 className="font-bold text-sm tracking-tight flex items-center gap-1.5">
                      <Layers size={16} className="text-accent" />
                      <span>Needs vs Wants (Essential Split)</span>
                    </h2>
                  </div>

                  <div className="mt-3">
                    {data.essential_vs_discretionary.essential_share === null ? (
                      <Empty title="Not enough classified transactions" />
                    ) : (
                      <div className="flex flex-col gap-3">
                        <div className="flex h-3 rounded-full overflow-hidden">
                          <div
                            style={{
                              width: `${data.essential_vs_discretionary.essential_share}%`,
                              backgroundColor: '#0f766e',
                            }}
                            title={`Essential: ${pct(data.essential_vs_discretionary.essential_share)}`}
                          />
                          <div
                            className="flex-1"
                            style={{ backgroundColor: '#d97706' }}
                            title="Discretionary"
                          />
                        </div>

                        <div className="flex items-center justify-between text-xs pt-1">
                          <div className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 rounded-full bg-[#0f766e]" />
                            <span>
                              Essential: <strong>{money(data.essential_vs_discretionary.essential, cur)}</strong>
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 rounded-full bg-[#d97706]" />
                            <span>
                              Discretionary: <strong>{money(data.essential_vs_discretionary.discretionary, cur)}</strong>
                            </span>
                          </div>
                        </div>

                        {data.essential_vs_discretionary.note && (
                          <p className="text-[11px] muted leading-relaxed">
                            {data.essential_vs_discretionary.note}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </section>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
