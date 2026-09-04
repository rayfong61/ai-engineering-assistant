export default function Input({ label, error, className = '', id, ...props }) {
  const inputId = id || props.name

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-slate-700">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`w-full rounded-card border border-slate-300 px-3 py-2 text-sm text-slate-900
          placeholder:text-slate-400 focus-visible:border-brand-500 ${className}`}
        {...props}
      />
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  )
}
