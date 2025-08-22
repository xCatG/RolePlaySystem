# Voice Backend Testing Suite

This directory contains comprehensive testing tools for the voice backend, allowing developers to test voice functionality without launching the full frontend.

## 🎯 Overview

The voice testing suite provides three approaches to testing:

1. **🚀 Quick Setup + Interactive Testing** - Generate HTML page with credentials
2. **🤖 Automated Testing** - Comprehensive backend functionality verification  
3. **📊 Manual Testing** - Direct WebSocket testing with existing tools

## 📁 Files

| File | Purpose | Usage |
|------|---------|-------|
| `setup_voice_test.py` | Creates test session and HTML page | Interactive testing |
| `test_voice_backend.py` | Automated test suite | CI/CD and validation |
| `voice_test_template.html` | HTML template for interactive testing | Browser-based testing |
| `README.md` | This documentation | Reference |

## 🚀 Quick Start

### 1. Setup Interactive Testing

```bash
# Start the backend server first
python src/python/run_server.py

# In another terminal, create a test session
python test/voice/setup_voice_test.py

# Output:
# ✅ Session created: session_abc123
# ✅ Test page generated: test/voice/test_session.html
# 
# Open in browser: file:///path/to/test/voice/test_session.html
```

### 2. Open Test Page

**Option A: Direct file access**
```bash
# Copy the file path from setup output and open in browser
open test/voice/test_session.html  # macOS
xdg-open test/voice/test_session.html  # Linux
```

**Option B: Local HTTP server**
```bash
cd test/voice/
python -m http.server 8080
# Open: http://localhost:8080/test_session.html
```

### 3. Test Voice Functionality

1. Click **"🔗 Connect to Voice"** - Should show "Connected" status
2. **Text Testing**: Type a message and click "📝 Send Text"
3. **Voice Testing**: Hold "🎤 Push to Talk" and speak
4. **Monitor**: Watch transcript and debug log for real-time feedback

## 🤖 Automated Testing

Run the comprehensive test suite:

```bash
# Basic test run
python test/voice/test_voice_backend.py

# With custom credentials
python test/voice/test_voice_backend.py --user admin@example.com --password secret

# Verbose output for debugging
python test/voice/test_voice_backend.py --verbose
```

### Test Coverage

The automated test verifies:

- ✅ **Authentication** - Login and JWT token validation
- ✅ **Session Creation** - Chat session setup with scenario/character
- ✅ **WebSocket Connection** - Voice WebSocket establishment
- ✅ **Text Messaging** - Send text, receive transcript and audio
- ✅ **Audio Simulation** - Send PCM audio data, verify processing
- ✅ **Graceful Disconnect** - Clean session termination
- ✅ **Error Handling** - Invalid data handling and stability

### Example Output

```
🎙️  Voice Backend Automated Test Suite
============================================================
  ✅ Authentication (0.34s)
  ✅ Content Loading (0.12s)
  ✅ Session Creation (0.28s)
  ✅ WebSocket Connection (1.45s)
  ✅ Text Messaging (3.21s)
  ✅ Audio Simulation (2.18s)
  ✅ Graceful Disconnect (0.52s)
  ✅ Error Handling (1.03s)

📈 Overall: 8/8 tests passed (100.0%)
⏱️  Total time: 9.13s
🎉 All tests passed! Voice backend is working correctly.
```

## 🛠️ Advanced Usage

### Custom Test Credentials

```bash
# Use different user account
python test/voice/setup_voice_test.py --user alice@company.com --password mypass

# Test with admin account
python test/voice/test_voice_backend.py --user admin@example.com --password admin123
```

### Multiple Test Sessions

```bash
# Create multiple test sessions for load testing
for i in {1..5}; do
  python test/voice/setup_voice_test.py --user "test${i}@example.com" &
done
```

### CI/CD Integration

```bash
#!/bin/bash
# ci_voice_test.sh

# Start server in background
python src/python/run_server.py &
SERVER_PID=$!

# Wait for server startup
sleep 5

# Run voice tests
python test/voice/test_voice_backend.py
TEST_RESULT=$?

# Cleanup
kill $SERVER_PID

exit $TEST_RESULT
```

## 🎛️ Interactive Test Features

### HTML Test Page Capabilities

- **🔗 Connection Management**: Connect/disconnect with status indicators
- **📝 Text Input**: Send text messages with Enter key support
- **🎤 Audio Recording**: Push-to-talk with microphone access
- **📊 Real-time Stats**: Message counts, connection time, audio chunks
- **🔍 Debug Log**: WebSocket message inspection with timestamps
- **📜 Transcript View**: Conversation history with partial updates

### Browser Requirements

- **WebSocket Support**: Modern browsers (Chrome 16+, Firefox 11+, Safari 7+)
- **Microphone Access**: HTTPS or localhost required for getUserMedia()
- **Audio Context**: Web Audio API support for audio processing

### Troubleshooting Interactive Tests

| Issue | Cause | Solution |
|-------|-------|---------|
| "Connection failed" | Server not running | Start `python src/python/run_server.py` |
| "Microphone error" | Permission denied | Allow microphone access in browser |
| "Session not found" | Expired session | Run setup script again |
| "Invalid token" | JWT expired | Re-run setup script for new token |

