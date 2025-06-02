# Role Play System - API Documentation

Base URL: 
- Development: `http://localhost:8000`
- Beta: `https://roleplay-api-beta-{hash}.a.run.app`
- Production: `https://roleplay-api-prod-{hash}.a.run.app`

## Authentication

All protected endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

## Endpoints

### Health Check

#### GET /health
Check if the service is running.

**Response**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Authentication Endpoints

#### POST /api/auth/register
Register a new user account.

**Request Body**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "John Doe"
}
```

**Response** (201 Created)
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "full_name": "John Doe",
  "role": "USER",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Errors**
- 400: Invalid email format or weak password
- 409: Email already registered

#### POST /api/auth/login
Login with email and password.

**Request Body**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response** (200 OK)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "USER"
  }
}
```

**Errors**
- 401: Invalid credentials
- 404: User not found

#### GET /api/auth/me
Get current user information. **Requires authentication.**

**Response** (200 OK)
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "full_name": "John Doe",
  "role": "USER",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Errors**
- 401: Unauthorized (invalid or missing token)

### Chat Endpoints

#### GET /api/chat/content/scenarios
Get all available roleplay scenarios. **Requires authentication.**

**Response** (200 OK)
```json
{
  "scenarios": [
    {
      "scenario_id": "medieval_court",
      "name": "Medieval Royal Court",
      "description": "Navigate the intrigue and politics of a medieval royal court",
      "setting": "The grand throne room of Castle Drakenhold...",
      "participant_role": "newly appointed Royal Advisor"
    }
  ]
}
```

#### GET /api/chat/content/scenarios/{scenario_id}/characters
Get available characters for a specific scenario. **Requires authentication.**

**Response** (200 OK)
```json
{
  "characters": [
    {
      "character_id": "king_aldric",
      "name": "King Aldric the Bold",
      "description": "The aging but formidable ruler of the kingdom",
      "greeting": "Ah, my new advisor arrives at last..."
    }
  ]
}
```

**Errors**
- 404: Scenario not found

#### POST /api/chat/session
Create a new roleplay session. **Requires authentication.**

**Request Body**
```json
{
  "scenario_id": "medieval_court",
  "character_id": "king_aldric",
  "participant_name": "Lord William"
}
```

**Response** (201 Created)
```json
{
  "session_id": "d81ed7ec-338f-4ac0-9ab3-5c6b84b791f5",
  "scenario_id": "medieval_court",
  "character_id": "king_aldric",
  "participant_name": "Lord William",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Errors**
- 400: Invalid scenario or character ID
- 404: Scenario or character not found

#### GET /api/chat/sessions
List all sessions for the current user. **Requires authentication.**

**Query Parameters**
- `active` (optional): Filter by active/ended sessions (true/false)

**Response** (200 OK)
```json
{
  "sessions": [
    {
      "session_id": "d81ed7ec-338f-4ac0-9ab3-5c6b84b791f5",
      "scenario_name": "Medieval Royal Court",
      "character_name": "King Aldric the Bold",
      "participant_name": "Lord William",
      "message_count": 15,
      "created_at": "2024-01-15T10:30:00Z",
      "ended_at": null
    }
  ]
}
```

#### POST /api/chat/session/{session_id}/message
Send a message in an active session. **Requires authentication.**

**Request Body**
```json
{
  "content": "Your Majesty, I bring news from the northern borders..."
}
```

**Response** (200 OK)
```json
{
  "message_id": "msg_123",
  "role": "assistant",
  "content": "The North? Speak quickly, advisor. What news do you bring?",
  "created_at": "2024-01-15T10:31:00Z"
}
```

**Errors**
- 404: Session not found
- 400: Session already ended

#### POST /api/chat/session/{session_id}/end
End an active session. **Requires authentication.**

**Response** (200 OK)
```json
{
  "session_id": "d81ed7ec-338f-4ac0-9ab3-5c6b84b791f5",
  "ended_at": "2024-01-15T10:35:00Z"
}
```

**Errors**
- 404: Session not found
- 400: Session already ended

#### GET /api/chat/session/{session_id}/export-text
Export session as plain text. **Requires authentication.**

**Response** (200 OK)
```
Content-Type: text/plain

Medieval Royal Court - King Aldric the Bold
Session started: 2024-01-15 10:30:00 UTC
Participant: Lord William

================================================================================

King Aldric the Bold: Ah, my new advisor arrives at last...

Lord William: Your Majesty, I bring news from the northern borders...

King Aldric the Bold: The North? Speak quickly, advisor. What news do you bring?

[... rest of conversation ...]

================================================================================
Session ended: 2024-01-15 10:35:00 UTC
Total messages: 15
```

**Errors**
- 404: Session not found

### Evaluation Endpoints

#### GET /api/evaluation/sessions
List sessions available for evaluation. **Requires authentication (USER or higher).**

**Response** (200 OK)
```json
{
  "sessions": [
    {
      "session_id": "d81ed7ec-338f-4ac0-9ab3-5c6b84b791f5",
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "scenario_name": "Medieval Royal Court",
      "character_name": "King Aldric the Bold",
      "message_count": 15,
      "created_at": "2024-01-15T10:30:00Z",
      "ended_at": "2024-01-15T10:35:00Z"
    }
  ]
}
```

#### GET /api/evaluation/session/{session_id}/download
Download session transcript as text file. **Requires authentication (USER or higher).**

**Response** (200 OK)
```
Content-Type: text/plain
Content-Disposition: attachment; filename="session_d81ed7ec_transcript.txt"

[Same format as export-text endpoint]
```

**Errors**
- 404: Session not found

## Error Response Format

All errors follow this format:

```json
{
  "detail": "Descriptive error message"
}
```

Common HTTP status codes:
- 400: Bad Request (invalid input)
- 401: Unauthorized (missing/invalid token)
- 403: Forbidden (insufficient permissions)
- 404: Not Found
- 409: Conflict (e.g., duplicate email)
- 500: Internal Server Error

## Rate Limiting

Production environment implements rate limiting:
- Default: 60 requests per minute per IP
- Configurable via `RATE_LIMIT_RPM` environment variable

Rate limit headers:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642248360
```

## CORS Configuration

CORS is enabled for all environments with different allowed origins:

- **Development**: `http://localhost:3000`, `http://localhost:5173`, `http://localhost:8080`
- **Beta**: Configured via `FRONTEND_URL` environment variable
- **Production**: Configured via `FRONTEND_URL` environment variable

## WebSocket Endpoints (Future)

WebSocket support for real-time chat is planned for future releases:
- `/ws/chat/{session_id}` - Real-time chat messages
- `/ws/audio/{session_id}` - Audio streaming for voice interaction

## Pagination (Future)

List endpoints will support pagination in future releases:
- `limit`: Number of items per page (default: 20, max: 100)
- `offset`: Number of items to skip
- `cursor`: Cursor-based pagination token