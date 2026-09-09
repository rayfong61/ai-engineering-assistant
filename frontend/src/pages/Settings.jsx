import { ArrowLeft, Mail, MailCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Alert from '../components/Alert'
import Badge from '../components/Badge'
import Button from '../components/Button'
import Card from '../components/Card'
import PageShell from '../components/PageShell'
import Spinner from '../components/Spinner'
import { apiGet, apiPost } from '../lib/api'

export default function Settings() {
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(searchParams.get('gmail') === 'error' ? 'Gmail 連接失敗，請再試一次。' : null)
  const [connecting, setConnecting] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)

  const loadStatus = () => {
    setLoading(true)
    apiGet('/api/gmail/status')
      .then(setStatus)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadStatus, [])

  const handleConnect = async () => {
    setConnecting(true)
    setError(null)
    try {
      const { url } = await apiGet('/api/gmail/authorize-url')
      window.location.href = url // full-page navigation -- Google requires a top-level redirect
    } catch (e) {
      setError(e.message)
      setConnecting(false)
    }
  }

  const handleDisconnect = async () => {
    if (!window.confirm('確定要中斷 Google 帳號連接嗎？之後寄信與建立日曆事件都會失敗，直到重新連接。')) return
    setDisconnecting(true)
    setError(null)
    try {
      await apiPost('/api/gmail/disconnect', {})
      loadStatus()
    } catch (e) {
      setError(e.message)
    } finally {
      setDisconnecting(false)
    }
  }

  return (
    <PageShell>
      <Link
        to="/projects"
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft className="h-4 w-4" />
        我的專案
      </Link>

      <h1 className="mb-4 text-xl font-semibold text-slate-900">帳號設定</h1>

      {error && (
        <div className="mb-4">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      <Card>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            {status?.connected ? (
              <MailCheck className="mt-0.5 h-5 w-5 text-green-600" />
            ) : (
              <Mail className="mt-0.5 h-5 w-5 text-slate-400" />
            )}
            <div>
              <p className="font-medium text-slate-900">Google 帳號授權（Gmail 寄信 + Calendar 建立事件）</p>
              <p className="mt-1 text-sm text-slate-500">
                連接 Google 帳號後，Agent 起草的 Email 在你按下「Confirm &amp; Send」時會透過 Gmail API
                真實寄出；Agent 起草的日曆事件在你按下「Confirm &amp; Create」時會透過 Google Calendar
                API 真實建立。這是獨立於登入用的 Google 帳號授權，僅要求 gmail.send 與
                calendar.events 權限。若你在此權限擴充之前就已連接過，請先「中斷連接」再重新連接，
                才能一併取得 Calendar 權限（Google 不會自動把新權限套用到舊的連接）。
              </p>
              {loading ? (
                <div className="mt-3">
                  <Spinner size="sm" label="載入中..." className="text-slate-500" />
                </div>
              ) : (
                status && (
                  <div className="mt-3">
                    {status.connected ? (
                      <Badge tone="success">
                        已連接{status.gmail_email ? ` — ${status.gmail_email}` : ''}
                      </Badge>
                    ) : (
                      <Badge tone="neutral">尚未連接</Badge>
                    )}
                  </div>
                )
              )}
            </div>
          </div>

          {!loading && status && (
            <div className="shrink-0">
              {status.connected ? (
                <Button variant="danger" size="sm" loading={disconnecting} onClick={handleDisconnect}>
                  中斷連接
                </Button>
              ) : (
                <Button size="sm" loading={connecting} onClick={handleConnect}>
                  連接 Google 帳號
                </Button>
              )}
            </div>
          )}
        </div>
      </Card>
    </PageShell>
  )
}
