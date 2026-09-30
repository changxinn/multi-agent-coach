import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/lib/authStore'
import { DeepChatBot } from './DeepChatBot'

const { callChatbotAPI, streamChatbotAPI } = vi.hoisted(() => ({
  callChatbotAPI: vi.fn(),
  streamChatbotAPI: vi.fn(),
}))

vi.mock('@/lib/chatbot-api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/chatbot-api')>()
  return { ...actual, callChatbotAPI, streamChatbotAPI }
})

type ChatMessage = { role: string; text?: string; html?: string }

class DeepChatTestElement extends HTMLElement {
  messages: ChatMessage[] = []
  history: ChatMessage[] = []

  addMessage(message: ChatMessage) {
    this.messages.push(message)
  }

  clearMessages() {
    this.messages = []
  }

  getMessages() {
    return this.messages
  }

  updateMessage(message: Partial<ChatMessage>, index: number) {
    this.messages[index] = { ...this.messages[index], ...message }
  }

  scrollToBottom() {}
}

beforeAll(() => {
  if (!customElements.get('deep-chat')) {
    customElements.define('deep-chat', DeepChatTestElement)
  }
})

afterEach(() => {
  callChatbotAPI.mockReset()
  streamChatbotAPI.mockReset()
  useAuthStore.setState({
    token: 'test-token',
    user: { sub: '1', email: 'coach@example.com', name: 'Coach', exp: 4_102_444_800 },
    isAuthInitialized: true,
  })
})

function sendMessage() {
  fireEvent.change(screen.getByPlaceholderText('Type your message...'), { target: { value: 'Need help' } })
  fireEvent.click(document.querySelector('.send-btn')!)
}

describe('DeepChatBot', () => {
  it('adds and renders a non-streaming assistant response', async () => {
    callChatbotAPI.mockResolvedValue({ success: true, message: 'Try a short walk.' })
    const { container } = render(<DeepChatBot defaultOpen streaming={false} enableTypewriter={false} />)

    sendMessage()

    await waitFor(() => expect(callChatbotAPI).toHaveBeenCalled())
    await waitFor(() => {
      const chat = container.querySelector('deep-chat') as unknown as DeepChatTestElement
      expect(chat.getMessages()).toEqual(expect.arrayContaining([
        expect.objectContaining({ role: 'user', text: 'Need help' }),
        expect.objectContaining({ role: 'assistant', html: expect.stringContaining('Try a short walk.') }),
      ]))
    })
  })

  it('adds a recovery message when a request fails', async () => {
    callChatbotAPI.mockRejectedValue(new Error('Network unavailable'))
    const { container } = render(<DeepChatBot defaultOpen streaming={false} enableTypewriter={false} />)

    sendMessage()

    await waitFor(() => {
      const chat = container.querySelector('deep-chat') as unknown as DeepChatTestElement
      expect(chat.getMessages()).toEqual(expect.arrayContaining([
        expect.objectContaining({ role: 'assistant', text: 'Sorry, I encountered an error. Please try again.' }),
      ]))
    })
  })

  it('aborts an in-progress stream when closed', async () => {
    let signal: AbortSignal | undefined
    streamChatbotAPI.mockImplementation((_, __, ___, ____, controller: AbortController) => {
      signal = controller.signal
      return new Promise(() => undefined)
    })
    render(<DeepChatBot defaultOpen streaming enableTypewriter={false} showCloseButton />)

    sendMessage()
    await waitFor(() => expect(streamChatbotAPI).toHaveBeenCalled())
    fireEvent.click(screen.getByTitle('Close'))

    expect(signal?.aborted).toBe(true)
  })
})