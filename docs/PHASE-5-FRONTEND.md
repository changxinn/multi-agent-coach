# Phase 5: Frontend Integration

**Status**: ⏳ Pending  
**Goal**: Connect React frontend to FastAPI backend

---

## Overview

This phase covers integrating the React frontend with the FastAPI backend for authentication, chat, and session management.

---

## Prerequisites

- ✅ Backend running on http://localhost:8000
- ✅ Frontend development server on http://localhost:5174
- ✅ Database setup complete (Phase 1)
- ✅ Authentication endpoints working

---

## Step 1: Update Frontend Environment

Create or update `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

---

## Step 2: Update Authentication Functions

**File**: `frontend/src/lib/auth.ts`

Replace mock authentication with backend calls:

```typescript
import { API_BASE_URL } from './constants/api';

interface LoginRequest {
  email: string;
  password: string;
}

interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
  user: {
    id: number;
    email: string;
    name: string;
  };
}

export async function login({ email, password }: LoginRequest): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Login failed');
  }

  return response.json();
}

export async function register({ email, password, name }: RegisterRequest): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password, name }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Registration failed');
  }

  return response.json();
}

export async function refreshToken(token: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Token refresh failed');
  }

  return response.json();
}
```

---

## Step 3: Update Chat API Functions

**File**: `frontend/src/lib/chatbot-api.ts`

Update to use backend endpoints with JWT authentication:

```typescript
import { API_BASE_URL } from './constants/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatRequest {
  messages: Message[];
  session_id: string;
}

interface ChatResponse {
  response: string;
  session_id: string;
}

export async function callChatbotAPI(
  messages: Message[],
  token: string,
  sessionId: string
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      messages,
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Chat request failed');
  }

  return response.json();
}

