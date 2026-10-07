import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { AlertCircle, HelpCircle, ArrowUpRight } from 'lucide-react'

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card flex items-center justify-between gap-3 p-3.5" role="alert" style={{ borderColor: 'var(--bad)', background: 'var(--bad-light)' }}>
      <div className="flex items-center gap-2.5 text-sm" style={{ color: 'var(--bad)' }}>
        <AlertCircle size={18} className="shrink-0" />
        <span className="font-medium">{message}</span>
      </div>
      {onRetry && (
        <button className="btn text-xs py-1 px-3 btn-secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function Empty({
  children,
  title,
  actionLabel,
  onAction,
  icon: Icon,
}: {
  children?: ReactNode
  title?: string
  actionLabel?: string
  onAction?: () => void
  icon?: typeof HelpCircle
}) {
  return (
    <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
      {Icon && (
        <div className="w-12 h-12 rounded-full flex items-center justify-center mb-3 text-muted" style={{ background: 'var(--border-subtle)' }}>
          <Icon size={22} />
        </div>
      )}
      {title && <h3 className="font-semibold text-base mb-1 text-fg">{title}</h3>}
      <div className="muted text-sm max-w-sm">{children}</div>
      {actionLabel && onAction && (
        <button className="btn mt-4 text-sm" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  )
}

export function Skeleton({ rows = 4, label = 'Loading...' }: { rows?: number; label?: string }) {
  return (
    <div className="grid gap-3" aria-busy="true" aria-label={label}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton h-20" />
      ))}
    </div>
  )
}

export const ghost = {
  background: 'transparent',
  color: 'var(--fg)',
  border: '1px solid var(--border)',
} as const

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
  useEffect(() => {
    setData(null)
    reload()
  }, [reload])
  return { data, error, reload, setData }
}

export function Stat({
  label,
  value,
  sub,
  tone,
  badge,
  onClick,
  icon,
}: {
  label: string
  value: string
  sub?: ReactNode
  tone?: 'good' | 'bad' | 'warn'
  badge?: string
  onClick?: () => void
  icon?: typeof HelpCircle | ReactNode
}) {
  return (
    <div
      className={`card flex flex-col justify-between ${onClick ? 'card-interactive group' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => e.key === 'Enter' && onClick() : undefined}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="muted text-xs font-medium uppercase tracking-wide flex items-center gap-1.5">
          {icon && (typeof icon === 'function' ? (() => { const I = icon as typeof HelpCircle; return <I size={14} className="opacity-75" /> })() : icon)}
          {label}
        </span>
        {badge && (
          <span className={`badge ${tone ? `badge-${tone}` : 'badge-neutral'}`}>
            {badge}
          </span>
        )}
        {onClick && (
          <ArrowUpRight size={14} className="muted opacity-0 group-hover:opacity-100 transition-opacity" />
        )}
      </div>
      <div>
        <div
          className="text-2xl font-bold tracking-tight"
          style={tone ? { color: `var(--${tone})` } : {}}
        >
          {value}
        </div>
        {sub && <div className="muted text-xs mt-1 font-normal">{sub}</div>}
      </div>
    </div>
  )
}

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: 'good' | 'bad' | 'warn' | 'neutral' | 'accent'
}) {
  const toneClass =
    tone === 'good'
      ? 'badge-good'
      : tone === 'bad'
      ? 'badge-bad'
      : tone === 'warn'
      ? 'badge-warn'
      : tone === 'accent'
      ? 'bg-accent/15 text-accent font-medium'
      : 'badge-neutral'

  return <span className={`badge ${toneClass}`}>{children}</span>
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: ReactNode
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 backdrop-blur-xs transition-opacity duration-200"
      style={{ background: 'rgba(0, 0, 0, 0.45)' }}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="card w-full sm:max-w-lg max-h-[90vh] overflow-y-auto rounded-b-none sm:rounded-2xl shadow-2xl p-5 sm:p-6 animate-in slide-in-from-bottom-4 sm:zoom-in-95 duration-200"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="flex justify-between items-center mb-4 pb-2 border-b" style={{ borderColor: 'var(--border)' }}>
          <h2 className="font-semibold text-lg">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-border-subtle muted hover:text-fg text-sm transition-colors"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
