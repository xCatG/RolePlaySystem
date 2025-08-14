"""Intelligent transcript management for voice chat sessions."""

import asyncio
import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from ..common.time_utils import utc_now_isoformat, utc_now

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """Represents a segment of transcribed speech."""
    text: str
    stability: float
    is_final: bool
    timestamp: str
    confidence: Optional[float] = None
    role: str = "user"  # "user" or "assistant"
    sequence: int = 0


@dataclass
class BufferedTranscript:
    """A transcript ready for logging with metadata."""
    text: str
    role: str
    timestamp: str
    duration_ms: int
    confidence: float
    partial_count: int
    voice_metadata: Dict[str, Any] = field(default_factory=dict)


class TranscriptBuffer:
    """
    Manages transcript buffering with intelligent partial/final handling.
    
    Handles the conversion from fragmented real-time speech recognition
    into coherent, loggable text segments.
    """
    
    def __init__(
        self, 
        stability_threshold: float = 0.8,
        finalization_timeout_ms: int = 2000,
        min_utterance_length: int = 3,
        sentence_boundary_patterns: Optional[List[str]] = None
    ):
        self.stability_threshold = stability_threshold
        self.finalization_timeout_ms = finalization_timeout_ms
        self.min_utterance_length = min_utterance_length
        
        # Default sentence boundary patterns
        self.sentence_patterns = sentence_boundary_patterns or [
            r'[.!?]+\s*$',  # Sentence endings
            r'\n+',         # Line breaks
        ]
        self._compiled_patterns = [re.compile(pattern) for pattern in self.sentence_patterns]
        
        # Buffers
        self.partial_segments: List[TranscriptSegment] = []
        self.final_segments: List[TranscriptSegment] = []
        self.pending_finalization: List[TranscriptSegment] = []
        
        # State tracking
        self.last_activity_time = utc_now()
        self.sequence_counter = 0
        self._finalization_task: Optional[asyncio.Task] = None

    async def add_segment(self, segment: TranscriptSegment) -> Tuple[Optional[str], Optional[BufferedTranscript]]:
        """
        Add a transcript segment and return display text and any finalized transcript.
        
        Args:
            segment: New transcript segment from speech recognition
            
        Returns:
            Tuple of (display_text, finalized_transcript)
            - display_text: Text for immediate UI display (may be partial)
            - finalized_transcript: Complete transcript ready for logging (None if not ready)
        """
        self.last_activity_time = utc_now()
        segment.sequence = self.sequence_counter
        self.sequence_counter += 1
        
        logger.debug(f"Adding segment: '{segment.text}' (final={segment.is_final}, stability={segment.stability})")
        
        finalized_transcript = None
        
        if segment.is_final:
            # Final result - replace all partials and finalize
            finalized_transcript = await self._finalize_segments(segment)
            self.partial_segments.clear()
            self.final_segments.append(segment)
        else:
            # Partial result
            if segment.stability >= self.stability_threshold:
                # High stability - likely to be accurate
                self.partial_segments.append(segment)
            else:
                # Low stability - replace previous partials
                self.partial_segments = [segment]
        
        # Schedule timeout-based finalization
        await self._schedule_finalization()
        
        display_text = self._get_display_text()
        return display_text, finalized_transcript

    async def _finalize_segments(self, final_segment: TranscriptSegment) -> Optional[BufferedTranscript]:
        """Convert accumulated segments into a finalized transcript."""
        if not final_segment.text.strip():
            return None
            
        # Calculate metadata
        partial_count = len(self.partial_segments)
        text = final_segment.text.strip()
        
        # Check minimum utterance length
        word_count = len(text.split())
        if word_count < self.min_utterance_length:
            logger.debug(f"Utterance too short ({word_count} words): '{text}'")
            return None
        
        # Calculate duration (rough estimate from segments)
        start_time = self.partial_segments[0].timestamp if self.partial_segments else final_segment.timestamp
        duration_ms = self._calculate_duration(start_time, final_segment.timestamp)
        
        buffered_transcript = BufferedTranscript(
            text=text,
            role=final_segment.role,
            timestamp=final_segment.timestamp,
            duration_ms=duration_ms,
            confidence=final_segment.confidence or 0.0,
            partial_count=partial_count,
            voice_metadata={
                "stability_threshold": self.stability_threshold,
                "sentence_boundaries": self._detect_sentence_boundaries(text),
                "word_count": word_count
            }
        )
        
        logger.info(f"Finalized transcript: '{text}' ({duration_ms}ms, {partial_count} partials)")
        return buffered_transcript

    async def _schedule_finalization(self):
        """Schedule timeout-based finalization for pending segments."""
        if self._finalization_task:
            self._finalization_task.cancel()
        
        if self.partial_segments:
            self._finalization_task = asyncio.create_task(
                self._timeout_finalization()
            )

    async def _timeout_finalization(self):
        """Finalize segments after timeout if no final result received."""
        try:
            await asyncio.sleep(self.finalization_timeout_ms / 1000.0)
            
            if self.partial_segments:
                logger.debug(f"Timeout finalization of {len(self.partial_segments)} partial segments")
                
                # Create a synthetic final segment from the most stable partial
                best_partial = max(self.partial_segments, key=lambda s: s.stability)
                synthetic_final = TranscriptSegment(
                    text=best_partial.text,
                    stability=best_partial.stability,
                    is_final=True,  # Mark as final for processing
                    timestamp=utc_now_isoformat(),
                    confidence=best_partial.confidence,
                    role=best_partial.role,
                    sequence=best_partial.sequence
                )
                
                finalized = await self._finalize_segments(synthetic_final)
                if finalized:
                    # Would need callback mechanism to handle this
                    logger.info(f"Timeout-finalized transcript: '{finalized.text}'")
                
                self.partial_segments.clear()
                self.final_segments.append(synthetic_final)
                
        except asyncio.CancelledError:
            pass  # Normal cancellation

    def _get_display_text(self) -> str:
        """Get text for immediate display (includes partials)."""
        all_segments = self.final_segments + self.partial_segments
        if not all_segments:
            return ""
        
        # Sort by sequence to maintain order
        sorted_segments = sorted(all_segments, key=lambda s: s.sequence)
        return " ".join(segment.text for segment in sorted_segments if segment.text.strip())

    def _detect_sentence_boundaries(self, text: str) -> List[int]:
        """Detect sentence boundaries in text."""
        boundaries = []
        for pattern in self._compiled_patterns:
            for match in pattern.finditer(text):
                boundaries.append(match.start())
        return sorted(boundaries)

    def _calculate_duration(self, start_timestamp: str, end_timestamp: str) -> int:
        """Calculate duration between timestamps in milliseconds."""
        try:
            start_dt = datetime.fromisoformat(start_timestamp.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_timestamp.replace('Z', '+00:00'))
            delta = end_dt - start_dt
            return int(delta.total_seconds() * 1000)
        except (ValueError, AttributeError):
            return 0

    def get_pending_count(self) -> int:
        """Get count of pending partial segments."""
        return len(self.partial_segments)

    def clear(self):
        """Clear all buffers."""
        self.partial_segments.clear()
        self.final_segments.clear()
        self.pending_finalization.clear()
        if self._finalization_task:
            self._finalization_task.cancel()
            self._finalization_task = None

    async def flush(self) -> List[BufferedTranscript]:
        """Force finalization of all pending segments."""
        finalized_transcripts = []
        
        if self.partial_segments:
            # Force finalize all partials
            for partial in self.partial_segments:
                synthetic_final = TranscriptSegment(
                    text=partial.text,
                    stability=partial.stability,
                    is_final=True,
                    timestamp=utc_now_isoformat(),
                    confidence=partial.confidence,
                    role=partial.role,
                    sequence=partial.sequence
                )
                
                finalized = await self._finalize_segments(synthetic_final)
                if finalized:
                    finalized_transcripts.append(finalized)
        
        self.clear()
        return finalized_transcripts


