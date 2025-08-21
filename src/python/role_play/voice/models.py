"""Simplified voice models - minimal essential types."""

import base64
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field


class VoiceRequest(BaseModel):
    """Generic client request for voice sessions."""
    mime_type: str = Field(..., description="MIME type (audio/pcm, text/plain)")
    data: str = Field(..., description="Base64-encoded data")
    end_session: bool = Field(default=False, description="Whether to end session")
    
    def decode_data(self) -> Union[bytes, str]:
        """Decode base64 data based on MIME type."""
        if self.mime_type.startswith("audio/"):
            return base64.b64decode(self.data)
        else:
            return base64.b64decode(self.data).decode('utf-8')


class VoiceMessage(BaseModel):
    """Generic server message for voice sessions."""
    type: str = Field(..., description="Message type")
    timestamp: Optional[str] = Field(None, description="ISO timestamp")
    
    class Config:
        """Pydantic configuration."""
        extra = "allow"  # Allow any additional fields for flexibility