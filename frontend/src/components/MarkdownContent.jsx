import ReactMarkdown from 'react-markdown'

// Claude's answers/summaries come back as Markdown (##, **bold**, lists) --
// these overrides keep it at the same text-sm scale used everywhere else in
// this app instead of pulling in a full typography plugin for a chat bubble.
const COMPONENTS = {
  p: ({ children }) => <p className="mb-1.5 break-words leading-relaxed last:mb-0">{children}</p>,
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
  pre: ({ children }) => (
    <pre className="mb-1.5 max-w-full overflow-x-auto rounded bg-black/10 p-2 text-xs last:mb-0">
      {children}
    </pre>
  ),
  // react-markdown v9 no longer passes an `inline` flag to `code` -- fenced
  // blocks with a language tag get a `language-xxx` className, so that's
  // the signal used to skip the inline "pill" styling for those.
  code: ({ className, children }) =>
    /language-/.test(className || '') ? (
      <code className="whitespace-pre">{children}</code>
    ) : (
      <code className="rounded bg-black/10 px-1 py-0.5 text-xs">{children}</code>
    ),
}

export default function MarkdownContent({ content, className = '' }) {
  return (
    <div className={`text-sm ${className}`}>
      <ReactMarkdown components={COMPONENTS}>{content}</ReactMarkdown>
    </div>
  )
}
