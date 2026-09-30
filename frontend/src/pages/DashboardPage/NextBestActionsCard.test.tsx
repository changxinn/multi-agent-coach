import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { NextBestActionsCard } from './NextBestActionsCard'

const navigate = vi.fn()
vi.mock('react-router-dom', async importOriginal => ({ ...await importOriginal<typeof import('react-router-dom')>(), useNavigate: () => navigate }))

afterEach(() => navigate.mockReset())

describe('NextBestActionsCard', () => {
  it('renders the empty state', () => {
    render(<MemoryRouter><NextBestActionsCard actions={[]} /></MemoryRouter>)

    expect(screen.getByText('You’re all caught up for now.')).toBeTruthy()
  })

  it('renders an action and navigates to its route', () => {
    render(<MemoryRouter><NextBestActionsCard actions={[{ id: 'log-lunch', priority: 1, severity: 'info', title: 'Log lunch', description: 'Keep totals current', route: '/nutrition' }]} /></MemoryRouter>)

    expect(screen.getByText('Log lunch')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    expect(navigate).toHaveBeenCalledWith('/nutrition')
  })
})