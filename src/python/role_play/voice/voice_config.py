class VoiceConfig:
    """
    Constants for voice chat functionality
    """

    MAX_TEXT_SIZE = 1024*10 # 10KB should be pretty big for plain text data
    MAX_AUDIO_CHUNK_SIZE = 1024*100 # 100KB as an initial guess
    AUDIO_SAMPLE_RATE = 16000
    AUDIO_CHANNELS = 1
    AUDIO_BIT_DEPTH = 16
    AUDIO_FORMAT = "pcm"

    # some limits on session
    MAX_SESSION_PER_USER = 3
    SESSION_TIMEOUT_SECONDS = 600 # 10 minute timeout

    # Websocket Error Codes
    WS_MISSING_TOKEN = 1008
    WS_INVALID_TOKEN = 1008
    WS_SESSION_NOT_FOUND = 1008
