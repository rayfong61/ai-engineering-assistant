import { Activity, ArrowLeft, Bot, FileText, Image, LogOut, MessageSquare } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import AgentPanel from '../components/AgentPanel'
import Button from '../components/Button'
import ChatPanel from '../components/ChatPanel'
import DocumentsPanel from '../components/DocumentsPanel'
import PageShell from '../components/PageShell'
import Spinner from '../components/Spinner'
import Tabs from '../components/Tabs'
import VisionPanel from '../components/VisionPanel'
import { apiGet } from '../lib/api'
import { supabase } from '../lib/supabaseClient'

const TABS = [
  { key: 'documents', label: 'Documents', icon: FileText },
  { key: 'chat', label: 'Chat', icon: MessageSquare },
  { key: 'vision', label: 'Vision', icon: Image },
  { key: 'agent', label: 'Agent', icon: Bot },
  { key: 'activity', label: 'Activity', icon: Activity, placeholder: 'Activity Log 將在 Day 5 加入。' },
]

export default function ProjectDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [project, setProject] = useState(null)
  const [tab, setTab] = useState('documents')

  useEffect(() => {
    apiGet(`/api/projects/${id}`).then(setProject)
  }, [id])

  const handleLogout = async () => {
    await supabase.auth.signOut()
    navigate('/login')
  }

  return (
    <PageShell
      headerActions={
        <Button variant="ghost" size="sm" icon={<LogOut className="h-4 w-4" />} onClick={handleLogout}>
          登出
        </Button>
      }
    >
      <Link
        to="/projects"
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft className="h-4 w-4" />
        我的專案
      </Link>

      {!project ? (
        <div className="flex justify-center py-12">
          <Spinner label="載入中..." className="text-slate-500" />
        </div>
      ) : (
        <>
          <h1 className="mb-4 text-xl font-semibold text-slate-900">{project.name}</h1>
          <Tabs tabs={TABS} activeKey={tab} onChange={setTab} />

          {/* Hidden via CSS rather than unmounted on tab switch -- keeping
              these mounted preserves ChatPanel's in-progress conversation
              and DocumentsPanel's polling instead of resetting on every
              switch back to the tab. */}
          <div hidden={tab !== 'documents'}>
            <DocumentsPanel projectId={id} />
          </div>
          <div hidden={tab !== 'chat'}>
            <ChatPanel projectId={id} />
          </div>
          <div hidden={tab !== 'vision'}>
            <VisionPanel projectId={id} />
          </div>
          <div hidden={tab !== 'agent'}>
            <AgentPanel projectId={id} />
          </div>
          {tab === 'activity' && (
            <p className="text-slate-500">{TABS.find((t) => t.key === tab)?.placeholder}</p>
          )}
        </>
      )}
    </PageShell>
  )
}
