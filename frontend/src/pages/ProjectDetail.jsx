import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiGet } from '../lib/api'

export default function ProjectDetail() {
  const { id } = useParams()
  const [project, setProject] = useState(null)

  useEffect(() => {
    apiGet(`/api/projects/${id}`).then(setProject)
  }, [id])

  if (!project) return <div className="p-8">載入中...</div>

  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-xl font-semibold mb-4">{project.name}</h1>
      <div className="border-b flex gap-4 mb-4 text-gray-500">
        <span className="pb-2 border-b-2 border-blue-600 text-blue-600">Documents</span>
        <span className="pb-2">Chat</span>
        <span className="pb-2">Vision</span>
        <span className="pb-2">Activity</span>
      </div>
      <p className="text-gray-500">文件上傳、RAG 問答、圖片分析將在後續階段加入。</p>
    </div>
  )
}
