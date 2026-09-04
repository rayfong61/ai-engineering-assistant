import Header from './Header'

export default function PageShell({ headerLeft, headerActions, children }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <Header left={headerLeft}>{headerActions}</Header>
      <main className="mx-auto max-w-5xl p-8">{children}</main>
    </div>
  )
}
