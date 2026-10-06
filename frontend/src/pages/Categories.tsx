import { FolderTree, Plus, Trash2, Pencil, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { Empty, ErrorBox, Modal, Skeleton, ghost, useLoad } from '../components/ui'
import type { Category } from '../lib/types'

interface CategoryRule {
  id: number
  merchant_key: string
  category_id: number
  category_name: string
  created_at: string
}

export default function Categories() {
  const [tab, setTab] = useState<'categories' | 'rules'>('categories')
  const [catType, setCatType] = useState<'expense' | 'income'>('expense')

  const [editingCat, setEditingCat] = useState<Category | 'new' | null>(null)
  const [catName, setCatName] = useState('')
  const [catEssential, setCatEssential] = useState(false)

  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const categories = useLoad(() => api<Category[]>('/categories'), [])
  const rules = useLoad(() => api<CategoryRule[]>('/categories/rules'), [])

  function openNew() {
    setCatName('')
    setCatEssential(false)
    setEditingCat('new')
  }

  function openEdit(c: Category) {
    setCatName(c.name)
    setCatEssential(Boolean(c.essential))
    setEditingCat(c)
  }

  async function saveCategory(e: React.FormEvent) {
    e.preventDefault()
    if (!catName.trim()) return
    setBusy(true)
    setErr(null)
    try {
      if (editingCat === 'new') {
        await api('/categories', {
          method: 'POST',
          body: JSON.stringify({ name: catName.trim(), kind: catType, essential: catEssential }),
        })
      } else if (editingCat) {
        await api(`/categories/${editingCat.id}`, {
          method: 'PUT',
          body: JSON.stringify({ name: catName.trim(), kind: editingCat.kind, essential: catEssential }),
        })
      }
      setEditingCat(null)
      categories.reload()
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Could not save category.')
    } finally {
      setBusy(false)
    }
  }

  async function deleteCat(id: number) {
    if (!confirm('Are you sure you want to delete this category?')) return
    try {
      await api(`/categories/${id}`, { method: 'DELETE' })
      categories.reload()
    } catch (e2) {
      alert(e2 instanceof Error ? e2.message : 'Could not delete category.')
    }
  }

  async function deleteRule(id: number) {
    try {
      await api(`/categories/rules/${id}`, { method: 'DELETE' })
      rules.reload()
    } catch (e2) {
      alert(e2 instanceof Error ? e2.message : 'Could not delete rule.')
    }
  }

  const filteredCats = categories.data?.filter((c) => c.kind === catType) ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <FolderTree size={22} /> Categories &amp; Rules
          </h1>
          <p className="muted text-xs">Organize your expenses and incomes. Manage rules that auto-categorize merchants.</p>
        </div>
        <div className="flex gap-2">
          <button className="btn" style={tab === 'categories' ? {} : ghost} onClick={() => setTab('categories')}>
            Categories
          </button>
          <button className="btn" style={tab === 'rules' ? {} : ghost} onClick={() => setTab('rules')}>
            Learned Rules ({rules.data?.length ?? 0})
          </button>
        </div>
      </div>

      {tab === 'categories' && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex gap-2">
              <button className="btn" style={catType === 'expense' ? {} : ghost} onClick={() => setCatType('expense')}>
                Expense Categories
              </button>
              <button className="btn" style={catType === 'income' ? {} : ghost} onClick={() => setCatType('income')}>
                Income Categories
              </button>
            </div>
            <button className="btn flex items-center gap-1" onClick={openNew}>
              <Plus size={16} /> Add Category
            </button>
          </div>

          <section className="card flex flex-col gap-2">
            {categories.error && <ErrorBox message={categories.error} onRetry={categories.reload} />}
            {!categories.data ? <Skeleton rows={4} /> : filteredCats.length === 0 ? (
              <Empty>No categories found for {catType}.</Empty>
            ) : (
              <ul className="divide-y text-sm" style={{ borderColor: 'var(--border)' }}>
                {filteredCats.map((c) => (
                  <li key={c.id} className="py-2.5 flex items-center justify-between gap-2">
                    <div>
                      <div className="font-medium flex items-center gap-2">
                        {c.name}
                        {c.essential && (
                          <span className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-accent/20 text-accent">
                            Essential
                          </span>
                        )}
                      </div>
                      <div className="muted text-xs">{c.kind}</div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button className="p-1 muted hover:text-fg" onClick={() => openEdit(c)} aria-label="Edit category">
                        <Pencil size={15} />
                      </button>
                      <button className="p-1 muted hover:text-bad" onClick={() => deleteCat(c.id)} aria-label="Delete category">
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      {tab === 'rules' && (
        <section className="card flex flex-col gap-3">
          <div>
            <h2 className="font-semibold text-base flex items-center gap-2">
              <Sparkles size={18} /> Automatic Categorization Rules
            </h2>
            <p className="muted text-xs">
              When you check &quot;Always categorize this merchant&quot; on a transaction, a rule is created here. Future transactions with that merchant key automatically match this category.
            </p>
          </div>

          {!rules.data ? <Skeleton rows={3} /> : rules.data.length === 0 ? (
            <Empty>No merchant categorization rules learned yet. Update any transaction to learn rules.</Empty>
          ) : (
            <div className="overflow-x-auto text-sm">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b muted text-xs" style={{ borderColor: 'var(--border)' }}>
                    <th className="py-2">Merchant Key</th>
                    <th>Mapped Category</th>
                    <th className="text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.data.map((r) => (
                    <tr key={r.id} className="border-b" style={{ borderColor: 'var(--border)' }}>
                      <td className="py-2 font-mono text-xs">{r.merchant_key}</td>
                      <td>
                        <span className="font-medium px-2 py-0.5 rounded bg-card border" style={{ borderColor: 'var(--border)' }}>
                          {r.category_name}
                        </span>
                      </td>
                      <td className="text-right">
                        <button className="p-1 muted hover:text-bad" onClick={() => deleteRule(r.id)} aria-label="Delete rule">
                          <Trash2 size={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* Edit Category Modal */}
      {editingCat && (
        <Modal title={editingCat === 'new' ? 'Add Category' : 'Edit Category'} onClose={() => setEditingCat(null)}>
          <form onSubmit={saveCategory} className="flex flex-col gap-3">
            <label className="text-sm">
              Category Name
              <input className="input" value={catName} onChange={(e) => setCatName(e.target.value)} required autoFocus />
            </label>
            <label className="text-sm flex items-center gap-2 cursor-pointer mt-1">
              <input type="checkbox" checked={catEssential} onChange={(e) => setCatEssential(e.target.checked)} />
              <span>Mark as Essential (Rent, Groceries, Medical, Utilities)</span>
            </label>
            <p className="muted text-xs">Used to calculate your Essential vs Discretionary spending breakdown.</p>
            {err && <ErrorBox message={err} />}
            <div className="flex justify-end gap-2 mt-2">
              <button type="button" className="btn" style={ghost} onClick={() => setEditingCat(null)}>Cancel</button>
              <button type="submit" className="btn" disabled={busy}>Save Category</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
