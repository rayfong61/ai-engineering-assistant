export default function Tabs({ tabs, activeKey, onChange }) {
  return (
    <div className="scrollbar-none flex gap-3 overflow-x-auto border-b border-slate-200 sm:gap-4 [-webkit-overflow-scrolling:touch]">
      {tabs.map(({ key, label, icon: Icon }) => {
        const active = key === activeKey
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={`flex flex-shrink-0 items-center gap-1 whitespace-nowrap border-b-2 pb-2 pt-3 text-xs font-medium transition-colors sm:gap-1.5 sm:text-sm ${
              active
                ? 'border-brand-600 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            {Icon && <Icon className="h-3.5 w-3.5 sm:h-4 sm:w-4" />}
            {label}
          </button>
        )
      })}
    </div>
  )
}
