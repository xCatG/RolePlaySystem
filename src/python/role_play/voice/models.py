"""Voice chat models and message types."""

import base64
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field
from ..common.models import BaseResponse


class VoiceClientRequest(BaseModel):
    """Request from client containing audio or text data."""
    mime_type: str = Field(..., description="MIME type of the data (audio/pcm, text/plain)")
    data: str = Field(..., description="Base64-encoded data")
    end_session: bool = Field(default=False, description="Whether to end the session")
    
    def decode_data(self) -> Union[bytes, str]:
        """Decode base64 data based on MIME type."""
        if self.mime_type.startswith("audio/"):
            return base64.b64decode(self.data)
        else:
            return base64.b64decode(self.data).decode('utf-8')


class VoiceConfigMessage(BaseModel):
    """Configuration message sent to client."""
    type: str = Field(default="config", description="Message type")
    audio_format: str = Field(..., description="Expected audio format (pcm)")
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels")
    bit_depth: int = Field(default=16, description="Audio bit depth")
    language: str = Field(..., description="Response language")
    voice_name: str = Field(..., description="Character voice name")
    output_audio_format: str = Field(default="pcm", description="Output audio format")


class VoiceStatusMessage(BaseModel):
    """Status update message."""
    type: str = Field(default="status", description="Message type")
    status: str = Field(..., description="Status (connected, ready, error, ended)")
    message: str = Field(..., description="Status message")
    timestamp: Optional[str] = None


class VoiceErrorMessage(BaseModel):
    """Error message."""
    type: str = Field(default="error", description="Message type")
    error: str = Field(..., description="Error description")
    code: Optional[str] = None
    timestamp: Optional[str] = None


class TranscriptMessage(BaseModel):
    """Transcript message (partial or final)."""
    type: str = Field(default="transcript", description="Message type")
    text: str = Field(..., description="Transcribed text")
    role: str = Field(..., description="Speaker role (user, assistant)")
    is_final: bool = Field(default=True, description="Whether this is a final transcript")
    stability: Optional[float] = Field(None, description="Stability score (0.0-1.0)")
    confidence: Optional[float] = Field(None, description="Confidence score (0.0-1.0)")
    timestamp: str = Field(..., description="ISO timestamp")


class TranscriptPartialMessage(BaseModel):
    """Partial transcript for live display."""
    type: str = Field(default="transcript_partial", description="Message type")
    text: str = Field(..., description="Partial transcribed text")
    role: str = Field(..., description="Speaker role (user, assistant)")
    stability: float = Field(..., description="Stability score (0.0-1.0)")
    timestamp: str = Field(..., description="ISO timestamp")


class TranscriptFinalMessage(BaseModel):
    """Final transcript for logging."""
    type: str = Field(default="transcript_final", description="Message type")
    text: str = Field(..., description="Final transcribed text")
    role: str = Field(..., description="Speaker role (user, assistant)")
    duration_ms: int = Field(..., description="Duration in milliseconds")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Voice metadata")
    timestamp: str = Field(..., description="ISO timestamp")


class AudioChunkMessage(BaseModel):
    """Audio chunk message."""
    type: str = Field(default="audio", description="Message type")
    data: str = Field(..., description="Base64-encoded audio data")
    mime_type: str = Field(default="audio/pcm", description="Audio MIME type")
    sequence: Optional[int] = Field(None, description="Sequence number for ordering")
    timestamp: str = Field(..., description="ISO timestamp")


class TurnStatusMessage(BaseModel):
    """Turn status update."""
    type: str = Field(default="turn_status", description="Message type")
    turn_complete: bool = Field(..., description="Whether turn is complete")
    interrupted: bool = Field(default=False, description="Whether turn was interrupted")
    timestamp: str = Field(..., description="ISO timestamp")


class VoiceSessionInfo(BaseModel):
    """Voice session information."""
    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    character_id: Optional[str] = Field(None, description="Character ID")
    scenario_id: Optional[str] = Field(None, description="Scenario ID")
    language: str = Field(default="en", description="Session language")
    started_at: Optional[str] = Field(None, description="Session start timestamp")
    transcript_available: bool = Field(default=False, description="Whether transcripts are available")


class VoiceSessionStats(BaseModel):
    """Voice session statistics."""
    session_id: str = Field(..., description="Session ID")
    started_at: str = Field(..., description="Session start timestamp")
    ended_at: Optional[str] = Field(None, description="Session end timestamp")
    duration_ms: Optional[int] = Field(None, description="Session duration in milliseconds")
    audio_chunks_sent: int = Field(default=0, description="Audio chunks sent to server")
    audio_chunks_received: int = Field(default=0, description="Audio chunks received from server")
    transcripts_processed: int = Field(default=0, description="Total transcripts processed")
    total_utterances: int = Field(default=0, description="Total finalized utterances")
    total_partials: int = Field(default=0, description="Total partial transcripts processed")
    errors: int = Field(default=0, description="Number of errors encountered")


class VoiceMessage(BaseModel):
    """Voice message for ChatLogger integration."""
    type: str = Field(default="voice_message", description="Message type")
    role: str = Field(..., description="Speaker role (user, assistant)")
    text: str = Field(..., description="Transcribed text")
    timestamp: str = Field(..., description="ISO timestamp")
    voice_metadata: Dict[str, Any] = Field(default_factory=dict, description="Voice-specific metadata")
    
    class Config:
        """Pydantic configuration."""
        extra = "allow"  # Allow additional fields for compatibility


class VoiceSessionRequest(BaseModel):
    """Request to create or join a voice session."""
    session_id: str = Field(..., description="Session ID to join")
    character_id: Optional[str] = Field(None, description="Character ID (if creating new)")
    scenario_id: Optional[str] = Field(None, description="Scenario ID (if creating new)")
    language: Optional[str] = Field("en", description="Language preference")
    transcript_config: Optional[Dict[str, Any]] = Field(None, description="Transcript buffer configuration")


class VoiceSessionResponse(BaseResponse):
    """Response from voice session operations."""
    session_info: Optional[VoiceSessionInfo] = None
    stats: Optional[VoiceSessionStats] = None


# Union type for all possible WebSocket messages from server to client
VoiceServerMessage = Union[
    VoiceConfigMessage,
    VoiceStatusMessage,
    VoiceErrorMessage,
    TranscriptPartialMessage,
    TranscriptFinalMessage,
    AudioChunkMessage,
    TurnStatusMessage
]


# Union type for all possible WebSocket messages from client to server
VoiceClientMessage = Union[VoiceClientRequest]


class VoiceTranscriptConfig(BaseModel):
    """Configuration for transcript buffering."""
    stability_threshold: float = Field(default=0.8, description="Minimum stability for partial acceptance")
    finalization_timeout_ms: int = Field(default=2000, description="Timeout for finalizing partials")
    min_utterance_length: int = Field(default=3, description="Minimum words for logging utterance")
    sentence_boundary_patterns: List[str] = Field(
        default_factory=lambda: [r'[.!?]+\s*$', r'\n+'],
        description="Regex patterns for sentence boundaries"
    )


class VoiceBufferStats(BaseModel):
    """Statistics from transcript buffering."""
    pending_user_segments: int = Field(..., description="Pending user transcript segments")
    pending_assistant_segments: int = Field(..., description="Pending assistant transcript segments")
    total_utterances: int = Field(..., description="Total finalized utterances")
    total_partials: int = Field(..., description="Total partial segments processed")
    started_at: str = Field(..., description="Buffer start timestamp")