import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { useAuth } from './lib/auth'
import AuthPage from './pages/AuthPage'
import Analytics from './pages/Analytics'
import Bills from './pages/Bills'
import CalendarPage from './pages/CalendarPage'
import Settings from './pages/Settings'
import Subscriptions from './pages/Subscriptions'
import Budgets from './pages/Budgets'
import Goals from './pages/Goals'
import Debts from './pages/Debts'
import NetWorth from './pages/NetWorth'
import Dashboard from './pages/Dashboard'
import Transactions from './pages/Transactions'
import TxForm from './pages/TxForm'
import ImportCenter from './pages/ImportCenter'
import MoneyCoach from './pages/MoneyCoach'
import SharedFinances from './pages/SharedFinances'
import Categories from './pages/Categories'
import Privacy from './pages/Privacy'

import { ToastProvider } from './components/Toast'

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="p-8 muted" role="status">Loading…</div>
  return user ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route path="/login" element={<AuthPage mode="login" />} />
        <Route path="/register" element={<AuthPage mode="register" />} />
        <Route element={<Protected><Layout /></Protected>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/transactions/:id/edit" element={<TxForm kind="expense" />} />
          <Route path="/add-expense" element={<TxForm kind="expense" />} />
          <Route path="/add-income" element={<TxForm kind="income" />} />
          <Route path="/add-transfer" element={<TxForm kind="transfer" />} />
          <Route path="/coach" element={<MoneyCoach />} />
          <Route path="/ai-coach" element={<MoneyCoach />} />
          <Route path="/imports" element={<ImportCenter />} />
          <Route path="/budgets" element={<Budgets />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/shared" element={<SharedFinances />} />
          <Route path="/categories" element={<Categories />} />
          <Route path="/subscriptions" element={<Subscriptions />} />
          <Route path="/bills" element={<Bills />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/goals" element={<Goals />} />
          <Route path="/debts" element={<Debts />} />
          <Route path="/net-worth" element={<NetWorth />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </ToastProvider>
  )
}
