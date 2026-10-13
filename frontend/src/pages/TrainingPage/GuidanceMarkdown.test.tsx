import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GuidanceMarkdown } from './GuidanceMarkdown'

describe('GuidanceMarkdown', () => {
  it('renders headings, lists, emphasis, paragraphs and line breaks', () => {
    const { container } = render(<GuidanceMarkdown content={'## Setup\n\nStand tall.\nBrace gently.\n\n**Technique cues**\n\n- Move slowly.\n- Keep control.\n\n1. Start light.\n2. Progress gradually.'} />)
    expect(screen.getByRole('heading', { name: 'Setup' })).toBeTruthy()
    expect(container.querySelector('strong')?.textContent).toBe('Technique cues')
    expect(screen.getAllByRole('listitem')).toHaveLength(4)
    expect(container.querySelector('br')).toBeTruthy()
    expect(container.querySelectorAll('p').length).toBeGreaterThan(1)
  })

  it('keeps plain-text guidance readable', () => {
    render(<GuidanceMarkdown content="Brace and stop for pain." />)
    expect(screen.getByText('Brace and stop for pain.')).toBeTruthy()
  })

  it('never inserts model HTML, images, or unsafe link URLs', () => {
    const { container } = render(<GuidanceMarkdown content={'<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[Unsafe](javascript:alert%281%29)\n\n![Image](https://example.com/image.png)'} />)
    expect(container.querySelector('script, img, a')).toBeNull()
    expect(screen.getByText('Unsafe')).toBeTruthy()
    expect(container.textContent).toContain('<script>alert(1)</script>')
  })
})