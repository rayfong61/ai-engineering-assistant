import { Mail } from 'lucide-react'
import { useState } from 'react'
import { apiPost } from '../lib/api'
import Alert from './Alert'
import Badge from './Badge'
import Button from './Button'
import Card from './Card'

const STATUS_TONE = { draft: 'neutral', sending: 'warning', sent: 'success', failed: 'danger' }
const STATUS_LABEL = { draft: '草稿', sending: '寄送中...', sent: '已寄出', failed: '寄送失敗' }

// spec2.md section 25's exact layout: To/Subject/Body, then Cancel /
// Confirm & Send. Never auto-sends -- section 24's human-in-the-loop rule --
// the send only happens from this component's own explicit button click.
export default function EmailPreviewCard({ projectId, draft }) {
  const [status, setStatus] = useState(draft.status)
  const [dismissed, setDismissed] = useState(false)
  const [error, setError] = useState(null)

  if (dismissed) return null

  const handleSend = async () => {
    setStatus('sending')
    setError(null)
    try {
      const result = await apiPost(`/api/projects/${projectId}/email/send`, {
        email_log_id: draft.email_log_id,
      })
      setStatus(result.status)
      if (result.status !== 'sent') {
        setError('寄送未成功，請稍後再試一次。')
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
          <Mail className="h-4 w-4" />
          Email Preview
        </div>
        <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>
      </div>

      <dl className="space-y-1.5 text-sm">
        <div>
          <dt className="inline text-slate-500">To: </dt>
          <dd className="inline break-all text-slate-900">{draft.to}</dd>
        </div>
        <div>
          <dt className="inline text-slate-500">Subject: </dt>
          <dd className="inline break-words text-slate-900">{draft.subject}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Body:</dt>
          <dd className="mt-0.5 whitespace-pre-wrap text-slate-900">{draft.body}</dd>
        </div>
      </dl>

      {error && (
        <div className="mt-2">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      {status !== 'sent' && (
        <div className="mt-3 flex justify-end gap-2">
          <Button
            variant="ghost"
            size="sm"
            disabled={status === 'sending'}
            onClick={() => setDismissed(true)}
          >
            Cancel
          </Button>
          <Button variant="primary" size="sm" loading={status === 'sending'} onClick={handleSend}>
            Confirm & Send
          </Button>
        </div>
      )}
    </Card>
  )
}
