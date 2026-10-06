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

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="p-8 muted" role="status">Loading…</div>
  return user ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
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
        <Route path="/budgets" element={<Budgets />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/subscriptions" element={<Subscriptions />} />
        <Route path="/bills" element={<Bills />} />
        <Route path="/calendar" element={<CalendarPage />} />
        <Route path="/goals" element={<Goals />} />
        <Route path="/debts" element={<Debts />} />
        <Route path="/net-worth" element={<NetWorth />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
