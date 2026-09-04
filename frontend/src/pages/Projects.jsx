import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPost } from '../lib/api'

export default function Projects() {
  const [projects, setProjects] = useState([])
  const [name, setName] = useState('')
  const [error, setError] = useState(null)

  const load = () => {
    apiGet('/api/projects').then(setProjects).catch((e) => setError(e.message))
  }

  useEffect(load, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    await apiPost('/api/projects', { name, description: '' })
    setName('')
    load()
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-xl font-semibold mb-4">我的專案</h1>
      {error && <p className="text-red-600 mb-2">{error}</p>}
      <form onSubmit={handleCreate} className="flex gap-2 mb-6">
        <input
          className="border rounded px-3 py-2 flex-1"
          placeholder="專案名稱"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button className="px-4 py-2 bg-blue-600 text-white rounded">建立</button>
      </form>
      <ul className="space-y-2">
        {projects.map((p) => (
          <li key={p.id}>
            <Link to={`/projects/${p.id}`} className="text-blue-600 hover:underline">
              {p.name}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
