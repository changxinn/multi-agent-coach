import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CompatibilityReviewsPage } from './CompatibilityReviewsPage'
import { compatibilityStatusColor } from './compatibilityStatus'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('@/lib/api', () => ({ api: { get, post } }))

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <CompatibilityReviewsPage />
    </QueryClientProvider>,
  )
}

describe('CompatibilityReviewsPage', () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
  })

  it.each([
    ['approved', 'green'],
    ['rejected', 'red'],
    ['review_required', 'gold'],
    ['pending', 'blue'],
  ])('maps %s reviews to %s tags', (status, color) => {
    expect(compatibilityStatusColor(status)).toBe(color)
  })

  it('blocks users without compatibility reviewer access', async () => {
    get.mockResolvedValue({ is_nutrition_compatibility_admin: false })

    renderPage()

    expect(await screen.findByText('Compatibility reviewer access required')).toBeTruthy()
    expect(post).not.toHaveBeenCalled()
  })

  it('loads, filters, and renders the authorized review queue', async () => {
    get.mockResolvedValue({ is_nutrition_compatibility_admin: true })
    post.mockResolvedValue({
      items: [{ food_cache_id: 7, description: 'Tomatoes, raw', review_status: 'pending', updated_at: '2026-01-01T12:00:00Z' }],
      total: 1,
    })

    renderPage()

    expect(await screen.findByText('Tomatoes, raw')).toBeTruthy()
    expect(post).toHaveBeenCalledWith('/nutrition/compatibility/review-queue', expect.objectContaining({ offset: 0, limit: 25 }))

    fireEvent.change(screen.getByPlaceholderText('Search food descriptions'), { target: { value: 'tomato' } })

    await waitFor(() => expect(post).toHaveBeenLastCalledWith(
      '/nutrition/compatibility/review-queue',
      expect.objectContaining({ query: 'tomato', offset: 0, limit: 25 }),
    ))
  })

  it('shows reviewer-profile and queue failures', async () => {
    get.mockRejectedValueOnce(new Error('Profile unavailable'))
    const { unmount } = renderPage()

    expect(await screen.findByText('Unable to verify reviewer access')).toBeTruthy()
    unmount()

    get.mockResolvedValue({ is_nutrition_compatibility_admin: true })
    post.mockRejectedValue(new Error('Queue unavailable'))
    renderPage()

    expect(await screen.findByText('Unable to load the review queue')).toBeTruthy()
    expect(screen.getByText('Queue unavailable')).toBeTruthy()
  })
})