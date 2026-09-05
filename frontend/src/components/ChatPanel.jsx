import { FileText, Send } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { apiGet, apiPost } from '../lib/api'
import Alert from './Alert'
import Button from './Button'
import ConversationList from './ConversationList'
import Spinner from './Spinner'

export default function ChatPanel({ projectId }) {
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const handleNew = () => {
    setConversationId(null)
    setMessages([])
    setError(null)
  }

  const handleSelect = async (id) => {
    setError(null)
    try {
      const conversation = await apiGet(`/api/conversations/${id}`)
      setConversationId(conversation.id)
      setMessages(
        conversation.messages.map((m) => ({
          role: m.role,
          content: m.content,
          sources: m.sources,
        }))
      )
    } catch (err) {
      setError(err.message)
    }
  }

  const handleSend = async (e) => {
    e.preventDefault()
    const question = input.trim()
    if (!question || sending) return

    setMessages((prev) => [...prev, { role: 'user', content: question }])
    setInput('')
    setSending(true)
    setError(null)

    try {
      const response = await apiPost(`/api/projects/${projectId}/chat`, {
        conversation_id: conversationId,
        message: question,
      })
      setConversationId(response.conversation_id)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: response.answer, sources: response.sources },
      ])
      setRefreshKey((k) => k + 1) // conversation list picks up the new/updated title
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-16rem)] min-h-[28rem] gap-4">
      <ConversationList
        projectId={projectId}
        activeId={conversationId}
        onSelect={handleSelect}
        onNew={handleNew}
        refreshKey={refreshKey}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-card border border-slate-200 bg-white">
        {error && (
          <div className="p-3">
            <Alert variant="error">{error}</Alert>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400">
              針對這個專案的工程文件提問，答案會附上來源文件與頁碼。
            </p>
          ) : (
            <div className="flex flex-col gap-4">
              {messages.map((msg, i) => (
                <div key={i} className={msg.role === 'user' ? 'text-right' : 'text-left'}>
                  <div
                    className={`inline-block max-w-[85%] rounded-card px-3 py-2 text-sm whitespace-pre-wrap ${
                      msg.role === 'user' ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-900'
                    }`}
                  >
                    {msg.content}
                  </div>
                  {msg.sources?.length > 0 && (
                    <div className="mt-1 flex flex-wrap justify-start gap-1.5">
                      {msg.sources.map((s, j) => (
                        <span
                          key={j}
                          className="inline-flex items-center gap-1 rounded-full bg-slate-50 px-2 py-0.5 text-xs text-slate-500"
                        >
                          <FileText className="h-3 w-3" />
                          {s.filename} — 第 {s.page} 頁
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {sending && <Spinner label="思考中..." className="text-slate-500" />}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <form onSubmit={handleSend} className="flex gap-2 border-t border-slate-200 p-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="輸入問題..."
            className="flex-1 rounded-card border border-slate-300 px-3 py-2 text-sm text-slate-900
              placeholder:text-slate-400 focus-visible:border-brand-500"
          />
          <Button type="submit" loading={sending} icon={<Send className="h-4 w-4" />}>
            送出
          </Button>
        </form>
      </div>
    </div>
  )
}
