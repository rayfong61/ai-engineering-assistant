import { ArrowUp, FileText, Menu } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { apiGet, apiPostStream } from '../lib/api'
import Alert from './Alert'
import ConversationList from './ConversationList'
import MarkdownContent from './MarkdownContent'
import Spinner from './Spinner'

export default function ChatPanel({ projectId }) {
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    // 'smooth' fires a scroll animation on every update -- fine for the old
    // two-updates-per-turn flow, but streaming now updates `messages` on
    // every token event, so overlapping smooth animations kept re-targeting
    // mid-flight and made the page visibly jitter. 'auto' snaps instantly,
    // which is imperceptible at token-sized scroll deltas.
    bottomRef.current?.scrollIntoView({ behavior: 'auto' })
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
        // The conversation list is shared with the Agent tab (same
        // project-level endpoint), so a conversation opened here can
        // actually be Agent-originated and include raw tool-call trace
        // rows (role="tool", JSON content) -- filter to user/assistant
        // only, same as AgentPanel already does, so that JSON never
        // renders as if it were an answer.
        conversation.messages
          .filter((m) => m.role === 'user' || m.role === 'assistant')
          .map((m) => ({
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

    setMessages((prev) => [...prev, { role: 'user', content: question }, { role: 'assistant', content: '', sources: [] }])
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    setSending(true)
    setError(null)

    // Streamed onto the trailing placeholder assistant message added above --
    // every handler below only ever touches the last element of `messages`.
    const appendToLastMessage = (patch) => {
      setMessages((prev) => {
        const next = [...prev]
        next[next.length - 1] = { ...next[next.length - 1], ...patch }
        return next
      })
    }

    let answer = ''
    try {
      await apiPostStream(
        `/api/projects/${projectId}/chat`,
        { conversation_id: conversationId, message: question },
        {
          meta: (event) => {
            setConversationId(event.conversation_id)
            appendToLastMessage({ sources: event.sources })
          },
          token: (event) => {
            answer += event.text
            appendToLastMessage({ content: answer })
          },
          error: (event) => {
            setMessages((prev) => prev.slice(0, -1)) // drop the empty placeholder
            setError(event.message)
          },
          done: () => {
            setRefreshKey((k) => k + 1) // conversation list picks up the new/updated title
          },
        }
      )
    } catch (err) {
      setMessages((prev) => prev.slice(0, -1))
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex gap-4">
      <ConversationList
        projectId={projectId}
        activeId={conversationId}
        onSelect={handleSelect}
        onNew={handleNew}
        refreshKey={refreshKey}
        mobileOpen={drawerOpen}
        onCloseMobile={() => setDrawerOpen(false)}
      />

      <div className="flex min-h-[28rem] min-w-0 flex-1 flex-col rounded-card border border-slate-200 bg-white">
        <div className="flex items-center gap-2 border-b border-slate-200 bg-white p-2 md:hidden">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-label="開啟對話列表"
            className="rounded p-2 text-slate-500 hover:bg-slate-100"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="truncate text-sm font-medium text-slate-700">對話</span>
        </div>

        {error && (
          <div className="p-3">
            <Alert variant="error">{error}</Alert>
          </div>
        )}

        <div className="p-4">
          {messages.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400">
              針對這個專案的工程文件提問，答案會附上來源文件與頁碼。
            </p>
          ) : (
            <div className="flex flex-col gap-4">
              {messages.map((msg, i) =>
                msg.role === 'user' ? (
                  <div key={i} className="flex justify-end">
                    <div className="max-w-[85%] rounded-card bg-brand-600 px-3 py-2 text-sm whitespace-pre-wrap text-white">
                      {msg.content}
                    </div>
                  </div>
                ) : (
                  <div key={i}>
                    <MarkdownContent content={msg.content} className="text-slate-900" />
                    {msg.sources?.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1.5">
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
                )
              )}
              {sending && !messages[messages.length - 1]?.content && (
                <Spinner label="思考中..." className="text-slate-500" />
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <form
          onSubmit={handleSend}
          className="sticky bottom-3 mx-3 flex items-center gap-1 rounded-full border border-slate-300 bg-white py-1.5 pl-4 pr-1.5 shadow-card focus-within:border-brand-500"
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              e.target.style.height = 'auto'
              e.target.style.height = `${Math.min(e.target.scrollHeight, 150)}px`
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend(e)
              }
            }}
            placeholder="輸入問題...（Shift+Enter 換行）"
            rows={1}
            className="max-h-[150px] flex-1 resize-none bg-transparent py-1 text-sm text-slate-900
              placeholder:text-slate-400 focus:outline-none"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            aria-label="送出"
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-brand-600 text-white transition-colors hover:bg-brand-700 disabled:opacity-40"
          >
            {sending ? <Spinner size="sm" className="text-white" /> : <ArrowUp className="h-4 w-4" />}
          </button>
        </form>
      </div>
    </div>
  )
}
