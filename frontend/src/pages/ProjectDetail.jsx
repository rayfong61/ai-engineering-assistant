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
      subNav={
        project && (
          <div className="flex items-center justify-between gap-3">
            <Tabs tabs={TABS} activeKey={tab} onChange={setTab} />
            <div className="flex flex-shrink-0 items-center gap-3 py-2">
              <Link
                to="/projects"
                className="inline-flex items-center gap-1 whitespace-nowrap text-sm text-slate-500 hover:text-slate-700"
              >
                <ArrowLeft className="h-4 w-4" />
                我的專案
              </Link>
              <span className="hidden h-4 w-px bg-slate-200 sm:block" />
              <h1 className="max-w-[8rem] truncate text-sm font-semibold text-slate-900 sm:max-w-none sm:text-base">
                {project.name}
              </h1>
            </div>
          </div>
        )
      }
    >
      {!project ? (
        <div className="flex justify-center py-12">
          <Spinner label="載入中..." className="text-slate-500" />
        </div>
      ) : (
        <>
          {/* Hidden via CSS rather than unmounted on tab switch -- keeping
              these mounted preserves ChatPanel's in-progress conversation
              and DocumentsPanel's polling instead of resetting on every
              switch back to the tab. */}
          <div hidden={tab !== 'documents'}>
            <DocumentsPanel projectId={id} />
          </div>
          <div hidden={tab !== 'chat'} className="h-full">
            <ChatPanel projectId={id} />
          </div>
          <div hidden={tab !== 'vision'}>
            <VisionPanel projectId={id} />
          </div>
          <div hidden={tab !== 'agent'} className="h-full">
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
