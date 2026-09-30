import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/lib/authStore'
import { DashboardPage } from './DashboardPage'
import type { DailyCommandCenterResponse } from './types'

const { commandCenter, refetch } = vi.hoisted(() => ({ commandCenter: vi.fn(), refetch: vi.fn() }))
vi.mock('./useDailyCommandCenter', () => ({ useDailyCommandCenter: commandCenter }))
vi.mock('./DailySummaryCard', () => ({ DailySummaryCard: () => <div>Daily summary</div> }))
vi.mock('./RecoveryStatusCard', () => ({ RecoveryStatusCard: () => <div>Recovery card</div> }))
vi.mock('./NutritionStatusCard', () => ({ NutritionStatusCard: () => <div>Nutrition card</div> }))
vi.mock('./TrainingStatusCard', () => ({ TrainingStatusCard: () => <div>Training card</div> }))

const data = {
  generated_at: '', dashboard_date: '', training: { status: 'unavailable', message: '', last_activity_at: null },
  recovery: { status: 'no_assessment', message: null, assessment_score: null, assessment_created_at: null, sleep_duration_minutes: null, sleep_quality: null, sleep_logged_at: null, energy: null, soreness: null, stress: null, check_in_created_at: null, trend: [] },
  nutrition: { status: 'no_target', message: null, calories: null, protein_g: null, meal_count: null, calorie_target_kcal: null, protein_target_g: null, remaining_calories: null, remaining_protein_g: null, calorie_adherence_pct: null, protein_adherence_pct: null, trend: [] },
  actions: [{ id: 'a', priority: 1, severity: 'info', title: 'Log lunch', description: 'Keep totals current', route: '/nutrition' }], errors: [],
} satisfies DailyCommandCenterResponse

describe('DashboardPage', () => {
  it('renders loading, error retry, and successful coaching composition', () => {
    useAuthStore.setState({ user: { sub: '1', email: 'coach@example.com', name: 'Coach', exp: 4_102_444_800 } })
    commandCenter.mockReturnValue({ isLoading: true, isFetching: false, isError: false })
    const view = render(<MemoryRouter><DashboardPage /></MemoryRouter>)
    expect(screen.getByText('Welcome back, Coach!')).toBeTruthy()

    commandCenter.mockReturnValue({ isLoading: false, isFetching: false, isError: true, refetch })
    view.rerender(<MemoryRouter><DashboardPage /></MemoryRouter>)
    fireEvent.click(screen.getByText('Retry').closest('button')!)
    expect(refetch).toHaveBeenCalled()

    commandCenter.mockReturnValue({ isLoading: false, isFetching: false, isError: false, data })
    view.rerender(<MemoryRouter><DashboardPage /></MemoryRouter>)
    expect(screen.getByText('Recovery card')).toBeTruthy()
    expect(screen.getByText('Nutrition card')).toBeTruthy()
    expect(screen.getByText('Training card')).toBeTruthy()
    expect(screen.getByText('Log lunch')).toBeTruthy()
  })
})