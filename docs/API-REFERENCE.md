# API Reference

**Base URL**: `http://localhost:8000/api`  
**Authentication**: JWT Bearer token (where required)

---

## Authentication

### Login

**POST** `/auth/login`

Authenticate user and return JWT token.

**Request**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 123,
    "email": "user@example.com",
    "name": "John Doe",
    "user_image": null
  }
}
```

**Errors**:
- 401 Unauthorized: Invalid credentials
- 403 Forbidden: Account disabled

---

### Register

**POST** `/auth/register`

Create new user account.

**Request**:
```json
{
  "email": "newuser@example.com",
  "password": "SecurePass123!",
  "name": "New User"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 124,
    "email": "newuser@example.com",
    "name": "New User",
    "user_image": null
  }
}
```

**Errors**:
- 400 Bad Request: Email already exists

---

### Refresh Token

**POST** `/auth/refresh`

Refresh expired JWT token.

**Headers**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 123,
    "email": "user@example.com",
    "name": "John Doe",
    "user_image": null
  }
}
```

**Errors**:
- 401 Unauthorized: Invalid or expired token

---

## Chat

### Send Message

**POST** `/chat`

Send message to multi-agent system and get aggregated response.

**Headers**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Request**:
```json
{
  "messages": [
    {
      "role": "user",
      "content": "What workout should I do today?"
    }
  ],
  "session_id": "chat_abc123def456789",
  "temperature": 0.7,
  "max_tokens": 500
}
```

**Response** (200 OK):
```json
{
  "message": "### Alex (Training Planner)\n\n• Start with 20 min cardio warmup\n• Focus on compound exercises today\n\n### Sam (Nutrition Advisor)\n\n• Remember to hydrate before workout\n• Post-workout protein within 30 min",
  "session_id": "chat_abc123def456789",
  "model": "gpt-5-nano",
  "agents_involved": ["training_planner", "nutrition_advisor"]
}
```

**Errors**:
- 401 Unauthorized: Invalid or missing token
- 400 Bad Request: Invalid session ID format
- 403 Forbidden: Cannot access another user's session
- 404 Not Found: User profile not found

---

### Stream Response

**GET** `/chat/stream`

Stream response token-by-token using Server-Sent Events (SSE).

**Headers**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Query Parameters**:
- `message` (required): User message
- `session_id` (required): Session ID

**Request**:
```
GET /chat/stream?message=What%20workout%20should%20I%20do&session_id=chat_abc123def456789
```

**Response** (200 OK, text/event-stream):
```
data: {"token": "###", "session_id": "chat_abc123def456789", "is_complete": false}
data: {"token": " Alex", "session_id": "chat_abc123def456789", "is_complete": false}
data: {"token": " (", "session_id": "chat_abc123def456789", "is_complete": false}
...
data: {"token": "", "session_id": "chat_abc123def456789", "is_complete": true}
```

**Errors**:
- 401 Unauthorized: Invalid or missing token
- 400 Bad Request: Invalid session ID format

---

### Request Summary

**POST** `/chat/summary`

Generate on-demand session summary (does not end session).

**Headers**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Request**:
```json
{
  "session_id": "chat_abc123def456789"
}
```

**Response** (200 OK):
```json
{
  "summary": "Session Summary:\n\nToday we discussed workout planning and nutrition. Key points:\n1. Start with cardio warmup\n2. Focus on compound exercises\n3. Stay hydrated\n\nNext steps: Complete the workout and log your meals.",
  "session_id": "chat_abc123def456789"
}
```

**Errors**:
- 401 Unauthorized: Invalid or missing token
- 404 Not Found: Session not found

---

### Clear Chat History

**DELETE** `/chat/history/{session_id}`

Clear all messages in a session.

**Headers**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Response** (200 OK):
```json
{
  "status": "cleared",
  "session_id": "chat_abc123def456789"
}
```

**Errors**:
- 401 Unauthorized: Invalid or missing token
- 404 Not Found: Session not found
- 403 Forbidden: Cannot access another user's session

---

## Session

### Create Session

**POST** `/session`

Create new chat session.

**Headers**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Request** (optional body):
```json
{
  "session_id": "chat_custom123456789",
  "user_profile": {
    "fitness_goal": "weight loss",
    "fitness_level": "intermediate"
  }
}
```

