import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
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
})