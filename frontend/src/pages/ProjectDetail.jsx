import { Activity, ArrowLeft, FileText, Image, LogOut, MessageSquare } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Button from '../components/Button'
import PageShell from '../components/PageShell'
import Spinner from '../components/Spinner'
import Tabs from '../components/Tabs'
import { apiGet } from '../lib/api'
import { supabase } from '../lib/supabaseClient'

const TABS = [
  { key: 'documents', label: 'Documents', icon: FileText, placeholder: '文件上傳與 RAG 問答將在 Day 2 加入。' },
  { key: 'chat', label: 'Chat', icon: MessageSquare, placeholder: '對話功能將在 Day 2 加入。' },
  { key: 'vision', label: 'Vision', icon: Image, placeholder: '工程圖片分析將在 Day 3 加入。' },
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
          <p className="text-slate-500">{TABS.find((t) => t.key === tab)?.placeholder}</p>
        </>
      )}
    </PageShell>
  )
}
