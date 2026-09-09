import { Calendar } from 'lucide-react'
import { useState } from 'react'
import { apiPost } from '../lib/api'
import Alert from './Alert'
import Badge from './Badge'
import Button from './Button'
import Card from './Card'

const STATUS_TONE = { draft: 'neutral', creating: 'warning', created: 'success', failed: 'danger' }
const STATUS_LABEL = { draft: '草稿', creating: '建立中...', created: '已建立', failed: '建立失敗' }

function formatRange(start, end) {
  try {
    const fmt = (d) => new Date(d).toLocaleString('zh-TW', { dateStyle: 'medium', timeStyle: 'short' })
    return `${fmt(start)} - ${fmt(end)}`
  } catch {
    return `${start} - ${end}`
  }
}

// Mirrors EmailPreviewCard.jsx's exact layout/state machine -- Confirm &
// Create instead of Confirm & Send. Never auto-creates -- the create only
// happens from this component's own explicit button click.
export default function CalendarEventPreviewCard({ projectId, draft }) {
  const [status, setStatus] = useState(draft.status)
  const [dismissed, setDismissed] = useState(false)
  const [error, setError] = useState(null)

  if (dismissed) return null

  const handleCreate = async () => {
    setStatus('creating')
    setError(null)
    try {
      const result = await apiPost(`/api/projects/${projectId}/calendar-events/create`, {
        calendar_event_log_id: draft.calendar_event_log_id,
      })
      setStatus(result.status)
      if (result.status !== 'created') {
        setError('建立失敗，請稍後再試一次。')
      }
    } catch (err) {
      setStatus('failed')
      setError(err.message)
    }
  }

  return (
    <Card className="max-w-md p-4 text-left">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-sm font-medium text-slate-900">
          <Calendar className="h-4 w-4" />
          Calendar Event Preview
        </div>
        <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>
      </div>

      <dl className="space-y-1.5 text-sm">
        <div>
          <dt className="inline text-slate-500">Summary: </dt>
          <dd className="inline break-words text-slate-900">{draft.summary}</dd>
        </div>
        <div>
          <dt className="inline text-slate-500">Time: </dt>
          <dd className="inline text-slate-900">{formatRange(draft.start_datetime, draft.end_datetime)}</dd>
        </div>
        {draft.description && (
          <div>
            <dt className="text-slate-500">Description:</dt>
            <dd className="mt-0.5 whitespace-pre-wrap text-slate-900">{draft.description}</dd>
          </div>
        )}
        {draft.attendees?.length > 0 && (
          <div>
            <dt className="inline text-slate-500">Attendees: </dt>
            <dd className="inline break-all text-slate-900">{draft.attendees.join(', ')}</dd>
          </div>
        )}
      </dl>

      {error && (
        <div className="mt-2">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      {status !== 'created' && (
        <div className="mt-3 flex justify-end gap-2">
          <Button variant="ghost" size="sm" disabled={status === 'creating'} onClick={() => setDismissed(true)}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" loading={status === 'creating'} onClick={handleCreate}>
            Confirm & Create
          </Button>
        </div>
      )}
    </Card>
  )
}
