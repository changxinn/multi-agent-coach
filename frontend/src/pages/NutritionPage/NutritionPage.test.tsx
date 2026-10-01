import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { NutritionPage } from './NutritionPage'

const { post } = vi.hoisted(() => ({ post: vi.fn() }))

post.mockImplementation((endpoint: string) => {
  if (endpoint === '/nutrition/daily-summary') {
    return Promise.resolve({
      calories: 0,
      protein_g: 0,
      carbohydrate_g: 0,
      fat_g: 0,
      fiber_g: 0,
      meal_count: 0,
      remaining: {},
    })
  }
  if (endpoint === '/nutrition/profile/get' || endpoint === '/nutrition/targets/active') {
    return Promise.resolve({})
  }
  return Promise.resolve({ items: [] })
})

vi.mock('@/lib/api', () => ({ api: { post } }))

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <NutritionPage />
    </QueryClientProvider>,
  )
}

describe('NutritionPage', () => {
  it('renders the nutrition overview and loads today’s summary', async () => {
    renderPage()

    expect(screen.getByRole('heading', { name: 'Nutrition' })).toBeTruthy()
    expect(screen.getByText('Track user-owned meals, USDA-backed food data, targets, and adherence.')).toBeTruthy()
    expect(screen.getByText('Review today’s calorie and macro totals, remaining targets, and adherence. Log meals to keep these figures up to date.')).toBeTruthy()

    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/daily-summary', expect.any(Object)))
  })

  it('loads the data for each non-default nutrition workflow tab', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('tab', { name: 'Meal Log' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/meals/list', expect.any(Object)))
    expect(screen.getByText('No meals logged today.')).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: 'Profile & Targets' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/profile/get', {}))
    expect(screen.getByText('No active nutrition targets')).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: 'Meal Plans' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/meal-plans/list', {}))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/meal-plans/active', expect.any(Object)))
    expect(screen.getByText('No active meal plan covers today.')).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: 'Progress' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/adherence', expect.any(Object)))
    expect(screen.getByText('Last 7 days')).toBeTruthy()
  })
})