class SessionTranscriptManager:
    """
    Manages transcript buffers for an entire voice session.
    
    Handles separate buffers for user and assistant speech,
    and coordinates batch logging to ChatLogger.
    """
    
    def __init__(self, **buffer_kwargs):
        self.user_buffer = TranscriptBuffer(**buffer_kwargs)
        self.assistant_buffer = TranscriptBuffer(**buffer_kwargs)
        self.session_metadata = {
            "started_at": utc_now_isoformat(),
            "total_utterances": 0,
            "total_partials": 0,
        }

    async def add_user_segment(self, segment: TranscriptSegment) -> Tuple[Optional[str], Optional[BufferedTranscript]]:
        """Add user speech segment."""
        segment.role = "user"
        display_text, finalized = await self.user_buffer.add_segment(segment)
        
        if finalized:
            self.session_metadata["total_utterances"] += 1
            self.session_metadata["total_partials"] += finalized.partial_count
            
        return display_text, finalized

    async def add_assistant_segment(self, segment: TranscriptSegment) -> Tuple[Optional[str], Optional[BufferedTranscript]]:
        """Add assistant speech segment."""
        segment.role = "assistant"
        display_text, finalized = await self.assistant_buffer.add_segment(segment)
        
        if finalized:
            self.session_metadata["total_utterances"] += 1
            self.session_metadata["total_partials"] += finalized.partial_count
            
        return display_text, finalized

    async def flush_all(self) -> List[BufferedTranscript]:
        """Flush all pending transcripts."""
        user_transcripts = await self.user_buffer.flush()
        assistant_transcripts = await self.assistant_buffer.flush()
        return user_transcripts + assistant_transcripts

    def get_session_stats(self) -> Dict[str, Any]:
        """Get session-level statistics."""
        return {
            **self.session_metadata,
            "pending_user_segments": self.user_buffer.get_pending_count(),
            "pending_assistant_segments": self.assistant_buffer.get_pending_count(),
        }