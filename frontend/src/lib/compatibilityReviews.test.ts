import { describe, expect, it, vi } from 'vitest'

const { post } = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock('@/lib/api', () => ({ api: { post } }))

import { compatibilityReviewsApi, type CompatibilityReviewStatus } from './compatibilityReviews'

describe('compatibilityReviewsApi', () => {
  it('uses the review endpoints and expected payloads', () => {
    const queuePayload = { statuses: ['pending'] as CompatibilityReviewStatus[], query: 'tomato', offset: 25, limit: 25 }
    const submission = {
      food_cache_id: 7,
      review_status: 'approved' as const,
      allergen_status: 'known' as const,
      known_allergens: [],
      strict_suitability: {},
      evidence: {},
      confidence: null,
      classifier_version: null,
      policy_version: 'v1',
      review_note: null,
    }

    compatibilityReviewsApi.getQueue(queuePayload)
    compatibilityReviewsApi.getDetail(7)
    compatibilityReviewsApi.getHistory(7)
    compatibilityReviewsApi.submit(submission)

    expect(post).toHaveBeenNthCalledWith(1, '/nutrition/compatibility/review-queue', queuePayload)
    expect(post).toHaveBeenNthCalledWith(2, '/nutrition/compatibility/review-detail', { food_cache_id: 7 })
    expect(post).toHaveBeenNthCalledWith(3, '/nutrition/compatibility/review-history', { food_cache_id: 7 })
    expect(post).toHaveBeenNthCalledWith(4, '/nutrition/compatibility/review', submission)
  })
})