import { useAuthStore } from '../../lib/authStore'
import { DeepChatBot } from '../DeepChat'

export function ChatbotWrapper() {
  const { token } = useAuthStore()

  if (!token) {
    return null
  }

  return (
    <DeepChatBot
      enableExpand={true}
      streaming={true} 
      enableTypewriter={false} 
      initialMessage={`👋 Hi! I'm your AI assistant. I can help you with:

- Employee management queries
- Project information
- System navigation
- General questions

How can I assist you today?`}
    />
  )
}