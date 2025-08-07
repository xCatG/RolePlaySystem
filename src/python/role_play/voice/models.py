"""Data models for voice chat functionality."""

from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal
from datetime import datetime
from google.genai import types


class VoiceClientRequest(BaseModel):
    """Request from client to voice handler."""

    model_config = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")
    """The pydantic model config."""

    audio_chunk: Optional[bytes] = None
    """If set, send the audio chunk to the model in realtime mode."""
    text: Optional[str] = None
    """If set, send the text to the model in turn-by-turn mode."""
    end_session: bool = False
    """If set, close the session."""


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
    output_audio_format: str = "wav"


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
