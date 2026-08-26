import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react-swc'
import path from 'path'
import fs from 'fs'

export default defineConfig(({ mode }) => {
  // Load environment files from environments folder
  const envDir = path.resolve(__dirname, 'environments')
  const env = loadEnv(mode, envDir, '')
  
  // Create proxy for environment variables
  const processEnv = {} as Record<string, string>
  Object.keys(env).forEach(key => {
    processEnv[`VITE_${key}`] = env[key]
  })

  return {
    plugins: [react()],
    envDir,
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
  }
})
