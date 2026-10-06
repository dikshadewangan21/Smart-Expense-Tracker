import { Bar, BarChart, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Area, AreaChart } from 'recharts'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money, pct } from '../lib/format'
import { pmLabel } from '../lib/types'
import { Empty, ErrorBox, Skeleton, Stat, ghost, useLoad } from '../components/ui'
import WhatChanged, { type WhatChangedData } from './WhatChanged'

const PERIODS = [
  ['this_month', 'This month'], ['last_month', 'Last month'], ['last_3_months', 'Last 3 months'],
  ['last_6_months', 'Last 6 months'], ['this_year', 'This year'], ['custom', 'Custom'],
] as const
const COLORS = ['#0f766e', '#2563eb', '#b45309', '#7c3aed', '#be123c', '#4d7c0f', '#0e7490', '#a16207', '#6b7280']

interface Cat { category_id: number | null; category: string; essential: boolean | null; amount: number; count: number; share: number }
interface Cmp { current: number; previous: number; change: number; change_pct: number | null; current_label: string; previous_label: string }
interface A {
  period: { kind: string; label: string; start: string; end: string; days: number; days_elapsed: number }
  previous_period: { label: string; start: string; end: string }
  totals: { income: number; expenses: number; net_savings: number; savings_rate: number | null; transaction_count: number; average_daily_spending: number }
  previous_totals: { income: number; expenses: number; net_savings: number; savings_rate: number | null }
  by_category: Cat[]
  by_merchant: { top: { merchant_key: string; merchant: string; amount: number; count: number; share: number }[]; other_total: number; other_count: number; no_merchant_total: number }
  by_payment_method: { payment_method: string; amount: number; count: number; share: number }[]
  income_vs_expenses: { granularity: string; points: { bucket: string; income: number; expenses: number; net: number }[] }
  monthly_trend: { month: string; income: number; expenses: number; savings: number; savings_rate: number | null }[]
  month_over_month: Cmp
  week_over_week: Cmp
  highest_category: Cat | null
  highest_spending_day: { date: string; amount: number } | null
  largest_transactions: { id: number; merchant: string | null; amount: number; date: string; category: string | null }[]
  essential_vs_discretionary: { essential: number; discretionary: number; unclassified: number; essential_share: number | null; coverage: number; note: string | null }
  budget_performance: { month: string; limit: number; spent: number; percent_used: number | null; partial: boolean }[]
  excluded_other_currency: number
}

