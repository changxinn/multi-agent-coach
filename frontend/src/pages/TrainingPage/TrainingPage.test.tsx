import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TrainingPage } from './TrainingPage'
import { idempotencyKey } from '@/lib/idempotencyKey'
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

  it('uses secure UUIDs for workout idempotency keys and rejects unavailable crypto', () => {
    const originalCrypto = globalThis.crypto
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: { randomUUID: () => 'secure-id' } })
    expect(idempotencyKey()).toBe('secure-id')
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: {
      getRandomValues: (bytes: Uint8Array) => {
        bytes.set(Array.from({ length: 16 }, (_, index) => index))
        return bytes
      },
    } })
    expect(idempotencyKey()).toBe('00010203-0405-4607-8809-0a0b0c0d0e0f')
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: undefined })
    expect(() => idempotencyKey()).toThrow('Secure random UUID generation is unavailable')
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: originalCrypto })
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

  it('searches for and displays exercise guidance', async () => {
    const defaultPost = post.getMockImplementation()!
    post.mockImplementation(async (endpoint, ...args) => {
      if (endpoint === '/training/exercises/search') return { items: [{ name: 'Squat', guidance: 'Brace and stop for pain.' }] }
      return defaultPost(endpoint, ...args)
    })

    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Exercise guidance' }))
    fireEvent.change(screen.getByPlaceholderText('Search an exercise'), { target: { value: 'squat' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByText('Brace and stop for pain.')).toBeTruthy()
    expect(post).toHaveBeenCalledWith('/training/exercises/search', { query: 'squat' })
  })

  it('generates a program and refreshes the saved versions', async () => {
    const defaultPost = post.getMockImplementation()!
    let generated = false
    post.mockImplementation(async (endpoint, ...args) => {
      if (endpoint === '/training/programs/generate') { generated = true; return { id: 1 } }
      if (endpoint === '/training/programs/list' && generated) return { items: [{ id: 1, version: 1, goal: 'Strength program', program: { target_rpe: '7' }, created_at: '2026-10-01T00:00:00Z' }] }
      return defaultPost(endpoint, ...args)
    })

    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Programs' }))
    fireEvent.click(screen.getByRole('button', { name: 'Generate program' }))

    expect(await screen.findByText('Strength program')).toBeTruthy()
    expect(post).toHaveBeenCalledWith('/training/programs/generate', {})
  })

  it('expands saved program days and exercises alongside adaptation', async () => {
    const defaultPost = post.getMockImplementation()!
    post.mockImplementation(async (endpoint, ...args) => {
      if (endpoint === '/training/programs/list') return { items: [{ id: 1, version: 1, goal: 'Strength', program: { days: [
        { day: 'Monday', focus: 'Lower body', movements: ['Goblet squat', 'Romanian deadlift'] },
        { day: 'Thursday', focus: 'Upper body', movements: ['Dumbbell row'] },
      ], target_rpe: '7' }, created_at: '2026-10-01T00:00:00Z' }] }
      return defaultPost(endpoint, ...args)
    })
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Programs' }))
    expect(await screen.findByText('Strength')).toBeTruthy()
    expect(screen.queryByText('Monday')).toBeNull()
    expect(screen.getByText('Adapt latest program')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Adapt' })).toBeTruthy()
    expect(screen.getByLabelText('Adaptation reason').tagName).toBe('TEXTAREA')
    fireEvent.click(screen.getByRole('button', { name: 'Expand row' }))
    expect(screen.getByRole('heading', { name: 'Monday' })).toBeTruthy()
    expect(screen.getByText('Lower body')).toBeTruthy()
    expect(screen.getByText('Goblet squat')).toBeTruthy()
    expect(screen.getByText('Romanian deadlift')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Thursday' })).toBeTruthy()
    expect(screen.getByText('Upper body')).toBeTruthy()
    expect(screen.getByText('Dumbbell row')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Collapse row' }))
    expect(screen.getByRole('button', { name: 'Expand row' })).toBeTruthy()
    expect(post.mock.calls.filter(([endpoint]) => endpoint === '/training/programs/list')).toHaveLength(1)
  })

  it.each([{}, { days: [] }])('handles programs without day details: %j', async program => {
    const defaultPost = post.getMockImplementation()!
    post.mockImplementation(async (endpoint, ...args) => {
      if (endpoint === '/training/programs/list') return { items: [{ id: 1, version: 1, goal: 'Legacy program', program, created_at: '2026-10-01T00:00:00Z' }] }
      return defaultPost(endpoint, ...args)
    })
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Programs' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Expand row' }))
    expect(screen.getByText('No day-by-day details available for this program.')).toBeTruthy()
  })

  it('submits a multiline adaptation reason and refreshes versions after success', async () => {
    const reason = 'Only dumbbells this week.\nReduce sessions to 30 minutes.'
    let finishAdapt!: () => void
    let adapted = false
    const defaultPost = post.getMockImplementation()!
    post.mockImplementation(async (endpoint, ...args) => {
      if (endpoint === '/training/programs/adapt') return new Promise(resolve => {
        finishAdapt = () => { adapted = true; resolve({ version: 2 }) }
      })
      if (endpoint === '/training/programs/list') return { items: adapted ? [{ id: 2, version: 2, goal: 'Adapted strength', program: { days: [], target_rpe: '6-7' }, created_at: '2026-10-01T00:00:00Z' }] : [] }
      return defaultPost(endpoint, ...args)
    })
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Programs' }))
    const textarea = screen.getByLabelText('Adaptation reason') as HTMLTextAreaElement
    expect(textarea.maxLength).toBe(1000)
    fireEvent.change(textarea, { target: { value: reason } })
    expect(textarea.value).toBe(reason)
    const adaptButton = screen.getByRole('button', { name: 'Adapt' })
    fireEvent.click(adaptButton)
    await waitFor(() => expect(post).toHaveBeenCalledWith('/training/programs/adapt', { reason }))
    await waitFor(() => expect(adaptButton.className).toContain('ant-btn-loading'))
    expect(textarea.value).toBe(reason)
    finishAdapt()
    expect(await screen.findByText('Adapted strength', {}, { timeout: 5000 })).toBeTruthy()
    expect(await screen.findByText('Program adapted. A new version has been saved.')).toBeTruthy()
    await waitFor(() => expect((screen.getByLabelText('Adaptation reason') as HTMLTextAreaElement).value).toBe(''))
    expect(post.mock.calls.filter(([endpoint]) => endpoint === '/training/programs/list')).toHaveLength(2)
  })

  it.each(['', '  \n  '])('rejects blank adaptation reasons: %j', async reason => {
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Programs' }))
    fireEvent.change(screen.getByLabelText('Adaptation reason'), { target: { value: reason } })
    fireEvent.click(screen.getByRole('button', { name: 'Adapt' }))
    expect(await screen.findByText('Please enter an adaptation reason.')).toBeTruthy()
    expect(post.mock.calls.some(([endpoint]) => endpoint === '/training/programs/adapt')).toBe(false)
  })

  it('rejects adaptation reasons beyond the API limit', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Programs' }))
    fireEvent.change(screen.getByLabelText('Adaptation reason'), { target: { value: 'a'.repeat(1001) } })
    fireEvent.click(screen.getByRole('button', { name: 'Adapt' }))
    expect(await screen.findByText('Use 1,000 characters or fewer.')).toBeTruthy()
    expect(post.mock.calls.some(([endpoint]) => endpoint === '/training/programs/adapt')).toBe(false)
  })

  it('shows adaptation failures and keeps the reason for retry', async () => {
    const defaultPost = post.getMockImplementation()!
    post.mockImplementation(async (endpoint, ...args) => {
      if (endpoint === '/training/programs/adapt') throw new Error('Adaptation is temporarily unavailable.')
      return defaultPost(endpoint, ...args)
    })
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Programs' }))
    fireEvent.change(screen.getByLabelText('Adaptation reason'), { target: { value: 'Reduce training volume.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Adapt' }))
    expect(await screen.findByText('Adaptation is temporarily unavailable.')).toBeTruthy()
    expect((screen.getByLabelText('Adaptation reason') as HTMLTextAreaElement).value).toBe('Reduce training volume.')
    expect(post.mock.calls.filter(([endpoint]) => endpoint === '/training/programs/list')).toHaveLength(1)
  })

  it('handles days without exercises', async () => {
    const defaultPost = post.getMockImplementation()!
    post.mockImplementation(async (endpoint, ...args) => {
      if (endpoint === '/training/programs/list') return { items: [{ id: 1, version: 1, goal: 'Recovery', program: { days: [{ day: 'Tuesday', focus: 'Rest', movements: [] }] }, created_at: '2026-10-01T00:00:00Z' }] }
      return defaultPost(endpoint, ...args)
    })
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Programs' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Expand row' }))
    expect(screen.getByText('No exercises listed for this day.')).toBeTruthy()
  })

  it('renders Markdown returned by exercise guidance search', async () => {
    const defaultPost = post.getMockImplementation()!
    post.mockImplementation(async (endpoint, ...args) => {
      if (endpoint === '/training/exercises/search') return { items: [{ name: 'Squat', guidance: '## Setup\n\n- Stand tall.\n- Brace gently.\n\n**Safety**\n\nStop for pain.' }] }
      return defaultPost(endpoint, ...args)
    })
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Exercise guidance' }))
    fireEvent.change(screen.getByPlaceholderText('Search an exercise'), { target: { value: 'squat' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByRole('heading', { name: 'Setup' })).toBeTruthy()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('Stop for pain.')).toBeTruthy()
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

  it('shows saved preferences separately from edits and updates only after saving', async () => {
    let finishSave!: (value: unknown) => void
    const defaultPost = post.getMockImplementation()!
    post.mockImplementation(async (endpoint, ...args) => {
      if (endpoint === '/training/preferences/update') return new Promise(resolve => { finishSave = resolve })
      return defaultPost(endpoint, ...args)
    })
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Preferences' }))
    expect(await screen.findByText('Saved preferences')).toBeTruthy()
    expect(await screen.findByText('Dumbbells, bench')).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy()
    expect(screen.getByText('45 minutes')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Equipment (comma separated)'), { target: { value: 'Resistance bands' } })
    fireEvent.change(screen.getByLabelText('Days per week'), { target: { value: '4' } })
    fireEvent.change(screen.getByLabelText('Session minutes'), { target: { value: '30' } })
    expect(screen.getByText('Dumbbells, bench')).toBeTruthy()
    expect(screen.queryByText('Resistance bands')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Save preferences' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/training/preferences/update', expect.objectContaining({ equipment: ['Resistance bands'], training_days_per_week: 4, session_duration_minutes: 30 })))
    expect(screen.getByText('Dumbbells, bench')).toBeTruthy()
    finishSave({ equipment: ['Resistance bands'], training_days_per_week: 4, session_duration_minutes: 30, preferences: {} })
    expect(await screen.findByText('Resistance bands')).toBeTruthy()
    expect(screen.getByText('4')).toBeTruthy()
    expect(screen.getByText('30 minutes')).toBeTruthy()
    expect(screen.queryByText('Dumbbells, bench')).toBeNull()
  })

  it('shows placeholders for empty saved preferences', async () => {
    const defaultPost = post.getMockImplementation()!
    post.mockImplementation(async (endpoint, ...args) => {
      if (endpoint === '/training/preferences/get') return { equipment: [], training_days_per_week: null, session_duration_minutes: null, preferences: {} }
      return defaultPost(endpoint, ...args)
    })
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Preferences' }))
    expect(await screen.findAllByText('Not specified')).toHaveLength(3)
  })

  it('expands and collapses saved workout notes without fetching additional data', async () => {
    const notes = 'Felt strong today.\nKeep the same load next session.'
    const defaultPost = post.getMockImplementation()!
    post.mockImplementation(async (endpoint, ...args) => {
      if (endpoint === '/training/workouts/list') return { items: [{ id: 1, description: 'Strength session', occurred_at: '2026-10-01T00:00:00Z', duration_minutes: 45, session_rpe: 7, notes }] }
      return defaultPost(endpoint, ...args)
    })
    const { container } = renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Workout log' }))
    expect(await screen.findByText('Strength session')).toBeTruthy()
    expect(container.querySelector('.training-workout-notes')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Expand row' }))
    expect(container.querySelector('.training-workout-notes')?.textContent).toBe(notes)
    fireEvent.click(screen.getByRole('button', { name: 'Collapse row' }))
    expect(screen.getByRole('button', { name: 'Expand row' })).toBeTruthy()
    expect(container.querySelector('.ant-table-expanded-row')?.getAttribute('style')).toContain('display: none')
    expect(post.mock.calls.filter(([endpoint]) => endpoint === '/training/workouts/list')).toHaveLength(1)
  })

  it.each([null, undefined, '', '  \n  '])('shows No notes recorded for blank notes: %j', async notes => {
    const defaultPost = post.getMockImplementation()!
    post.mockImplementation(async (endpoint, ...args) => {
      if (endpoint === '/training/workouts/list') return { items: [{ id: 1, description: 'Workout without notes', occurred_at: '2026-10-01T00:00:00Z', duration_minutes: 30, session_rpe: 6, notes }] }
      return defaultPost(endpoint, ...args)
    })
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Workout log' }))
    expect(await screen.findByText('Workout without notes', {}, { timeout: 5000 })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Expand row' }))
    expect(screen.getByText('No notes recorded')).toBeTruthy()
  })
})