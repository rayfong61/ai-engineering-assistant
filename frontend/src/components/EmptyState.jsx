export default function EmptyState({ icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-card border border-dashed border-slate-300 p-12 text-center">
      {icon && <div className="mb-2 text-slate-400">{icon}</div>}
      <p className="font-medium text-slate-700">{title}</p>
      {description && <p className="text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}
