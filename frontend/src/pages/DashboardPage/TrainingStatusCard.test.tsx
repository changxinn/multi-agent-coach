import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TrainingStatusCard } from './TrainingStatusCard'
import { useDailyTrainingWorkout } from './useDailyTrainingWorkout'

vi.mock('./useDailyTrainingWorkout', () => ({ useDailyTrainingWorkout: vi.fn() }))

const useWorkout = vi.mocked(useDailyTrainingWorkout)
const refresh = { isPending: false, mutate: vi.fn() }
const refetch = vi.fn()

describe('TrainingStatusCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a loading skeleton while a refresh is pending', () => {
    useWorkout.mockReturnValue({
      workout: { isLoading: false },
      refresh: { ...refresh, isPending: true },
    } as unknown as ReturnType<typeof useDailyTrainingWorkout>)

    render(<TrainingStatusCard />)

    expect(document.querySelector('.ant-skeleton')).not.toBeNull()
  })

  it('shows retry guidance when the workout cannot be loaded', () => {
    useWorkout.mockReturnValue({ workout: { isLoading: false, isError: true, refetch }, refresh } as unknown as ReturnType<typeof useDailyTrainingWorkout>)

    render(<TrainingStatusCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))

    expect(screen.getByText('Today’s workout is temporarily unavailable.')).toBeTruthy()
    expect(refetch).toHaveBeenCalledOnce()
  })

  it('renders recovery guidance, term definitions, and refreshes the workout', () => {
    useWorkout.mockReturnValue({
      workout: {
        isLoading: false,
        isError: false,
        data: {
          status: 'recovery_adjusted',
          title: 'Recovery-focused movement',
          workout_text: 'Walk at RPE 7 with a DB.',
          recovery_note: 'Keep effort controlled.',
          recovery_status: 'amber',
          generated_at: '2026-09-30T10:00:00Z',
          reused: false,
        },
      },
      refresh,
    } as unknown as ReturnType<typeof useDailyTrainingWorkout>)

    render(<TrainingStatusCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Generate a new plan for today' }))

    expect(screen.getByText('Recovery-focused movement')).toBeTruthy()
    expect(screen.getByText('Keep effort controlled.')).toBeTruthy()
    expect(screen.getByText(/Rate of Perceived Exertion/)).toBeTruthy()
    expect(screen.getByText(/Dumbbell \(DB\)/)).toBeTruthy()
    expect(refresh.mutate).toHaveBeenCalledOnce()
  })

  it('renders a ready workout without guidance', () => {
    useWorkout.mockReturnValue({
      workout: { isLoading: false, isError: false, data: {
        status: 'ready', title: 'Strength session', workout_text: 'Controlled squats.', recovery_note: null,
        recovery_status: 'green', generated_at: '2026-09-30T10:00:00Z', reused: true,
      } },
      refresh,
    } as unknown as ReturnType<typeof useDailyTrainingWorkout>)

    render(<TrainingStatusCard />)

    expect(screen.getByText('Strength session')).toBeTruthy()
    expect(document.querySelector('.dashboard-training-guidance')).toBeNull()
    expect(document.querySelector('.ant-btn-loading')).toBeNull()
  })
})