export default function Card({ as: Tag = 'div', hover = false, className = '', children, ...props }) {
  return (
    <Tag
      className={`rounded-card border border-slate-200 bg-white p-6 shadow-card
        ${hover ? 'transition-shadow hover:shadow-card-hover' : ''} ${className}`}
      {...props}
    >
      {children}
    </Tag>
  )
}
