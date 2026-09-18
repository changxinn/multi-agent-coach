import { DeepChatBot } from '../../common/DeepChat/DeepChatBot'
import { useAuthStore } from '../../lib/authStore'
import './ChatPage.css'

export function ChatPage() {
  const email = useAuthStore((state) => state.user?.email || 'anonymous')

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
      />
    </div>
  )
}

export default ChatPage
