export default function Tabs({ tabs, activeKey, onChange }) {
  return (
    <div className="scrollbar-none flex min-w-0 flex-1 gap-6 overflow-x-auto sm:gap-4 [-webkit-overflow-scrolling:touch]">
      {tabs.map(({ key, label, icon: Icon }) => {
        const active = key === activeKey
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            aria-label={label}
            className={`flex flex-shrink-0 items-center gap-1 whitespace-nowrap border-b-2 pb-2 pt-3 text-xs font-medium transition-colors sm:gap-1.5 sm:text-sm ${
              active
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            {Icon && <Icon className="h-4 w-4 sm:h-4 sm:w-4" />}
            <span className="hidden sm:inline">{label}</span>
          </button>
        )
      })}
    </div>
  )
}