function CmpCard({ title, c, cur }: { title: string; c: Cmp; cur: string }) {
  const up = c.change > 0
  return (
    <div className="card">
      <div className="muted text-sm">{title}</div>
      <div className="text-xl font-bold">{money(c.current, cur)}</div>
      <div className="text-sm" style={{ color: c.change === 0 ? undefined : up ? 'var(--bad)' : 'var(--good)' }}>
        {c.change === 0 ? 'No change' : `${up ? '+' : '−'}${money(Math.abs(c.change), cur)}`}
        {c.change_pct !== null && c.change !== 0 && ` (${c.change_pct > 0 ? '+' : ''}${c.change_pct}%)`}
      </div>
      <div className="muted text-xs">{c.current_label} vs {c.previous_label}: {money(c.previous, cur)}</div>
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

  const a = useLoad<A | null>(() => (customReady ? api<A>(`/analytics?${qs}`) : Promise.resolve(null)), [qs, customReady])
  const w = useLoad<WhatChangedData | null>(() => (customReady ? api<WhatChangedData>(`/what-changed?${qs}`) : Promise.resolve(null)), [qs, customReady])

  const set = (k: string, v: string) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); setParams(n, { replace: true }) }
  const drill = (extra: Record<string, string>) => {
    if (!a.data) return
    nav(`/transactions?${new URLSearchParams({ date_from: a.data.period.start, date_to: a.data.period.end, ...extra })}`)
  }
  const drillCat = (c: Cat) => drill({ type: 'expense', ...(c.category_id === null ? { uncategorized: 'true' } : { category_id: String(c.category_id) }) })

  const d = a.data
  const tickMoney = (v: number) => money(v, cur)

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-bold">Analytics</h1>

      <div className="card flex flex-wrap gap-2 items-center" role="group" aria-label="Period">
        {PERIODS.map(([k, l]) => (
          <button key={k} className="btn" style={period === k ? {} : ghost} aria-pressed={period === k}
            onClick={() => set('period', k === 'this_month' ? '' : k)}>{l}</button>
        ))}
        {period === 'custom' && (
          <div className="flex gap-2 items-center">
            <input className="input" type="date" aria-label="From date" value={from} max={to || undefined} onChange={(e) => set('date_from', e.target.value)} />
            <span className="muted">to</span>
            <input className="input" type="date" aria-label="To date" value={to} min={from || undefined} onChange={(e) => set('date_to', e.target.value)} />
          </div>
        )}
      </div>

      {!customReady && <div className="card muted text-sm">{from && to && from > to ? 'The start date must be on or before the end date.' : 'Pick a start and end date.'}</div>}
      {a.error && <ErrorBox message={a.error} onRetry={a.reload} />}
      {customReady && !d && !a.error && <Skeleton rows={6} label="Loading analytics" />}

      {d && (
        <>
          <p className="muted text-sm">{d.period.label}: {d.period.start} to {d.period.end}. Compared with {d.previous_period.label} ({d.previous_period.start} to {d.previous_period.end}).</p>
          {d.excluded_other_currency > 0 && (
            <p className="card text-sm" role="note">{d.excluded_other_currency} transaction(s) in another currency are not included in these totals.</p>
          )}

          {d.totals.transaction_count === 0 ? (
            <div className="card"><Empty>No transactions in this period. Add some, or pick a different period.</Empty></div>
          ) : (
            <>
              <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
                <Stat label="Income" value={money(d.totals.income, cur)} />
                <Stat label="Expenses" value={money(d.totals.expenses, cur)} />
                <Stat label="Net savings" value={money(d.totals.net_savings, cur)} tone={d.totals.net_savings < 0 ? 'bad' : 'good'} />
                <Stat label="Savings rate" value={d.totals.savings_rate === null ? '—' : pct(d.totals.savings_rate)}
                  sub={d.totals.savings_rate === null ? 'No income in this period' : undefined} />
                <Stat label="Avg daily spending" value={money(d.totals.average_daily_spending, cur)} sub={`over ${d.period.days_elapsed} day(s) so far`} />
                <Stat label="Highest category" value={d.highest_category ? d.highest_category.category : '—'}
                  sub={d.highest_category && `${money(d.highest_category.amount, cur)} · ${pct(d.highest_category.share)}`} />
                <Stat label="Highest spending day" value={d.highest_spending_day ? d.highest_spending_day.date : '—'}
                  sub={d.highest_spending_day && money(d.highest_spending_day.amount, cur)} />
                <Stat label="Transactions" value={String(d.totals.transaction_count)} />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <CmpCard title="Month over month" c={d.month_over_month} cur={cur} />
                <CmpCard title="Week over week" c={d.week_over_week} cur={cur} />
              </div>

              {w.data && <WhatChanged data={w.data} currency={cur} />}
              {w.error && <ErrorBox message={w.error} onRetry={w.reload} />}

              <div className="grid gap-4 lg:grid-cols-2">
                <section className="card">
                  <h2 className="font-semibold">Spending by category</h2>
                  <p className="muted text-xs">Click a slice or a row to see its transactions.</p>
                  {d.by_category.length === 0 ? <Empty>No expenses in this period.</Empty> : (
                    <>
                      <ResponsiveContainer width="100%" height={240}>
                        <PieChart>
                          <Pie data={d.by_category} dataKey="amount" nameKey="category" innerRadius={50} outerRadius={90} onClick={(_, i) => drillCat(d.by_category[i])} style={{ cursor: 'pointer' }}>
                            {d.by_category.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                          </Pie>
                          <Tooltip formatter={(v) => money(Number(v), cur)} />
                        </PieChart>
                      </ResponsiveContainer>
                      <ul className="text-sm">
                        {d.by_category.map((c, i) => (
                          <li key={c.category + i}>
                            <button className="w-full flex justify-between gap-2 py-1 hover:underline text-left" onClick={() => drillCat(c)}>
                              <span><span className="inline-block w-3 h-3 rounded-sm mr-2" style={{ background: COLORS[i % COLORS.length] }} aria-hidden />{c.category}</span>
                              <span className="muted whitespace-nowrap">{money(c.amount, cur)} · {pct(c.share)}</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </section>

                <section className="card">
                  <h2 className="font-semibold">Top merchants</h2>
                  <p className="muted text-xs">Click a bar to see its transactions.</p>
                  {d.by_merchant.top.length === 0 ? <Empty>No merchant data in this period.</Empty> : (
                    <ResponsiveContainer width="100%" height={Math.max(220, d.by_merchant.top.length * 34)}>
                      <BarChart data={d.by_merchant.top} layout="vertical" margin={{ left: 8, right: 16 }}>
                        <XAxis type="number" stroke="var(--muted)" fontSize={12} tickFormatter={tickMoney} />
                        <YAxis type="category" dataKey="merchant" stroke="var(--muted)" fontSize={12} width={90} />
                        <Tooltip formatter={(v) => money(Number(v), cur)} />
                        <Bar dataKey="amount" fill="#0f766e" radius={4} style={{ cursor: 'pointer' }}
                          onClick={(row) => drill({ type: 'expense', merchant_exact: (row as unknown as { merchant_key: string }).merchant_key })} />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                  {d.by_merchant.other_count > 0 && <p className="muted text-xs">Plus {d.by_merchant.other_count} smaller merchant(s): {money(d.by_merchant.other_total, cur)}.</p>}
                  {d.by_merchant.no_merchant_total > 0 && <p className="muted text-xs">{money(d.by_merchant.no_merchant_total, cur)} has no merchant recorded.</p>}
                </section>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <section className="card">
                  <h2 className="font-semibold">Income vs expenses</h2>
                  <p className="muted text-xs mb-2">By {d.income_vs_expenses.granularity}.</p>
                  <ResponsiveContainer width="100%" height={240}>
                    <AreaChart data={d.income_vs_expenses.points}>
                      <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                      <XAxis dataKey="bucket" stroke="var(--muted)" fontSize={11} minTickGap={24} />
                      <YAxis stroke="var(--muted)" fontSize={11} tickFormatter={tickMoney} width={80} />
                      <Tooltip formatter={(v) => money(Number(v), cur)} />
                      <Legend />
                      <Area type="monotone" dataKey="income" stroke="#15803d" fill="#15803d" fillOpacity={0.15} />
                      <Area type="monotone" dataKey="expenses" stroke="#be123c" fill="#be123c" fillOpacity={0.15} />
                    </AreaChart>
                  </ResponsiveContainer>
                </section>

                <section className="card">
                  <h2 className="font-semibold">Savings, last 6 months</h2>
                  <p className="muted text-xs mb-2">Full calendar months ending with the period's last month.</p>
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={d.monthly_trend}>
                      <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                      <XAxis dataKey="month" stroke="var(--muted)" fontSize={11} />
                      <YAxis stroke="var(--muted)" fontSize={11} tickFormatter={tickMoney} width={80} />
                      <Tooltip formatter={(v) => money(Number(v), cur)} />
                      <Legend />
                      <Line dataKey="income" stroke="#15803d" strokeWidth={2} dot={false} />
                      <Line dataKey="expenses" stroke="#be123c" strokeWidth={2} dot={false} />
                      <Line dataKey="savings" stroke="#2563eb" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </section>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <section className="card">
                  <h2 className="font-semibold">Payment methods</h2>
                  <p className="muted text-xs">Click a row to see its transactions.</p>
                  {d.by_payment_method.length === 0 ? <Empty>No expenses in this period.</Empty> : (
                    <ul className="text-sm mt-1">
                      {d.by_payment_method.map((p) => (
                        <li key={p.payment_method}>
                          <button className="w-full text-left py-1" onClick={() => drill({ type: 'expense', payment_method: p.payment_method })}>
                            <div className="flex justify-between hover:underline"><span>{pmLabel(p.payment_method)}</span>
                              <span className="muted">{money(p.amount, cur)} · {pct(p.share)}</span></div>
                            <div className="h-2 rounded" style={{ background: 'var(--border)' }}>
                              <div className="h-2 rounded" style={{ width: `${Math.min(p.share, 100)}%`, background: 'var(--accent)' }} /></div>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>

                <section className="card">
                  <h2 className="font-semibold">Essential vs discretionary</h2>
                  {d.essential_vs_discretionary.essential_share === null ? <Empty>{d.essential_vs_discretionary.note ?? 'Nothing to split yet.'}</Empty> : (
                    <>
                      <div className="flex h-4 rounded overflow-hidden mt-2" role="img"
                        aria-label={`Essential ${pct(d.essential_vs_discretionary.essential_share)}`}>
                        <div style={{ width: `${d.essential_vs_discretionary.essential_share}%`, background: '#0f766e' }} />
                        <div style={{ flex: 1, background: '#b45309' }} />
                      </div>
                      <ul className="text-sm mt-2">
                        <li className="flex justify-between"><span>Essential</span><span>{money(d.essential_vs_discretionary.essential, cur)}</span></li>
                        <li className="flex justify-between"><span>Discretionary</span><span>{money(d.essential_vs_discretionary.discretionary, cur)}</span></li>
                        {d.essential_vs_discretionary.unclassified > 0 && <li className="flex justify-between muted"><span>Uncategorized</span><span>{money(d.essential_vs_discretionary.unclassified, cur)}</span></li>}
                      </ul>
                      {d.essential_vs_discretionary.note && <p className="muted text-xs mt-1">{d.essential_vs_discretionary.note}</p>}
                    </>
                  )}
                </section>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <section className="card">
                  <h2 className="font-semibold mb-1">Largest transactions</h2>
                  {d.largest_transactions.length === 0 ? <Empty>No expenses in this period.</Empty> : (
                    <ul className="text-sm">
                      {d.largest_transactions.map((t) => (
                        <li key={t.id} className="flex justify-between gap-2 py-1">
                          <span>{t.merchant ?? 'No merchant'} <span className="muted">· {t.category ?? 'Uncategorized'} · {t.date}</span></span>
                          <span className="whitespace-nowrap">{money(t.amount, cur)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
                <section className="card">
                  <h2 className="font-semibold mb-1">Budget performance</h2>
                  {d.budget_performance.length === 0 ? <Empty>No budget covers this period.</Empty> : (
                    <ul className="text-sm">
                      {d.budget_performance.map((b) => (
                        <li key={b.month} className="py-1">
                          <div className="flex justify-between"><span>{b.month}{b.partial && <span className="muted"> (so far)</span>}</span>
                            <span className="muted">{money(b.spent, cur)} / {money(b.limit, cur)} · {pct(b.percent_used)}</span></div>
                          <div className="h-2 rounded" style={{ background: 'var(--border)' }}>
                            <div className="h-2 rounded" style={{ width: `${Math.min(b.percent_used ?? 0, 100)}%`, background: (b.percent_used ?? 0) >= 100 ? 'var(--bad)' : 'var(--accent)' }} /></div>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
