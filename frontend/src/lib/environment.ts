import { envConfig } from './envConfig'

export const environment = {
  appEnv: import.meta.env.VITE_APP_ENV || 'development',
  appName: import.meta.env.VITE_APP_NAME || 'Workforce Console',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  enableQuickLogin: import.meta.env.VITE_ENABLE_QUICK_LOGIN === 'true',
  showDebugInfo: import.meta.env.VITE_SHOW_DEBUG_INFO === 'true',
  useAzureAd: import.meta.env.VITE_USE_AZURE_AD === 'true',
  frontendBaseUrl: import.meta.env.VITE_FRONTEND_BASE_URL || 'http://localhost:5174',
}

export const isDevelopment = () => environment.appEnv === 'development'
export const isQA = () => environment.appEnv === 'qa'
export const isProduction = () => environment.appEnv === 'production'
export const isTestEnvironment = () => isDevelopment() || isQA()

export { envConfig }