**Response** (200 OK):
```json
{
  "session_id": "chat_custom123456789",
  "user_id": 123,
  "created": true,
  "profile": {
    "user_id": 123,
    "name": "John Doe",
    "fitness_goal": "weight loss",
    "fitness_level": "intermediate",
    "weight_kg": null,
    "height_cm": null,
    "age": null
  },
  "message_count": 0
}
```

**Errors**:
- 401 Unauthorized: Invalid or missing token
- 400 Bad Request: Invalid session ID format

---

### Get Session Details

**GET** `/session/{session_id}`

Get session details and message history.

**Headers**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Response** (200 OK):
```json
{
  "session_id": "chat_abc123def456789",
  "user_id": 123,
  "profile": {
    "user_id": 123,
    "name": "John Doe",
    "fitness_goal": "general fitness",
    "fitness_level": "beginner"
  },
  "messages": [
    {
      "role": "user",
      "content": "What workout should I do?"
    },
    {
      "role": "assistant",
      "content": "### Alex (Training Planner)\n\nStart with cardio..."
    }
  ],
  "created_at": "2026-08-24T12:00:00Z",
  "last_activity": "2026-08-24T12:05:00Z"
}
```

**Errors**:
- 401 Unauthorized: Invalid or missing token
- 404 Not Found: Session not found
- 403 Forbidden: Cannot access another user's session

---

### Delete Session

**DELETE** `/session/{session_id}`

Delete session completely (including S3 history if configured).

**Headers**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Response** (200 OK):
```json
{
  "status": "deleted",
  "session_id": "chat_abc123def456789"
}
```

**Errors**:
- 401 Unauthorized: Invalid or missing token
- 404 Not Found: Session not found
- 403 Forbidden: Cannot access another user's session

---

### Clear Session Messages

**POST** `/session/clear`

Clear session messages but keep session alive.

**Headers**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Request**:
```json
{
  "session_id": "chat_abc123def456789"
}
```

**Response** (200 OK):
```json
{
  "status": "cleared",
  "session_id": "chat_abc123def456789"
}
```

**Errors**:
- 401 Unauthorized: Invalid or missing token
- 404 Not Found: Session not found
- 403 Forbidden: Cannot access another user's session

---

## Health & Info

### Health Check

**GET** `/health`

Check if API is healthy.

**Response** (200 OK):
```json
{
  "status": "healthy",
  "app": "Multi-Agent Coach API",
  "version": "1.0.0"
}
```

---

### Root

**GET** `/`

Get API information.

**Response** (200 OK):
```json
{
  "name": "Multi-Agent Coach API",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/health"
}
```

---

## Error Responses

All endpoints may return these error responses:

### 400 Bad Request

```json
{
  "detail": "Invalid session ID format. Must be: chat_[a-f0-9]{16}"
}
```

### 401 Unauthorized

```json
{
  "detail": "Invalid or expired token"
}
```

### 403 Forbidden

```json
{
  "detail": "Cannot access another user's session"
}
```

### 404 Not Found

```json
{
  "detail": "Session not found"
}
```

### 500 Internal Server Error

```json
{
  "detail": "An error occurred while processing your request"
}
```

---

## Authentication

### Obtaining Token

1. Register: `POST /api/auth/register`
2. Login: `POST /api/auth/login`
3. Save `access_token` from response

### Using Token

Include in Authorization header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Token Expiry

- Default: 24 hours
- Refresh: `POST /api/auth/refresh`

---

## Session ID Format

All session IDs must match this pattern:

```
^chat_[a-f0-9]{16}$
```

**Examples**:
- ✅ `chat_abc123def456789`
- ✅ `chat_1234567890abcdef`
- ❌ `session_123`
- ❌ `chat_ABC123` (uppercase not allowed)

---

## Rate Limiting

Currently not implemented. Future implementation will include:
- Request rate limiting per user
- Concurrent session limits
- Message rate limits

---

## Pagination

Not applicable for current API version. All messages returned in single response.

---

## Versioning

Current API version: `1.0.0`

Version included in:
- Root endpoint response
- Health check response
- OpenAPI spec (`/docs`)

---

**Last Updated**: 2026-08-24  
**API Version**: 1.0.0
