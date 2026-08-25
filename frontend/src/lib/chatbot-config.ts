/**
 * Chatbot Configuration
 * 
 * Developer-only configuration for chatbot behavior.
 * Modify these values to customize chatbot functionality.
 * 
 * @example
 * // Enable streaming mode
 * ChatbotConfig.STREAMING.ENABLED = true
 * 
 * // Enable typewriter effect
 * ChatbotConfig.TYPEWRITER.ENABLED = true
 * 
 * // Adjust typing speed
 * ChatbotConfig.TYPEWRITER.SPEED_MS = 50
 */
export const ChatbotConfig = {
  /**
   * Streaming Configuration
   * 
   * Controls whether chat responses are received as a stream (SSE) or as a complete response.
   * When enabled, tokens are received in real-time from the backend.
   * When disabled, the full response is received at once.
   */
  STREAMING: {
    /**
     * Enable streaming mode
     * 
     * - `true`: Responses are streamed in real-time using Server-Sent Events (SSE)
     * - `false`: Full response is received at once via standard HTTP POST
     * 
     * @default true
     */
    ENABLED: true,
  },

  /**
   * Typewriter Effect Configuration
   * 
   * Controls letter-by-letter display behavior for chat responses.
   * When enabled, characters appear one-by-one creating a typewriter effect.
   * When disabled, full tokens appear immediately (word-by-word).
   * 
   * Note: This works independently of streaming mode.
   * - Streaming + Typewriter: Real-time tokens with character-by-character display
   * - Streaming + No Typewriter: Real-time tokens displayed immediately
   * - Non-Streaming + Typewriter: Full response with simulated character-by-character display
   * - Non-Streaming + No Typewriter: Full response displayed immediately
   */
  TYPEWRITER: {
    /**
     * Enable typewriter effect
     * 
     * - `true`: Characters appear one-by-one (typewriter style)
     * - `false`: Full tokens appear immediately (word-by-word)
     * 
     * @default true
     */
    ENABLED: true,

    /**
     * Typing speed in milliseconds per character
     * 
     * Lower values = faster typing
     * Higher values = slower typing
     * 
     * Recommended values:
     * - `25`: Fast (production use)
     * - `50`: Medium (demos and presentations)
     * - `100`: Slow (debugging and testing)
     * - `200`: Very slow (debugging only)
     * 
     * @default 25
     */
    SPEED_MS: 25,
  },
}

export default ChatbotConfig
