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

const review = {
  food_cache_id: 7,
  provider: 'usda',
  provider_food_id: '123',
  description: 'Tomatoes, raw',
  review_status: 'review_required',
  allergen_status: 'unknown',
  known_allergens: [],
  strict_suitability: {},
  evidence: { source: 'USDA ingredient data' },
  confidence: null,
  classifier_version: 'classifier-v1',
  policy_version: 'compatibility_review_v1',
  review_note: null,
  raw_response: { fdcId: 123 },
  reviewer_user_id: null,
  reviewer_email: null,
  reviewed_at: null,
  created_at: '2026-01-01T12:00:00Z',
  updated_at: '2026-01-01T12:00:00Z',
}

function mockReviewEndpoints(overrides: Record<string, unknown> = {}) {
  post.mockImplementation((endpoint: string) => {
    if (endpoint === '/nutrition/compatibility/review-queue') {
      return Promise.resolve({ items: [review], total: 1, offset: 0, limit: 25 })
    }
    if (endpoint === '/nutrition/compatibility/review-detail') return Promise.resolve(review)
    if (endpoint === '/nutrition/compatibility/review-history') {
      return Promise.resolve({ items: [{ id: 1, food_cache_id: 7, prior_review_status: 'pending', result_review_status: 'review_required', metadata_snapshot: { source: 'USDA' }, reviewer_user_id: 4, reviewer_email: 'reviewer@example.com', review_note: 'Needs a label check', reviewed_at: '2026-01-01T12:00:00Z' }] })
    }
    if (endpoint === '/nutrition/compatibility/review') return Promise.resolve({ ...review, ...overrides })
    return Promise.reject(new Error(`Unexpected endpoint: ${endpoint}`))
  })
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

  it('loads the workspace evidence, hydrated decision form, and audit history', async () => {
    get.mockResolvedValue({ is_nutrition_compatibility_admin: true })
    mockReviewEndpoints({ review_status: 'rejected' })
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Review' }))

    expect(await screen.findByText('Current metadata')).toBeTruthy()
    expect(await screen.findByDisplayValue('USDA ingredient data')).toBeTruthy()
    expect(await screen.findByText('Needs a label check')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Save review decision' })).toBeTruthy()
    expect(screen.getByText('Reviewer identity is recorded from your authenticated session.')).toBeTruthy()
  })

  it('renders a detail failure in the workspace', async () => {
    get.mockResolvedValue({ is_nutrition_compatibility_admin: true })
    post.mockImplementation((endpoint: string) => {
      if (endpoint === '/nutrition/compatibility/review-queue') return Promise.resolve({ items: [review], total: 1 })
      if (endpoint === '/nutrition/compatibility/review-detail') return Promise.reject(new Error('Detail unavailable'))
      if (endpoint === '/nutrition/compatibility/review-history') return Promise.resolve({ items: [] })
      return Promise.resolve({})
    })
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Review' }))

    expect(await screen.findByText('Unable to load compatibility review')).toBeTruthy()
    expect(screen.getByText('Detail unavailable')).toBeTruthy()
  })

  it('renders an audit-history failure after loading food detail', async () => {
    get.mockResolvedValue({ is_nutrition_compatibility_admin: true })
    post.mockImplementation((endpoint: string) => {
      if (endpoint === '/nutrition/compatibility/review-queue') return Promise.resolve({ items: [review], total: 1 })
      if (endpoint === '/nutrition/compatibility/review-detail') return Promise.resolve(review)
      if (endpoint === '/nutrition/compatibility/review-history') return Promise.reject(new Error('History unavailable'))
      return Promise.resolve({})
    })
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Review' }))

    expect(await screen.findByText('Unable to load history')).toBeTruthy()
    expect(screen.getByText('History unavailable')).toBeTruthy()
  })
})