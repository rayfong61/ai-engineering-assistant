import { useEffect, useState } from 'react'
import { apiGet } from '../lib/api'
import { supabase } from '../lib/supabaseClient'

export function useSession() {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })

    const { data: listener } = supabase.auth.onAuthStateChange((event, newSession) => {
      setSession(newSession)
      if (event === 'SIGNED_IN') {
        // Fire-and-forget: this call exists purely to record the
        // user_logged_in Activity Log event (spec2.md section 29) --
        // login itself is entirely client-side via Supabase Auth, so the
        // backend otherwise never learns a login happened.
        apiGet('/api/auth/me').catch(() => {})
      }
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  return { session, loading }
}
