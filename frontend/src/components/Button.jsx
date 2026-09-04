import Spinner from './Spinner'

const BASE =
  'inline-flex items-center justify-center gap-2 rounded-card font-medium transition-colors ' +
  'disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 ' +
  'focus-visible:ring-offset-2'

const VARIANTS = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 focus-visible:ring-brand-500',
  secondary:
    'border border-slate-300 text-slate-700 bg-white hover:bg-slate-50 focus-visible:ring-brand-500',
  ghost: 'text-slate-500 hover:text-slate-700 hover:bg-slate-100 focus-visible:ring-slate-400',
  danger: 'text-red-600 hover:bg-red-50 focus-visible:ring-red-500',
}

const SIZES = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-4 py-2.5 text-base',
}

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon = null,
  disabled = false,
  className = '',
  children,
  ...props
}) {
  return (
    <button
      disabled={disabled || loading}
      className={`${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {loading ? <Spinner size="sm" className="text-current" /> : icon}
      {children}
    </button>
  )
}
