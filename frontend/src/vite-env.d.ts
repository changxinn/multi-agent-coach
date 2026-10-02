/// <reference types="vite/client" />

import type { DeepChat } from 'deep-chat'
import type { DetailedHTMLProps, HTMLAttributes } from 'react'

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'deep-chat': DetailedHTMLProps<HTMLAttributes<DeepChat>, DeepChat> & {
        displayLoadingBubble?: DeepChat['displayLoadingBubble']
        demo?: DeepChat['demo']
      }
    }
  }
}

declare module '*.css' {
  const content: Record<string, string>;
  export default content;
}
