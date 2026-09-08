import { Activity, ArrowLeft, Bot, FileText, Image, MessageSquare } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ActivityPanel from '../components/ActivityPanel'
import AgentPanel from '../components/AgentPanel'
import ChatPanel from '../components/ChatPanel'
import DocumentsPanel from '../components/DocumentsPanel'
import HeaderActions from '../components/HeaderActions'
import PageShell from '../components/PageShell'
import Spinner from '../components/Spinner'
import Tabs from '../components/Tabs'
import VisionPanel from '../components/VisionPanel'
import { apiGet } from '../lib/api'

const TABS = [
  { key: 'documents', label: 'Documents', icon: FileText },
  { key: 'chat', label: 'Chat', icon: MessageSquare },
  { key: 'vision', label: 'Vision', icon: Image },
  { key: 'agent', label: 'Agent', icon: Bot },
  { key: 'activity', label: 'Activity', icon: Activity },
]

export default function ProjectDetail() {
  const { id } = useParams()
  const [project, setProject] = useState(null)
  const [tab, setTab] = useState('documents')

  useEffect(() => {
    apiGet(`/api/projects/${id}`).then(setProject)
  }, [id])

  return (
    <PageShell
      headerActions={<HeaderActions />}
      subNav={project && <Tabs tabs={TABS} activeKey={tab} onChange={setTab} />}
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
          <div hidden={tab !== 'activity'}>
            <ActivityPanel projectId={id} />
          </div>
        </>
      )}
    </PageShell>
  )
}
