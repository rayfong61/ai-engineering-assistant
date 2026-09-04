import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabaseClient'

export default function Login() {
  const navigate = useNavigate()
  const [mode, setMode] = useState('login') // 'login' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)

  const handleGoogleLogin = () => {
    supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/projects` },
    })
  }

  const handleEmailAuth = async (e) => {
    e.preventDefault()
    setError(null)
    setInfo(null)

    const { data, error: authError } =
      mode === 'signup'
        ? await supabase.auth.signUp({ email, password })
        : await supabase.auth.signInWithPassword({ email, password })

    if (authError) {
      setError(authError.message)
      return
    }

    if (data.session) {
      navigate('/projects')
      return
    }

    // No session yet (e.g. email confirmation required on this project) —
    // let the user know instead of leaving the form looking unresponsive.
    setInfo(mode === 'signup' ? '註冊成功，請確認 email 後再登入。' : '請先確認 email 後再登入。')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white shadow rounded-lg p-8 w-full max-w-sm">
        <h1 className="text-xl font-semibold mb-6 text-center">AI Engineering Assistant</h1>

        <button
          onClick={handleGoogleLogin}
          className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 mb-6"
        >
          使用 Google 登入
        </button>

        <div className="flex items-center gap-3 mb-6 text-gray-400 text-sm">
          <div className="flex-1 border-t" />
          <span>本地開發用（Email / Password）</span>
          <div className="flex-1 border-t" />
        </div>

        <form onSubmit={handleEmailAuth} className="space-y-3">
          <input
            type="email"
            required
            placeholder="Email"
            className="w-full border rounded px-3 py-2"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            type="password"
            required
            minLength={6}
            placeholder="Password"
            className="w-full border rounded px-3 py-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <p className="text-red-600 text-sm">{error}</p>}
          {info && <p className="text-green-600 text-sm">{info}</p>}
          <button
            type="submit"
            className="w-full px-4 py-2 border border-blue-600 text-blue-600 rounded hover:bg-blue-50"
          >
            {mode === 'signup' ? '註冊' : '登入'}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode(mode === 'signup' ? 'login' : 'signup')
            setError(null)
            setInfo(null)
          }}
          className="mt-3 text-sm text-gray-500 hover:underline w-full text-center"
        >
          {mode === 'signup' ? '已有帳號？改用登入' : '沒有帳號？改用註冊'}
        </button>
      </div>
    </div>
  )
}
