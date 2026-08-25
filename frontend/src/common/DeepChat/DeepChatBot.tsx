import { useState, useRef, useEffect, useCallback } from 'react'
import { CloseOutlined, SendOutlined, ExpandOutlined } from '@ant-design/icons'
import { Bot } from 'lucide-react'
import { Input, Button } from 'antd'
import { message } from 'antd'
import { marked } from 'marked'

marked.setOptions({
  gfm: true,
  breaks: true,
  async: false,
})

import { useAuthStore } from '../../lib/authStore'
import {
  getSessionId,
  clearSessionId,
  callChatbotAPI,
  streamChatbotAPI,
  wasDemoModeShown,
  clearDemoModeShown,
  type ChatMessage,
} from '../../lib/chatbot-api'
import {
  deepChatRequestBodyLimits,
  deepChatTextInputConfig,
  deepChatAuxiliaryStyle,
} from '../../lib/deep-chat-config'
import { ChatbotConfig } from '../../lib/chatbot-config'
import './DeepChatWrapper.css'

interface DeepChatBotProps {
  enableExpand?: boolean
  initialMessage?: string
  streaming?: boolean
  enableTypewriter?: boolean
  defaultOpen?: boolean
  showCloseButton?: boolean
  embedInPage?: boolean
}

export function DeepChatBot({
  enableExpand = true,
  initialMessage,
  streaming,
  enableTypewriter,
  defaultOpen = false,
  showCloseButton = true,
  embedInPage = false,
}: DeepChatBotProps) {
  const [messageApi, messageContextHolder] = message.useMessage()
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const [isExpanded, setIsExpanded] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const [isSending, setIsSending] = useState(false)
  const { token, user, logout } = useAuthStore()
  const userEmail = user?.email || 'anonymous'
  const deepChatRef = useRef<any>(null)
  const sessionId = useRef<string>(getSessionId(userEmail))
  const streamingMessageIndexRef = useRef<number | null>(null)
  const accumulatedMessageRef = useRef<string>('')
  const isStreamingRef = useRef(false)
  const isInitialized = useRef(false)
  const hasInitialMessage = useRef(false)
  const hasShownOllamaToast = useRef(false)
  const inputRef = useRef<any>(null)
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const tokenBufferRef = useRef<string>('')  // Buffer for incoming tokens
  const isTypingRef = useRef<boolean>(false)  // Track if typewriter is currently typing
  const displayIndexRef = useRef(0)  // Current character index being displayed
  const streamAbortControllerRef = useRef<AbortController | null>(null)  // For cancelling stream
  
  const useStreaming = streaming ?? ChatbotConfig.STREAMING.ENABLED
  const useTypewriter = enableTypewriter ?? ChatbotConfig.TYPEWRITER.ENABLED
  
  /**
   * Update message display in DeepChat UI
   * Uses marked library to render Markdown
   */
  const updateMessageDisplay = useCallback(() => {
    if (!deepChatRef.current) return
    
    // Preserve whitespace by replacing multiple spaces with non-breaking spaces
    // This prevents HTML from collapsing consecutive spaces
    const preservedText = accumulatedMessageRef.current.replace(/ {2,}/g, (match) => {
      return '&nbsp;'.repeat(match.length)
    })
    
    // Convert markdown to HTML using marked
    const htmlContent = marked.parse(preservedText)
    
    const allMessages = deepChatRef.current.getMessages()
    const lastMessageIndex = allMessages.length - 1
    const lastMessage = allMessages[lastMessageIndex]
    
    if (lastMessage?.html?.includes('typing-dots')) {
      // Remove loading message and add new message with HTML
      deepChatRef.current.clearMessages()
      allMessages.slice(0, -1).forEach((m: any) => deepChatRef.current.addMessage(m))
      deepChatRef.current.addMessage({
        role: 'assistant',
        html: htmlContent
      })
      streamingMessageIndexRef.current = allMessages.length - 1
    } else {
      // Update existing message with HTML
      deepChatRef.current.updateMessage(
        { html: htmlContent },
        streamingMessageIndexRef.current
      )
    }
    
    deepChatRef.current.scrollToBottom()
  }, [])
  
  /**
   * Type next character from buffer with typewriter effect
   */
  const typeNextCharacter = useCallback(() => {
    if (!isTypingRef.current || !deepChatRef.current) {
      console.log('📝 Typewriter stopped - isTyping:', isTypingRef.current, 'has deepChat:', !!deepChatRef.current)
      isTypingRef.current = false
      return
    }
    
    // Check if there's more content to type
    if (displayIndexRef.current < tokenBufferRef.current.length) {
      // Add next character to accumulated message
      const char = tokenBufferRef.current[displayIndexRef.current]
      accumulatedMessageRef.current += char
      displayIndexRef.current++
      
      console.log('📝 Typing char:', char, '| Display index:', displayIndexRef.current, '| Accumulated:', accumulatedMessageRef.current.length)
      
      // Update UI
      updateMessageDisplay()
      
      // Schedule next character
      typingTimeoutRef.current = setTimeout(typeNextCharacter, ChatbotConfig.TYPEWRITER.SPEED_MS)
    } else {
      // Finished typing current buffer, check if more tokens arrived
      console.log('📝 Buffer exhausted, checking for more tokens...')
      if (tokenBufferRef.current.length > 0) {
        console.log('📝 Clearing buffer and continuing')
        tokenBufferRef.current = ''
        displayIndexRef.current = 0
        // Keep typing if there's more content
        typeNextCharacter()
      } else {
        console.log('📝 Typewriter finished - no more tokens')
        isTypingRef.current = false
      }
    }
  }, [updateMessageDisplay])

  // Clear session on logout
  useEffect(() => {
    if (!token) {
      clearSessionId(userEmail)
      clearDemoModeShown()
      hasShownOllamaToast.current = false
    }
  }, [token, userEmail])

  const handleSend = useCallback(async () => {
    if (!inputValue.trim() || isSending) {
      console.log('handleSend: Skipping - isSending:', isSending, 'inputValue:', inputValue)
      return
    }
    
    console.log('handleSend: Starting with message:', inputValue)
    setIsSending(true)
    const userMessage = inputValue.trim()
    setInputValue('')
    
    try {
      if (deepChatRef.current) {
        deepChatRef.current.addMessage({
          role: 'user',
          text: userMessage
        })
        
        deepChatRef.current.addMessage({
          role: 'assistant',
          html: '<div class="typing-dots"><span class="dot"></span><span class="dot dot-2"></span><span class="dot dot-3"></span></div>'
        })
      }
      
      const messages: ChatMessage[] = [
        {
          role: 'system',
          content: 'You are a helpful AI assistant for a Workforce Console application. You help users with employee management, project tracking, system navigation, and general questions. Be concise, friendly, and professional.',
        },
        { role: 'user', content: userMessage }
      ]
      
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current)
        typingTimeoutRef.current = null
      }
      tokenBufferRef.current = ''
      isTypingRef.current = false
      displayIndexRef.current = 0
      
      accumulatedMessageRef.current = ''
      isStreamingRef.current = true
      
      if (streamAbortControllerRef.current) {
        streamAbortControllerRef.current.abort()
        streamAbortControllerRef.current = null
      }
      
      tokenBufferRef.current = ''
      isTypingRef.current = false
      
      let result: any
      
      if (useStreaming) {
        streamAbortControllerRef.current = new AbortController()
        
        result = await streamChatbotAPI(
          messages,
          token || '',
          sessionId.current,
          (tokenContent) => {
            console.log('📝 Token received:', tokenContent, '| Buffer length:', tokenBufferRef.current.length)
            if (useTypewriter) {
              tokenBufferRef.current += tokenContent
              console.log('📝 Added to buffer, new length:', tokenBufferRef.current.length)
              
              if (!isTypingRef.current) {
                console.log('📝 Starting typewriter')
                isTypingRef.current = true
                typeNextCharacter()
              }
            } else {
              accumulatedMessageRef.current += tokenContent
              console.log('📝 Direct update, accumulated length:', accumulatedMessageRef.current.length)
              updateMessageDisplay()
            }
          },
          streamAbortControllerRef.current
        )
        
        if (useTypewriter) {
          await new Promise<void>((resolve) => {
            const checkTyping = () => {
              if (!isTypingRef.current) {
                resolve()
              } else {
                setTimeout(checkTyping, 50)
              }
            }
            checkTyping()
          })
        }
      } else {
        result = await callChatbotAPI(
          messages,
          token || '',
          sessionId.current
        )
        
        if (result.success && result.message) {
          accumulatedMessageRef.current = result.message
          
          if (useTypewriter) {
            tokenBufferRef.current = result.message
            isTypingRef.current = true
            typeNextCharacter()
            
            await new Promise<void>((resolve) => {
              const checkTyping = () => {
                if (!isTypingRef.current) {
                  resolve()
                } else {
                  setTimeout(checkTyping, 50)
                }
              }
              checkTyping()
            })
          } else {
            updateMessageDisplay()
          }
        }
      }
      
      if (result.isOllamaResponse && !hasShownOllamaToast.current && wasDemoModeShown()) {
        // messageApi.success({
        //   content: 'Response powered by Ollama AI',
        //   duration: 3,
        // })
        hasShownOllamaToast.current = true
      } else if (result.isDemoResponse && !wasDemoModeShown()) {
        messageApi.info({
          content: 'Backend unavailable, using demo mode',
          duration: 3,
        })
      }
      
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Stream aborted by user')
        setIsSending(false)
        isStreamingRef.current = false
        accumulatedMessageRef.current = ''
        streamingMessageIndexRef.current = null
        tokenBufferRef.current = ''
        isTypingRef.current = false
        displayIndexRef.current = 0
        return
      }
      
      console.error('Chat error:', error)
      
      if (accumulatedMessageRef.current.length > 0) {
        if (deepChatRef.current) {
          const allMessages = deepChatRef.current.getMessages()
          const lastMessage = allMessages[allMessages.length - 1]
          if (lastMessage?.html?.includes('typing-dots')) {
            deepChatRef.current.clearMessages()
            allMessages.slice(0, -1).forEach((m: any) => deepChatRef.current.addMessage(m))
          }
          
          deepChatRef.current.addMessage({
            role: 'assistant',
            text: `${accumulatedMessageRef.current}\n\n⚠️ Response interrupted. Please try again.`
          })
        }
      } else {
        if (deepChatRef.current) {
          deepChatRef.current.addMessage({
            role: 'assistant',
            text: 'Sorry, I encountered an error. Please try again.'
          })
        }
      }
    } finally {
      setIsSending(false)
      isStreamingRef.current = false
      
      if ((useTypewriter || ChatbotConfig.TYPEWRITER.ENABLED) && isTypingRef.current) {
        await new Promise<void>((resolve) => {
          const checkTyping = () => {
            if (!isTypingRef.current) {
              resolve()
            } else {
              setTimeout(checkTyping, 50)
            }
          }
          checkTyping()
        })
      }
      
      accumulatedMessageRef.current = ''
      streamingMessageIndexRef.current = null
      tokenBufferRef.current = ''
      isTypingRef.current = false
      displayIndexRef.current = 0
      
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current)
        typingTimeoutRef.current = null
      }
      
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [inputValue, isSending, token, messageApi, useStreaming, useTypewriter, typeNextCharacter, updateMessageDisplay])

  // Cleanup typewriter timeout and abort streaming on component unmount
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current)
        typingTimeoutRef.current = null
      }
      // Abort any ongoing stream to prevent backend errors
      if (streamAbortControllerRef.current) {
        streamAbortControllerRef.current.abort()
        streamAbortControllerRef.current = null
      }
      tokenBufferRef.current = ''
      isTypingRef.current = false
      displayIndexRef.current = 0
    }
  }, [])

  const handleKeyPress = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  const handleExpand = useCallback(() => {
    setIsExpanded(true)
  }, [])

  useEffect(() => {
    if (isOpen && deepChatRef.current && !isInitialized.current) {
      const deepChatEl = deepChatRef.current
      
      deepChatEl.requestBodyLimits = deepChatRequestBodyLimits
      deepChatEl.textInput = deepChatTextInputConfig
      deepChatEl.auxiliaryStyle = deepChatAuxiliaryStyle
      deepChatEl.style = { 
        width: '100%', 
        height: '100%', 
        border: 'none'
      }
      
      // Disable deep-chat's built-in handlers
      deepChatEl.connect = null
      deepChatEl.interceptors = null
      deepChatEl.onTextInput = null
      deepChatEl.submitMessageOnEnter = false
      deepChatEl.autoSave = false
      
      // Enable HTML rendering
      deepChatEl.renderHTML = true
      deepChatEl.allowHTML = true
      deepChatEl.disableHTML = false
      deepChatEl.renderHtml = true
      deepChatEl.allowHtml = true
      deepChatEl.parseHTML = true
      deepChatEl.innerHTML = true
      
      // Disable deep-chat's built-in connection and handlers - we use manual handleSend
      deepChatEl.connect = null
      deepChatEl.interceptors = null
      deepChatEl.onTextInput = null
      deepChatEl.submitMessageOnEnter = false
      deepChatEl.autoSave = false
      
      if (initialMessage && !hasInitialMessage.current) {
        setTimeout(() => {
          deepChatEl.addMessage({
            role: 'assistant',
            html: marked.parse(initialMessage)
          })
          hasInitialMessage.current = true
        }, 200)
      }
      
      isInitialized.current = true
    }
  }, [isOpen, initialMessage, messageApi, token])

  return (
    <>
      {messageContextHolder}
      
      {/* Floating chat trigger button - only show when closed and not embedded */}
      {!isOpen && !embedInPage && (
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="chat-trigger-btn"
          aria-label="Open chatbot"
        >
          <Bot className="h-5 w-5 text-white" />
        </button>
      )}

      {isOpen && (
        <div className={`chat-container ${isExpanded ? 'expanded' : ''} ${embedInPage ? 'embedded' : ''}`}>
          <div className="chat-window">
            <header className="chat-header">
              <div className="chat-header-info">
                <div className="chat-header-icon">
                  <Bot className="h-4 w-4 text-blue-500" />
                </div>
                <div>
                  <h3 className="chat-header-title">Ask me</h3>
                  <p className="chat-header-subtitle">I am here to help!</p>
                </div>
              </div>
              <div className="chat-header-actions">
                {/* Expand button - only show in floating mode (not embedded) */}
                {enableExpand && !isExpanded && !embedInPage && (
                  <button
                    className="header-action-btn"
                    onClick={handleExpand}
                    title="Expand"
                  >
                    <ExpandOutlined />
                  </button>
                )}
                {showCloseButton && (
                  <button
                    onClick={() => {
                      // Abort streaming when closing chat
                      if (streamAbortControllerRef.current) {
                        streamAbortControllerRef.current.abort()
                        streamAbortControllerRef.current = null
                      }
                      setIsOpen(false)
                    }}
                    className="header-action-btn"
                    title="Close"
                  >
                    <CloseOutlined />
                  </button>
                )}
              </div>
            </header>
            
            <div className="chat-content">
              <deep-chat displayLoadingBubble="true" ref={deepChatRef} demo={true} />
            </div>
            
            <div className="input-area">
              {/* add buttons here if need be */}
              {/* <div className="button-group" style={{ marginBottom: '0.5rem' }}>
              </div> 
              */}
              <div className="input-wrapper">
                <Input.TextArea
                  ref={inputRef}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your message..."
                  className="chat-input"
                  autoSize={{ minRows: 1, maxRows: 4 }}
                  disabled={isSending}
                />
                <Button
                  type="primary"
                  shape="circle"
                  icon={<SendOutlined />}
                  size="large"
                  onClick={handleSend}
                  disabled={!inputValue.trim() || isSending}
                  className="send-btn"
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
