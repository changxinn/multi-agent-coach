import CryptoJS from 'crypto-js'
import ChatbotConfig, { ChatbotConfig as ChatbotSettings } from './chatbot-config'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface ChatResponse {
  message: string
  model?: string
  usage?: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
}

export interface StreamResult {
  success: boolean
  isDemoResponse?: boolean
  isOllamaResponse?: boolean
  error?: string
}

export interface ApiResult {
  success: boolean
  message?: string
  error?: string
  isDemoResponse?: boolean
  isOllamaResponse?: boolean
}

export interface ChatOptions {
  streaming?: boolean
  onToken?: (token: string) => void
  enableDemoResponse?: boolean
  backendUrl?: string
  timeout?: number
}

interface InternalChatbotConfig {
  enableDemoResponse: boolean
  backendUrl?: string
  timeout?: number
}

const defaultConfig: InternalChatbotConfig = {
  enableDemoResponse: false,  // Disabled by default - only use when backend is unavailable
  backendUrl: API_BASE_URL,
  timeout: 30000,
}

// Demo mode tracking
const DEMO_MODE_SHOWN_KEY = 'chat_demo_mode_shown'

export function wasDemoModeShown(): boolean {
  return sessionStorage.getItem(DEMO_MODE_SHOWN_KEY) === 'true'
}

export function setDemoModeShown(): void {
  sessionStorage.setItem(DEMO_MODE_SHOWN_KEY, 'true')
}

export function clearDemoModeShown(): void {
  sessionStorage.removeItem(DEMO_MODE_SHOWN_KEY)
}

// Session ID generation with hash
export function generateSessionId(userEmail: string): string {
  const timestamp = Date.now()
  const raw = `${userEmail}_${timestamp}`
  const hash = CryptoJS.SHA256(raw).toString(CryptoJS.enc.Hex)
  return `chat_${hash.substring(0, 16)}`
}

export function isValidSessionId(sessionId: string): boolean {
  return /^chat_[a-f0-9]{16}$/.test(sessionId)
}

export function getSessionId(userEmail: string): string {
  const sessionKey = `chat_session_${userEmail}`
  const stored = localStorage.getItem(sessionKey)
  
  if (stored && isValidSessionId(stored)) {
    return stored
  }
  
  const newId = generateSessionId(userEmail)
  localStorage.setItem(sessionKey, newId)
  return newId
}

export function setSessionId(id: string): void {
  localStorage.setItem('matechat_session_id', id)
}

export function clearSessionId(userEmail: string): void {
  localStorage.removeItem(`chat_session_${userEmail}`)
}

export async function callChatbotAPI(
  messages: ChatMessage[],
  token: string,
  sessionId: string,
  config: any = defaultConfig
): Promise<ApiResult> {
  const backendUrl = config.backendUrl || API_BASE_URL
  
  try {
    console.log('Chat API Call:', {
      url: `${backendUrl}/chat`,
      tokenPresent: !!token,
      tokenLength: token?.length,
      sessionId: sessionId,
      tokenStart: token?.substring(0, 20) + '...'
    })
    
    const response = await fetch(`${backendUrl}/chat`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        messages: messages,
        session_id: sessionId,
      }),
      signal: AbortSignal.timeout(config.timeout),
    })
    
    console.log('Response status:', response.status)
    
    // Try to read error response body
    let errorBody = null
    if (!response.ok) {
      try {
        errorBody = await response.text()
        console.error('Error response body:', errorBody)
      } catch (e) {
        console.error('Could not read error body:', e)
      }
    }

    if (!response.ok) {
      throw new Error(`Server error: ${response.status} - ${errorBody || response.statusText}`)
    }

    const data: ChatResponse = await response.json()
    console.log('✅ Backend response received:', {
      messageLength: data.message?.length,
      model: data.model,
      hasUsage: !!data.usage
    })
    
    return {
      success: true,
      message: data.message || 'I apologize, I could not generate a response.',
      isDemoResponse: false,
      isOllamaResponse: true,
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Failed to get response'
    console.error('❌ Backend error:', errorMessage)
    
    if (config.enableDemoResponse) {
      const lastUserMessage = messages.filter(m => m.role === 'user').pop()?.content || ''
      const demoResponse = generateDemoResponse(lastUserMessage)
      
      console.warn('⚠️ Using demo mode as fallback')
      setDemoModeShown()
      
      return {
        success: true,
        message: demoResponse,
        isDemoResponse: true,
        isOllamaResponse: false,
        error: `Backend unavailable (using demo mode): ${errorMessage}`,
      }
    } else {
      console.error('❌ Demo mode disabled - returning error to user')
      return {
        success: false,
        error: `Unable to connect to backend: ${errorMessage}. Please ensure the backend server is running at ${backendUrl}`,
        isDemoResponse: false,
        isOllamaResponse: false,
      }
    }
  }
}

