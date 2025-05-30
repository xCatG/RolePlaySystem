"""Service for logging chat sessions using storage backend abstraction."""
import json
import uuid
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import logging

from ..common.time_utils import utc_now_isoformat
from ..common.storage import StorageBackend

logger = logging.getLogger(__name__)

class ChatLogger:
    """
    Manages the creation, writing, and reading of chat session logs
    using the storage backend abstraction. Works with file, GCS, and S3 storage.
    """

    def __init__(self, storage_backend: StorageBackend):
        """
        Initialize ChatLogger with a storage backend.

        Args:
            storage_backend: Storage backend instance (FileStorage, GCSStorage, or S3Storage)
        """
        self.storage = storage_backend
        logger.info(f"ChatLogger initialized with {type(storage_backend).__name__} backend")

    def _get_log_key(self, user_id: str, app_session_id: str) -> str:
        """Constructs the log key for a session."""
        return f"chat_sessions/{user_id}_{app_session_id}"

    async def start_session(
        self,
        user_id: str,
        participant_name: str,
        scenario_id: str,
        scenario_name: str,
        character_id: str,
        character_name: str,
        goal: Optional[str] = None,
        initial_settings: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Starts a new chat session log.

        Generates a unique session ID and writes the initial 'session_start' event
        using the storage backend.

        Returns:
            The app_session_id.
        """
        app_session_id = str(uuid.uuid4())
        log_key = self._get_log_key(user_id, app_session_id)

        session_start_event = {
            "type": "session_start",
            "timestamp": utc_now_isoformat(),
            "app_session_id": app_session_id,
            "user_id": user_id,
            "participant_name": participant_name,
            "scenario_id": scenario_id,
            "scenario_name": scenario_name,
            "character_id": character_id,
            "character_name": character_name,
            "goal": goal,
            "initial_settings": initial_settings or {},
            "version": "1.0"
        }

        try:
            await self.storage.append_to_log(log_key, session_start_event)
            logger.info(f"Started session log for {app_session_id} using {type(self.storage).__name__}")
        except Exception as e:
            logger.error(f"Error starting session log for {app_session_id}: {e}")
            raise

        return app_session_id

    async def log_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        message_number: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Logs a message to the session using the storage backend.

        Args:
            session_id: The application session ID.
            user_id: The user ID (needed to construct log key).
            role: The role of the message sender (e.g., "participant", "character").
            content: The message content.
            message_number: The sequential number of the message in the session.
            metadata: Optional additional data for the message.
        """
        log_key = self._get_log_key(user_id, session_id)
        
        message_event = {
            "type": "message",
            "timestamp": utc_now_isoformat(),
            "app_session_id": session_id,
            "role": role,
            "content": content,
            "message_number": message_number,
            "metadata": metadata or {}
        }
        
        try:
            await self.storage.append_to_log(log_key, message_event)
            logger.debug(f"Logged message to session {session_id} (Msg#: {message_number}, Role: {role})")
        except Exception as e:
            logger.error(f"Error logging message to session {session_id}: {e}")
            raise

    async def end_session(
        self,
        session_id: str,
        user_id: str,
        total_messages: int,
        duration_seconds: float,
        reason: Optional[str] = None,
        final_state: Optional[Dict[str, Any]] = None
    ) -> None:
        """Logs the end of a session using the storage backend."""
        log_key = self._get_log_key(user_id, session_id)
        
        session_end_event = {
            "type": "session_end",
            "timestamp": utc_now_isoformat(),
            "app_session_id": session_id,
            "total_messages": total_messages,
            "duration_seconds": round(duration_seconds, 2),
            "reason": reason,
            "final_state": final_state or {}
        }
        
        try:
            await self.storage.append_to_log(log_key, session_end_event)
            logger.info(f"Ended session log for {session_id}")
        except Exception as e:
            logger.error(f"Error ending session log for {session_id}: {e}")
            raise

    async def list_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Lists all sessions for a given user.
        
        Note: This is a simplified implementation that doesn't scan all logs.
        For production with cloud storage, consider storing session metadata
        separately for efficient listing.
        """
        logger.warning(
            "list_user_sessions is not fully implemented for cloud storage backends. "
            "Consider storing session metadata separately for efficient listing."
        )
        return []

    async def export_session_text(self, app_session_id: str, user_id: str) -> str:
        """Exports a session as a human-readable text transcript using storage backend."""
        log_key = self._get_log_key(user_id, app_session_id)
        
        try:
            if not await self.storage.log_exists(log_key):
                logger.warning(f"Attempted to export non-existent session: {app_session_id}")
                return "Session log file not found."

            entries = await self.storage.read_log(log_key)
            
            session_info = {}
            messages = []
            session_ended_info = {}

            for entry in entries:
                entry_type = entry.get("type")
                if entry_type == "session_start":
                    session_info = entry
                elif entry_type == "message":
                    messages.append(entry)
                elif entry_type == "session_end":
                    session_ended_info = entry

        except Exception as e:
            logger.error(f"Error reading session {app_session_id} for export: {e}")
            return f"Error processing session file: {str(e)}"

        # Format the transcript
        lines = []
        lines.append("=" * 70)
        lines.append("ROLEPLAY SESSION TRANSCRIPT")
        lines.append("=" * 70)
        lines.append(f"  Session ID: {session_info.get('app_session_id', 'Unknown')}")
        lines.append(f"  User ID: {session_info.get('user_id', 'Unknown')}")
        lines.append(f"  Participant: {session_info.get('participant_name', 'Unknown')}")
        lines.append(f"  Scenario: {session_info.get('scenario_name', 'Unknown')}")
        lines.append(f"  Character: {session_info.get('character_name', 'Unknown')}")
        if session_info.get('goal'):
            lines.append(f"  Goal: {session_info.get('goal')}")
        lines.append(f"  Started: {session_info.get('timestamp', 'Unknown')}")
        lines.append("")

        lines.append("-" * 70)
        lines.append("CONVERSATION:")
        lines.append("-" * 70)
        lines.append("")

        for msg in messages:
            speaker_map = {
                "participant": session_info.get('participant_name', 'Participant'),
                "character": session_info.get('character_name', 'Character').split(' - ')[0] if session_info.get('character_name') else 'Character',
                "system": "System"
            }
            speaker = speaker_map.get(msg.get("role", "unknown").lower(), msg.get("role", "Unknown"))
            lines.append(f"[{msg.get('message_number', 'N/A')}] {speaker} ({msg.get('timestamp')}):")
            lines.append(f"  {msg.get('content', '')}")
            lines.append("")

        if not messages:
            lines.append("[No messages in session]")
            lines.append("")

        lines.append("=" * 70)
        if session_ended_info:
            lines.append("SESSION ENDED")
            lines.append(f"  Ended At: {session_ended_info.get('timestamp')}")
            lines.append(f"  Total Messages: {session_ended_info.get('total_messages')}")
            lines.append(f"  Duration: {session_ended_info.get('duration_seconds')} seconds")
            if session_ended_info.get('reason'):
                lines.append(f"  Reason: {session_ended_info.get('reason')}")
        else:
            lines.append("SESSION ACTIVE OR NOT PROPERLY ENDED")
        lines.append("=" * 70)

        return "\n".join(lines)