## 🔧 Backend Requirements

### Server Setup

```bash
# 1. Install dependencies
pip install -r src/python/requirements.txt

# 2. Set environment variables
export STORAGE_PATH="./data/test"
export JWT_SECRET_KEY="test-secret-key"

# 3. Start server
python src/python/run_server.py
```

### Test User Setup

```bash
# Create test user (if needed)
python -c "
import asyncio
from src.python.role_play.common.auth import AuthManager
from src.python.role_play.common.storage import FileStorage
from src.python.role_play.common.storage_factory import create_storage

async def create_user():
    storage = create_storage()
    auth = AuthManager(storage)
    await auth.register_user('test@example.com', 'password', 'USER')
    print('Test user created')

asyncio.run(create_user())
"
```

## 📊 Message Format Reference

### Client to Server (VoiceRequest)

```json
{
  "mime_type": "text/plain" | "audio/pcm",
  "data": "base64_encoded_data",
  "end_session": false
}
```

### Server to Client (VoiceMessage)

```json
// Configuration
{
  "type": "config",
  "audio_format": "pcm",
  "sample_rate": 16000,
  "channels": 1,
  "bit_depth": 16,
  "language": "en"
}

// Status updates
{
  "type": "status",
  "status": "connecting" | "ready" | "ended",
  "message": "Human readable status"
}

// Transcripts
{
  "type": "transcript_partial",
  "text": "Partial text...",
  "role": "user" | "assistant",
  "stability": 0.85
}

{
  "type": "transcript_final", 
  "text": "Final transcribed text",
  "role": "user" | "assistant",
  "confidence": 0.92
}

// Audio data
{
  "type": "audio",
  "data": "base64_encoded_pcm_audio",
  "mime_type": "audio/pcm"
}

// Turn management
{
  "type": "turn_status",
  "turn_complete": true,
  "interrupted": false
}

// Errors
{
  "type": "error",
  "error": "Error description",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

## 🚨 Common Issues

### Connection Issues

1. **"Connection refused"**
   - Check if server is running on port 8000
   - Verify `python src/python/run_server.py` is active

2. **"Authentication failed"**
   - Verify test user exists: `test@example.com` / `password`
   - Check JWT_SECRET_KEY environment variable

3. **"Session not found"**
   - Sessions expire after 1 hour
   - Re-run setup script to create fresh session

### Audio Issues

1. **"Microphone error"**
   - Grant microphone permissions in browser
   - Use HTTPS or localhost for getUserMedia()

2. **"No audio received"**
   - Check ADK/Gemini API configuration
   - Verify voice model availability

### Performance Issues

1. **Slow responses**
   - Check network connectivity to Gemini API
   - Monitor server logs for errors
   - Verify adequate system resources

## 🔍 Debug Tips

### Server-side Debugging

```bash
# Run with debug logging
PYTHONPATH=./src/python LOG_LEVEL=DEBUG python src/python/run_server.py

# Monitor voice handler logs
tail -f logs/voice_handler.log
```

### Client-side Debugging

1. **Browser Developer Tools**
   - Network tab: WebSocket connection details
   - Console tab: JavaScript errors and debug messages
   - Application tab: localStorage inspection

2. **WebSocket Message Inspection**
   - Use the debug panel in the HTML test page
   - Monitor sent/received message timestamps
   - Check message size and format

### API Testing

```bash
# Test REST endpoints
curl -H "Authorization: Bearer $JWT_TOKEN" \
     http://localhost:8000/api/chat/content/scenarios

# Check WebSocket endpoint
wscat -c "ws://localhost:8000/api/voice/ws/$SESSION_ID?token=$JWT_TOKEN"
```

## 📈 Performance Benchmarks

| Test | Expected Duration | Pass Criteria |
|------|------------------|---------------|
| Authentication | < 1s | JWT token received |
| Session Creation | < 2s | Valid session ID |
| WebSocket Connection | < 3s | Ready status received |
| Text Messaging | < 10s | Transcript + audio response |
| Audio Simulation | < 8s | Audio processing confirmed |
| Graceful Disconnect | < 2s | Clean connection close |

## 🤝 Contributing

To add new tests:

1. **Add test method** to `VoiceBackendTester` class
2. **Include in test suite** by adding to `tests` array in `run_all_tests()`
3. **Document expected behavior** in this README
4. **Update HTML template** if testing new WebSocket message types

### Test Method Template

```python
async def test_new_feature(self) -> bool:
    """Test new voice feature."""
    start_time = time.time()
    
    try:
        async with websockets.connect(self.ws_url) as websocket:
            await self._wait_for_ready(websocket)
            
            # Test implementation here
            
            duration = time.time() - start_time
            self.add_test_result("New Feature", True, "Success details", duration)
            return True
            
    except Exception as e:
        duration = time.time() - start_time
        self.add_test_result("New Feature", False, str(e), duration)
        return False
```

---

## 📞 Support

For issues with voice testing:

1. **Check server logs** for backend errors
2. **Verify test user credentials** and permissions
3. **Test with simple curl/wscat** to isolate issues
4. **Review WebSocket message format** against API documentation

Happy testing! 🎙️✨