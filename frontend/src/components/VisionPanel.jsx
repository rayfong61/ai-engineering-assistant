import { Image as ImageIcon, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { apiGet, apiUpload } from '../lib/api'
import Alert from './Alert'
import Button from './Button'
import EmptyState from './EmptyState'
import Spinner from './Spinner'

export default function VisionPanel({ projectId }) {
  const [analyses, setAnalyses] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  const load = () => {
    apiGet(`/api/projects/${projectId}/vision`)
      .then(setAnalyses)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [projectId])

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setError(null)
    setUploading(true)
    try {
      // Synchronous: a single Claude Vision call takes a few seconds, unlike
      // document ingestion's multi-minute rate-limited embedding batch job --
      // no background task / polling needed here, the response already has
      // the final analysis.
      await apiUpload(`/api/projects/${projectId}/vision`, file)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
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
          accept="image/jpeg,image/png,image/webp"
          onChange={handleFileChange}
          className="hidden"
          id="image-upload-input"
        />
        <Button
          variant="secondary"
          icon={<Upload className="h-4 w-4" />}
          loading={uploading}
          onClick={() => fileInputRef.current?.click()}
        >
          {uploading ? '分析中...' : '上傳工程圖片'}
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner label="載入中..." className="text-slate-500" />
        </div>
      ) : analyses.length === 0 ? (
        <EmptyState
          icon={<ImageIcon className="h-10 w-10" />}
          title="還沒有任何圖片分析"
          description="上傳工程圖片（JPG/PNG/WEBP），由 Claude Vision 產生初步分析。"
        />
      ) : (
        <ul className="space-y-3">
          {analyses.map((item) => (
            <li key={item.id} className="rounded-card border border-slate-200 bg-white p-4">
              <div className="mb-2 flex items-center gap-2">
                <ImageIcon className="h-4 w-4 flex-shrink-0 text-slate-400" />
                <span className="truncate text-sm font-medium text-slate-900">{item.filename}</span>
              </div>
              <p className="mb-3 text-sm text-slate-700">{item.analysis}</p>

              {item.observations?.length > 0 && (
                <div className="mb-2">
                  <p className="mb-1 text-xs font-semibold text-slate-500">可觀察到</p>
                  <ul className="list-inside list-disc space-y-0.5 text-sm text-slate-600">
                    {item.observations.map((obs, i) => (
                      <li key={i}>{obs}</li>
                    ))}
                  </ul>
                </div>
              )}

              {item.limitations?.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold text-amber-600">限制／需人工確認</p>
                  <ul className="list-inside list-disc space-y-0.5 text-sm text-amber-700">
                    {item.limitations.map((lim, i) => (
                      <li key={i}>{lim}</li>
                    ))}
                  </ul>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
