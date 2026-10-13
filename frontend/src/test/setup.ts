import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

// Ant Design rendering and chained queries can exceed the default one-second
// wait on CI, especially with coverage instrumentation enabled.
configure({ asyncUtilTimeout: 5000 })

afterEach(() => {
  cleanup()
})

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: () => ({
    matches: false,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }),
})

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

Object.defineProperty(globalThis, 'ResizeObserver', {
  writable: true,
  value: ResizeObserverMock,
})