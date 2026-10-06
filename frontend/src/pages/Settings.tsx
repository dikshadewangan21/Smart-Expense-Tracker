import { useState } from 'react'
import { useAuth } from '../lib/auth'
import { TIMEZONES } from '../lib/types'

export default function Settings() {
  const { user, updateProfile } = useAuth()
  const [name, setName] = useState(user?.name ?? '')
  const [tz, setTz] = useState(user?.timezone ?? 'Asia/Kolkata')
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const zones = TIMEZONES.includes(tz) ? TIMEZONES : [tz, ...TIMEZONES]

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true); setMsg(null)
    try { await updateProfile({ name, timezone: tz }); setMsg({ ok: true, text: 'Saved.' }) }
    catch (e2) { setMsg({ ok: false, text: e2 instanceof Error ? e2.message : 'Could not save.' }) }
    setBusy(false)
  }

  return (
    <div className="flex flex-col gap-4 max-w-lg">
      <h1 className="text-xl font-bold">Settings</h1>
      <form className="card flex flex-col gap-3" onSubmit={save}>
        <label className="text-sm">Email<input className="input" value={user?.email ?? ''} disabled /></label>
        <label className="text-sm">Name<input className="input" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} /></label>
        <label className="text-sm">Timezone
          <select className="input" value={tz} onChange={(e) => setTz(e.target.value)}>{zones.map((z) => <option key={z} value={z}>{z}</option>)}</select></label>
        <p className="muted text-xs">Decides what "today" means for due dates, overdue bills and "this month". Currency: {user?.currency}.</p>
        {msg && <p role={msg.ok ? 'status' : 'alert'} className="text-sm" style={{ color: msg.ok ? 'var(--good)' : 'var(--bad)' }}>{msg.text}</p>}
        <button className="btn self-start" disabled={busy}>Save</button>
      </form>
    </div>
  )
}
