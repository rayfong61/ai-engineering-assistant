import ReactMarkdown from 'react-markdown'

// Claude's answers/summaries come back as Markdown (##, **bold**, lists) --
// these overrides keep it at the same text-sm scale used everywhere else in
// this app instead of pulling in a full typography plugin for a chat bubble.
const COMPONENTS = {
  p: ({ children }) => <p className="mb-1.5 leading-relaxed last:mb-0">{children}</p>,
  h1: ({ children }) => <h3 className="mt-2 mb-1 text-sm font-semibold first:mt-0">{children}</h3>,
  h2: ({ children }) => <h3 className="mt-2 mb-1 text-sm font-semibold first:mt-0">{children}</h3>,
  h3: ({ children }) => <h4 className="mt-2 mb-1 text-sm font-semibold first:mt-0">{children}</h4>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  ul: ({ children }) => <ul className="mb-1.5 list-disc space-y-0.5 pl-4 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-1.5 list-decimal space-y-0.5 pl-4 last:mb-0">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="underline">
      {children}
    </a>
  ),
  code: ({ children }) => <code className="rounded bg-black/10 px-1 py-0.5 text-xs">{children}</code>,
}

export default function MarkdownContent({ content, className = '' }) {
  return (
    <div className={`text-sm ${className}`}>
      <ReactMarkdown components={COMPONENTS}>{content}</ReactMarkdown>
    </div>
  )
}
