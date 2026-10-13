import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NutritionPage } from './NutritionPage'
import { idempotencyKey } from '@/lib/idempotencyKey'

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

  it('presents a single USDA food selector', async () => {
    post.mockImplementation((endpoint: string) => endpoint === '/nutrition/foods/catalogue'
      ? Promise.resolve({ items: [{ provider_food_id: 'oats-1', description: 'Rolled oats', calories_per_100g: 389, protein_g_per_100g: 17, carbohydrate_g_per_100g: 66, fat_g_per_100g: 7, fiber_g_per_100g: 11 }] })
      : defaultPost(endpoint))
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Meal Log' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Log meal' }))
    const foodSelect = await screen.findByRole('combobox', { name: 'Food' })
    fireEvent.mouseDown(foodSelect)
    expect(await screen.findByRole('option', { name: 'Rolled oats' })).toBeTruthy()
    expect(screen.queryByText(/manual food/i)).toBeNull()
  })

  it('edits a single USDA meal and preserves the original meal time', async () => {
    post.mockImplementation((endpoint: string) => endpoint === '/nutrition/meals/list'
      ? Promise.resolve({ items: [{ id: 7, eaten_at: '2026-10-01T08:00:00.000Z', meal_type: 'breakfast', notes: 'Original note', items: [{ food_name: 'Rolled oats', quantity: 100, grams: 100, unit: 'g', calories: 389, protein_g: 17, carbohydrate_g: 66, fat_g: 7, fiber_g: 11, source: 'usda', food_cache_id: 4 }] }] })
      : endpoint === '/nutrition/foods/catalogue'
        ? Promise.resolve({ items: [{ id: 4, provider_food_id: 'oats-1', description: 'Rolled oats', calories_per_100g: 389, protein_g_per_100g: 17, carbohydrate_g_per_100g: 66, fat_g_per_100g: 7, fiber_g_per_100g: 11 }] })
        : defaultPost(endpoint))
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Meal Log' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))

    expect(await screen.findByText('Edit meal log')).toBeTruthy()
    expect(screen.getByDisplayValue('100')).toBeTruthy()
    expect(screen.getByDisplayValue('Original note')).toBeTruthy()
    expect(screen.getByText('Rolled oats (existing food)')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/meals/replace', expect.objectContaining({
      meal_id: 7,
      meal_type: 'breakfast',
      notes: 'Original note',
      eaten_at: '2026-10-01T08:00:00.000Z',
      items: [expect.objectContaining({ food_name: 'Rolled oats', grams: 100, source: 'usda', food_cache_id: 4 })],
    })))
  })

  it.each(['meal_plan', 'manual_estimate', 'usda'])('edits %s food without a catalogue reference', async source => {
    post.mockImplementation((endpoint: string) => endpoint === '/nutrition/meals/list'
      ? Promise.resolve({ items: [{ id: 8, eaten_at: '2026-10-01T08:00:00.000Z', meal_type: 'lunch', notes: 'Original', items: [{ food_name: 'Rice', quantity: 1, unit: 'serving', grams: 150, calories: 200, protein_g: 4, carbohydrate_g: 40, fat_g: 2, fiber_g: 1, source }] }] })
      : defaultPost(endpoint))
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Meal Log' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    expect(await screen.findByText('Rice (existing food)')).toBeTruthy()
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantity (serving)' }), { target: { value: '2' } })
    fireEvent.change(screen.getByDisplayValue('Original'), { target: { value: 'Updated' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/meals/replace', expect.objectContaining({
      meal_id: 8, eaten_at: '2026-10-01T08:00:00.000Z', notes: 'Updated',
      items: [expect.objectContaining({ food_name: 'Rice', quantity: 2, unit: 'serving', grams: 300, calories: 400, protein_g: 8, carbohydrate_g: 80, fat_g: 4, fiber_g: 2, source })],
    })))
    expect(post.mock.calls.some(([endpoint]) => endpoint === '/nutrition/foods/catalogue')).toBe(true)
  })

  it('replaces a serving-based meal-plan food with a USDA food in grams', async () => {
    post.mockImplementation((endpoint: string) => endpoint === '/nutrition/meals/list'
      ? Promise.resolve({ items: [{ id: 9, eaten_at: '2026-10-01T08:00:00.000Z', meal_type: 'lunch', notes: 'Keep note', items: [{ food_name: 'Rice', quantity: 1, unit: 'serving', grams: 150, calories: 200, source: 'meal_plan' }] }] })
      : endpoint === '/nutrition/foods/catalogue'
        ? Promise.resolve({ items: [{ id: 4, provider_food_id: 'oats-1', description: 'Rolled oats', calories_per_100g: 400, protein_g_per_100g: 10, carbohydrate_g_per_100g: 60, fat_g_per_100g: 8, fiber_g_per_100g: 4 }] })
        : defaultPost(endpoint))
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Meal Log' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    fireEvent.mouseDown(await screen.findByRole('combobox', { name: 'Food' }))
    fireEvent.click(await screen.findByText('Rolled oats'))
    expect((await screen.findByRole('spinbutton', { name: 'Quantity (g)' })).getAttribute('value')).toBe('150')
    expect(await screen.findByText('Verified USDA nutrients')).toBeTruthy()
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Quantity (g)' }), { target: { value: '200' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/meals/replace', {
      meal_id: 9, eaten_at: '2026-10-01T08:00:00.000Z', meal_type: 'lunch', notes: 'Keep note',
      items: [{ food_name: 'Rolled oats', quantity: 200, unit: 'g', grams: 200, calories: 800, protein_g: 20, carbohydrate_g: 120, fat_g: 16, fiber_g: 8, source: 'usda', food_cache_id: 4 }],
    }))
  }, 30_000)

  it('keeps the original food editable when the catalogue fails', async () => {
    post.mockImplementation((endpoint: string) => endpoint === '/nutrition/meals/list'
      ? Promise.resolve({ items: [{ id: 10, eaten_at: '2026-10-01T08:00:00.000Z', meal_type: 'lunch', items: [{ food_name: 'Rice', quantity: 100, unit: 'g', calories: 200, source: 'manual_estimate' }] }] })
      : endpoint === '/nutrition/foods/catalogue' ? Promise.reject(new Error('Catalogue unavailable')) : defaultPost(endpoint))
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Meal Log' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    expect(await screen.findByText(/You can still update the existing food/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/nutrition/meals/replace', expect.objectContaining({ meal_id: 10, items: [expect.objectContaining({ food_name: 'Rice', source: 'manual_estimate', quantity: 100 })] })))
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

  it('generates a meal-plan draft with an idempotency key and displays generation failures', async () => {
    const originalCrypto = globalThis.crypto
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: { randomUUID: () => 'meal-plan-key' } })
    post.mockImplementation((endpoint: string) => endpoint === '/nutrition/meal-plans/generate'
      ? Promise.reject(new Error('Generation unavailable'))
      : defaultPost(endpoint))
    renderPage()

    fireEvent.click(screen.getByRole('tab', { name: 'Meal Plans' }))
    const generateButtons = await screen.findAllByRole('button', { name: 'Generate meal plan' })
    fireEvent.click(generateButtons[generateButtons.length - 1])
    fireEvent.click(await screen.findByRole('button', { name: 'Generate draft' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/nutrition/meal-plans/generate',
      expect.objectContaining({ meal_types: ['breakfast', 'lunch', 'dinner'] }),
      { headers: { 'Idempotency-Key': 'meal-plan-key' } },
    ))
    expect(await screen.findByText('Generation unavailable')).toBeTruthy()
    Object.defineProperty(globalThis, 'crypto', { configurable: true, value: originalCrypto })
  }, 30_000)
})