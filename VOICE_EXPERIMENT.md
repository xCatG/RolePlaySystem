# Voice Chat WebSocket Experiment

This document summarizes the experimental voice chat implementation using Gemini Live API for real-time bidirectional audio streaming.

## Overview

This experiment implements a WebSocket-based voice chat handler that enables real-time voice conversations with roleplay characters using Google's Gemini Live API. The implementation serves as a proof-of-concept and reference for future voice chat features.

## Key Components

### 1. Voice Chat Handler (`src/python/role_play/voice/handler.py`)

**Core Features:**
- WebSocket endpoint: `/api/voice/ws/{session_id}`
- JWT authentication via query parameter
- Real-time bidirectional audio streaming
- Character context integration with ADK sessions
- Audio transcription and logging

**Architecture:**
- Stateless handler design following existing patterns
- Dual-task architecture: receive task + send task
- Shared conversation state for task coordination
- Mock session support for development without API key

### 2. Audio Processing

**Input Processing:**
- Accepts PCM audio data (16kHz, mono) via base64-encoded JSON messages
- ADK-style message format: `{mime_type: "audio/pcm", data: "base64..."}`
- Real-time forwarding to Gemini Live API using `types.Blob`

**Output Processing:**
- Receives audio and transcription from Gemini Live
- Forwards audio as base64-encoded JSON to client
- Transcriptions logged to ChatLogger with voice metadata

### 3. Client Test Interface (`test_voice_chat.html`)

**Features:**
- Push-to-talk audio recording using ScriptProcessorNode
- Audio playback queue for smooth streaming
- Text input fallback for testing
- Real-time transcript display
- JWT token and session ID management

## Technical Implementation Details

### WebSocket Message Flow

1. **Connection**: Client connects with JWT token in query params
2. **Configuration**: Server sends audio config (format, voice, language)
3. **Bidirectional Streaming**: 
   - Client → Server: PCM audio chunks or text
   - Server → Client: Audio data, transcriptions, status updates
4. **Session Management**: Continuous conversation until explicit end

### Key API Integrations

**Gemini Live API Configuration:**
```python
config = types.LiveConnectConfig(
    responseModalities=[types.Modality.AUDIO],
    speechConfig=types.SpeechConfig(
        voiceConfig=types.VoiceConfig(
            prebuiltVoiceConfig=types.PrebuiltVoiceConfig(
                voiceName=voice_name
            )
        )
    ),
    outputAudioTranscription=AudioTranscriptionConfig(),
    inputAudioTranscription=AudioTranscriptionConfig(),
    systemInstruction=system_instruction
)
```

**Critical Fix - Field Naming:**
- Google GenAI library expects camelCase field names, not snake_case
- Fixed: `mimeType` (not `mime_type`), `responseModalities` (not `response_modalities`), etc.

### Conversation Continuity Solution

**Problem:** WebSocket was closing after model's `turn_complete` message.

**Solution:** Implemented shared conversation state pattern:
```python
conversation_state = {
    "active": True,
    "session_ended": False
}
```

**Key Changes:**
- Send task continues listening after `turn_complete`
- Handles `StopAsyncIteration` when Gemini session generator ends
- Only exits when client explicitly ends session or disconnects
- Coordinated shutdown between receive and send tasks

## Audio Processing Pipeline

### Client Side (JavaScript)
1. **Input**: `getUserMedia()` → `ScriptProcessorNode` → Int16 PCM data
2. **Encoding**: PCM → Base64 → JSON message
3. **Output**: JSON audio messages → Base64 decode → AudioBuffer → playback

### Server Side (Python)
1. **Input**: JSON message → Base64 decode → `types.Blob` → Gemini Live
2. **Output**: Gemini Live audio → Base64 encode → JSON message → WebSocket

## Character Integration

**Context Loading:**
- Loads character and scenario from ResourceLoader
- Builds system instruction with character personality and scenario context
- Respects user's preferred language for both content and AI responses
- Integrates with existing ChatLogger for transcript persistence

**System Instruction Format:**
```
You are {character_name} in a voice conversation.
Character Description: {character_description}
Scenario: {scenario_description}
Participant: {participant_name}

IMPORTANT: You must respond in {language_name} language.
Stay in character at all times. Respond naturally as if in a real conversation.
{character_system_prompt}
```

## Development Features

### Mock Session Support
- Fallback when `GEMINI_API_KEY` is not available
- Echoes back mock responses for testing
- Maintains same WebSocket message format
- Useful for frontend development without API costs

### Error Handling
- JWT validation with proper error responses
- Session validation (active sessions only)
- WebSocket disconnect handling
- Gemini API error recovery
- Graceful degradation patterns

## Known Limitations & Considerations

1. **API Dependencies**: Requires valid Gemini API key and quota
2. **Audio Quality**: Uses basic PCM encoding; could be optimized
3. **Latency**: Real-time streaming has inherent network latency
4. **Browser Compatibility**: Uses ScriptProcessorNode (deprecated but widely supported)
5. **Production Readiness**: Experimental code, needs hardening for production

## Files Modified/Created

### Core Implementation
- `src/python/role_play/voice/handler.py` - Main WebSocket handler
- `src/python/role_play/voice/models.py` - Data models for voice messages

### Test Interface
- `test_voice_chat.html` - Client-side test interface with audio recording/playback

### Reference Files
- `live_request_queue.py` - ADK-style queue pattern (for future reference)

## Configuration Requirements

**Environment Variables:**
- `GEMINI_API_KEY` - Required for live API integration
- `JWT_SECRET_KEY` - For authentication
- `STORAGE_PATH` - For audio file storage

**Dependencies:**
- `google-genai` - Gemini Live API client
- `websockets` - WebSocket support
- Standard FastAPI/Pydantic stack

## Future Considerations

1. **Production Architecture**: Consider using ADK's `LiveRequestQueue` pattern
2. **Audio Optimization**: Implement Opus encoding for better compression
3. **Scalability**: WebRTC direct peer connections for lower latency
4. **UI Integration**: Embed voice controls in main Vue.js frontend
5. **Error Recovery**: Better handling of network interruptions
6. **Audio Quality**: Noise suppression, echo cancellation

## Success Metrics

✅ **Achieved:**
- Real-time bidirectional audio streaming
- Character-aware voice conversations
- Continuous conversation flow (no disconnect after responses)
- WebSocket-based architecture
- Integration with existing auth and session systems

🎯 **Demonstrated Feasibility:**
- Voice chat can be integrated with existing roleplay system
- Gemini Live API provides quality voice synthesis
- WebSocket pattern works for real-time audio streaming
- Character context successfully influences voice responses

This experiment provides a solid foundation for implementing production voice chat features in the roleplay system.