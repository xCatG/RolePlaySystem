"""Tests for the voice transcript management system."""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.python.role_play.voice.transcript_manager import (
    TranscriptBuffer,
    TranscriptSegment,
    BufferedTranscript,
    SessionTranscriptManager
)
from src.python.role_play.common.time_utils import utc_now_isoformat


class TestTranscriptBuffer:
    """Test cases for TranscriptBuffer class."""

    @pytest.fixture
    def transcript_buffer(self):
        """Create a test transcript buffer."""
        return TranscriptBuffer(
            stability_threshold=0.8,
            finalization_timeout_ms=1000,  # Short timeout for tests
            min_utterance_length=2
        )

    @pytest.fixture
    def sample_segment(self):
        """Create a sample transcript segment."""
        return TranscriptSegment(
            text="Hello world",
            stability=0.9,
            is_final=False,
            timestamp=utc_now_isoformat(),
            confidence=0.95,
            role="user"
        )

    def test_buffer_initialization(self, transcript_buffer):
        """Test buffer initializes with correct settings."""
        assert transcript_buffer.stability_threshold == 0.8
        assert transcript_buffer.finalization_timeout_ms == 1000
        assert transcript_buffer.min_utterance_length == 2
        assert len(transcript_buffer.partial_segments) == 0
        assert len(transcript_buffer.final_segments) == 0

    async def test_add_partial_segment(self, transcript_buffer, sample_segment):
        """Test adding partial transcript segments."""
        display_text, finalized = await transcript_buffer.add_segment(sample_segment)
        
        assert display_text == "Hello world"
        assert finalized is None
        assert len(transcript_buffer.partial_segments) == 1
        assert transcript_buffer.partial_segments[0].text == "Hello world"

    async def test_add_final_segment(self, transcript_buffer, sample_segment):
        """Test adding final transcript segments."""
        # First add some partials
        partial1 = TranscriptSegment(
            text="Hello",
            stability=0.7,
            is_final=False,
            timestamp=utc_now_isoformat(),
            role="user"
        )
        await transcript_buffer.add_segment(partial1)
        
        # Then add final segment
        final_segment = TranscriptSegment(
            text="Hello world test",
            stability=1.0,
            is_final=True,
            timestamp=utc_now_isoformat(),
            confidence=0.95,
            role="user"
        )
        
        display_text, finalized = await transcript_buffer.add_segment(final_segment)
        
        assert display_text == "Hello world test"
        assert finalized is not None
        assert isinstance(finalized, BufferedTranscript)
        assert finalized.text == "Hello world test"
        assert finalized.role == "user"
        assert finalized.confidence == 0.95
        assert len(transcript_buffer.partial_segments) == 0  # Cleared after finalization

    async def test_stability_threshold_filtering(self, transcript_buffer):
        """Test that low stability segments are filtered."""
        # Low stability segment should replace previous partials
        low_stability = TranscriptSegment(
            text="Uncertain text",
            stability=0.3,  # Below threshold
            is_final=False,
            timestamp=utc_now_isoformat(),
            role="user"
        )
        
        high_stability = TranscriptSegment(
            text="Clear text",
            stability=0.9,  # Above threshold
            is_final=False,
            timestamp=utc_now_isoformat(),
            role="user"
        )
        
        # Add high stability first
        await transcript_buffer.add_segment(high_stability)
        assert len(transcript_buffer.partial_segments) == 1
        
        # Add low stability - should replace
        await transcript_buffer.add_segment(low_stability)
        assert len(transcript_buffer.partial_segments) == 1
        assert transcript_buffer.partial_segments[0].text == "Uncertain text"

    async def test_min_utterance_length_filtering(self, transcript_buffer):
        """Test that short utterances are filtered out."""
        short_final = TranscriptSegment(
            text="Hi",  # Only 1 word, below min_utterance_length=2
            stability=1.0,
            is_final=True,
            timestamp=utc_now_isoformat(),
            confidence=0.95,
            role="user"
        )
        
        display_text, finalized = await transcript_buffer.add_segment(short_final)
        
        assert display_text == "Hi"
        assert finalized is None  # Should be filtered out

    async def test_sentence_boundary_detection(self, transcript_buffer):
        """Test sentence boundary detection."""
        boundaries = transcript_buffer._detect_sentence_boundaries("Hello world. How are you?")
        assert len(boundaries) == 2
        assert boundaries[0] == 11  # Position of the period
        assert boundaries[1] == 24  # Position of the question mark

    async def test_timeout_finalization(self, transcript_buffer):
        """Test timeout-based finalization."""
        # Add a partial segment
        partial = TranscriptSegment(
            text="Hello world test",
            stability=0.9,
            is_final=False,
            timestamp=utc_now_isoformat(),
            role="user"
        )
        
        await transcript_buffer.add_segment(partial)
        
        # Wait for timeout
        await asyncio.sleep(1.1)  # Slightly longer than timeout
        
        # Check that segment was moved to final
        assert len(transcript_buffer.partial_segments) == 0
        assert len(transcript_buffer.final_segments) == 1

    async def test_flush_all_segments(self, transcript_buffer):
        """Test flushing all pending segments."""
        # Add some partial segments
        partials = [
            TranscriptSegment(
                text=f"Test segment {i}",
                stability=0.9,
                is_final=False,
                timestamp=utc_now_isoformat(),
                role="user"
            )
            for i in range(3)
        ]
        
        for partial in partials:
            await transcript_buffer.add_segment(partial)
        
        # Flush all
        flushed = await transcript_buffer.flush()
        
        assert len(flushed) == 3
        assert all(isinstance(t, BufferedTranscript) for t in flushed)
        assert len(transcript_buffer.partial_segments) == 0

    def test_get_display_text(self, transcript_buffer):
        """Test display text generation."""
        # Add some segments manually to test display
        transcript_buffer.final_segments.append(
            TranscriptSegment(
                text="Final text",
                stability=1.0,
                is_final=True,
                timestamp=utc_now_isoformat(),
                role="user",
                sequence=1
            )
        )
        
        transcript_buffer.partial_segments.append(
            TranscriptSegment(
                text="partial text",
                stability=0.8,
                is_final=False,
                timestamp=utc_now_isoformat(),
                role="user",
                sequence=2
            )
        )
        
        display_text = transcript_buffer._get_display_text()
        assert display_text == "Final text partial text"

    def test_clear_buffer(self, transcript_buffer):
        """Test clearing all buffers."""
        # Add some segments
        transcript_buffer.partial_segments.append(Mock())
        transcript_buffer.final_segments.append(Mock())
        
        transcript_buffer.clear()
        
        assert len(transcript_buffer.partial_segments) == 0
        assert len(transcript_buffer.final_segments) == 0


