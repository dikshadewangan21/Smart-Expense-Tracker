import { Users, Plus, UserPlus, ArrowRight, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money } from '../lib/format'
import { Empty, ErrorBox, Modal, Skeleton, ghost, useLoad } from '../components/ui'

interface Member {
  user_id: number
  name: string
  email: string
  status: string
}

interface Expense {
  id: number
  description: string
  amount: number
  date: string
  paid_by: number
  paid_by_name: string
  splits: Record<string, number>
  settled: boolean
}

interface Settlement {
  from_user_id: number
  from_name: string
  to_user_id: number
  to_name: string
  amount: number
}

interface GroupDetail {
  id: number
  name: string
  kind: string
  owner_id: number
  members: Member[]
  expenses: Expense[]
  balances: { user_id: number; name: string; net_balance: number }[]
  settlements: Settlement[]
}

export default function SharedFinances() {
  const { user } = useAuth()
  const cur = user?.currency ?? 'INR'

  const [activeGroupId, setActiveGroupId] = useState<number | null>(null)
  const [createGroupModal, setCreateGroupModal] = useState(false)
  const [newGroupName, setNewGroupName] = useState('')
  const [newGroupKind, setNewGroupKind] = useState('friends')

  const [addMemberModal, setAddMemberModal] = useState(false)
  const [memberEmail, setMemberEmail] = useState('')

  const [addExpenseModal, setAddExpenseModal] = useState(false)
  const [expDesc, setExpDesc] = useState('')
  const [expAmount, setExpAmount] = useState('')
  const [expDate, setExpDate] = useState(new Date().toISOString().split('T')[0])
  const [expPayer, setExpPayer] = useState<string>('')

  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const groups = useLoad(() => api<GroupDetail[]>('/shared/groups'), [])
  const groupDetail = useLoad<GroupDetail | null>(
    () => (activeGroupId ? api<GroupDetail>(`/shared/groups/${activeGroupId}`) : Promise.resolve(null)),
    [activeGroupId]
  )

  const activeGroup = groupDetail.data || (groups.data?.find((g) => g.id === activeGroupId) ?? groups.data?.[0])

  async function handleCreateGroup(e: React.FormEvent) {
    e.preventDefault()
    if (!newGroupName.trim()) return
    setBusy(true)
    setErr(null)
    try {
      const res = await api<GroupDetail>('/shared/groups', {
        method: 'POST',
        body: JSON.stringify({ name: newGroupName.trim(), kind: newGroupKind }),
      })
      setCreateGroupModal(false)
      setNewGroupName('')
      setActiveGroupId(res.id)
      groups.reload()
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Could not create group.')
    } finally {
      setBusy(false)
    }
  }

  async function handleAddMember(e: React.FormEvent) {
    e.preventDefault()
    if (!activeGroup || !memberEmail.trim()) return
    setBusy(true)
    setErr(null)
    try {
      await api(`/shared/groups/${activeGroup.id}/members`, {
        method: 'POST',
        body: JSON.stringify({ email: memberEmail.trim() }),
      })
      setAddMemberModal(false)
      setMemberEmail('')
      groupDetail.reload()
      groups.reload()
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Could not add member.')
    } finally {
      setBusy(false)
    }
  }

  async function handleAddExpense(e: React.FormEvent) {
    e.preventDefault()
    if (!activeGroup || !expDesc.trim() || !(Number(expAmount) > 0)) return
    setBusy(true)
    setErr(null)
    try {
      await api(`/shared/groups/${activeGroup.id}/expenses`, {
        method: 'POST',
        body: JSON.stringify({
          description: expDesc.trim(),
          amount: expAmount,
          date: expDate,
          paid_by: expPayer ? Number(expPayer) : user?.id,
          split_type: 'equal',
        }),
      })
      setAddExpenseModal(false)
      setExpDesc('')
      setExpAmount('')
      groupDetail.reload()
      groups.reload()
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Could not add shared expense.')
    } finally {
      setBusy(false)
    }
  }

  async function deleteExpense(expId: number) {
    if (!activeGroup) return
    try {
      await api(`/shared/groups/${activeGroup.id}/expenses/${expId}`, { method: 'DELETE' })
      groupDetail.reload()
      groups.reload()
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Could not delete expense.')
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Users size={22} /> Shared Finances &amp; Split Expenses
          </h1>
          <p className="muted text-xs">Split bills with roommates, friends, or family. Clear debts with simplified settlements.</p>
        </div>
        <button className="btn flex items-center gap-1" onClick={() => setCreateGroupModal(true)}>
          <Plus size={16} /> New Group
        </button>
      </div>

      {groups.error && <ErrorBox message={groups.error} onRetry={groups.reload} />}
      {!groups.data ? <Skeleton rows={4} /> : groups.data.length === 0 ? (
        <div className="card">
          <Empty>No shared groups yet. Create one for your apartment rent, trip, or dinner group!</Empty>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Groups list */}
          <div className="card flex flex-col gap-2 p-3">
            <div className="font-semibold text-xs uppercase muted mb-1">Your Groups</div>
            <ul className="flex flex-col gap-1">
              {groups.data.map((g) => {
                const active = (activeGroup?.id ?? groups.data?.[0]?.id) === g.id
                return (
                  <li key={g.id}>
                    <button
                      className={`w-full text-left p-2 rounded text-sm flex justify-between items-center ${
                        active ? 'font-semibold bg-card border' : 'muted hover:bg-card/50'
                      }`}
                      style={active ? { borderColor: 'var(--border)' } : {}}
                      onClick={() => setActiveGroupId(g.id)}
                    >
                      <span>{g.name}</span>
                      <span className="text-xs muted">{g.members.length} members</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>

          {/* Group details */}
          {activeGroup && (
            <div className="md:col-span-3 flex flex-col gap-4">
              <div className="card flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold">{activeGroup.name}</h2>
                  <div className="muted text-xs">
                    {activeGroup.members.map((m) => m.name).join(', ')}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="btn text-xs flex items-center gap-1" style={ghost} onClick={() => setAddMemberModal(true)}>
                    <UserPlus size={14} /> Add Member
                  </button>
                  <button className="btn text-xs flex items-center gap-1" onClick={() => { setExpPayer(String(user?.id || '')); setAddExpenseModal(true) }}>
                    <Plus size={14} /> Add Expense
                  </button>
                </div>
              </div>

              {/* Net balances & settlements */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <section className="card">
                  <h3 className="font-semibold text-sm mb-2">Member Balances</h3>
                  <ul className="text-sm divide-y" style={{ borderColor: 'var(--border)' }}>
                    {activeGroup.balances.map((b) => (
                      <li key={b.user_id} className="py-2 flex justify-between items-center">
                        <span>{b.name}</span>
                        <span
                          className="font-medium"
                          style={{
                            color: b.net_balance > 0 ? 'var(--good)' : b.net_balance < 0 ? 'var(--bad)' : 'var(--muted)',
                          }}
                        >
                          {b.net_balance > 0 ? `+${money(b.net_balance, cur)}` : b.net_balance < 0 ? `−${money(Math.abs(b.net_balance), cur)}` : 'Settled'}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>

                <section className="card">
                  <h3 className="font-semibold text-sm mb-2">Suggested Settlement Steps</h3>
                  {activeGroup.settlements.length === 0 ? (
                    <p className="muted text-sm">Everyone is all squared up! No debts to settle.</p>
                  ) : (
                    <ul className="text-sm flex flex-col gap-2">
                      {activeGroup.settlements.map((s, idx) => (
                        <li key={idx} className="p-2 border rounded flex items-center justify-between text-xs" style={{ borderColor: 'var(--border)' }}>
                          <span className="font-medium">{s.from_name}</span>
                          <span className="muted flex items-center gap-1">
                            pays {money(s.amount, cur)} <ArrowRight size={12} />
                          </span>
                          <span className="font-medium">{s.to_name}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>

              {/* Expenses table */}
              <section className="card flex flex-col gap-3">
                <h3 className="font-semibold text-sm">Shared Expenses</h3>
                {activeGroup.expenses.length === 0 ? (
                  <Empty>No expenses added to this group yet.</Empty>
                ) : (
                  <ul className="divide-y text-sm" style={{ borderColor: 'var(--border)' }}>
                    {activeGroup.expenses.map((exp) => (
                      <li key={exp.id} className="py-2 flex justify-between items-center">
                        <div>
                          <div className="font-medium">{exp.description}</div>
                          <div className="muted text-xs">
                            Paid by <span className="font-semibold">{exp.paid_by_name}</span> on {exp.date} · split equally
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-semibold">{money(exp.amount, cur)}</span>
                          <button className="p-1 muted hover:text-bad" onClick={() => deleteExpense(exp.id)} aria-label="Delete expense">
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          )}
        </div>
      )}

      {/* Create Group Modal */}
      {createGroupModal && (
        <Modal title="Create New Group" onClose={() => setCreateGroupModal(false)}>
          <form onSubmit={handleCreateGroup} className="flex flex-col gap-3">
            <label className="text-sm">
              Group Name
              <input className="input" value={newGroupName} onChange={(e) => setNewGroupName(e.target.value)} placeholder="e.g. Flat 402 or Trip to Manali" required />
            </label>
            <label className="text-sm">
              Group Type
              <select className="input" value={newGroupKind} onChange={(e) => setNewGroupKind(e.target.value)}>
                <option value="friends">Friends</option>
                <option value="roommates">Roommates / Apartment</option>
                <option value="trip">Trip / Vacation</option>
                <option value="couple">Couple</option>
              </select>
            </label>
            {err && <ErrorBox message={err} />}
            <div className="flex justify-end gap-2 mt-2">
              <button type="button" className="btn" style={ghost} onClick={() => setCreateGroupModal(false)}>Cancel</button>
              <button type="submit" className="btn" disabled={busy}>Create Group</button>
            </div>
          </form>
        </Modal>
      )}

      {/* Add Member Modal */}
      {addMemberModal && (
        <Modal title="Add Member by Email" onClose={() => setAddMemberModal(false)}>
          <form onSubmit={handleAddMember} className="flex flex-col gap-3">
            <label className="text-sm">
              Registered Email
              <input className="input" type="email" value={memberEmail} onChange={(e) => setMemberEmail(e.target.value)} placeholder="friend@example.com" required />
            </label>
            {err && <ErrorBox message={err} />}
            <div className="flex justify-end gap-2 mt-2">
              <button type="button" className="btn" style={ghost} onClick={() => setAddMemberModal(false)}>Cancel</button>
              <button type="submit" className="btn" disabled={busy}>Add Member</button>
            </div>
          </form>
        </Modal>
      )}

      {/* Add Expense Modal */}
      {addExpenseModal && activeGroup && (
        <Modal title="Add Shared Expense" onClose={() => setAddExpenseModal(false)}>
          <form onSubmit={handleAddExpense} className="flex flex-col gap-3">
            <label className="text-sm">
              Description
              <input className="input" value={expDesc} onChange={(e) => setExpDesc(e.target.value)} placeholder="e.g. Grocery run or Dinner" required />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm">
                Total Amount ({cur})
                <input className="input" inputMode="decimal" value={expAmount} onChange={(e) => setExpAmount(e.target.value)} required />
              </label>
              <label className="text-sm">
                Date
                <input className="input" type="date" value={expDate} onChange={(e) => setExpDate(e.target.value)} required />
              </label>
            </div>
            <label className="text-sm">
              Paid by
              <select className="input" value={expPayer} onChange={(e) => setExpPayer(e.target.value)}>
                {activeGroup.members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.name} {m.user_id === user?.id ? '(You)' : ''}
                  </option>
                ))}
              </select>
            </label>
            <p className="muted text-xs">This amount will be split equally among all {activeGroup.members.length} members.</p>
            {err && <ErrorBox message={err} />}
            <div className="flex justify-end gap-2 mt-2">
              <button type="button" className="btn" style={ghost} onClick={() => setAddExpenseModal(false)}>Cancel</button>
              <button type="submit" className="btn" disabled={busy}>Save Expense</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
