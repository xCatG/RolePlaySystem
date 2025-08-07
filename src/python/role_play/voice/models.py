"""Data models for voice chat functionality."""

from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


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
    audio_format: str = "opus"
    sample_rate: int = 48000
    channels: int = 1
    voice_name: Optional[str] = None
    language: str = "en"


class VoiceErrorMessage(BaseModel):
    """Error message for voice session."""
    type: Literal["error"] = "error"
    error: str
    code: Optional[str] = None
    details: Optional[dict] = None


class VoiceStatusMessage(BaseModel):
    """Status update for voice session."""
    type: Literal["status"] = "status"
    status: Literal["connected", "ready", "processing", "disconnected"]
    message: Optional[str] = None