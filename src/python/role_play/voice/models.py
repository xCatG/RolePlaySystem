"""Simplified voice models - minimal essential types."""

import base64
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator

from .config import VoiceConfig


class VoiceRequest(BaseModel):
    """Generic client request for voice sessions."""
    mime_type: str = Field(..., description="MIME type (audio/pcm, text/plain)")
    data: str = Field(..., description="Base64-encoded data")
    end_session: bool = Field(default=False, description="Whether to end session")
    
    @validator('mime_type')
    def validate_mime_type(cls, v):
        """Validate MIME type is supported."""
        allowed = ['audio/pcm', 'text/plain']
        if v not in allowed:
            raise ValueError(f"Unsupported MIME type: {v}. Allowed: {allowed}")
        return v
    
    def decode_data(self) -> Union[bytes, str]:
        """Decode and validate base64 data."""
        try:
            data = base64.b64decode(self.data)
        except Exception as e:
            raise ValueError(f"Invalid base64 data: {e}")
        
        if self.mime_type.startswith("audio/"):
            if len(data) > VoiceConfig.MAX_AUDIO_CHUNK_SIZE:
                raise ValueError(f"Audio chunk too large: {len(data)} bytes (max: {VoiceConfig.MAX_AUDIO_CHUNK_SIZE})")
            return data
        else:
            if len(data) > VoiceConfig.MAX_TEXT_SIZE:
                raise ValueError(f"Text too large: {len(data)} bytes (max: {VoiceConfig.MAX_TEXT_SIZE})")
            return data.decode('utf-8')


class VoiceMessage(BaseModel):
    """Generic server message for voice sessions."""
    type: str = Field(..., description="Message type")
    timestamp: Optional[str] = Field(None, description="ISO timestamp")
    
    class Config:
        """Pydantic configuration."""
        extra = "allow"  # Allow any additional fields for flexibility