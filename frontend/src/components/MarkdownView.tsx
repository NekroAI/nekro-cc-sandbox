import { isValidElement, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const nodeToText = (node: ReactNode): string => {
  if (typeof node === 'string') return node
  if (typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(nodeToText).join('')
  if (isValidElement(node)) return nodeToText((node.props as { children?: ReactNode }).children)
  return ''
}

export function MarkdownView(props: { content: string; tone?: 'normal' | 'error' }) {
  const { content, tone = 'normal' } = props
  const isError = tone === 'error'

  return (
    <div className={isError ? 'text-red-200' : 'text-gray-100'}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ children, ...p }) => (
            <a {...p} className="text-blue-300 underline hover:text-blue-200" target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
          code: ({ className, children, ...p }) => {
            const isInline = !className
            if (isInline) {
              return (
                <code {...p} className="px-1 py-0.5 rounded bg-gray-800 text-gray-100">
                  {children}
                </code>
              )
            }
            return (
              <code {...p} className={className}>
                {children}
              </code>
            )
          },
          pre: ({ children, ...p }) => (
            <div className="relative">
              <button
                type="button"
                className="absolute top-2 right-2 text-xs px-2 py-1 rounded bg-gray-700 text-gray-200 hover:bg-gray-600"
                onClick={() => {
                  const text = nodeToText(children).replace(/\n$/, '')
                  navigator.clipboard.writeText(text).catch(() => {})
                }}
              >
                复制
              </button>
              <pre {...p} className="p-3 pt-10 rounded bg-gray-800 overflow-auto border border-gray-700">
                {children}
              </pre>
            </div>
          ),
          table: ({ children, ...p }) => (
            <div className="overflow-auto">
              <table {...p} className="min-w-full border border-gray-700">
                {children}
              </table>
            </div>
          ),
          th: ({ children, ...p }) => (
            <th {...p} className="border border-gray-700 px-2 py-1 text-left bg-gray-800">
              {children}
            </th>
          ),
          td: ({ children, ...p }) => (
            <td {...p} className="border border-gray-700 px-2 py-1 align-top">
              {children}
            </td>
          ),
          ul: ({ children, ...p }) => (
            <ul {...p} className="list-disc pl-5 space-y-1">
              {children}
            </ul>
          ),
          ol: ({ children, ...p }) => (
            <ol {...p} className="list-decimal pl-5 space-y-1">
              {children}
            </ol>
          ),
          blockquote: ({ children, ...p }) => (
            <blockquote {...p} className="border-l-4 border-gray-700 pl-3 text-gray-200">
              {children}
            </blockquote>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

