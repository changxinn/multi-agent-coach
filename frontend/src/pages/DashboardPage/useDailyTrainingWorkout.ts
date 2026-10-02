import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { ApiEndpoints } from '@/lib/constants'
import type { DailyTrainingWorkout } from './types'

export const dailyTrainingWorkoutQueryKey = ['dashboard', 'daily-training-workout'] as const

export function useDailyTrainingWorkout() {
  const queryClient = useQueryClient()
  const workout = useQuery({
    queryKey: dailyTrainingWorkoutQueryKey,
    queryFn: () => api.post<DailyTrainingWorkout>(ApiEndpoints.Dashboard.DailyTrainingWorkout, {}),
    staleTime: 5 * 60 * 1000,
  })
  const refresh = useMutation({
    mutationFn: () => api.post<DailyTrainingWorkout>(`${ApiEndpoints.Dashboard.DailyTrainingWorkout}?refresh=true`, {}),
    onSuccess: data => queryClient.setQueryData(dailyTrainingWorkoutQueryKey, data),
  })
  return { workout, refresh }
}