import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export default function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { user, login, register } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/dashboard" replace />

  const isRegister = mode === 'register'
  const tooShort = isRegister && password.length > 0 && password.length < 10

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (tooShort) return
    setBusy(true)
    setError(null)
    try {
      if (isRegister) await register(email, password, name)
      else await login(email, password)
      nav('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-4">
      <form onSubmit={submit} className="card w-full max-w-sm flex flex-col gap-3" noValidate>
        <h1 className="text-xl font-bold">{isRegister ? 'Create your account' : 'Welcome back'}</h1>
        <p className="muted text-sm">Track less. Understand more. Save smarter.</p>
        {isRegister && (
          <label className="text-sm">Name
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
          </label>
        )}
        <label className="text-sm">Email
          <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
        </label>
        <label className="text-sm">Password
          <input className="input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete={isRegister ? 'new-password' : 'current-password'} aria-describedby="pw-help" />
        </label>
        {isRegister && <p id="pw-help" className="text-xs" style={{ color: tooShort ? 'var(--bad)' : 'var(--muted)' }}>
          At least 10 characters.</p>}
        {error && <p role="alert" className="text-sm" style={{ color: 'var(--bad)' }}>{error}</p>}
        <button className="btn" disabled={busy || !email || !password || tooShort}>
          {busy ? 'Please wait…' : isRegister ? 'Create account' : 'Sign in'}
        </button>
        <p className="text-sm muted">
          {isRegister ? <>Already registered? <Link to="/login" className="underline">Sign in</Link></>
            : <>New here? <Link to="/register" className="underline">Create an account</Link></>}
        </p>
      </form>
    </div>
  )
}
