import { DeepChatBot } from '../../common/DeepChat/DeepChatBot'
import { useAuthStore } from '../../lib/authStore'
import './ChatPage.css'

export function ChatPage() {
  const email = useAuthStore((state) => state.user?.email || 'anonymous')
  const initialMessage = `Hey! 👋 Ready to level up your fitness game?

I'm your AI workout buddy – think of me as your personal trainer who never sleeps! 😄

Ask me anything about:
• Workouts 
• Nutrition 
• Progress tracking 
• Motivation

What would you like to do first?
  `
  return (
    <div className="chat-page-container">
      <DeepChatBot
        key={email}
        enableExpand={false}
        streaming={true}
        enableTypewriter={true}
        defaultOpen={true}
        showCloseButton={false}
        embedInPage={true}
        initialMessage={initialMessage}
      />
    </div>
  )
}

export default ChatPage
