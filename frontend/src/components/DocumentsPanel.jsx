import { FileText, Trash2, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { apiDelete, apiGet, apiUpload } from '../lib/api'
import Alert from './Alert'
import Badge from './Badge'
import Button from './Button'
import EmptyState from './EmptyState'
import Spinner from './Spinner'

const STATUS_TONE = {
  uploaded: 'neutral',
  processing: 'warning',
  ready: 'success',
  failed: 'danger',
}

const STATUS_LABEL = {
  uploaded: '已上傳',
  processing: '處理中',
  ready: '就緒',
  failed: '處理失敗',
}

export default function DocumentsPanel({ projectId }) {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  const load = () => {
    apiGet(`/api/projects/${projectId}/documents`)
      .then(setDocuments)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [projectId])

  // Ingestion runs in the background after upload -- poll while any
  // document is still uploaded/processing so status flips to ready/failed
  // without the user having to refresh.
  useEffect(() => {
    const pending = documents.some((d) => d.status === 'uploaded' || d.status === 'processing')
    if (!pending) return
    const timer = setInterval(load, 3000)
    return () => clearInterval(timer)
  }, [documents, projectId])

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setError(null)
    setUploading(true)
    try {
      await apiUpload(`/api/projects/${projectId}/documents`, file)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDelete = async (document) => {
    if (!window.confirm(`確定要刪除「${document.filename}」嗎？`)) return
    try {
      await apiDelete(`/api/projects/${projectId}/documents/${document.id}`)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      {error && (
        <div className="mb-4">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      <div className="mb-4">
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          onChange={handleFileChange}
          className="hidden"
          id="pdf-upload-input"
        />
        <Button
          variant="secondary"
          icon={<Upload className="h-4 w-4" />}
          loading={uploading}
          onClick={() => fileInputRef.current?.click()}
        >
          上傳 PDF
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner label="載入中..." className="text-slate-500" />
        </div>
      ) : documents.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-10 w-10" />}
          title="還沒有任何文件"
          description="上傳工程 PDF，開始建立這個專案的知識庫。"
        />
      ) : (
        <ul className="divide-y divide-slate-200 rounded-card border border-slate-200 bg-white">
          {documents.map((doc) => (
            <li key={doc.id} className="flex items-center justify-between gap-3 p-4">
              <div className="flex min-w-0 items-center gap-3">
                <FileText className="h-5 w-5 flex-shrink-0 text-slate-400" />
                <span className="truncate text-sm text-slate-900">{doc.filename}</span>
              </div>
              <div className="flex flex-shrink-0 items-center gap-3">
                <Badge tone={STATUS_TONE[doc.status] || 'neutral'}>
                  {STATUS_LABEL[doc.status] || doc.status}
                </Badge>
                <button
                  onClick={() => handleDelete(doc)}
                  className="text-slate-400 hover:text-red-600"
                  aria-label="刪除文件"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
