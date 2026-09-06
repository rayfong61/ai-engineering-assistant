import { FolderOpen, LogOut, Plus, Settings as SettingsIcon, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card from '../components/Card'
import EmptyState from '../components/EmptyState'
import Input from '../components/Input'
import PageShell from '../components/PageShell'
import Spinner from '../components/Spinner'
import { apiDelete, apiGet, apiPost } from '../lib/api'
import { supabase } from '../lib/supabaseClient'

export default function Projects() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [error, setError] = useState(null)
  const [creating, setCreating] = useState(false)
  const creatingRef = useRef(false) // synchronous guard — state alone can lag a fast double-click

  const load = () => {
    apiGet('/api/projects')
      .then(setProjects)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!name.trim() || creatingRef.current) return
    creatingRef.current = true
    setCreating(true)
    setError(null)
    try {
      await apiPost('/api/projects', { name, description: '' })
      setName('')
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      creatingRef.current = false
      setCreating(false)
    }
  }

  const handleDelete = async (e, project) => {
    e.stopPropagation() // the button sits inside a card that navigates on click
    if (!window.confirm(`確定要刪除「${project.name}」嗎？底下的文件與對話也會一併刪除，無法復原。`)) {
      return
    }
    try {
      await apiDelete(`/api/projects/${project.id}`)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleLogout = async () => {
    await supabase.auth.signOut()
    navigate('/login')
  }

  return (
    <PageShell
      headerActions={
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            icon={<SettingsIcon className="h-4 w-4" />}
            onClick={() => navigate('/settings')}
          >
            設定
          </Button>
          <Button variant="ghost" size="sm" icon={<LogOut className="h-4 w-4" />} onClick={handleLogout}>
            登出
          </Button>
        </div>
      }
    >
      <h1 className="mb-4 text-xl font-semibold text-slate-900">我的專案</h1>

      {error && (
        <div className="mb-4">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      <form onSubmit={handleCreate} className="mb-6 flex gap-2">
        <div className="flex-1">
          <Input placeholder="專案名稱" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <Button
          type="submit"
          loading={creating}
          icon={<Plus className="h-4 w-4" />}
          className="shrink-0 whitespace-nowrap"
        >
          建立
        </Button>
      </form>

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner label="載入中..." className="text-slate-500" />
        </div>
      ) : projects.length === 0 ? (
        <EmptyState
          icon={<FolderOpen className="h-10 w-10" />}
          title="還沒有任何專案"
          description="建立第一個專案，開始上傳工程文件。"
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <Card
              key={p.id}
              hover
              className="relative cursor-pointer"
              onClick={() => navigate(`/projects/${p.id}`)}
            >
              <p className="pr-8 font-medium text-slate-900">{p.name}</p>
              {p.description && <p className="mt-1 text-sm text-slate-500">{p.description}</p>}
              <button
                onClick={(e) => handleDelete(e, p)}
                className="absolute right-4 top-4 text-slate-400 hover:text-red-600"
                aria-label="刪除專案"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </Card>
          ))}
        </div>
      )}
    </PageShell>
  )
}
