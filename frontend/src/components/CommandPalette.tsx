import { useEffect, useState, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, PlusCircle, LayoutDashboard, Receipt, PiggyBank,
  BarChart3, Repeat, FileText, Target, Landmark, Scale,
  Bot, Settings, UploadCloud, Users, ShieldCheck, CornerDownLeft
} from 'lucide-react'

interface CommandItem {
  id: string
  label: string
  category: 'Actions' | 'Navigation' | 'Filters'
  icon: typeof Search
  shortcut?: string
  keywords?: string[]
  onSelect: () => void
}

interface CommandPaletteProps {
  isOpen: boolean
  onClose: () => void
  onOpenQuickAdd?: (kind?: 'expense' | 'income' | 'transfer') => void
}

export default function CommandPalette({ isOpen, onClose, onOpenQuickAdd }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const nav = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const commands: CommandItem[] = useMemo(() => [
    // Actions
    {
      id: 'action-add-expense',
      label: 'Add Expense',
      category: 'Actions',
      icon: PlusCircle,
      shortcut: 'N',
      keywords: ['add', 'expense', 'spend', 'new', 'cost'],
      onSelect: () => {
        onClose()
        if (onOpenQuickAdd) onOpenQuickAdd('expense')
        else nav('/add-expense')
      },
    },
    {
      id: 'action-add-income',
      label: 'Add Income',
      category: 'Actions',
      icon: PlusCircle,
      keywords: ['income', 'salary', 'received', 'deposit'],
      onSelect: () => {
        onClose()
        if (onOpenQuickAdd) onOpenQuickAdd('income')
        else nav('/add-income')
      },
    },
    {
      id: 'action-add-transfer',
      label: 'Add Transfer',
      category: 'Actions',
      icon: PlusCircle,
      keywords: ['transfer', 'move', 'between', 'accounts'],
      onSelect: () => {
        onClose()
        nav('/add-transfer')
      },
    },

    // Navigation
    {
      id: 'nav-dashboard',
      label: 'Dashboard',
      category: 'Navigation',
      icon: LayoutDashboard,
      shortcut: 'D',
      keywords: ['home', 'overview', 'summary', 'health'],
      onSelect: () => { onClose(); nav('/dashboard') },
    },
    {
      id: 'nav-transactions',
      label: 'Transactions',
      category: 'Navigation',
      icon: Receipt,
      shortcut: 'T',
      keywords: ['expenses', 'history', 'list', 'search'],
      onSelect: () => { onClose(); nav('/transactions') },
    },
    {
      id: 'nav-budgets',
      label: 'Budgets',
      category: 'Navigation',
      icon: PiggyBank,
      shortcut: 'B',
      keywords: ['limits', 'monthly', 'spending', 'categories'],
      onSelect: () => { onClose(); nav('/budgets') },
    },
    {
      id: 'nav-analytics',
      label: 'Analytics',
      category: 'Navigation',
      icon: BarChart3,
      shortcut: 'A',
      keywords: ['charts', 'reports', 'trends', 'what changed', 'breakdown'],
      onSelect: () => { onClose(); nav('/analytics') },
    },
    {
      id: 'nav-subscriptions',
      label: 'Subscriptions',
      category: 'Navigation',
      icon: Repeat,
      keywords: ['recurring', 'netflix', 'spotify', 'monthly'],
      onSelect: () => { onClose(); nav('/subscriptions') },
    },
    {
      id: 'nav-bills',
      label: 'Bills & Reminders',
      category: 'Navigation',
      icon: FileText,
      keywords: ['due', 'rent', 'utilities', 'electricity', 'wifi'],
      onSelect: () => { onClose(); nav('/bills') },
    },
    {
      id: 'nav-goals',
      label: 'Savings Goals',
      category: 'Navigation',
      icon: Target,
      keywords: ['emergency fund', 'vacation', 'target', 'savings'],
      onSelect: () => { onClose(); nav('/goals') },
    },
    {
      id: 'nav-debts',
      label: 'Debts & Loans',
      category: 'Navigation',
      icon: Landmark,
      keywords: ['emi', 'borrowed', 'lent', 'credit card'],
      onSelect: () => { onClose(); nav('/debts') },
    },
    {
      id: 'nav-net-worth',
      label: 'Net Worth & Accounts',
      category: 'Navigation',
      icon: Scale,
      keywords: ['assets', 'liabilities', 'bank', 'investments'],
      onSelect: () => { onClose(); nav('/net-worth') },
    },
    {
      id: 'nav-ai-coach',
      label: 'AI Money Coach',
      category: 'Navigation',
      icon: Bot,
      keywords: ['ai', 'coach', 'chat', 'ask', 'advice', 'assistant'],
      onSelect: () => { onClose(); nav('/ai-coach') },
    },
    {
      id: 'nav-imports',
      label: 'Import Center (CSV & OCR)',
      category: 'Navigation',
      icon: UploadCloud,
      keywords: ['upload', 'csv', 'statement', 'receipt', 'scan'],
      onSelect: () => { onClose(); nav('/imports') },
    },
    {
      id: 'nav-shared',
      label: 'Shared Finances',
      category: 'Navigation',
      icon: Users,
      keywords: ['split', 'group', 'roommates', 'friends', 'trip'],
      onSelect: () => { onClose(); nav('/shared') },
    },
    {
      id: 'nav-privacy',
      label: 'Privacy & Data Export',
      category: 'Navigation',
      icon: ShieldCheck,
      keywords: ['download', 'takeout', 'export', 'gdpr', 'audit'],
      onSelect: () => { onClose(); nav('/privacy') },
    },
    {
      id: 'nav-settings',
      label: 'Settings',
      category: 'Navigation',
      icon: Settings,
      keywords: ['profile', 'timezone', 'currency', 'preferences'],
      onSelect: () => { onClose(); nav('/settings') },
    },
  ], [nav, onClose, onOpenQuickAdd])

  // Filter based on input
  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim()
    if (!q) return commands

    // Clean leading slash
    const clean = q.startsWith('/') ? q.slice(1).trim() : q
    if (!clean) return commands

    return commands.filter((cmd) => {
      const matchLabel = cmd.label.toLowerCase().includes(clean)
      const matchCategory = cmd.category.toLowerCase().includes(clean)
      const matchKeyword = cmd.keywords?.some((k) => k.toLowerCase().includes(clean))
      return matchLabel || matchCategory || matchKeyword
    })
  }, [commands, query])

  // Include dynamic Search option if query has search terms
  const searchAction: CommandItem | null = useMemo(() => {
    const clean = query.startsWith('/') ? query.slice(1).trim() : query.trim()
    if (!clean) return null
    return {
      id: 'search-transactions',
      label: `Search transactions for "${clean}"`,
      category: 'Filters',
      icon: Search,
      onSelect: () => {
        onClose()
        nav(`/transactions?q=${encodeURIComponent(clean)}`)
      },
    }
  }, [query, onClose, nav])

  const allItems = useMemo(() => {
    if (searchAction) return [searchAction, ...filtered]
    return filtered
  }, [searchAction, filtered])

  // Reset selected index when filtered list changes
  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  // Focus input on open
  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isOpen])

  // Keyboard navigation inside palette
  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev + 1) % allItems.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev - 1 + allItems.length) % allItems.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (allItems[selectedIndex]) {
        allItems[selectedIndex].onSelect()
      }
    } else if (e.key === 'Escape') {
      onClose()
    }
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 px-4 backdrop-blur-xs"
      style={{ background: 'rgba(0, 0, 0, 0.45)' }}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="card w-full max-w-xl p-0 overflow-hidden shadow-2xl rounded-2xl animate-in fade-in zoom-in-95 duration-150 border"
        style={{ borderColor: 'var(--border)' }}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <Search size={18} className="text-muted shrink-0" />
          <input
            ref={inputRef}
            className="w-full bg-transparent border-0 text-fg text-sm sm:text-base focus:outline-none placeholder:text-muted"
            placeholder="Type a command or search (e.g. / add expense, / budgets, food)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono text-muted border" style={{ borderColor: 'var(--border)' }}>
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div ref={listRef} className="max-h-80 overflow-y-auto p-2 flex flex-col gap-0.5">
          {allItems.length === 0 ? (
            <div className="py-8 text-center text-sm muted">No matching commands or pages found.</div>
          ) : (
            allItems.map((item, idx) => {
              const isSelected = idx === selectedIndex
              const Icon = item.icon
              return (
                <div
                  key={item.id}
                  onClick={item.onSelect}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer text-sm transition-colors ${
                    isSelected ? 'bg-accent/10 font-medium text-fg' : 'text-fg/80 hover:bg-card-hover'
                  }`}
                >
                  <div className="flex items-center gap-3 truncate">
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                        isSelected ? 'bg-accent text-accent-fg' : 'bg-border-subtle text-muted'
                      }`}
                    >
                      <Icon size={15} />
                    </div>
                    <span className="truncate">{item.label}</span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {item.shortcut && (
                      <kbd className="px-1.5 py-0.5 rounded text-[10px] font-mono muted border" style={{ borderColor: 'var(--border)' }}>
                        {item.shortcut}
                      </kbd>
                    )}
                    {isSelected && (
                      <CornerDownLeft size={13} className="text-accent" />
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* Footer with Keyboard Shortcuts Legend */}
        <div className="px-4 py-2.5 bg-border-subtle border-t flex items-center justify-between text-[11px] muted" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-3">
            <span><kbd className="font-mono">↑↓</kbd> navigate</span>
            <span><kbd className="font-mono">↵</kbd> select</span>
            <span><kbd className="font-mono">esc</kbd> close</span>
          </div>
          <div className="hidden sm:flex items-center gap-2">
            <span>Tip: press <kbd className="font-mono">/</kbd> anytime to open</span>
          </div>
        </div>
      </div>
    </div>
  )
}
