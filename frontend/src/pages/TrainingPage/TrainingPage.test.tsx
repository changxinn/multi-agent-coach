import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TrainingPage } from './TrainingPage'
import { useDailyTrainingWorkout } from '@/pages/DashboardPage/useDailyTrainingWorkout'
import { api } from '@/lib/api'

vi.mock('@/pages/DashboardPage/useDailyTrainingWorkout', () => ({ useDailyTrainingWorkout: vi.fn() }))
vi.mock('@/lib/api', () => ({ api: { post: vi.fn() } }))

const useWorkout = vi.mocked(useDailyTrainingWorkout)
const post = vi.mocked(api.post)
const refresh = { isPending: false, mutate: vi.fn() }
const refetch = vi.fn()
const renderPage = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><TrainingPage /></QueryClientProvider>)

describe('TrainingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    post.mockImplementation(async endpoint => {
      if (endpoint === '/training/preferences/get') return { equipment: ['Dumbbells', 'bench'], training_days_per_week: 3, session_duration_minutes: 45, preferences: {} }
      if (endpoint === '/training/programs/list' || endpoint === '/training/workouts/list') return { items: [] }
      if (endpoint === '/training/progress') return { workout_count: 0, average_rpe: null, total_duration_minutes: 0, last_workout_at: null, plateau_detected: false }
      return { items: [] }
    })
  })

  it('renders the live recommendation in Manage your training and omits removed informational sections', () => {
    useWorkout.mockReturnValue({ workout: { isLoading: false, isError: false, data: {
      status: 'ready', title: 'Today’s personalized workout', workout_text: 'Warm-up: easy mobility.', recovery_note: null,
      recovery_status: 'green', generated_at: '2026-10-07T10:00:00Z', reused: true, generation_source: 'llm',
    } }, refresh } as unknown as ReturnType<typeof useDailyTrainingWorkout>)

    renderPage()

    expect(screen.getByRole('heading', { name: 'Training' })).toBeTruthy()
    expect(screen.getByText('Manage your training')).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Live daily recommendation' })).toBeTruthy()
    expect(screen.getByText('Today’s personalized workout')).toBeTruthy()
    expect(screen.queryByText('Safety behavior is enforced before training')).toBeNull()
    expect(screen.queryByText('What the agent does')).toBeNull()
    expect(screen.queryByText('Want individualized training guidance?')).toBeNull()
    expect(screen.queryByText('Recovery-aware coaching')).toBeNull()
    expect(screen.queryByText('Secure service boundary')).toBeNull()
    expect(screen.queryByText('Inputs and resilience')).toBeNull()
  })

  it('refreshes the live recommendation', () => {
    useWorkout.mockReturnValue({ workout: { isLoading: false, isError: false, data: {
      status: 'ready', title: 'Workout', workout_text: 'Move.', recovery_note: null,
      recovery_status: 'green', generated_at: '2026-10-07T10:00:00Z', reused: false, generation_source: 'llm',
    } }, refresh } as unknown as ReturnType<typeof useDailyTrainingWorkout>)

    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Live daily recommendation' }))
    fireEvent.click(screen.getByRole('button', { name: 'Generate new plan' }))

    expect(refresh.mutate).toHaveBeenCalledOnce()
  })

  it('shows a retry state when the live workout is unavailable', () => {
    useWorkout.mockReturnValue({ workout: { isLoading: false, isError: true, refetch }, refresh } as unknown as ReturnType<typeof useDailyTrainingWorkout>)

    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Live daily recommendation' }))
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))

    expect(screen.getByText('Today’s workout is temporarily unavailable.')).toBeTruthy()
    expect(refetch).toHaveBeenCalledOnce()
  })

  it('hydrates saved preferences after the query resolves', async () => {
    useWorkout.mockReturnValue({ workout: { isLoading: false, isError: false, data: {
      status: 'ready', title: 'Workout', workout_text: 'Move.', recovery_note: null,
      recovery_status: 'green', generated_at: '2026-10-07T10:00:00Z', reused: false, generation_source: 'llm',
    } }, refresh } as unknown as ReturnType<typeof useDailyTrainingWorkout>)

    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Preferences' }))

    await waitFor(() => expect((screen.getByLabelText('Equipment (comma separated)') as HTMLInputElement).value).toBe('Dumbbells, bench'))
    expect((screen.getByLabelText('Days per week') as HTMLInputElement).value).toBe('3')
    expect((screen.getByLabelText('Session minutes') as HTMLInputElement).value).toBe('45')
  })
})