class TestSessionTranscriptManager:
    """Test cases for SessionTranscriptManager class."""

    @pytest.fixture
    def session_manager(self):
        """Create a test session transcript manager."""
        return SessionTranscriptManager(
            stability_threshold=0.8,
            finalization_timeout_ms=1000,
            min_utterance_length=2
        )

    async def test_add_user_segment(self, session_manager):
        """Test adding user speech segments."""
        segment = TranscriptSegment(
            text="User speaking",
            stability=1.0,
            is_final=True,
            timestamp=utc_now_isoformat(),
            confidence=0.9
        )
        
        display_text, finalized = await session_manager.add_user_segment(segment)
        
        assert segment.role == "user"
        assert display_text == "User speaking"
        assert finalized is not None
        assert finalized.role == "user"

    async def test_add_assistant_segment(self, session_manager):
        """Test adding assistant speech segments."""
        segment = TranscriptSegment(
            text="Assistant responding",
            stability=1.0,
            is_final=True,
            timestamp=utc_now_isoformat(),
            confidence=0.9
        )
        
        display_text, finalized = await session_manager.add_assistant_segment(segment)
        
        assert segment.role == "assistant"
        assert display_text == "Assistant responding"
        assert finalized is not None
        assert finalized.role == "assistant"

    async def test_session_statistics(self, session_manager):
        """Test session statistics tracking."""
        # Add some segments
        user_segment = TranscriptSegment(
            text="User message one",
            stability=1.0,
            is_final=True,
            timestamp=utc_now_isoformat(),
            confidence=0.9
        )
        
        assistant_segment = TranscriptSegment(
            text="Assistant response one",
            stability=1.0,
            is_final=True,
            timestamp=utc_now_isoformat(),
            confidence=0.95
        )
        
        await session_manager.add_user_segment(user_segment)
        await session_manager.add_assistant_segment(assistant_segment)
        
        stats = session_manager.get_session_stats()
        
        assert stats["total_utterances"] == 2
        assert stats["total_partials"] == 0
        assert "started_at" in stats
        assert "pending_user_segments" in stats
        assert "pending_assistant_segments" in stats

    async def test_flush_all_transcripts(self, session_manager):
        """Test flushing transcripts from both user and assistant buffers."""
        # Add partial segments to both buffers
        user_partial = TranscriptSegment(
            text="User partial",
            stability=0.9,
            is_final=False,
            timestamp=utc_now_isoformat()
        )
        
        assistant_partial = TranscriptSegment(
            text="Assistant partial",
            stability=0.9,
            is_final=False,
            timestamp=utc_now_isoformat()
        )
        
        await session_manager.add_user_segment(user_partial)
        await session_manager.add_assistant_segment(assistant_partial)
        
        # Flush all
        flushed = await session_manager.flush_all()
        
        assert len(flushed) == 2
        user_transcripts = [t for t in flushed if t.role == "user"]
        assistant_transcripts = [t for t in flushed if t.role == "assistant"]
        
        assert len(user_transcripts) == 1
        assert len(assistant_transcripts) == 1


class TestTranscriptSegment:
    """Test cases for TranscriptSegment data class."""

    def test_segment_creation(self):
        """Test creating transcript segments."""
        segment = TranscriptSegment(
            text="Test text",
            stability=0.9,
            is_final=True,
            timestamp=utc_now_isoformat(),
            confidence=0.95,
            role="user",
            sequence=1
        )
        
        assert segment.text == "Test text"
        assert segment.stability == 0.9
        assert segment.is_final is True
        assert segment.confidence == 0.95
        assert segment.role == "user"
        assert segment.sequence == 1


class TestBufferedTranscript:
    """Test cases for BufferedTranscript data class."""

    def test_transcript_creation(self):
        """Test creating buffered transcripts."""
        transcript = BufferedTranscript(
            text="Final transcript",
            role="assistant",
            timestamp=utc_now_isoformat(),
            duration_ms=2500,
            confidence=0.92,
            partial_count=5,
            voice_metadata={"test": "data"}
        )
        
        assert transcript.text == "Final transcript"
        assert transcript.role == "assistant"
        assert transcript.duration_ms == 2500
        assert transcript.confidence == 0.92
        assert transcript.partial_count == 5
        assert transcript.voice_metadata["test"] == "data"


if __name__ == "__main__":
    pytest.main([__file__])