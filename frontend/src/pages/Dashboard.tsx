import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../lib/api'
import { money, pct } from '../lib/format'
import WhatChanged, { type WhatChangedData } from './WhatChanged'

interface UpItem { kind: string; name: string; amount: number; due_date: string; days_until: number; group: string }

interface Dash {
  currency: string
  cards: { total_balance: number; month_income: number; month_expenses: number; savings: number; budget_remaining: number | null; net_worth: number }
  spending_by_category: { category: string; amount: number }[]
  monthly_trend: { month: string; income: number; expenses: number }[]
  budget_status: null | { total_limit: number; remaining: number; categories: { category: string; limit: number; used: number; remaining: number; percent_used: number | null }[] }
  upcoming_payments: {
    items: UpItem[]; groups: Record<'overdue' | 'today' | 'tomorrow' | 'this_week' | 'later', UpItem[]>
    totals: { overdue: number; next_7_days: number; next_30_days: number }
  }
  recurring_summary: { subscriptions_count: number; subscriptions_monthly: number; subscriptions_annual: number; bills_monthly: number; total_monthly: number; total_annual: number; pending_review: number }
  analytics_summary: { savings_rate: number | null; average_daily_spending: number; highest_category: { category: string; amount: number; share: number } | null
    month_over_month: { change: number; change_pct: number | null; current_label: string; previous_label: string } }
  what_changed: WhatChangedData
  goals: { id: number; name: string; target: number; current: number; remaining: number; percent: number | null; target_date: string | null
    status?: string; required_monthly?: number | null; on_track?: boolean | null }[]
  insights: string[]
  financial_health: { score: number | null; score_change: number | null; note: string | null; components: { key: string; label: string; points: number; max: number; reason: string; change_points: number | null }[] }
}

const COLORS = ['#0f766e', '#2563eb', '#b45309', '#7c3aed', '#be123c', '#4d7c0f', '#0e7490', '#a16207']

