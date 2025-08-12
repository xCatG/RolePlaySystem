"""Data models for voice chat functionality."""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal, Union
from datetime import datetime
import base64
from google.genai import types


class VoiceClientRequest(BaseModel):
    """Request from client using ADK-style format."""
    
    mime_type: str = Field(..., description="MIME type: 'audio/pcm' or 'text/plain'")
    """The MIME type of the data."""
    
    data: str = Field(..., description="Base64 encoded content")
    """Base64 encoded audio or text data."""
    
    end_session: bool = Field(default=False, description="End the voice session")
    """If set, close the session."""
    
    def decode_data(self) -> Union[bytes, str]:
        """Decode the base64 data based on mime_type."""
        if self.mime_type == "audio/pcm":
            return base64.b64decode(self.data)
        elif self.mime_type == "text/plain":
            # Decode base64 then decode UTF-8
            return base64.b64decode(self.data).decode('utf-8')
        else:
            raise ValueError(f"Unsupported mime_type: {self.mime_type}")


class VoiceSessionInfo(BaseModel):
    """Information about a voice chat session."""
    session_id: str
    user_id: str
    character_id: str
    scenario_id: str
    language: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    audio_format: str = "opus"
    transcript_available: bool = False


class TranscriptMessage(BaseModel):
    """A transcribed message from voice chat."""
    type: Literal["transcript"] = "transcript"
    text: str
    role: Literal["user", "assistant"]
    timestamp: str
    confidence: Optional[float] = None


class VoiceConfigMessage(BaseModel):
    """Configuration message for voice session."""
    type: Literal["config"] = "config"
    audio_format: str = "pcm"
    sample_rate: int = 16000
    channels: int = 1
    voice_name: Optional[str] = None
    language: str = "en"
    output_audio_format: str = "pcm"
    output_sample_rate: Optional[int] = None


class VoiceErrorMessage(BaseModel):
    """Error message for voice session."""
    type: Literal["error"] = "error"
    error: str
    code: Optional[str] = None
    details: Optional[dict] = None


class VoiceStatusMessage(BaseModel):
    """Status update for voice session."""
    type: Literal["status"] = "status"
    status: Literal["connected", "ready", "processing", "disconnected", "response_complete"]
    message: Optional[str] = None
