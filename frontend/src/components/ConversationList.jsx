import { Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apiDelete, apiGet } from '../lib/api'

export default function ConversationList({ projectId, activeId, onSelect, onNew, refreshKey }) {
  const [conversations, setConversations] = useState([])

  useEffect(() => {
    apiGet(`/api/projects/${projectId}/conversations`)
      .then(setConversations)
      .catch(() => {}) // sidebar failing to load isn't worth its own error banner
  }, [projectId, refreshKey])

  const handleDelete = async (e, conversation) => {
    e.stopPropagation() // the button sits inside a row that selects on click
    if (!window.confirm(`確定要刪除「${conversation.title || '這個對話'}」嗎？`)) return
    try {
      await apiDelete(`/api/conversations/${conversation.id}`)
      setConversations((prev) => prev.filter((c) => c.id !== conversation.id))
      if (conversation.id === activeId) onNew()
    } catch {
      // best-effort -- the row stays if delete failed, user can retry
    }
  }

  return (
    <aside className="flex w-56 flex-shrink-0 flex-col gap-2 overflow-y-auto rounded-card border border-slate-200 bg-white p-2">
      <button
        onClick={onNew}
        className="flex items-center gap-2 rounded-card px-3 py-2 text-left text-sm font-medium text-brand-600 hover:bg-slate-50"
      >
        <Plus className="h-4 w-4" />
        新對話
      </button>

      {conversations.length === 0 ? (
        <p className="px-3 py-2 text-sm text-slate-400">還沒有對話</p>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {conversations.map((c) => (
            <li
              key={c.id}
              className={`group flex items-center gap-1 rounded-card ${
                c.id === activeId ? 'bg-brand-50' : 'hover:bg-slate-50'
              }`}
            >
              <button
                onClick={() => onSelect(c.id)}
                className={`min-w-0 flex-1 truncate px-3 py-2 text-left text-sm ${
                  c.id === activeId ? 'text-brand-700' : 'text-slate-700'
                }`}
              >
                {c.title || '（無標題對話）'}
              </button>
              <button
                onClick={(e) => handleDelete(e, c)}
                className="mr-1 flex-shrink-0 text-slate-300 opacity-0 hover:text-red-600 group-hover:opacity-100"
                aria-label="刪除對話"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
