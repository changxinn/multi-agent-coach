// Environment Configuration
// These values are set based on the .env file used during build

export const envConfig = {
  // Environment name: 'development', 'qa', or 'production'
  appEnv: import.meta.env.VITE_APP_ENV || 'development',
  
  // Application display name
  appName: import.meta.env.VITE_APP_NAME || 'Workforce Console',
  
  // Backend API base URL
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  
  // Enable quick login (dropdown for dev/QA testing)
  enableQuickLogin: import.meta.env.VITE_ENABLE_QUICK_LOGIN === 'true',
  
  // Show debug information
  showDebugInfo: import.meta.env.VITE_SHOW_DEBUG_INFO === 'true',
  
  // Azure AD authentication (production only)
  useAzureAd: import.meta.env.VITE_USE_AZURE_AD === 'true',
  
  // Frontend base URL for redirects
  frontendBaseUrl: import.meta.env.VITE_FRONTEND_BASE_URL || 'http://localhost:5174',
}

// Helper functions
export const isDevelopment = () => envConfig.appEnv === 'development'
export const isQA = () => envConfig.appEnv === 'qa'
export const isProduction = () => envConfig.appEnv === 'production'
export const isTestEnvironment = () => isDevelopment() || isQA()
