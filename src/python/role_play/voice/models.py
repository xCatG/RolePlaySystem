import base64
from typing import Union

from pydantic import BaseModel, Field, field_validator

from .voice_config import VoiceConfig


class VoiceRequest(BaseModel):
    mime_type: str = Field(..., description="MIME type, valid: audio/pcm, text/plain")
    data: str = Field(..., description="base64 encoded data")
    end_session:bool = Field(default=False, description="Flag whether to end session")

    @field_validator("mime_type")
    def validate_mime_type(cls, value):
        allowed = ["audio/pcm", "text/plain"]
        if value not in allowed:
            raise ValueError(f"Invalid MIME type: {value}")
        return value

    def decode_data(self) -> Union[bytes, str]:
        """Decode and validate base64 data"""

        try:
            data = base64.b64decode(self.data)
        except Exception as e:
            raise ValueError(f"Could not decode base64 data: {e}")

        if self.mime_type.startswith("audio/"):
            if len(data) > VoiceConfig.MAX_AUDIO_CHUNK_SIZE:
                raise ValueError(f"Audio chunk size too large: {len(data)}")
            return data
        else:
            if len(data) > VoiceConfig.MAX_TEXT_SIZE:
                raise ValueError(f"Text chunk size too large: {len(data)}")
            return data.decode("utf-8")
