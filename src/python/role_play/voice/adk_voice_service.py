"""ADK-based voice service for real-time bidirectional audio streaming."""

import asyncio
import logging
from typing import AsyncGenerator, Optional, Dict, Any, Tuple, List
from google.adk.runners import Runner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.adk.sessions import InMemorySessionService
from google.genai.types import (
    Content, Part, Blob, 
    AudioTranscriptionConfig,
    AudioChunk
)

from ..dev_agents.roleplay_agent.agent import get_production_agent
from ..chat.chat_logger import ChatLogger
from ..common.time_utils import utc_now_isoformat
from .transcript_manager import (
    SessionTranscriptManager, 
    TranscriptSegment, 
    BufferedTranscript
)

logger = logging.getLogger(__name__)


class ADKVoiceService:
    """
    Manages ADK live streaming sessions for voice chat.
    
    This service creates and manages real-time voice interactions using
    ADK's run_live() method with intelligent transcript buffering.
    """
    
    def __init__(self):
        self.active_sessions: Dict[str, 'VoiceSession'] = {}

    async def create_voice_session(
        self,
        session_id: str,
        user_id: str,
        character_id: str,
        scenario_id: str,
        language: str = "en",
        script_data: Optional[Dict] = None,
        adk_session_service: Optional[InMemorySessionService] = None,
        transcript_config: Optional[Dict] = None
    ) -> 'VoiceSession':
        """
        Create and start an ADK live voice session.
        
        Args:
            session_id: Unique session identifier
            user_id: User ID for session ownership
            character_id: Character to roleplay
            scenario_id: Scenario context
            language: Language for responses (en, zh-TW, ja)
            script_data: Optional script data for guided conversations
            adk_session_service: ADK session service instance
            transcript_config: Configuration for transcript buffering
            
        Returns:
            VoiceSession: Active voice session instance
        """
        logger.info(f"Creating voice session {session_id} for user {user_id}")
        
        # Get production agent with character/scenario context
        agent = await get_production_agent(
            character_id=character_id,
            scenario_id=scenario_id,
            language=language,
            scripted=bool(script_data)
        )
        
        if not agent:
            raise ValueError(f"Could not create agent for character {character_id}, scenario {scenario_id}")

        # Create ADK runner
        runner = Runner(app_name="roleplay_voice", agent=agent)
        
        # Get or create ADK session
        if adk_session_service:
            adk_session = await adk_session_service.get_session(
                app_name="roleplay_voice", 
                user_id=user_id, 
                session_id=session_id
            )
            
            if not adk_session:
                # Create new ADK session
                initial_state = {
                    "character_id": character_id,
                    "scenario_id": scenario_id,
                    "script_data": script_data,
                    "language": language,
                    "voice_session": True,
                    "session_creation_time_iso": utc_now_isoformat()
                }
                
                adk_session = await adk_session_service.create_session(
                    app_name="roleplay_voice",
                    user_id=user_id,
                    session_id=session_id,
                    state=initial_state
                )
        else:
            adk_session = None

        # Configure for audio response and transcription
        run_config = RunConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription=AudioTranscriptionConfig(),
            input_audio_transcription=AudioTranscriptionConfig()
        )

        # Create live request queue for bidirectional streaming
        live_request_queue = LiveRequestQueue()
        
        # Start live streaming
        live_events = runner.run_live(
            session=adk_session,
            live_request_queue=live_request_queue,
            run_config=run_config
        )

        # Create transcript manager
        transcript_manager = SessionTranscriptManager(**(transcript_config or {}))

        # Create voice session wrapper
        voice_session = VoiceSession(
            session_id=session_id,
            user_id=user_id,
            runner=runner,
            live_events=live_events,
            live_request_queue=live_request_queue,
            transcript_manager=transcript_manager,
            adk_session=adk_session
        )
        
        # Store session
        self.active_sessions[session_id] = voice_session
        
        logger.info(f"Voice session {session_id} created successfully")
        return voice_session

    async def get_session(self, session_id: str) -> Optional['VoiceSession']:
        """Get active voice session by ID."""
        return self.active_sessions.get(session_id)

    async def end_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """End voice session and return session statistics."""
        voice_session = self.active_sessions.pop(session_id, None)
        if not voice_session:
            return None
            
        return await voice_session.cleanup()


