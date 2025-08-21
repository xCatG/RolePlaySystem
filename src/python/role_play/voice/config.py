"""Voice chat configuration constants."""


class VoiceConfig:
    """Configuration constants for voice chat functionality."""
    
    # Audio parameters
    AUDIO_SAMPLE_RATE = 16000
    AUDIO_CHANNELS = 1
    AUDIO_BIT_DEPTH = 16
    AUDIO_FORMAT = "pcm"
    
    # Size limits for security
    MAX_AUDIO_CHUNK_SIZE = 1024 * 100  # 100KB per audio chunk
    MAX_TEXT_SIZE = 1024 * 10  # 10KB per text message
    
    # Session management
    MAX_SESSIONS_PER_USER = 5  # Prevent resource exhaustion
    SESSION_TIMEOUT_SECONDS = 3600  # 1 hour timeout
    
    # WebSocket codes
    WS_MISSING_TOKEN = 1008
    WS_INVALID_TOKEN = 1008
    WS_SESSION_NOT_FOUND = 1008