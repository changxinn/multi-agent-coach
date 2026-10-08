import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react-swc'
import path from 'path'
import { fileURLToPath } from 'url'

const configDirectory = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig(() => {
  // Load environment files from environments folder
  const envDir = path.resolve(configDirectory, 'environments')

  return {
    plugins: [react()],
    envDir,
    server: {
      allowedHosts: ['frontend'],
      headers: {
        'Cache-Control': 'no-store',
        'Content-Security-Policy': "default-src 'self'; base-uri 'self'; connect-src 'self' http://localhost:8000 ws://localhost:5174 ws://frontend:5174; font-src 'self'; frame-ancestors 'none'; img-src 'self' data:; object-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'",
        'Cross-Origin-Embedder-Policy': 'require-corp',
        'Cross-Origin-Opener-Policy': 'same-origin',
        'Cross-Origin-Resource-Policy': 'same-origin',
        'Permissions-Policy': 'accelerometer=(), camera=(), geolocation=(), gyroscope=(), microphone=(), payment=(), usb=()',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
      },
    },
    build: {
      chunkSizeWarningLimit: 2000, // in KiB (default is 500)
    },
    resolve: {
      alias: {
        '@': path.resolve(configDirectory, './src'),
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      testTimeout: 15_000,
      coverage: {
        provider: 'v8',
        reporter: ['text', 'lcov'],
        reportsDirectory: './coverage',
        include: ['src/**/*.{ts,tsx}'],
        exclude: [
          'src/**/*.test.{ts,tsx}',
          'src/test/**',
          'src/**/*.d.ts',
        ],
      },
    },
  }
})
