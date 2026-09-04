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

export async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: await authHeader(),
  })
  await throwForStatus(res, `DELETE ${path} failed: ${res.status}`)
}
