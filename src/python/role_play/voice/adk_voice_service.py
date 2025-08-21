"""Simplified ADK voice session for real-time bidirectional audio streaming."""

import asyncio
import logging
from typing import AsyncGenerator, Optional, Dict, Any
from google.adk.runners import Runner
from google.adk.agents import LiveRequestQueue
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part, Blob

from ..common.time_utils import utc_now_isoformat

logger = logging.getLogger(__name__)

class LiveVoiceSession:
    """
    Represents an active voice session with ADK live streaming.
    Manages the lifecycle of a voice conversation including audio streaming,
    transcript processing, and cleanup.
    """
    
    def __init__(
        self,
        session_id: str,
        user_id: str,
        runner: Runner,
        live_events: AsyncGenerator,
        live_request_queue: LiveRequestQueue,
        adk_session: Optional[Any] = None
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.runner = runner
        self.live_events = live_events
        self.live_request_queue = live_request_queue
        self.adk_session = adk_session
        self.active = True
        self.stats = {
            "started_at": utc_now_isoformat(),
            "audio_chunks_sent": 0,
            "audio_chunks_received": 0,
            "transcripts_processed": 0,
            "errors": 0,
        }

    async def send_audio(self, audio_data: bytes, mime_type: str = "audio/pcm"):
        """Send audio data to the live session."""
        try:
            blob = Blob(mime_type=mime_type, data=audio_data)
            await self.live_request_queue.send_realtime(blob)
            self.stats["audio_chunks_sent"] += 1
        except Exception as e:
            logger.error(f"Error sending audio in session {self.session_id}: {e}")
            self.stats["errors"] += 1
            raise

    async def send_text(self, text: str):
        """Send text input to the live session."""
        try:
            content = Content(parts=[Part(text=text)])
            await self.live_request_queue.send_content(content)
        except Exception as e:
            logger.error(f"Error sending text in session {self.session_id}: {e}")
            self.stats["errors"] += 1
            raise

    async def process_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Process live events from ADK and yield processed events."""
        try:
            async for event in self.live_events:
                if not self.active:
                    break
                yield self._process_single_event(event)
        except asyncio.CancelledError:
            logger.info(f"Voice session {self.session_id} event processing cancelled.")
        except Exception as e:
            logger.error(f"Error processing events in session {self.session_id}: {e}")
            self.stats["errors"] += 1
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": utc_now_isoformat()
            }

    def _process_single_event(self, event: Any) -> Dict[str, Any]:
        """Process a single ADK live event."""
        self.stats["transcripts_processed"] += 1
        
        if hasattr(event, 'turn_complete') or hasattr(event, 'interrupted'):
            return self._process_turn_status(event)
        if hasattr(event, 'input_transcription') and event.input_transcription:
            return self._process_transcript(event.input_transcription, "user")
        if hasattr(event, 'output_transcription') and event.output_transcription:
            return self._process_transcript(event.output_transcription, "assistant")
        if hasattr(event, 'content') and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    self.stats["audio_chunks_received"] += 1
                    return {
                        "type": "audio_chunk",
                        "data": part.inline_data.data,
                        "mime_type": part.inline_data.mime_type,
                        "timestamp": utc_now_isoformat()
                    }
        
        return {
            "type": "unknown",
            "event_type": type(event).__name__,
            "timestamp": utc_now_isoformat()
        }

    def _process_turn_status(self, event: Any) -> Dict[str, Any]:
        """Process turn status events."""
        return {
            "type": "turn_status",
            "turn_complete": getattr(event, 'turn_complete', False),
            "interrupted": getattr(event, 'interrupted', False),
            "timestamp": utc_now_isoformat()
        }

    def _process_transcript(self, transcription: Any, role: str) -> Dict[str, Any]:
        """Process transcript events for user or assistant."""
        is_final = getattr(transcription, 'is_final', True)
        if is_final:
            return {
                "type": "transcript_final",
                "text": transcription.text,
                "role": role,
                "duration_ms": 0,
                "confidence": getattr(transcription, 'confidence', 1.0),
                "metadata": {},
                "timestamp": utc_now_isoformat()
            }
        else:
            return {
                "type": "transcript_partial",
                "text": transcription.text,
                "role": role,
                "stability": getattr(transcription, 'stability', 1.0),
                "timestamp": utc_now_isoformat()
            }

    async def end_session(self):
        """End the voice session gracefully."""
        if self.active:
            logger.info(f"Ending voice session {self.session_id}")
            self.active = False
            if self.live_request_queue:
                self.live_request_queue.close()

    async def cleanup(self) -> Dict[str, Any]:
        """Cleanup session and return final statistics."""
        await self.end_session()
        final_stats = {**self.stats, "ended_at": utc_now_isoformat()}
        logger.info(f"Voice session {self.session_id} cleanup completed: {final_stats}")
        return final_stats

    def get_stats(self) -> Dict[str, Any]:
        """Get current session statistics."""
        return self.stats