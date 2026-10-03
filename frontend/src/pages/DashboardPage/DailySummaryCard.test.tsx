import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DailySummaryCard } from './DailySummaryCard'

const { post } = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock('@/lib/api', () => ({ api: { post } }))

describe('DailySummaryCard', () => {
  beforeEach(() => {
    post.mockReset()
  })

  it('shows the generated summary and refreshes it on demand', async () => {
    post.mockResolvedValueOnce({ summary: 'Your day at a glance: Recovery emphasis: easy movement.', generated_at: '', reused: false })
      .mockResolvedValueOnce({ summary: 'Fuel: add protein at lunch.', generated_at: '', reused: false })
    render(<DailySummaryCard />)

    await screen.findByText(/easy movement/)
    expect(screen.getByText('Recovery emphasis', { exact: false })).toBeTruthy()
    const refreshButton = screen.getByText('Refresh').closest('button')!
    await waitFor(() => expect(refreshButton.disabled).toBe(false))
    fireEvent.click(refreshButton)
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
    expect(post).toHaveBeenNthCalledWith(1, '/summaries/daily', {})
    expect(post).toHaveBeenNthCalledWith(2, '/summaries/daily?refresh=1', {})
    await screen.findByText(/add protein at lunch/)
  })

  it('shows an API failure instead of summary content', async () => {
    post.mockRejectedValueOnce(new Error('Summary unavailable'))
    render(<DailySummaryCard />)
    await waitFor(() => expect(screen.getByText('Summary unavailable')).toBeTruthy())
  })
})