import { Activity as ActivityIcon, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apiGet } from '../lib/api'
import Alert from './Alert'
import EmptyState from './EmptyState'
import Spinner from './Spinner'

const EVENT_LABEL = {
  user_logged_in: '使用者登入',
  project_created: '建立專案',
  pdf_uploaded: '上傳 PDF',
  pdf_processing_completed: 'PDF 處理完成',
  embedding_generated: '產生向量嵌入',
  rag_search_executed: '執行文件檢索',
  vision_analysis_completed: '完成圖片分析',
  meeting_summary_generated: '產生會議摘要',
  email_draft_generated: '產生 Email 草稿',
  user_confirmed_email: '確認寄送 Email',
  email_sent: 'Email 已寄出',
}

function formatRelativeTime(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '剛剛'
  if (diffMin < 60) return `${diffMin} 分鐘前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} 小時前`
  return new Date(isoString).toLocaleString('zh-TW')
}

export default function ActivityPanel({ projectId }) {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    apiGet(`/api/projects/${projectId}/activity`)
      .then(setEvents)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [projectId])

  // Live-ish view for demo purposes -- polls continuously while the tab is
  // mounted, unlike DocumentsPanel's conditional polling, since there's no
  // "pending" state concept here to gate on.
  useEffect(() => {
    const timer = setInterval(load, 5000)
    return () => clearInterval(timer)
  }, [projectId])

  return (
    <div>
      {error && (
        <div className="mb-4">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-medium text-slate-700">Activity Log</h2>
        <button
          onClick={load}
          className="text-slate-400 hover:text-slate-700"
          aria-label="重新整理"
          title="重新整理"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner label="載入中..." className="text-slate-500" />
        </div>
      ) : events.length === 0 ? (
        <EmptyState
          icon={<ActivityIcon className="h-10 w-10" />}
          title="還沒有任何活動紀錄"
          description="上傳文件、提問、分析圖片或寄送 Email 後，這裡會顯示完整的工作流程紀錄。"
        />
      ) : (
        <ul className="divide-y divide-slate-200 rounded-card border border-slate-200 bg-white">
          {events.map((event) => (
            <li key={event.id} className="flex items-center justify-between gap-3 p-3 text-sm">
              <div className="flex min-w-0 items-center gap-2">
                <span className="font-medium text-slate-900">
                  {EVENT_LABEL[event.event_type] || event.event_type}
                </span>
                {event.detail && (
                  <span className="truncate text-slate-500">{event.detail}</span>
                )}
              </div>
              <span className="flex-shrink-0 text-xs text-slate-400">
                {formatRelativeTime(event.created_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
