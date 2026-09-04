import { AlertCircle, CheckCircle2, Info } from 'lucide-react'

const VARIANTS = {
  error: {
    wrap: 'border-red-200 bg-red-50 text-red-700',
    Icon: AlertCircle,
  },
  success: {
    wrap: 'border-green-200 bg-green-50 text-green-700',
    Icon: CheckCircle2,
  },
  info: {
    wrap: 'border-slate-200 bg-slate-50 text-slate-700',
    Icon: Info,
  },
}

export default function Alert({ variant = 'info', children }) {
  const { wrap, Icon } = VARIANTS[variant]

  return (
    <div className={`flex items-start gap-2 rounded-card border p-3 text-sm ${wrap}`}>
      <Icon className="mt-0.5 h-4 w-4 flex-shrink-0" />
      <span>{children}</span>
    </div>
  )
}
