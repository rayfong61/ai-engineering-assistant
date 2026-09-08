import { HelpCircle, LogOut, Settings as SettingsIcon } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabaseClient'
import Button from './Button'
import HelpModal from './HelpModal'

export default function HeaderActions() {
  const navigate = useNavigate()
  const [helpOpen, setHelpOpen] = useState(false)

  const handleLogout = async () => {
    await supabase.auth.signOut()
    navigate('/login')
  }

  return (
    <>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          icon={<HelpCircle className="h-4 w-4" />}
          onClick={() => setHelpOpen(true)}
        >
          <span className="sr-only sm:not-sr-only">使用說明</span>
        </Button>
        <Button
          variant="ghost"
          size="sm"
          icon={<SettingsIcon className="h-4 w-4" />}
          onClick={() => navigate('/settings')}
        >
          <span className="sr-only sm:not-sr-only">設定</span>
        </Button>
        <Button variant="ghost" size="sm" icon={<LogOut className="h-4 w-4" />} onClick={handleLogout}>
          <span className="sr-only sm:not-sr-only">登出</span>
        </Button>
      </div>
      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </>
  )
}
