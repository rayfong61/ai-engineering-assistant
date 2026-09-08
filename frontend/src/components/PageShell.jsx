import Header from './Header'

export default function PageShell({ headerLeft, headerActions, subNav, children }) {
  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-slate-50">
      <Header left={headerLeft}>{headerActions}</Header>
      {subNav && (
        <div className="border-b border-slate-200 bg-white px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-5xl">{subNav}</div>
        </div>
      )}
      <main className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  )
}
