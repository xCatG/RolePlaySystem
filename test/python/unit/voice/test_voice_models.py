
import pytest
from pydantic import ValidationError

from role_play.voice.models import VoiceRequest

def test_voice_request_validation():
    # Test valid mime types
    VoiceRequest(mime_type="audio/pcm", data="")
    VoiceRequest(mime_type="text/plain", data="")

    # Test invalid mime type
    with pytest.raises(ValidationError):
        VoiceRequest(mime_type="audio/mp3", data="")


def test_voice_request_decoding():
    # Test audio decoding
    audio_data = b"\x01\x02\x03"
    encoded_audio = "AQID"
    req = VoiceRequest(mime_type="audio/pcm", data=encoded_audio)
    assert req.decode_data() == audio_data

    # Test text decoding
    text_data = "Hello world"
    encoded_text = "SGVsbG8gd29ybGQ="
    req = VoiceRequest(mime_type="text/plain", data=encoded_text)
    assert req.decode_data() == text_data

    # Test invalid base64
    with pytest.raises(ValueError):
        req = VoiceRequest(mime_type="audio/pcm", data="invalid!")
        req.decode_data()