function Skeleton() {
  return <div className="grid gap-4 md:grid-cols-3" aria-busy="true" aria-label="Loading dashboard">
    {Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton h-24" />)}
  </div>
}

function Empty({ text }: { text: string }) {
  return <p className="muted text-sm py-6 text-center">{text}</p>
}

export default function Dashboard() {
  const [data, setData] = useState<Dash | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [safe, setSafe] = useState<{ safe_to_spend_daily: number; safe_to_spend_total: number; days_left_in_month: number } | null>(null)

  const load = () => {
    setError(null)
    api<Dash>('/dashboard').then(setData).catch((e) => setError(e.message))
    api<{ safe_to_spend_daily: number; safe_to_spend_total: number; days_left_in_month: number }>('/planning/safe-to-spend')
      .then(setSafe).catch(() => {})
  }
  useEffect(load, [])

  if (error) return <div className="card" role="alert">{error} <button className="btn ml-2" onClick={load}>Retry</button></div>
  if (!data) return <Skeleton />

  const c = data.cards, cur = data.currency
  const stat = (label: string, v: number | null, tone?: boolean, sub?: string) => (
    <div className="card" key={label}>
      <div className="muted text-sm">{label}</div>
      <div className="text-2xl font-bold" style={tone && v !== null ? { color: v < 0 ? 'var(--bad)' : 'var(--good)' } : {}}>{money(v, cur)}</div>
      {sub && <div className="muted text-xs mt-1">{sub}</div>}
    </div>
  )

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-bold">Dashboard</h1>
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        {stat('Total balance', c.total_balance)}
        {stat("This month's expenses", c.month_expenses)}
        {stat('Savings', c.savings, true)}
        {stat('Net worth', c.net_worth, true)}
        {safe && stat('Safe to Spend Daily', safe.safe_to_spend_daily, true, `${money(safe.safe_to_spend_total, cur)} left over ${safe.days_left_in_month} days`)}
        {stat('Budget remaining', c.budget_remaining, true)}
      </div>
      {c.budget_remaining === null && <p className="muted text-sm">No budget set for this month yet.</p>}

      {data.insights.length > 0 && (
        <section className="card" aria-label="Insights">
          <h2 className="font-semibold mb-2">Insights from your data</h2>
          <ul className="list-disc pl-5 text-sm flex flex-col gap-1">{data.insights.map((s) => <li key={s}>{s}</li>)}</ul>
        </section>
      )}

      <WhatChanged data={data.what_changed} currency={cur} />

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card" aria-label="Recurring payments">
          <div className="flex justify-between items-baseline"><h2 className="font-semibold mb-1">Recurring payments</h2>
            <span className="text-sm"><Link to="/subscriptions" className="underline">Subscriptions</Link> · <Link to="/bills" className="underline">Bills</Link></span></div>
          {data.recurring_summary.total_monthly === 0 ? <Empty text="No bills or confirmed subscriptions yet." /> : (
            <>
              <p className="text-2xl font-bold">{money(data.recurring_summary.total_monthly, cur)}<span className="muted text-sm font-normal">/month</span></p>
              <p className="muted text-sm">Subscriptions {money(data.recurring_summary.subscriptions_monthly, cur)} · Bills {money(data.recurring_summary.bills_monthly, cur)} · about {money(data.recurring_summary.total_annual, cur)}/year</p>
            </>
          )}
          {data.recurring_summary.pending_review > 0 && <p className="text-sm mt-1"><Link to="/subscriptions" className="underline">{data.recurring_summary.pending_review} detected payment(s) waiting for your review</Link></p>}
        </section>
        <section className="card" aria-label="Analytics summary">
          <div className="flex justify-between items-baseline"><h2 className="font-semibold mb-1">This month in numbers</h2><Link to="/analytics" className="text-sm underline">Analytics</Link></div>
          <ul className="text-sm flex flex-col gap-1">
            <li>Savings rate: <strong>{data.analytics_summary.savings_rate === null ? '— (no income yet)' : pct(data.analytics_summary.savings_rate)}</strong></li>
            <li>Average daily spending: <strong>{money(data.analytics_summary.average_daily_spending, cur)}</strong></li>
            <li>Top category: <strong>{data.analytics_summary.highest_category ? `${data.analytics_summary.highest_category.category} (${money(data.analytics_summary.highest_category.amount, cur)})` : '—'}</strong></li>
            <li className="muted">{data.analytics_summary.month_over_month.change === 0 ? 'Spending is level' : `Spending is ${money(Math.abs(data.analytics_summary.month_over_month.change), cur)} ${data.analytics_summary.month_over_month.change > 0 ? 'higher' : 'lower'}`} than {data.analytics_summary.month_over_month.previous_label}.</li>
          </ul>
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card">
          <h2 className="font-semibold mb-2">Spending by category</h2>
          {data.spending_by_category.length === 0 ? <Empty text="No expenses recorded this month." /> : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={data.spending_by_category} dataKey="amount" nameKey="category" innerRadius={55} outerRadius={90}>
                  {data.spending_by_category.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v) => money(Number(v), cur)} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          )}
        </section>

        <section className="card">
          <h2 className="font-semibold mb-2">Last 6 months</h2>
          {data.monthly_trend.every((m) => m.income === 0 && m.expenses === 0) ? <Empty text="No history yet." /> : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={data.monthly_trend}>
                <XAxis dataKey="month" stroke="var(--muted)" fontSize={12} />
                <YAxis stroke="var(--muted)" fontSize={12} tickFormatter={(v) => money(v, cur)} width={80} />
                <Tooltip formatter={(v) => money(Number(v), cur)} />
                <Legend />
                <Line type="monotone" dataKey="income" stroke="#15803d" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="expenses" stroke="#be123c" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card">
          <h2 className="font-semibold mb-2">Budget status</h2>
          {!data.budget_status || data.budget_status.categories.length === 0 ? <Empty text="No category budgets yet." /> : (
            <ul className="flex flex-col gap-3">
              {data.budget_status.categories.map((b) => (
                <li key={b.category}>
                  <div className="flex justify-between text-sm"><span>{b.category}</span>
                    <span className="muted">{money(b.used, cur)} / {money(b.limit, cur)} · {pct(b.percent_used)}</span></div>
                  <div className="h-2 rounded" style={{ background: 'var(--border)' }} role="progressbar" aria-label={`${b.category} budget used`}
                    aria-valuenow={Math.round(b.percent_used ?? 0)} aria-valuemin={0} aria-valuemax={100}>
                    <div className="h-2 rounded" style={{ width: `${Math.min(b.percent_used ?? 0, 100)}%`,
                      background: (b.percent_used ?? 0) >= 100 ? 'var(--bad)' : (b.percent_used ?? 0) >= 90 ? 'var(--warn)' : 'var(--accent)' }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <div className="flex justify-between items-baseline"><h2 className="font-semibold mb-2">Upcoming payments</h2>
            <Link to="/calendar" className="text-sm underline">Calendar</Link></div>
          {data.upcoming_payments.items.length === 0 ? <Empty text="Nothing due in the next 30 days." /> : (
            <div className="flex flex-col gap-2 text-sm">
              {([['overdue', 'Overdue'], ['today', 'Today'], ['tomorrow', 'Tomorrow'], ['this_week', 'This week'], ['later', 'Later']] as const).map(([k, l]) => {
                const rows = data.upcoming_payments.groups[k]
                if (!rows.length) return null
                return (
                  <div key={k}>
                    <h3 className="text-xs uppercase muted">{l}</h3>
                    <ul>{rows.slice(0, 4).map((p) => (
                      <li key={`${p.kind}-${p.name}-${p.due_date}`} className="flex justify-between py-0.5">
                        <span>{p.name} <span className="muted">· {p.due_date}</span></span>
                        <span style={k === 'overdue' ? { color: 'var(--bad)' } : {}}>{money(p.amount, cur)}</span>
                      </li>))}
                    </ul>
                    {rows.length > 4 && <Link to="/bills" className="muted text-xs underline">+{rows.length - 4} more</Link>}
                  </div>
                )
              })}
            </div>
          )}
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card">
          <h2 className="font-semibold mb-2 flex justify-between">Savings goals <Link to="/goals" className="text-sm font-normal underline">Manage</Link></h2>
          {data.goals.length === 0 ? <Empty text="No goals yet." /> : (
            <ul className="flex flex-col gap-3 text-sm">
              {data.goals.map((g) => (
                <li key={g.id}>
                  <div className="flex justify-between"><span>{g.name}</span><span className="muted">{pct(g.percent)}</span></div>
                  <div className="muted">{money(g.current, cur)} of {money(g.target, cur)} · {money(g.remaining, cur)} to go{g.target_date ? ` · by ${g.target_date}` : ''}</div>
                  {g.status === 'active' && g.required_monthly != null && (
                    <div className="muted text-xs">Needs {money(g.required_monthly, cur)}/month{g.on_track === false ? ' · behind pace' : g.on_track ? ' · on track' : ''}</div>
                  )}
                  {g.status === 'overdue' && <div className="text-xs" style={{ color: 'var(--warn)' }}>Past its target date</div>}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <h2 className="font-semibold mb-1">Financial health</h2>
          {data.financial_health.score === null ? <Empty text={data.financial_health.note ?? 'Not enough data yet.'} /> : (
            <>
              <div className="text-3xl font-bold">{data.financial_health.score}<span className="muted text-base">/100</span>
                {data.financial_health.score_change !== null && data.financial_health.score_change !== 0 &&
                  <span className="text-sm ml-2" style={{ color: data.financial_health.score_change > 0 ? 'var(--good)' : 'var(--bad)' }}>
                    {data.financial_health.score_change > 0 ? '+' : ''}{data.financial_health.score_change} vs last month</span>}
              </div>
              <ul className="flex flex-col gap-2 text-sm mt-2">
                {data.financial_health.components.map((k) => (
                  <li key={k.key}><strong>{k.label}</strong>: {k.points}/{k.max}
                    {k.change_points ? <span className="muted"> ({k.change_points > 0 ? '+' : ''}{k.change_points})</span> : null}
                    <div className="muted">{k.reason}</div></li>
                ))}
              </ul>
              <p className="muted text-xs mt-2">A score from your own numbers, not financial advice.</p>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
