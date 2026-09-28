import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { ApiEndpoints } from '@/lib/constants'
import type { DailyCommandCenterResponse } from './types'

export const dailyCommandCenterQueryKey = ['dashboard', 'daily-command-center'] as const

export function useDailyCommandCenter() {
  return useQuery({
    queryKey: dailyCommandCenterQueryKey,
    queryFn: () => api.get<DailyCommandCenterResponse>(ApiEndpoints.Dashboard.DailyCommandCenter),
    // This aggregate is sourced from other pages' mutations. Always refetch
    // when the dashboard route mounts so returning to it never shows a fresh
    // cache as though it were current status.
    staleTime: 0,
  })
}