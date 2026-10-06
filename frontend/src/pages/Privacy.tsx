import { Download, ShieldCheck, Trash2, History, AlertTriangle } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Empty, ErrorBox, Modal, Skeleton, ghost, useLoad } from '../components/ui'

interface AuditLog {
  id: number
  action: string
  detail: string | null
  created_at: string
}

export default function Privacy() {
  const { logout } = useAuth()
  const [deleteModal, setDeleteModal] = useState(false)
  const [password, setPassword] = useState('')
  const [delBusy, setDelBusy] = useState(false)
  const [delErr, setDelErr] = useState<string | null>(null)

  const logs = useLoad(() => api<AuditLog[]>('/privacy/audit-logs'), [])

  function downloadCsv() {
    window.open(`${import.meta.env.VITE_API_URL || '/api'}/privacy/export/csv`, '_blank')
  }

  function downloadJson() {
    window.open(`${import.meta.env.VITE_API_URL || '/api'}/privacy/export/json`, '_blank')
  }

  async function handleDeleteAccount(e: React.FormEvent) {
    e.preventDefault()
    if (!password) return
    setDelBusy(true)
    setDelErr(null)
    try {
      await api('/privacy/delete-account', {
        method: 'POST',
        body: JSON.stringify({ password }),
      })
      logout()
    } catch (e2) {
      setDelErr(e2 instanceof Error ? e2.message : 'Could not delete account.')
      setDelBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold flex items-center gap-2">
          <ShieldCheck size={22} /> Privacy &amp; Data Center
        </h1>
        <p className="muted text-xs">Export your data, inspect security audit logs, or manage data retention.</p>
      </div>

      {/* Export Section */}
      <section className="card flex flex-col gap-3">
        <h2 className="font-semibold text-base">Data Export &amp; Takeout</h2>
        <p className="muted text-sm">Download your complete financial records at any time. Your data belongs to you.</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-1">
          <div className="p-3 border rounded-lg flex flex-col justify-between gap-3" style={{ borderColor: 'var(--border)' }}>
            <div>
              <div className="font-medium text-sm">Transactions Spreadsheet (.CSV)</div>
              <div className="muted text-xs">Excel / Sheets compatible list of all transactions with dates, categories, and accounts.</div>
            </div>
            <button className="btn flex items-center justify-center gap-2" style={ghost} onClick={downloadCsv}>
              <Download size={16} /> Export CSV
            </button>
          </div>

          <div className="p-3 border rounded-lg flex flex-col justify-between gap-3" style={{ borderColor: 'var(--border)' }}>
            <div>
              <div className="font-medium text-sm">Full Data Takeout (.JSON)</div>
              <div className="muted text-xs">Complete export including profile, accounts, budgets, goals, debts, bills, and recurring patterns.</div>
            </div>
            <button className="btn flex items-center justify-center gap-2" style={ghost} onClick={downloadJson}>
              <Download size={16} /> Download JSON
            </button>
          </div>
        </div>
      </section>

      {/* Audit Logs Section */}
      <section className="card flex flex-col gap-3">
        <h2 className="font-semibold text-base flex items-center gap-2">
          <History size={18} /> Security &amp; Audit Logs
        </h2>
        <p className="muted text-xs">Record of significant account actions, logins, updates, and deletions.</p>

        {logs.error && <ErrorBox message={logs.error} onRetry={logs.reload} />}
        {!logs.data ? <Skeleton rows={3} /> : logs.data.length === 0 ? <Empty>No audit events recorded.</Empty> : (
          <div className="overflow-x-auto text-sm">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b muted text-xs" style={{ borderColor: 'var(--border)' }}>
                  <th className="py-2">Time</th>
                  <th>Action</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {logs.data.slice(0, 15).map((l) => (
                  <tr key={l.id} className="border-b" style={{ borderColor: 'var(--border)' }}>
                    <td className="py-2 text-xs muted whitespace-nowrap">{new Date(l.created_at).toLocaleString()}</td>
                    <td className="font-medium font-mono text-xs">{l.action}</td>
                    <td className="text-xs muted truncate max-w-xs">{l.detail || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Danger Zone */}
      <section className="card flex flex-col gap-3" style={{ borderColor: 'var(--bad)' }}>
        <h2 className="font-semibold text-base flex items-center gap-2" style={{ color: 'var(--bad)' }}>
          <AlertTriangle size={18} /> Danger Zone
        </h2>
        <p className="muted text-sm">Permanently delete your account and all associated transactions, accounts, and financial data.</p>
        <button className="btn self-start flex items-center gap-2 text-bad" style={{ background: 'transparent', borderColor: 'var(--bad)', color: 'var(--bad)' }} onClick={() => setDeleteModal(true)}>
          <Trash2 size={16} /> Delete Account &amp; Wipe Data
        </button>
      </section>

      {/* Delete Confirmation Modal */}
      {deleteModal && (
        <Modal title="Delete Account Permanently" onClose={() => setDeleteModal(false)}>
          <form onSubmit={handleDeleteAccount} className="flex flex-col gap-3">
            <p className="text-sm">
              This action cannot be undone. All your accounts, transactions, receipts, and settings will be permanently erased.
            </p>
            <label className="text-sm">
              Confirm your password
              <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoFocus />
            </label>
            {delErr && <ErrorBox message={delErr} />}
            <div className="flex justify-end gap-2 mt-2">
              <button type="button" className="btn" style={ghost} onClick={() => setDeleteModal(false)}>Cancel</button>
              <button type="submit" className="btn" style={{ background: 'var(--bad)', color: 'white' }} disabled={delBusy}>
                {delBusy ? 'Deleting...' : 'Permanently Delete Everything'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
