import { Sparkles } from 'lucide-react'

interface DeepChatTriggerProps {
  onClick: () => void
  className?: string
}

export function DeepChatTrigger({ onClick, className = '' }: DeepChatTriggerProps) {
  return (
    <button
      onClick={onClick}
      className={`fixed left-6 bottom-6 z-50 h-14 w-14 rounded-full bg-primary flex items-center justify-center shadow-lg hover:shadow-xl transition-all ${className}`}
      style={{ boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)' }}
      aria-label="Open chatbot"
    >
      <Sparkles className="h-4 w-4 text-white" />
    </button>
  )
}
