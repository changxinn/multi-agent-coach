import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'
import './lib/register-deep-chat'
import './index.css'
import App from './App.tsx'
import { queryClient } from './lib/queryClient'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <ConfigProvider
          theme={{
            token: {
              colorPrimary: '#1890ff',
              borderRadius: 6,
              // Font families
              fontFamily: "'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
              fontFamilyCode: "'Inter', ui-monospace, SFMono-Regular, 'SF Mono', Consolas, monospace",
              // Font sizes
              fontSize: 14,
              fontSizeSM: 12,
              fontSizeLG: 16,
              fontSizeXL: 20,
            },
          }}
        >
          <App />
        </ConfigProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
)
