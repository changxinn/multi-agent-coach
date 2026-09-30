import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { NutritionStatusCard } from './NutritionStatusCard'
import type { NutritionSnapshot } from './types'

const navigate = vi.fn()
vi.mock('react-router-dom', async importOriginal => ({ ...await importOriginal<typeof import('react-router-dom')>(), useNavigate: () => navigate }))

const nutrition = (status: NutritionSnapshot['status']): NutritionSnapshot => ({
  status, message: status === 'unavailable' ? 'Nutrition is unavailable' : 'Set targets first', calories: 900, protein_g: 65, meal_count: 2,
  calorie_target_kcal: status === 'available' ? 2000 : null, protein_target_g: status === 'available' ? 120 : null,
  remaining_calories: null, remaining_protein_g: 55, calorie_adherence_pct: null, protein_adherence_pct: null, trend: [],
})

describe('NutritionStatusCard', () => {
  it.each([
    ['available' as const, 'Open Nutrition'], ['no_target' as const, 'Set targets'], ['unavailable' as const, 'Set targets'],
  ])('renders the %s state and navigates', (status, buttonName) => {
    render(<MemoryRouter><NutritionStatusCard nutrition={nutrition(status)} /></MemoryRouter>)
    expect(screen.getByText(status === 'available' ? 'Calories / 2000' : status === 'unavailable' ? 'Nutrition is unavailable' : 'Set targets first')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: buttonName }))
    expect(navigate).toHaveBeenCalledWith('/nutrition')
  })
})