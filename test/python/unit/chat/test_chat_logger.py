
import pytest
from unittest.mock import call, AsyncMock
import json

from role_play.common.time_utils import utc_now_isoformat

@pytest.mark.asyncio
async def test_log_voice_message_success(chat_logger, mock_storage):
    user_id = "test_user"
    session_id = "test_session"
    await chat_logger.log_voice_message(
        user_id=user_id,
        session_id=session_id,
        role="participant",
        transcript_text="Hello world",
        duration_ms=1000,
        confidence=0.9,
        message_number=1,
    )

    expected_path = f"users/{user_id}/chat_logs/{session_id}"
    assert mock_storage.append.call_count == 1
    args, _ = mock_storage.append.call_args
    assert args[0] == expected_path
    log_data = json.loads(args[1])
    assert log_data["type"] == "voice_message"
    assert log_data["role"] == "participant"
    assert log_data["content"] == "Hello world"


@pytest.mark.asyncio
async def test_log_pcm_audio_success(chat_logger, mock_storage):
    user_id = "test_user"
    session_id = "test_session"
    audio_data = b"\x01\x02\x03"
    await chat_logger.log_pcm_audio(
        user_id=user_id,
        session_id=session_id,
        audio_data=audio_data,
    )

    assert mock_storage.write_bytes.call_count == 1
    args, _ = mock_storage.write_bytes.call_args
    assert args[0].startswith(f"users/{user_id}/voice_logs/{session_id}/audio_in_")
    assert args[1] == audio_data


@pytest.mark.asyncio
async def test_log_voice_session_start_and_end(chat_logger, mock_storage):
    user_id = "test_user"
    session_id = "test_session"
    voice_config = {"sample_rate": 16000}
    voice_stats = {"duration": 10000}

    await chat_logger.log_voice_session_start(
        user_id=user_id,
        session_id=session_id,
        voice_config=voice_config,
    )

    await chat_logger.log_voice_session_end(
        user_id=user_id,
        session_id=session_id,
        voice_stats=voice_stats,
    )

    assert mock_storage.append.call_count == 2
    
    # Check start event
    args, _ = mock_storage.append.call_args_list[0]
    start_log_data = json.loads(args[1])
    assert start_log_data["type"] == "voice_session_start"
    assert start_log_data["voice_config"] == voice_config

    # Check end event
    args, _ = mock_storage.append.call_args_list[1]
    end_log_data = json.loads(args[1])
    assert end_log_data["type"] == "voice_session_end"
    assert end_log_data["voice_stats"] == voice_stats