export async function streamChatbotAPI(
  messages: Message[],
  token: string,
  sessionId: string,
  onToken: (token: string) => void
): Promise<void> {
  const params = new URLSearchParams({
    message: messages[messages.length - 1].content,
    session_id: sessionId,
  });

  const response = await fetch(`${API_BASE_URL}/chat/stream?${params}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Stream request failed');
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No reader available');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') continue;
        try {
          const parsed = JSON.parse(data);
          if (parsed.token) {
            onToken(parsed.token);
          }
        } catch (e) {
          console.error('Failed to parse SSE data:', e);
        }
      }
    }
  }
}
```

---

## Step 4: Update API Constants

**File**: `frontend/src/lib/constants/api.ts`

```typescript
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export const ENDPOINTS = {
  // Authentication
  LOGIN: `${API_BASE_URL}/auth/login`,
  REGISTER: `${API_BASE_URL}/auth/register`,
  REFRESH: `${API_BASE_URL}/auth/refresh`,

  // Chat
  CHAT: `${API_BASE_URL}/chat`,
  CHAT_STREAM: `${API_BASE_URL}/chat/stream`,
  CHAT_SUMMARY: `${API_BASE_URL}/chat/summary`,
  CHAT_HISTORY: (sessionId: string) => `${API_BASE_URL}/chat/history/${sessionId}`,

  // Session
  SESSION: `${API_BASE_URL}/session`,
  SESSION_BY_ID: (sessionId: string) => `${API_BASE_URL}/session/${sessionId}`,
  SESSION_CLEAR: `${API_BASE_URL}/session/clear`,
} as const;
```

---

## Step 5: Update Auth Store

**File**: `frontend/src/lib/authStore.ts`

Ensure JWT token is properly stored and decoded:

```typescript
import { create } from 'zustand';
import { jwtDecode } from 'jwt-decode';

interface JwtPayload {
  sub: number;
  email: string;
  role: string;
  exp: number;
}

interface AuthState {
  token: string | null;
  user: {
    id: number;
    email: string;
    role: 'admin' | 'staff' | 'user';
  } | null;
  isAuthenticated: boolean;
  setToken: (token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  user: null,
  isAuthenticated: !!localStorage.getItem('token'),
  setToken: (token: string) => {
    localStorage.setItem('token', token);
    try {
      const decoded = jwtDecode<JwtPayload>(token);
      set({
        token,
        user: {
          id: decoded.sub,
          email: decoded.email,
          role: decoded.role.toLowerCase() as 'admin' | 'staff' | 'user',
        },
        isAuthenticated: true,
      });
    } catch (error) {
      console.error('Failed to decode JWT:', error);
      set({ token: null, user: null, isAuthenticated: false });
    }
  },
  logout: () => {
    localStorage.removeItem('token');
    set({ token: null, user: null, isAuthenticated: false });
  },
}));
```

---

## Step 6: Update Login Page

**File**: `frontend/src/pages/QuickLoginPage/QuickLoginPage.tsx`

Integrate with backend authentication:

```typescript
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/lib/authStore';
import { login } from '@/lib/auth';

export function QuickLoginPage() {
  const [email, setEmail] = useState('admin@example.com');
  const [password, setPassword] = useState('ChangeMe123!');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const setToken = useAuthStore((state) => state.setToken);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await login({ email, password });
      setToken(response.access_token);
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Form fields */}
      {error && <div className="error">{error}</div>}
      <button type="submit" disabled={loading}>
        {loading ? 'Logging in...' : 'Login'}
      </button>
    </form>
  );
}
```

---

## Step 7: Update Chat Components

**File**: `frontend/src/common/DeepChatBox/DeepChatBox.tsx`

Integrate with backend chat API:

```typescript
import { useAuthStore } from '@/lib/authStore';
import { callChatbotAPI, streamChatbotAPI } from '@/lib/chatbot-api';

export function DeepChatBox() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState(`chat_${generateSessionId()}`);
  const token = useAuthStore((state) => state.token);

  const sendMessage = async (message: string) => {
    const userMessage: Message = { role: 'user', content: message };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);

    try {
      // Use streaming
      let assistantMessage = '';
      await streamChatbotAPI(
        newMessages,
        token!,
        sessionId,
        (token) => {
          assistantMessage += token;
          // Update UI with partial response
        }
      );

      setMessages([...newMessages, { role: 'assistant', content: assistantMessage }]);
    } catch (error) {
      console.error('Chat error:', error);
      // Show error to user
    }
  };

  // ... rest of component
}

function generateSessionId(): string {
  return Array.from({ length: 16 }, () =>
    Math.floor(Math.random() * 16).toString(16)
  ).join('');
}
```

---

## Testing Checklist

### Authentication Flow
- [ ] User can register with email/password
- [ ] User can login with credentials
- [ ] JWT token is stored in localStorage
- [ ] Token is included in API requests
- [ ] Token refresh works when expired
- [ ] Logout clears token and redirects

### Chat Flow
- [ ] User can send messages
- [ ] Streaming responses work
- [ ] Session ID is validated by backend
- [ ] Chat history persists across page reloads
- [ ] Session summary can be requested

### Error Handling
- [ ] 401 Unauthorized redirects to login
- [ ] Network errors are displayed to user
- [ ] Invalid session ID shows appropriate error
- [ ] Loading states are shown during requests

---

## Common Issues

### Issue: CORS Error

**Error**: `Access to fetch at 'http://localhost:8000' has been blocked by CORS policy`

**Solution**: Backend CORS is configured for `http://localhost:5174` and `http://localhost:5175`. If using different port, update `.env`:

```env
ALLOWED_ORIGINS=http://localhost:5174,http://localhost:5175,http://localhost:3000
```

### Issue: 401 Unauthorized

**Error**: `401 Unauthorized` on chat endpoint

**Solution**: Ensure JWT token is included in Authorization header:

```typescript
headers: {
  'Authorization': `Bearer ${token}`
}
```

### Issue: Session ID Validation Failed

**Error**: `Invalid session ID format`

**Solution**: Session ID must match pattern `^chat_[a-f0-9]{16}$`

```typescript
// Correct format
const sessionId = `chat_${crypto.randomUUID().replace(/-/g, '').slice(0, 16)}`;
```

---

## Next Steps

After completing frontend integration:

1. **Test End-to-End Flow**
   - Register → Login → Chat → Logout
   - Verify session persistence
   - Test error scenarios

2. **Performance Optimization**
   - Implement request debouncing
   - Add optimistic UI updates
   - Cache frequently accessed data

3. **Security Enhancements**
   - Implement token expiry handling
   - Add refresh token rotation
   - Secure localStorage usage

---

**Status**: Template ready for implementation  
**Last Updated**: 2026-08-24  
**Dependencies**: Phase 1 (Foundation), Phase 2 (Authentication), Phase 3 (Session Management), Phase 4 (Multi-Agent Integration)
