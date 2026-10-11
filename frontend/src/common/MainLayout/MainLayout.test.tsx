import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/lib/authStore'
import { MainLayout } from './MainLayout'

const { get, shell } = vi.hoisted(() => ({ get: vi.fn(), shell: vi.fn() }))

vi.mock('@/lib/api', () => ({ api: { get } }))
vi.mock('@/common/AppShell', () => ({
  default: (props: Record<string, unknown>) => {
    shell(props)
    const pages = props.pages as Array<{ label: string }>
    return <div>
      <span data-testid="page-label">{props.currentPageLabel as string}</span>
      <span data-testid="user-name">{props.userName as string}</span>
      <span data-testid="pages">{pages.map((page) => page.label).join(', ')}</span>
      <button onClick={() => (props.onNavigate as (path: string) => void)('/nutrition')}>navigate</button>
      <button onClick={props.onLogout as () => void}>logout</button>
      {props.children as React.ReactNode}
    </div>
  },
}))

function renderLayout(path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}><MainLayout><p>Page content</p></MainLayout></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('MainLayout', () => {
  beforeEach(() => {
    get.mockReset()
    shell.mockClear()
    useAuthStore.setState({
      user: { sub: '1', email: 'member@example.com', name: 'Member', exp: 4_102_444_800 },
      logout: vi.fn(),
    })
  })

  it('hides compatibility reviews until the profile grants reviewer access', async () => {
    get.mockResolvedValue({ is_nutrition_compatibility_admin: false })
    renderLayout('/nutrition')

    await waitFor(() => expect(get).toHaveBeenCalledWith('/auth/profile'))
    expect(screen.getByTestId('page-label').textContent).toBe('Nutrition')
    expect(screen.getByTestId('user-name').textContent).toBe('Member')
    expect(screen.getByTestId('pages').textContent).not.toContain('Compatibility Reviews')
    expect(screen.getByText('Page content')).toBeTruthy()
  })

  it('shows reviewer navigation and delegates navigation and logout', async () => {
    const logout = vi.fn()
    useAuthStore.setState({ user: null, logout })
    get.mockResolvedValue({ is_nutrition_compatibility_admin: true })
    renderLayout('/unknown')

    await waitFor(() => expect(screen.getByTestId('pages').textContent).toContain('Compatibility Reviews'))
    expect(screen.getByTestId('page-label').textContent).toBe('Dashboard')
    expect(screen.getByTestId('user-name').textContent).toBe('User')

    fireEvent.click(screen.getByRole('button', { name: 'navigate' }))
    await waitFor(() => expect(screen.getByTestId('page-label').textContent).toBe('Nutrition'))
    fireEvent.click(screen.getByRole('button', { name: 'logout' }))
    expect(logout).toHaveBeenCalledOnce()
  })
})