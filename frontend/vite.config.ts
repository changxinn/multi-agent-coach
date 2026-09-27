import { defineConfig } from 'vite'
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
    build: {
      chunkSizeWarningLimit: 2000, // in KiB (default is 500)
    },
    resolve: {
      alias: {
        '@': path.resolve(configDirectory, './src'),
      },
    },
  }
})
