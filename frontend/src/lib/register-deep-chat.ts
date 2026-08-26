// Register deep-chat web component
import 'deep-chat';

declare global {
  namespace JSX {
    interface IntrinsicElements {
      'deep-chat': any;
    }
  }
}

export {};
