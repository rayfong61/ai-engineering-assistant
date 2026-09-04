import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card from '../components/Card'
import Input from '../components/Input'
import { supabase } from '../lib/supabaseClient'

function GoogleIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24">
      <path
        fill="#4285F4"
        d="M23.52 12.27c0-.85-.08-1.66-.22-2.44H12v4.62h6.47a5.53 5.53 0 0 1-2.4 3.63v3h3.88c2.27-2.09 3.57-5.17 3.57-8.81z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.96-1.07 7.95-2.92l-3.88-3c-1.08.72-2.45 1.15-4.07 1.15-3.13 0-5.78-2.11-6.73-4.96H1.27v3.11A12 12 0 0 0 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.27a7.2 7.2 0 0 1 0-4.54v-3.1H1.27a12 12 0 0 0 0 10.75l4-3.11z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.44-3.44C17.95 1.19 15.24 0 12 0A12 12 0 0 0 1.27 6.63l4 3.1C6.22 6.86 8.87 4.75 12 4.75z"
      />
    </svg>
  )
}

export default function Login() {
  const navigate = useNavigate()
  const [mode, setMode] = useState('login') // 'login' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)
  const [submitting, setSubmitting] = useState(false)

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
    setSubmitting(true)
    try {
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
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <h1 className="mb-1 text-center text-xl font-semibold text-slate-900">
          AI Engineering Assistant
        </h1>
        <p className="mb-6 text-center text-sm text-slate-500">
          工程文件 RAG × Vision × Agent 助理
        </p>

        <Button
          onClick={handleGoogleLogin}
          variant="primary"
          size="lg"
          icon={<GoogleIcon />}
          className="w-full mb-6"
        >
          使用 Google 登入
        </Button>

        <div className="mb-4 flex items-center gap-3 text-sm text-slate-400">
          <div className="flex-1 border-t border-slate-200" />
          <span>本地開發用（Email / Password）</span>
          <div className="flex-1 border-t border-slate-200" />
        </div>

        <form onSubmit={handleEmailAuth} className="space-y-3">
          <Input
            type="email"
            required
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input
            type="password"
            required
            minLength={6}
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <Alert variant="error">{error}</Alert>}
          {info && <Alert variant="success">{info}</Alert>}
          <Button type="submit" variant="secondary" size="sm" loading={submitting} className="w-full">
            {mode === 'signup' ? '註冊' : '登入'}
          </Button>
        </form>

        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => {
            setMode(mode === 'signup' ? 'login' : 'signup')
            setError(null)
            setInfo(null)
          }}
          className="mt-3 w-full"
        >
          {mode === 'signup' ? '已有帳號？改用登入' : '沒有帳號？改用註冊'}
        </Button>
      </Card>
    </div>
  )
}