class VoiceSession:
    """
    Represents an active voice session with ADK live streaming.
    
    Manages the lifecycle of a voice conversation including audio streaming,
    transcript management, and cleanup.
    """
    
    def __init__(
        self,
        session_id: str,
        user_id: str,
        runner: Runner,
        live_events: AsyncGenerator,
        live_request_queue: LiveRequestQueue,
        transcript_manager: SessionTranscriptManager,
        adk_session: Optional[Any] = None
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.runner = runner
        self.live_events = live_events
        self.live_request_queue = live_request_queue
        self.transcript_manager = transcript_manager
        self.adk_session = adk_session
        
        # Session state
        self.active = True
        self.event_handlers: Dict[str, callable] = {}
        
        # Statistics
        self.stats = {
            "started_at": utc_now_isoformat(),
            "audio_chunks_sent": 0,
            "audio_chunks_received": 0,
            "transcripts_processed": 0,
            "errors": 0
        }

    async def send_audio(self, audio_data: bytes, mime_type: str = "audio/pcm") -> None:
        """Send audio data to the live session."""
        try:
            blob = Blob(mime_type=mime_type, data=audio_data)
            await self.live_request_queue.send_realtime(blob)
            self.stats["audio_chunks_sent"] += 1
            
        except Exception as e:
            logger.error(f"Error sending audio in session {self.session_id}: {e}")
            self.stats["errors"] += 1
            raise

    async def send_text(self, text: str) -> None:
        """Send text input to the live session."""
        try:
            content = Content(parts=[Part(text=text)])
            await self.live_request_queue.send_content(content)
            
            # Create transcript segment for immediate display
            segment = TranscriptSegment(
                text=text,
                stability=1.0,
                is_final=True,
                timestamp=utc_now_isoformat(),
                confidence=1.0,
                role="user"
            )
            
            await self.transcript_manager.add_user_segment(segment)
            
        except Exception as e:
            logger.error(f"Error sending text in session {self.session_id}: {e}")
            self.stats["errors"] += 1
            raise

    async def process_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process live events from ADK and yield processed events.
        
        Yields events like:
        - audio_chunk: Audio data from assistant
        - transcript_partial: Partial transcript for display
        - transcript_final: Final transcript for logging
        - turn_status: Turn completion/interruption status
        """
        try:
            async for event in self.live_events:
                if not self.active:
                    break
                    
                yield await self._process_single_event(event)
                
        except asyncio.CancelledError:
            logger.info(f"Voice session {self.session_id} event processing cancelled")
        except Exception as e:
            logger.error(f"Error processing events in session {self.session_id}: {e}")
            self.stats["errors"] += 1
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": utc_now_isoformat()
            }

    async def _process_single_event(self, event) -> Dict[str, Any]:
        """Process a single ADK live event."""
        self.stats["transcripts_processed"] += 1
        
        # Turn status events
        if hasattr(event, 'turn_complete') or hasattr(event, 'interrupted'):
            return {
                "type": "turn_status",
                "turn_complete": getattr(event, 'turn_complete', False),
                "interrupted": getattr(event, 'interrupted', False),
                "timestamp": utc_now_isoformat()
            }

        # Input transcription (user speech)
        if hasattr(event, 'input_transcription') and event.input_transcription:
            transcription = event.input_transcription
            
            segment = TranscriptSegment(
                text=transcription.text,
                stability=getattr(transcription, 'stability', 1.0),
                is_final=getattr(transcription, 'is_final', True),
                timestamp=utc_now_isoformat(),
                confidence=getattr(transcription, 'confidence', None),
                role="user"
            )
            
            display_text, finalized = await self.transcript_manager.add_user_segment(segment)
            
            if finalized:
                return {
                    "type": "transcript_final",
                    "text": finalized.text,
                    "role": "user",
                    "duration_ms": finalized.duration_ms,
                    "confidence": finalized.confidence,
                    "metadata": finalized.voice_metadata,
                    "timestamp": finalized.timestamp
                }
            else:
                return {
                    "type": "transcript_partial",
                    "text": display_text or "",
                    "role": "user",
                    "stability": segment.stability,
                    "timestamp": segment.timestamp
                }

        # Output transcription (assistant speech)
        if hasattr(event, 'output_transcription') and event.output_transcription:
            transcription = event.output_transcription
            
            segment = TranscriptSegment(
                text=transcription.text,
                stability=getattr(transcription, 'stability', 1.0),
                is_final=getattr(transcription, 'is_final', True),
                timestamp=utc_now_isoformat(),
                confidence=getattr(transcription, 'confidence', None),
                role="assistant"
            )
            
            display_text, finalized = await self.transcript_manager.add_assistant_segment(segment)
            
            if finalized:
                return {
                    "type": "transcript_final",
                    "text": finalized.text,
                    "role": "assistant",
                    "duration_ms": finalized.duration_ms,
                    "confidence": finalized.confidence,
                    "metadata": finalized.voice_metadata,
                    "timestamp": finalized.timestamp
                }
            else:
                return {
                    "type": "transcript_partial",
                    "text": display_text or "",
                    "role": "assistant",
                    "stability": segment.stability,
                    "timestamp": segment.timestamp
                }

        # Audio content (assistant response)
        if hasattr(event, 'content') and event.content:
            content = event.content
            if content.parts:
                for part in content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        self.stats["audio_chunks_received"] += 1
                        return {
                            "type": "audio_chunk",
                            "data": part.inline_data.data,
                            "mime_type": part.inline_data.mime_type,
                            "timestamp": utc_now_isoformat()
                        }

        # Default: unknown event
        return {
            "type": "unknown",
            "event_type": type(event).__name__,
            "timestamp": utc_now_isoformat()
        }

    async def end_session(self) -> None:
        """End the voice session gracefully."""
        logger.info(f"Ending voice session {self.session_id}")
        self.active = False
        
        # Close the live request queue
        if self.live_request_queue:
            self.live_request_queue.close()

    async def flush_transcripts(self) -> List[BufferedTranscript]:
        """Flush all pending transcripts."""
        return await self.transcript_manager.flush_all()

    async def cleanup(self) -> Dict[str, Any]:
        """Cleanup session and return final statistics."""
        if self.active:
            await self.end_session()
        
        # Flush any remaining transcripts
        pending_transcripts = await self.flush_transcripts()
        
        # Get session statistics
        session_stats = self.transcript_manager.get_session_stats()
        
        final_stats = {
            **self.stats,
            "ended_at": utc_now_isoformat(),
            "pending_transcripts_flushed": len(pending_transcripts),
            **session_stats
        }
        
        logger.info(f"Voice session {self.session_id} cleanup completed: {final_stats}")
        return final_stats

    def get_stats(self) -> Dict[str, Any]:
        """Get current session statistics."""
        return {
            **self.stats,
            **self.transcript_manager.get_session_stats()
        }