export default function Tabs({ tabs, activeKey, onChange }) {
  return (
    <div className="mb-4 flex gap-4 border-b border-slate-200">
      {tabs.map(({ key, label, icon: Icon }) => {
        const active = key === activeKey
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={`flex items-center gap-1.5 border-b-2 pb-2 text-sm font-medium transition-colors ${
              active
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            {Icon && <Icon className="h-4 w-4" />}
            {label}
          </button>
        )
      })}
    </div>
  )
}
