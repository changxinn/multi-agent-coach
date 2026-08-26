import { DeepChatBot } from '../../common/DeepChat/DeepChatBot'
import './ChatPage.css'

export function ChatPage() {
  return (
    <div className="chat-page-container">
      <DeepChatBot 
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
