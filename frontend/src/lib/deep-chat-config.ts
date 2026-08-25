export const deepChatConnectConfig = {
  // Enable HTML rendering for messages
  renderHTML: true,
  allowHTML: true,
};

export const deepChatRequestBodyLimits = {
  maxMessages: 10,
};

export const deepChatTextInputConfig = {
  placeholder: { text: '' },
  styles: {
    container: {
      display: 'none',
    },
  },
};

export const deepChatAuxiliaryStyle = `
  deep-chat {
    --deep-chat-primary-color: #3b82f6;
    --deep-chat-user-message-background-color: #3b82f6;
    --deep-chat-user-message-color: #ffffff;
    --deep-chat-ai-message-background-color: #ffffff;
    --deep-chat-ai-message-color: #111827;
    --deep-chat-border-radius: 16px;
    width: 100% !important;
    height: 100% !important;
    border: none !important;
  }
  
  .deep-chat-messages-container {
    background-color: #f9fafb !important;
    height: 100% !important;
    overflow-y: auto !important;
  }
  
  .deep-chat-message-bubble-user { 
    background-color: #3b82f6 !important; 
    color: white !important; 
    border-radius: 16px 16px 4px 16px !important;
    box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2) !important;
  }
  
  .deep-chat-message-bubble-ai { 
    background-color: white !important; 
    color: #111827 !important; 
    border: 1px solid #e5e7eb !important;
    border-radius: 16px 16px 16px 4px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
    line-height: 1.6 !important;
  }
  
  /* Markdown formatting styles */
  .deep-chat-message-bubble-ai p {
    margin: 0.5em 0 !important;
    line-height: 1.6 !important;
  }
  
  .deep-chat-message-bubble-ai p:first-child {
    margin-top: 0 !important;
  }
  
  .deep-chat-message-bubble-ai p:last-child {
    margin-bottom: 0 !important;
  }
  
  .deep-chat-message-bubble-ai strong {
    font-weight: 600 !important;
    color: #1f2937 !important;
  }
  
  .deep-chat-message-bubble-ai ul,
  .deep-chat-message-bubble-ai ol {
    margin: 0.5em 0 !important;
    padding-left: 1.5em !important;
  }
  
  .deep-chat-message-bubble-ai li {
    margin: 0.25em 0 !important;
    line-height: 1.5 !important;
  }
  
  /* Hide deep-chat input area */
  #input,
  #input-area,
  .input-area,
  [class*="input-area"],
  [id*="input"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
  }
  
  .typing-indicator-msg {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem;
  }
  
  /* Loading/thinking message styling */
  /* Typing indicator - three animated bouncing dots */
  /* Typing dots inside messages */
  .typing-dots {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
  }
  
  .typing-dots .dot {
    width: 8px;
    height: 8px;
    background: #3b82f6;
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out;
    display: inline-block;
  }
  
  .typing-dots .dot-2 {
    animation-delay: 0.2s;
  }
  
  .typing-dots .dot-3 {
    animation-delay: 0.4s;
  }
  
  @keyframes bounce {
    0%, 80%, 100% {
      transform: translateY(0);
      opacity: 0.4;
    }
    40% {
      transform: translateY(-8px);
      opacity: 1;
    }
  }
  
  ::-webkit-scrollbar { 
    width: 4px; 
  }
  ::-webkit-scrollbar-thumb { 
    background: #9ca3af; 
    border-radius: 2px; 
  }
`;
