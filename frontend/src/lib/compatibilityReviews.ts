import { api } from '@/lib/api'

export const compatibilityReviewStatuses = ['pending', 'auto_classified', 'review_required', 'needs_review', 'approved', 'rejected'] as const
export const reviewDecisions = ['approved', 'rejected', 'review_required'] as const
export const allergenStatuses = ['known', 'unknown', 'conflicting'] as const
export const strictSuitabilityKeys = [
  'vegetarian', 'vegan', 'pescatarian', 'halal', 'kosher', 'gluten_free',
  'dairy_free', 'egg_free', 'soy_free', 'nut_free', 'no_pork', 'no_beef',
  'alcohol_free',
] as const

export type CompatibilityReviewStatus = typeof compatibilityReviewStatuses[number]
export type ReviewDecision = typeof reviewDecisions[number]
export type AllergenStatus = typeof allergenStatuses[number]
export type StrictSuitabilityKey = typeof strictSuitabilityKeys[number]
export type StrictSuitabilityValue = 'suitable' | 'unsuitable'

export type ReviewQueueItem = {
  food_cache_id: number
  provider: string
  provider_food_id: string
  description: string
  review_status: string
  allergen_status: string
  known_allergens: string[]
  strict_suitability: Record<string, string>
  evidence: Record<string, unknown>
  confidence: number | null
  classifier_version: string | null
  policy_version: string | null
  review_note: string | null
  updated_at: string
}

export type CompatibilityReviewDetail = ReviewQueueItem & {
  raw_response: Record<string, unknown>
  reviewer_user_id: number | null
  reviewer_email: string | null
  reviewed_at: string | null
  created_at: string
}

export type CompatibilityReviewQueue = {
  items: ReviewQueueItem[]
  total: number
  offset: number
  limit: number
}

export type CompatibilityReviewHistoryItem = {
  id: number
  food_cache_id: number
  prior_review_status: string | null
  result_review_status: string
  metadata_snapshot: Record<string, unknown>
  reviewer_user_id: number
  reviewer_email: string
  review_note: string | null
  reviewed_at: string
}

export type ReviewSubmission = {
  food_cache_id: number
  review_status: ReviewDecision
  allergen_status: AllergenStatus
  known_allergens: string[]
  strict_suitability: Partial<Record<StrictSuitabilityKey, StrictSuitabilityValue>>
  evidence: Record<string, unknown>
  confidence: number | null
  classifier_version: string | null
  policy_version: string
  review_note: string | null
}

export const compatibilityReviewsApi = {
  getQueue: (payload: { statuses: CompatibilityReviewStatus[]; query: string; offset: number; limit: number }) =>
    api.post<CompatibilityReviewQueue>('/nutrition/compatibility/review-queue', payload),
  getDetail: (foodCacheId: number) =>
    api.post<CompatibilityReviewDetail>('/nutrition/compatibility/review-detail', { food_cache_id: foodCacheId }),
  getHistory: (foodCacheId: number) =>
    api.post<{ items: CompatibilityReviewHistoryItem[] }>('/nutrition/compatibility/review-history', { food_cache_id: foodCacheId }),
  submit: (payload: ReviewSubmission) =>
    api.post<CompatibilityReviewDetail>('/nutrition/compatibility/review', payload),
}