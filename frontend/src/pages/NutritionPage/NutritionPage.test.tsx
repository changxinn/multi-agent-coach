import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { idempotencyKey, NutritionPage } from './NutritionPage'

const { post } = vi.hoisted(() => ({ post: vi.fn() }))

const defaultPost = (endpoint: string) => {
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
}

post.mockImplementation(defaultPost)

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
  beforeEach(() => {
    post.mockClear()
    post.mockImplementation(defaultPost)
  })

  it('uses secure UUIDs for meal-plan idempotency keys and rejects unavailable crypto', () => {
    const originalCrypto = globalThis.crypto
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: { randomUUID: () => 'secure-id' } })
    expect(idempotencyKey()).toBe('secure-id')
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: undefined })
    expect(() => idempotencyKey()).toThrow('Secure random UUID generation is unavailable')
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: originalCrypto })
  })

  it('renders the nutrition overview and loads today’s summary', async () => {
    renderPage()

    expect(screen.getByRole('heading', { name: 'Nutrition' })).toBeTruthy()
    expect(screen.getByText('Track user-owned meals, USDA-backed food data, targets, and adherence.')).toBeTruthy()
    expect(screen.getByText('Review today’s calorie and macro totals, remaining targets, and adherence. Log meals to keep these figures up to date.')).toBeTruthy()

    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/daily-summary', expect.any(Object)))
  })

  it('renders summary and adherence error states', async () => {
    post.mockImplementation((endpoint: string) => endpoint === '/nutrition/daily-summary'
      ? Promise.reject(new Error('Summary unavailable'))
      : endpoint === '/nutrition/adherence'
        ? Promise.reject(new Error('Adherence unavailable'))
        : defaultPost(endpoint))
    renderPage()

    await waitFor(() => expect(screen.getByText('Summary unavailable')).toBeTruthy())

    fireEvent.click(screen.getByRole('tab', { name: 'Progress' }))

    await waitFor(() => expect(screen.getByText('Adherence unavailable')).toBeTruthy())
  })

  it('renders numeric and missing adherence values', async () => {
    post.mockImplementation((endpoint: string) => endpoint === '/nutrition/daily-summary'
      ? Promise.resolve({ calories: 100, protein_g: 20, carbohydrate_g: 30, fat_g: 10, fiber_g: 5, meal_count: 1, remaining: {} })
      : endpoint === '/nutrition/adherence'
        ? Promise.resolve({ items: [{ summary_date: '2026-09-30', calories: 100, protein_g: 20, calorie_adherence_pct: null }, { summary_date: '2026-09-29', calories: 200, protein_g: 30, calorie_adherence_pct: 75 }] })
        : defaultPost(endpoint))
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Progress' }))

    await waitFor(() => expect(screen.getByText('No target')).toBeTruthy())
    expect(screen.getByText('75%')).toBeTruthy()
  })

  it('opens the meal log dialog and loads the USDA catalogue', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Meal Log' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Log meal' })).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Log meal' }))

    expect(await screen.findByText('Confirm meal log')).toBeTruthy()
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/foods/catalogue', {}))
  })

  it('shows populated active targets and opens the meal-plan generator', async () => {
    post.mockImplementation((endpoint: string) => endpoint === '/nutrition/targets/active'
      ? Promise.resolve({ calorie_target_kcal: 2000, protein_target_g: 120, carbohydrate_target_g: 220, fat_target_g: 65, fiber_target_g: 30 })
      : defaultPost(endpoint))
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Profile & Targets' }))

    expect(await screen.findByText('Active targets')).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: 'Meal Plans' }))
    expect(await screen.findByRole('button', { name: 'Generate meal plan' })).toBeTruthy()
    const generateButtons = screen.getAllByRole('button', { name: 'Generate meal plan' })
    fireEvent.click(generateButtons[generateButtons.length - 1])
    expect(await screen.findByRole('dialog')).toBeTruthy()
  }, 30_000)

  it('loads the data for each non-default nutrition workflow tab', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('tab', { name: 'Meal Log' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/meals/list', expect.any(Object)))
    expect(screen.getByText('No meals logged today.')).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: 'Profile & Targets' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/profile/get', {}))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/targets/active', {}))
    await waitFor(() => expect(screen.getByText('No active nutrition targets')).toBeTruthy())

    fireEvent.click(screen.getByRole('tab', { name: 'Meal Plans' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/meal-plans/list', {}))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/meal-plans/active', expect.any(Object)))
    expect(screen.getByText('No active meal plan covers today.')).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: 'Progress' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/adherence', expect.any(Object)))
    expect(screen.getByText('Last 7 days')).toBeTruthy()
  }, 30_000)
})