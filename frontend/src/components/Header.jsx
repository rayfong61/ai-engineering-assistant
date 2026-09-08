export default function Header({ title = 'AI Engineering Assistant', left = null, children }) {
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          {left}
          <span className="font-semibold text-slate-900">{title}</span>
        </div>
        <div className="flex items-center gap-2">{children}</div>
      </div>
    </header>
  )
}
