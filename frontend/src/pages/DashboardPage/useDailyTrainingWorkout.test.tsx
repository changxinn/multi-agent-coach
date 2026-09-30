import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { PropsWithChildren } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '@/lib/api'
import { ApiEndpoints } from '@/lib/constants'
import { dailyTrainingWorkoutQueryKey, useDailyTrainingWorkout } from './useDailyTrainingWorkout'

vi.mock('@/lib/api', () => ({ api: { post: vi.fn() } }))

const post = vi.mocked(api.post)
const workout = {
  status: 'ready' as const,
  title: 'Today’s personalized workout',
  workout_text: 'Warm-up',
  recovery_note: null,
  recovery_status: 'green' as const,
  generated_at: '2026-09-30T10:00:00Z',
  reused: false,
}

function wrapper({ children }: PropsWithChildren) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('useDailyTrainingWorkout', () => {
  it('loads the daily workout and replaces cached data after a refresh', async () => {
    post.mockResolvedValueOnce(workout).mockResolvedValueOnce({ ...workout, title: 'Fresh workout' })

    const { result } = renderHook(() => useDailyTrainingWorkout(), { wrapper })

    await waitFor(() => expect(result.current.workout.data).toEqual(workout))
    result.current.refresh.mutate()

    await waitFor(() => expect(result.current.workout.data?.title).toBe('Fresh workout'))
    expect(post).toHaveBeenNthCalledWith(1, ApiEndpoints.Dashboard.DailyTrainingWorkout, {})
    expect(post).toHaveBeenNthCalledWith(2, `${ApiEndpoints.Dashboard.DailyTrainingWorkout}?refresh=true`, {})
    expect(dailyTrainingWorkoutQueryKey).toEqual(['dashboard', 'daily-training-workout'])
  })
})