export type StoredChatMessage = {
  role: 'user' | 'assistant'
  text?: string
  html?: string
}

function storageKey(email: string): string {
  return `deepchat_history_${email}`
}

export function loadChatHistory(email: string): StoredChatMessage[] {
  try {
    const raw = localStorage.getItem(storageKey(email))
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw) as StoredChatMessage[]
    if (!Array.isArray(parsed)) {
      return []
    }
    const deduped: StoredChatMessage[] = []
    for (const message of parsed) {
      if (message.role !== 'user' && message.role !== 'assistant') {
        continue
      }
      const previous = deduped[deduped.length - 1]
      if (
        previous &&
        previous.role === message.role &&
        previous.text === message.text &&
        previous.html === message.html
      ) {
        continue
      }
      deduped.push(message)
    }
    return deduped
  } catch {
    return []
  }
}

export function saveChatHistory(email: string, messages: StoredChatMessage[]): void {
  try {
    const compact = messages
      .filter((message) => message.role === 'user' || message.role === 'assistant')
      .map((message) => ({
        role: message.role,
        text: message.text,
        html: message.html,
      }))
      .filter((message) => message.text || message.html)

    const deduped: StoredChatMessage[] = []
    for (const message of compact) {
      const previous = deduped[deduped.length - 1]
      if (
        previous &&
        previous.role === message.role &&
        previous.text === message.text &&
        previous.html === message.html
      ) {
        continue
      }
      deduped.push(message)
    }
    if (deduped.length === 0) {
      return
    }
    localStorage.setItem(storageKey(email), JSON.stringify(deduped))
  } catch {
    // Ignore quota / private-mode failures.
  }
}

export function toStoredMessages(rawMessages: unknown[]): StoredChatMessage[] {
  return rawMessages.flatMap((item) => {
    const message = item as { role?: string; text?: string; html?: string }
    if (message.role !== 'user' && message.role !== 'assistant') {
      return []
    }
    if (typeof message.html === 'string' && message.html.includes('typing-dots')) {
      return []
    }
    return [
      {
        role: message.role,
        text: message.text,
        html: message.html,
      },
    ]
  })
}
