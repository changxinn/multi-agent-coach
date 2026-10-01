import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RecoveryStatusCard } from './RecoveryStatusCard'
import type { RecoverySnapshot } from './types'

const navigate = vi.fn()
vi.mock('react-router-dom', async importOriginal => ({ ...await importOriginal<typeof import('react-router-dom')>(), useNavigate: () => navigate }))

const recovery = (status: RecoverySnapshot['status']): RecoverySnapshot => ({
  status,
  message: status === 'unavailable' ? 'Recovery is unavailable' : status === 'no_assessment' ? 'Complete a recovery assessment' : null,
  assessment_score: status === 'green' ? 82 : null,
  assessment_created_at: null,
  sleep_duration_minutes: 450,
  sleep_quality: 4,
  sleep_logged_at: null,
  energy: 8,
  soreness: 2,
  stress: 3,
  check_in_created_at: null,
  trend: [],
})

afterEach(() => navigate.mockReset())

describe('RecoveryStatusCard', () => {
  it.each([
    ['green' as const, '7h 30m · quality 4/5'],
    ['no_assessment' as const, 'Complete a recovery assessment'],
    ['unavailable' as const, 'Recovery is unavailable'],
  ])('renders the %s state and navigates', (status, expectedText) => {
    render(<MemoryRouter><RecoveryStatusCard recovery={recovery(status)} /></MemoryRouter>)

    expect(screen.getByText(expectedText)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Open Recovery' }))
    expect(navigate).toHaveBeenCalledWith('/recovery-table')
  })
})