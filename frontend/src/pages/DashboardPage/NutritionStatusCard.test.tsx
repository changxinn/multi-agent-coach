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

  it('clamps progress values and renders the adherence summary when data is present', () => {
    render(<MemoryRouter><NutritionStatusCard nutrition={{
      ...nutrition('available'), calories: -10, protein_g: 500, calorie_target_kcal: 100, protein_target_g: 100,
      trend: [{ date: '2026-09-30', calorie_adherence_pct: 125, protein_adherence_pct: 90, meal_count: 2 }],
    }} /></MemoryRouter>)

    expect(screen.getByRole('img', { name: 'Seven-day nutrition adherence. Last recorded adherence: 125% calories and 90% protein.' })).toBeTruthy()
    expect(screen.getByText('Calories / 100')).toBeTruthy()
    expect(screen.getByText('Protein / 100g')).toBeTruthy()
  })

  it('renders zero-value targets and the empty trend message safely', () => {
    render(<MemoryRouter><NutritionStatusCard nutrition={{
      ...nutrition('available'), calories: null, protein_g: null, calorie_target_kcal: 0, protein_target_g: 0,
    }} /></MemoryRouter>)

    expect(screen.getByText('No nutrition data recorded in the last 7 days.')).toBeTruthy()
    expect(screen.getByText('Calories / 0')).toBeTruthy()
  })
})