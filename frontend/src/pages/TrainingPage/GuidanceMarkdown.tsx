import { Fragment, createElement } from 'react'
import type { ReactNode } from 'react'
import { marked } from 'marked'
import type { Token, MarkedToken } from 'marked'

// Render an allowlist of Markdown elements. Model HTML, images, and link URLs
// are never inserted into the DOM; React escapes all remaining text.
function renderTokens(tokens: Token[]): ReactNode[] {
  return tokens.map((value, index) => {
    const token = value as MarkedToken
    const children = 'tokens' in token && token.tokens ? renderTokens(token.tokens) : null
    switch (token.type) {
      case 'space':
      case 'def':
        return null
      case 'heading':
        return createElement(`h${Math.min(token.depth + 2, 6)}`, { key: index }, children)
      case 'paragraph':
        return <p key={index}>{children}</p>
      case 'text':
        return <Fragment key={index}>{children ?? token.text}</Fragment>
      case 'strong':
        return <strong key={index}>{children}</strong>
      case 'em':
        return <em key={index}>{children}</em>
      case 'del':
        return <del key={index}>{children}</del>
      case 'br':
        return <br key={index} />
      case 'list': {
        const items = token.items.map((item, itemIndex) => <li key={itemIndex}>{renderTokens(item.tokens)}</li>)
        return token.ordered
          ? <ol key={index} start={Number(token.start) || 1}>{items}</ol>
          : <ul key={index}>{items}</ul>
      }
      case 'blockquote':
        return <blockquote key={index}>{children}</blockquote>
      case 'codespan':
        return <code key={index}>{token.text}</code>
      case 'code':
        return <pre key={index}><code>{token.text}</code></pre>
      case 'hr':
        return <hr key={index} />
      case 'link':
        return <Fragment key={index}>{children}</Fragment>
      case 'image':
      case 'html':
      case 'escape':
        return <Fragment key={index}>{token.text}</Fragment>
      default:
        return <Fragment key={index}>{token.raw}</Fragment>
    }
  })
}

export function GuidanceMarkdown({ content }: Readonly<{ content: string }>) {
  return <div className="training-guidance-markdown">{renderTokens(marked.lexer(content, { gfm: true, breaks: true }))}</div>
}