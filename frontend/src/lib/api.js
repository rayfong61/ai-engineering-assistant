import { supabase } from './supabaseClient'

const API_BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

async function authHeader() {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function throwForStatus(res, fallbackMessage) {
  if (res.ok) return
  const body = await res.json().catch(() => null)
  throw new Error(body?.detail || fallbackMessage)
}

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { headers: await authHeader() })
  await throwForStatus(res, `GET ${path} failed: ${res.status}`)
  return res.json()
}

export async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeader()) },
    body: JSON.stringify(body),
  })
  await throwForStatus(res, `POST ${path} failed: ${res.status}`)
  return res.json()
}

// Consumes a text/event-stream response of `data: {...}\n\n` frames (see
// _sse() in backend/app/api/chat.py) and dispatches each parsed event to
// handlers[event.type]. Not EventSource -- that can't send a POST body or
// an Authorization header, so this reads the fetch body stream by hand.
export async function apiPostStream(path, body, handlers) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeader()) },
    body: JSON.stringify(body),
  })
  await throwForStatus(res, `POST ${path} failed: ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary
    while ((boundary = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const line = rawEvent.split('\n').find((l) => l.startsWith('data: '))
      if (!line) continue
      const event = JSON.parse(line.slice(6))
      handlers[event.type]?.(event)
    }
  }
}

export async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: await authHeader(),
  })
  await throwForStatus(res, `DELETE ${path} failed: ${res.status}`)
}

export async function apiUpload(path, file) {
  const formData = new FormData()
  formData.append('file', file)
  // No Content-Type header here -- the browser sets multipart/form-data
  // with the correct boundary itself; setting it manually breaks the parse.
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: await authHeader(),
    body: formData,
  })
  await throwForStatus(res, `POST ${path} failed: ${res.status}`)
  return res.json()
}
