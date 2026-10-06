import { Bot, Send, Sparkles, MessageSquare } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { ErrorBox, Skeleton, ghost, useLoad } from '../components/ui'

interface Message {
  id?: number
  role: 'user' | 'assistant'
  content: string
  created_at?: string
}

interface CoachResponse {
  conversation_id: number
  message: Message
  context_summary: Record<string, unknown>
  suggested_prompts: string[]
}

interface Conversation {
  id: number
  title: string
  created_at: string
}

export default function MoneyCoach() {
  const [prompt, setPrompt] = useState('')
  const [activeConvId, setActiveConvId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [suggested, setSuggested] = useState<string[]>([
    'How is my financial health score computed?',
    'Am I staying within my budget this month?',
    'What bills and subscriptions are coming up?',
    'How can I improve my savings rate?'
  ])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const convList = useLoad(() => api<Conversation[]>('/coach/conversations'), [])

  async function sendMessage(textToSend?: string) {
    const q = (textToSend || prompt).trim()
    if (!q || busy) return

    setPrompt('')
    setErr(null)
    const newMessages: Message[] = [...messages, { role: 'user', content: q }]
    setMessages(newMessages)
    setBusy(true)

    try {
      const res = await api<CoachResponse>('/coach/chat', {
        method: 'POST',
        body: JSON.stringify({
          prompt: q,
          conversation_id: activeConvId,
        }),
      })

      setActiveConvId(res.conversation_id)
      setMessages([...newMessages, res.message])
      if (res.suggested_prompts && res.suggested_prompts.length > 0) {
        setSuggested(res.suggested_prompts)
      }
      convList.reload()
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Could not contact Money Coach.')
    } finally {
      setBusy(false)
    }
  }

  async function loadConversation(id: number) {
    setActiveConvId(id)
    setBusy(true)
    try {
      const msgs = await api<Message[]>(`/coach/conversations/${id}`)
      setMessages(msgs)
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Could not load conversation.')
    } finally {
      setBusy(false)
    }
  }

  function startNewChat() {
    setActiveConvId(null)
    setMessages([])
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Bot size={22} className="text-accent" /> AI Money Coach
          </h1>
          <p className="muted text-xs">Grounded in your real financial calculations. Explains your numbers and helps you save smarter.</p>
        </div>
        <button className="btn flex items-center gap-1" style={ghost} onClick={startNewChat}>
          <MessageSquare size={16} /> New Chat
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Past conversations sidebar */}
        <aside className="card hidden md:flex md:flex-col gap-2 p-3 text-sm">
          <div className="font-semibold text-xs uppercase muted mb-1">Previous Conversations</div>
          {!convList.data ? <Skeleton rows={3} /> : convList.data.length === 0 ? <p className="muted text-xs">No prior chats.</p> : (
            <ul className="flex flex-col gap-1 overflow-y-auto max-h-96">
              {convList.data.map((c) => (
                <li key={c.id}>
                  <button
                    className={`w-full text-left truncate px-2 py-1.5 rounded hover:bg-card text-xs ${activeConvId === c.id ? 'font-semibold bg-card' : 'muted'}`}
                    onClick={() => loadConversation(c.id)}
                  >
                    {c.title || 'Chat'}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* Chat area */}
        <div className="md:col-span-3 card flex flex-col min-h-[500px]">
          <div className="flex-1 overflow-y-auto flex flex-col gap-3 p-2">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center my-auto p-6 text-center gap-3">
                <Sparkles size={36} className="muted" />
                <h2 className="font-semibold text-base">How can I help your finances today?</h2>
                <p className="muted text-sm max-w-md">Ask questions about your budget, savings rate, upcoming bills, or financial health.</p>

                <div className="flex flex-wrap gap-2 justify-center mt-2 max-w-lg">
                  {suggested.map((s, idx) => (
                    <button key={idx} className="btn text-xs py-1.5 px-3" style={ghost} onClick={() => sendMessage(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, idx) => {
              const isUser = m.role === 'user'
              return (
                <div key={idx} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`rounded-xl px-4 py-2.5 max-w-xl text-sm leading-relaxed whitespace-pre-wrap ${
                      isUser ? 'bg-accent text-accent-fg font-medium' : 'bg-card border'
                    }`}
                    style={isUser ? {} : { borderColor: 'var(--border)' }}
                  >
                    {m.content}
                  </div>
                </div>
              )
            })}

            {busy && (
              <div className="flex justify-start">
                <div className="rounded-xl px-4 py-2 text-sm muted bg-card border animate-pulse" style={{ borderColor: 'var(--border)' }}>
                  Analyzing financial data...
                </div>
              </div>
            )}

            {err && <ErrorBox message={err} />}
          </div>

          {/* Prompt pills below chat */}
          {messages.length > 0 && suggested.length > 0 && (
            <div className="flex gap-2 overflow-x-auto p-2 border-t text-xs" style={{ borderColor: 'var(--border)' }}>
              {suggested.slice(0, 3).map((s, i) => (
                <button key={i} className="whitespace-nowrap px-2 py-1 rounded border muted hover:text-fg" style={{ borderColor: 'var(--border)' }} onClick={() => sendMessage(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Input form */}
          <form
            onSubmit={(e) => { e.preventDefault(); sendMessage() }}
            className="flex gap-2 p-2 border-t"
            style={{ borderColor: 'var(--border)' }}
          >
            <input
              className="input flex-1"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Ask anything about your money, budget, or debts..."
              disabled={busy}
            />
            <button type="submit" className="btn flex items-center gap-1" disabled={busy || !prompt.trim()}>
              <Send size={16} /> Send
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
