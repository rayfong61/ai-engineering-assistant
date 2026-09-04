import { Loader2 } from 'lucide-react'

const SIZES = {
  sm: 'h-4 w-4',
  md: 'h-6 w-6',
  lg: 'h-8 w-8',
}

export default function Spinner({ size = 'md', label, className = '' }) {
  // No default text color here — it inherits currentColor from context
  // (white inside a primary Button, slate-500 when callers pass that
  // explicitly for a standalone page-loading state). Baking in a default
  // would fight with a caller's color via Tailwind's unordered specificity.
  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      <Loader2 className={`animate-spin ${SIZES[size]}`} />
      {label && <span className="text-sm">{label}</span>}
    </div>
  )
}
