import { useCallback, useEffect, useState, type ReactNode } from 'react'

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="card" role="alert">{message}{onRetry && <button className="btn ml-2" onClick={onRetry}>Retry</button>}</div>
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="muted text-sm py-6 text-center">{children}</p>
}

export function Skeleton({ rows = 4, label = 'Loading' }: { rows?: number; label?: string }) {
  return <div className="grid gap-3" aria-busy="true" aria-label={label}>{Array.from({ length: rows }).map((_, i) => <div key={i} className="skeleton h-20" />)}</div>
}

export const ghost = { background: 'transparent', color: 'var(--fg)', border: '1px solid var(--border)' } as const

/** Loads data from a loader function; re-runs when `deps` change. */
export function useLoad<T>(loader: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const fn = useCallback(loader, deps)
  const reload = useCallback(() => {
    setError(null)
    fn().then(setData).catch((e: Error) => setError(e.message))
  }, [fn])
  useEffect(() => { setData(null); reload() }, [reload])
  return { data, error, reload, setData }
}

export function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: ReactNode; tone?: 'good' | 'bad' }) {
  return (
    <div className="card">
      <div className="muted text-sm">{label}</div>
      <div className="text-2xl font-bold" style={tone ? { color: `var(--${tone})` } : {}}>{value}</div>
      {sub && <div className="muted text-xs mt-1">{sub}</div>}
    </div>
  )
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center p-0 md:p-4" style={{ background: 'rgb(0 0 0 / 0.5)' }}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="card w-full md:max-w-md max-h-[90vh] overflow-y-auto" role="dialog" aria-modal="true" aria-label={title}>
        <div className="flex justify-between items-center mb-3"><h2 className="font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="p-1">✕</button></div>
        {children}
      </div>
    </div>
  )
}
