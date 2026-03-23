import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import './lib/i18n'
import { initObservability } from './lib/observability'
import App from './App.tsx'
import { queryClient } from './lib/queryClient'
import { ThemeProvider } from './providers/ThemeProvider'

// Phase 2: FE 에러 추적 + Web Vitals 수집 초기화
initObservability()

createRoot(document.getElementById('root')!).render(
 <StrictMode>
 <QueryClientProvider client={queryClient}>
 <ThemeProvider>
 <App />
 </ThemeProvider>
 </QueryClientProvider>
 </StrictMode>,
)
