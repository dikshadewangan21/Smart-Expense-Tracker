import { ChevronLeft, ChevronRight, TrendingUp, Calendar } from 'lucide-react'
import { useState } from 'react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money } from '../lib/format'
import { Empty, ErrorBox, Skeleton, Stat, ghost, useLoad } from '../components/ui'

interface Ev { kind: 'bill' | 'recurring' | 'income'; name: string; amount: number; source: string; ref_id: number; status: string; large: boolean }
interface Day { date: string; is_today: boolean; events: Ev[]; income_total: number; outflow_total: number }
interface Cal {
  month: string; today: string; days: Day[]
  summary: { income_received: number; income_expected: number; paid: number; scheduled: number; overdue: number; estimated_net: number; large_count: number }
  large_threshold: number | null
}

interface TimelinePoint {
  date: string
  label: string
  projected_balance: number
  expected_income: number
  bills_due: number
  discretionary_spend: number
}

interface TimelineData {
  starting_balance: number
  avg_daily_spend: number
  days_ahead: number
  currency: string
  points: TimelinePoint[]
}

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const STATUS_COLOR: Record<string, string> = { overdue: 'var(--bad)', due_today: 'var(--warn)', received: 'var(--good)', paid: 'var(--muted)' }

function shift(month: string, by: number) {
  const [y, m] = month.split('-').map(Number)
  const d = new Date(y, m - 1 + by, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function Chip({ e, cur }: { e: Ev; cur: string }) {
  const sign = e.kind === 'income' ? '+' : ''
  return (
    <div className="text-xs truncate rounded px-1 py-0.5" style={{ background: 'var(--bg)', color: STATUS_COLOR[e.status], border: e.large ? '1px solid var(--warn)' : '1px solid transparent' }}
      title={`${e.name} · ${money(e.amount, cur)} · ${e.status.replace('_', ' ')}${e.large ? ' · large payment' : ''}`}>
      {e.kind === 'income' ? '↓' : '↑'} {e.name} {sign}{money(e.amount, cur)}
    </div>
  )
}

export default function CalendarPage() {
  const { user } = useAuth()
  const cur = user?.currency ?? 'INR'
  const [viewMode, setViewMode] = useState<'calendar' | 'timeline'>('calendar')
  const [month, setMonth] = useState<string | null>(null)
  const { data, error, reload } = useLoad(() => api<Cal>(`/calendar${month ? `?month=${month}` : ''}`), [month])
  const timeline = useLoad(() => api<TimelineData>('/planning/timeline?days=60'), [])
  const [sel, setSel] = useState<string | null>(null)

  const shown = data?.month ?? month ?? ''
  const first = data ? (new Date(data.days[0].date + 'T00:00:00').getDay() + 6) % 7 : 0
  const selected = data?.days.find((d) => d.date === sel)
  const withEvents = data?.days.filter((d) => d.events.length > 0) ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold">Money Timeline &amp; Calendar</h1>
        <div className="flex items-center gap-2">
          <div className="flex gap-1" role="group">
            <button className="btn text-xs flex items-center gap-1" style={viewMode === 'calendar' ? {} : ghost} onClick={() => setViewMode('calendar')}>
              <Calendar size={14} /> Month Calendar
            </button>
            <button className="btn text-xs flex items-center gap-1" style={viewMode === 'timeline' ? {} : ghost} onClick={() => setViewMode('timeline')}>
              <TrendingUp size={14} /> 60-Day Cashflow Curve
            </button>
          </div>
          {viewMode === 'calendar' && (
            <div className="flex items-center gap-1 ml-2">
              <button className="btn p-1.5" style={ghost} aria-label="Previous month" disabled={!shown} onClick={() => { setSel(null); setMonth(shift(shown, -1)) }}><ChevronLeft size={16} /></button>
              <span className="font-medium text-sm w-20 text-center">{shown}</span>
              <button className="btn p-1.5" style={ghost} aria-label="Next month" disabled={!shown} onClick={() => { setSel(null); setMonth(shift(shown, 1)) }}><ChevronRight size={16} /></button>
            </div>
          )}
        </div>
      </div>

      {viewMode === 'timeline' && (
        <section className="card flex flex-col gap-3">
          <div className="flex justify-between items-baseline">
            <div>
              <h2 className="font-semibold">Projected Cash Balance (Next 60 Days)</h2>
              <p className="muted text-xs">Simulates balance trajectory based on scheduled salary, bills, and everyday spending habits.</p>
            </div>
            {timeline.data && (
              <span className="text-xs muted">Daily burn estimate: {money(timeline.data.avg_daily_spend, cur)}/day</span>
            )}
          </div>

          {timeline.error && <ErrorBox message={timeline.error} onRetry={timeline.reload} />}
          {!timeline.data ? <Skeleton rows={5} /> : (
            <div style={{ width: '100%', height: 280 }}>
              <ResponsiveContainer>
                <AreaChart data={timeline.data.points} margin={{ left: 0, right: 8, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={6} />
                  <YAxis tick={{ fontSize: 11 }} width={60} tickFormatter={(v: number) => money(v, cur)} />
                  <Tooltip formatter={(v) => money(Number(v), cur)} />
                  <Area type="monotone" dataKey="projected_balance" name="Projected Balance" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.15} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      )}

      {viewMode === 'calendar' && (
        <>
          {error && <ErrorBox message={error} onRetry={reload} />}
          {!data && !error && <Skeleton rows={4} label="Loading calendar" />}

          {data && (
            <>
              <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
                <Stat label="Income received" value={money(data.summary.income_received, cur)} sub={data.summary.income_expected > 0 ? `${money(data.summary.income_expected, cur)} more expected` : undefined} />
                <Stat label="Paid so far" value={money(data.summary.paid, cur)} />
                <Stat label="Still to pay" value={money(data.summary.scheduled + data.summary.overdue, cur)} sub={data.summary.overdue > 0 ? `${money(data.summary.overdue, cur)} overdue` : undefined} tone={data.summary.overdue > 0 ? 'bad' : undefined} />
                <Stat label="Estimated net" value={money(data.summary.estimated_net, cur)} sub="Income minus paid and scheduled" tone={data.summary.estimated_net < 0 ? 'bad' : undefined} />
              </div>
              {data.summary.large_count > 0 && data.large_threshold !== null &&
                <p className="card text-sm" role="note">{data.summary.large_count} unpaid payment(s) this month are large: each is {money(data.large_threshold, cur)} or more, a quarter of your average monthly income.</p>}

              {withEvents.length === 0 ? <div className="card"><Empty>Nothing scheduled or recorded this month.</Empty></div> : (
                <>
                  <div className="hidden md:grid grid-cols-7 gap-1" role="grid" aria-label={`Calendar ${data.month}`}>
                    {WEEKDAYS.map((w) => <div key={w} className="muted text-xs text-center">{w}</div>)}
                    {Array.from({ length: first }).map((_, i) => <div key={`b${i}`} />)}
                    {data.days.map((d) => (
                      <button key={d.date} onClick={() => setSel(d.date === sel ? null : d.date)} aria-label={`${d.date}, ${d.events.length} event(s)`}
                        className="card p-1 min-h-24 text-left flex flex-col gap-0.5 items-stretch"
                        style={{ padding: '0.25rem', outline: d.is_today ? '2px solid var(--accent)' : d.date === sel ? '2px solid var(--muted)' : 'none' }}>
                        <span className="text-xs font-semibold">{Number(d.date.slice(8))}</span>
                        {d.events.slice(0, 3).map((e, i) => <Chip key={i} e={e} cur={cur} />)}
                        {d.events.length > 3 && <span className="muted text-xs">+{d.events.length - 3} more</span>}
                      </button>
                    ))}
                  </div>
                  {selected && (
                    <section className="card hidden md:block" aria-label={`Events on ${selected.date}`}>
                      <h2 className="font-semibold mb-1">{selected.date}</h2>
                      {selected.events.length === 0 ? <p className="muted text-sm">Nothing on this day.</p> : <ul className="text-sm">{selected.events.map((e, i) => (
                        <li key={i} className="flex justify-between py-0.5"><span>{e.name} <span className="muted">· {e.kind} · {e.status.replace('_', ' ')}{e.large ? ' · large' : ''}</span></span><span>{money(e.amount, cur)}</span></li>))}</ul>}
                    </section>
                  )}
                  <ul className="md:hidden flex flex-col gap-2" aria-label="Events this month">
                    {withEvents.map((d) => (
                      <li key={d.date} className="card" style={d.is_today ? { outline: '2px solid var(--accent)' } : {}}>
                        <div className="font-semibold text-sm">{d.date}{d.is_today && ' · today'}</div>
                        <ul className="text-sm">{d.events.map((e, i) => (
                          <li key={i} className="flex justify-between py-0.5" style={{ color: STATUS_COLOR[e.status] }}><span>{e.name}<span className="muted"> · {e.status.replace('_', ' ')}</span></span><span>{e.kind === 'income' ? '+' : ''}{money(e.amount, cur)}</span></li>))}</ul>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