export function generateDemoResponse(userMessage: string): string {
  const lowerMessage = userMessage.toLowerCase()
  
  if (lowerMessage.includes('employee') || lowerMessage.includes('staff')) {
    return "You can view all employees in the **Table Listing** page. It shows employee details including name, email, department, role, status, and location. You can search, filter, and manage employee records there."
  }
  if (lowerMessage.includes('project') || lowerMessage.includes('timeline')) {
    return "The **Timeline** page shows project milestones and deliverables. You can track project progress, view completed and pending tasks, and see who's assigned to each milestone."
  }
  if (lowerMessage.includes('form') || lowerMessage.includes('input')) {
    return "The **Forms** page demonstrates various form components with validation using React Hook Form and Zod. It includes examples of text inputs, passwords, and form submission."
  }
  if (lowerMessage.includes('hello') || lowerMessage.includes('hi')) {
    return "Hello! 👋 How can I assist you today? Feel free to ask me anything about the workforce console system."
  }
  if (lowerMessage.includes('help')) {
    return "I can help you with:\n\n1. **Navigation** - Guide you through different pages\n2. **Features** - Explain system capabilities\n3. **Employee Info** - Direct you to employee management\n4. **Projects** - Show project tracking features\n\nWhat would you like to know?"
  }
  
  return "Thank you for your message! I'm here to help you with any questions about the workforce console. You can ask me about employees, projects, forms, or navigation."
}

export function isBackendConfigured(): boolean {
  return !!API_BASE_URL
}

export { ChatbotSettings as ChatbotConfig }

export async function clearChatHistoryAPI(sessionId?: string): Promise<void> {
  try {
    const url = sessionId 
      ? `${API_BASE_URL}/chat/history/${sessionId}`
      : `${API_BASE_URL}/chat/history`;
    
    await fetch(url, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error('Failed to clear chat history:', error);
  }
}

export async function streamChatbotAPI(
  messages: ChatMessage[],
  token: string,
  sessionId: string,
  onToken: (token: string) => void,
  configOrAbortController: InternalChatbotConfig | AbortController = defaultConfig,
  config: InternalChatbotConfig = defaultConfig
): Promise<StreamResult> {
  const backendUrl = (configOrAbortController instanceof AbortController ? config : configOrAbortController).backendUrl || API_BASE_URL
  
  // Support passing AbortController as second parameter
  const abortController = configOrAbortController instanceof AbortController 
    ? configOrAbortController 
    : new AbortController()
  
  console.log('📡 Attempting to connect to backend:', {
    url: backendUrl,
    hasToken: !!token,
    tokenLength: token?.length,
    sessionId,
    demoModeEnabled: config.enableDemoResponse
  })
  
  try {
    const message = messages.filter(m => m.role === 'user').pop()?.content || ''
    
    console.log('📡 Fetching stream endpoint:', `${backendUrl}/chat/stream?message=${encodeURIComponent(message.substring(0, 50))}...&session_id=${sessionId}`)
    
    const response = await fetch(
      `${backendUrl}/chat/stream?message=${encodeURIComponent(message)}&session_id=${sessionId}`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        signal: abortController.signal
      }
    )
    
    console.log('📡 Response status:', response.status, response.ok ? '✅' : '❌')
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error('❌ Error response body:', errorText)
      throw new Error(`Server error: ${response.status} - ${errorText}`)
    }
    
    let reader;
    if (response && response.body) {
      reader = response.body.getReader()
      console.log('📡 Stream reader initialized')
    }
    const decoder = new TextDecoder()
    
    try {
      let buffer = ''
      let tokenCount = 0
      
      while (true && reader) {
        const { done, value } = await reader.read()
        if (done) {
          console.log('📡 Stream completed, total tokens:', tokenCount)
          break
        }
        
        const chunk = decoder.decode(value, { stream: true })
        buffer += chunk
        
        // Process complete SSE messages (separated by double newline)
        const messages = buffer.split('\n\n')
        buffer = messages.pop() || '' // Keep incomplete message in buffer
        
        for (const msg of messages) {
          const lines = msg.split('\n')
          for (const line of lines) {
            // Check for 'data:' prefix
            if (line.startsWith('data:')) {
              try {
                // Parse the JSON data
                const dataStr = line.substring(5).trim()
                const data = JSON.parse(dataStr)
                
                // Extract token from the JSON
                if (data.token !== undefined) {
                  tokenCount++
                  if (tokenCount <= 5 || tokenCount % 50 === 0) {
                    console.log(`📡 Token ${tokenCount}:`, data.token.substring(0, 20))
                  }
                  onToken(data.token)
                }
                
                // Check for completion or error
                if (data.is_complete === true) {
                  console.log('📡 Stream marked as complete')
                  return { success: true, isOllamaResponse: true }
                }
                
                if (data.error) {
                  throw new Error(data.error)
                }
              } catch (parseError) {
                console.error('Failed to parse SSE data:', line, parseError)
              }
            }
          }
        }
      }
    } finally {
      // Release the reader
      if (reader) reader.releaseLock()
    }
    
    return {
      success: true,
      isOllamaResponse: true
    }
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Stream failed'
    
    // Fallback to demo mode with simulated streaming
    if (config.enableDemoResponse) {
      const lastUserMessage = messages.filter(m => m.role === 'user').pop()?.content || ''
      const demoResponse = generateDemoResponse(lastUserMessage)
      
      // Simulate streaming for demo mode (uses config speed)
      let index = 0
      const demoInterval = setInterval(() => {
        if (index < demoResponse.length) {
          onToken(demoResponse[index])
          index++
        } else {
          clearInterval(demoInterval)
        }
      }, ChatbotConfig.TYPEWRITER.SPEED_MS)
      
      setDemoModeShown()
      
      return {
        success: true,
        isDemoResponse: true,
        isOllamaResponse: false,
        error: `Backend unavailable (using demo mode): ${errorMessage}`
      }
    }
    
    return {
      success: false,
      error: errorMessage
    }
  }
}
