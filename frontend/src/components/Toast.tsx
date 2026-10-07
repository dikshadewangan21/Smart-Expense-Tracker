import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react'
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

type ToastType = 'success' | 'error' | 'info'

interface Toast {
  id: string
  message: string
  type: ToastType
}

interface ToastContextValue {
  toast: {
    success: (msg: string) => void
    error: (msg: string) => void
    info: (msg: string) => void
  }
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((message: string, type: ToastType) => {
    const id = Math.random().toString(36).substring(2, 9)
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 3500)
  }, [])

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = {
    success: (msg: string) => addToast(msg, 'success'),
    error: (msg: string) => addToast(msg, 'error'),
    info: (msg: string) => addToast(msg, 'info'),
  }

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-20 md:bottom-5 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none px-2" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className="pointer-events-auto flex items-center justify-between gap-3 p-3.5 rounded-xl border shadow-lg bg-card text-fg transition-all text-sm font-medium animate-in fade-in slide-in-from-bottom-2 duration-200"
            style={{
              borderColor: t.type === 'success' ? 'var(--good)' : t.type === 'error' ? 'var(--bad)' : 'var(--border)',
            }}
          >
            <div className="flex items-center gap-2.5">
              {t.type === 'success' && <CheckCircle2 size={18} style={{ color: 'var(--good)' }} className="shrink-0" />}
              {t.type === 'error' && <AlertCircle size={18} style={{ color: 'var(--bad)' }} className="shrink-0" />}
              {t.type === 'info' && <Info size={18} style={{ color: 'var(--accent)' }} className="shrink-0" />}
              <span>{t.message}</span>
            </div>
            <button
              onClick={() => removeToast(t.id)}
              className="p-1 rounded hover:bg-border-subtle text-muted hover:text-fg"
              aria-label="Dismiss"
            >
              <X size={15} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  const fallback = {
    success: (msg: string) => console.log('Toast:', msg),
    error: (msg: string) => console.error('Toast Error:', msg),
    info: (msg: string) => console.log('Toast Info:', msg),
  }
  const t = ctx ? ctx.toast : fallback
  return {
    ...t,
    toast: t,
  }
}

