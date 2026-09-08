import { ArrowUp, FileText, Menu, Plus, Wrench, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { apiGet, apiPost, apiUpload } from '../lib/api'
import Alert from './Alert'
import ConversationList from './ConversationList'
import EmailPreviewCard from './EmailPreviewCard'
import MarkdownContent from './MarkdownContent'
import Spinner from './Spinner'

export default function AgentPanel({ projectId }) {
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [pendingImage, setPendingImage] = useState(null) // {id, filename, url}
  const [uploadingImage, setUploadingImage] = useState(false)
  const [lightboxUrl, setLightboxUrl] = useState(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const bottomRef = useRef(null)
  const fileInputRef = useRef(null)
  const textareaRef = useRef(null)

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
      // Tool-call trace rows (role="tool") are persisted as the exact same
      // {tool, input, output} shape a live /agent response returns in
      // tool_calls[] (see agent_service.py) -- re-parse them here and
      // re-attach to the assistant message that follows, so a reloaded
      // conversation can still render an EmailPreviewCard for an
      // unsent draft, not just its plain-text description.
      const reconstructed = []
      let pendingToolCalls = []
      for (const m of conversation.messages) {
        if (m.role === 'tool') {
          try {
            pendingToolCalls.push(JSON.parse(m.content))
          } catch {
            // malformed trace row -- drop it rather than crash the reload
          }
          continue
        }
        if (m.role !== 'user' && m.role !== 'assistant') continue
        const entry = { role: m.role, content: m.content, sources: m.sources, image: m.image }
        if (m.role === 'assistant' && pendingToolCalls.length > 0) {
          entry.toolCalls = pendingToolCalls
          pendingToolCalls = []
        }
        reconstructed.push(entry)
      }
      setMessages(reconstructed)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setError(null)
    setUploadingImage(true)
    try {
      // Reuses the existing Vision-tab upload+analyze endpoint unchanged --
      // the image also shows up under the Vision tab, this isn't a second
      // upload pipeline. `url` is normalized here (the endpoint returns
      // `image_url`) so both the just-sent bubble and a reloaded one
      // (MessageOut.image.url) read the same key.
      const result = await apiUpload(`/api/projects/${projectId}/vision`, file)
      setPendingImage({ id: result.id, filename: result.filename, url: result.image_url })
      // Pre-fill a default question so attaching alone is enough to send --
      // only when the user hasn't already started typing their own, so this
      // never clobbers real input.
      setInput((prev) => (prev.trim() ? prev : '請分析這張圖片'))
    } catch (err) {
      setError(err.message)
    } finally {
      setUploadingImage(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleSend = async (e) => {
    e.preventDefault()
    const question = input.trim()
    if (!question || sending) return

    const attachedImage = pendingImage
    setMessages((prev) => [...prev, { role: 'user', content: question, image: attachedImage }])
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    setPendingImage(null)
    setSending(true)
    setError(null)

    try {
      const response = await apiPost(`/api/projects/${projectId}/agent`, {
        conversation_id: conversationId,
        message: question,
        image_id: attachedImage?.id ?? null,
      })
      setConversationId(response.conversation_id)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: response.answer,
          sources: response.sources,
          toolCalls: response.tool_calls,
        },
      ])
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex h-full min-h-[28rem] gap-4">
      <ConversationList
        projectId={projectId}
        activeId={conversationId}
        onSelect={handleSelect}
        onNew={handleNew}
        refreshKey={refreshKey}
        mobileOpen={drawerOpen}
        onCloseMobile={() => setDrawerOpen(false)}
      />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col rounded-card border border-slate-200 bg-white">
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

        <div className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400">
              請 Agent 整理工程文件與圖片分析成會議摘要，或協助處理其他任務。
              Agent 會自行判斷需要搜尋文件、查看圖片分析，或整理摘要。
            </p>
          ) : (
            <div className="flex flex-col gap-4">
              {messages.map((msg, i) => (
                <div key={i} className={msg.role === 'user' ? 'text-right' : 'text-left'}>
                  {msg.toolCalls?.some((tc) => tc.tool !== 'draft_email') && (
                    <div className="mb-1.5 flex flex-col items-start gap-1">
                      {msg.toolCalls
                        .filter((tc) => tc.tool !== 'draft_email')
                        .map((tc, j) => (
                          <span
                            key={j}
                            className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-xs text-indigo-600"
                          >
                            <Wrench className="h-3 w-3" />
                            {tc.tool}
                            {tc.input && Object.keys(tc.input).length > 0 && (
                              <span className="text-indigo-400">
                                ({Object.values(tc.input).filter(Boolean).join(', ')})
                              </span>
                            )}
                          </span>
                        ))}
                    </div>
                  )}
                  {msg.toolCalls
                    ?.filter((tc) => tc.tool === 'draft_email')
                    .map((tc, j) => (
                      <div key={`email-${j}`} className="mb-2 inline-block">
                        <EmailPreviewCard projectId={projectId} draft={tc.output} />
                      </div>
                    ))}
                  <div
                    className={`flex flex-col gap-1.5 ${
                      msg.role === 'user' ? 'items-end' : 'items-start'
                    }`}
                  >
                    {msg.image?.url && (
                      <button
                        type="button"
                        onClick={() => setLightboxUrl(msg.image.url)}
                        aria-label="放大檢視圖片"
                      >
                        <img
                          src={msg.image.url}
                          alt={msg.image.filename}
                          className="h-28 w-28 rounded-card border border-slate-200 object-cover"
                        />
                      </button>
                    )}
                    {msg.role === 'user' ? (
                      <div className="max-w-[85%] rounded-card bg-brand-600 px-3 py-2 text-sm whitespace-pre-wrap text-white">
                        {msg.content}
                      </div>
                    ) : (
                      <div className="w-full text-slate-900">
                        <MarkdownContent content={msg.content} />
                      </div>
                    )}
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
              {sending && <Spinner label="Agent 思考中..." className="text-slate-500" />}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div className="mx-3 mb-3">
          {pendingImage && (
            <div className="mb-2 flex items-center gap-2 rounded-card border border-slate-200 bg-white px-2 py-1.5 shadow-card">
              <button
                type="button"
                onClick={() => setLightboxUrl(pendingImage.url)}
                aria-label="放大檢視圖片"
              >
                <img
                  src={pendingImage.url}
                  alt={pendingImage.filename}
                  className="h-10 w-10 rounded-card border border-slate-200 object-cover"
                />
              </button>
              <span className="truncate text-xs text-slate-500">{pendingImage.filename}</span>
              <button
                type="button"
                onClick={() => setPendingImage(null)}
                className="text-slate-400 hover:text-slate-600"
                aria-label="移除附加圖片"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
          <form
            onSubmit={handleSend}
            className="flex items-center gap-1 rounded-full border border-slate-300 bg-white py-1.5 pl-1.5 pr-1.5 shadow-card focus-within:border-brand-500"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleFileChange}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingImage}
              aria-label="附加圖片"
              className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-slate-500 transition-colors hover:bg-slate-100 disabled:opacity-50"
            >
              {uploadingImage ? <Spinner size="sm" /> : <Plus className="h-5 w-5" />}
            </button>
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
              placeholder="請 Agent 協助處理任務...（Shift+Enter 換行）"
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

      {lightboxUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 p-4"
          onClick={() => setLightboxUrl(null)}
        >
          <img src={lightboxUrl} alt="放大檢視" className="max-h-full max-w-full rounded-card" />
        </div>
      )}
    </div>
  )
}
