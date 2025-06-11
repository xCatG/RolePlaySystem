"""Service for logging chat sessions to JSONL files using storage backend."""
import json
import uuid
from typing import Dict, List, Tuple, Any, Optional
import logging
from pathlib import Path

from ..common.storage import StorageBackend, StorageError
from ..common.time_utils import utc_now_isoformat

logger = logging.getLogger(__name__)


class ChatLogger:
    """
    Manages the creation, writing, and reading of chat session logs
    in JSONL format. Uses the storage backend for all file operations
    with built-in locking support.
    """

    def __init__(self, storage_backend: StorageBackend):
        """
        Initialize ChatLogger with a storage backend.

        Args:
            storage_backend: The storage backend to use for all operations.
        """
        self.storage = storage_backend
        logger.info(f"ChatLogger initialized with {type(storage_backend).__name__}")

    def _get_chat_log_path(self, user_id: str, session_id: str) -> str:
        """Constructs the storage path for a session's chat log."""
        return f"users/{user_id}/chat_logs/{session_id}"

    async def _parse_jsonl_file(self, storage_path: str) -> List[Dict[str, Any]]:
        """
        Parse JSONL file and return list of events, handling malformed lines gracefully.
        
        Args:
            storage_path: Path to the JSONL file in storage
            
        Returns:
            List of parsed JSON events
            
        Raises:
            StorageError: If file cannot be read
        """
        try:
            async with self.storage.lock(storage_path, timeout=10.0):
                log_content = await self.storage.read(storage_path)
                lines = log_content.strip().split('\n')
                
                events = []
                for line_num, line in enumerate(lines):
                    try:
                        if line.strip():  # Skip empty lines
                            events.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        logger.warning(f"Skipping malformed JSON line {line_num+1} in {storage_path}")
                        continue
                return events
        except StorageError:
            raise
        except Exception as e:
            logger.error(f"Error parsing JSONL file {storage_path}: {e}")
            raise StorageError(f"Failed to parse session log: {e}")

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
    ) -> Tuple[str, str]:
        """
        Starts a new chat session log.

        Generates a unique session ID, creates the JSONL file, and writes
        the initial 'session_start' event.

        Returns:
            A tuple containing the (app_session_id, storage_path).
        """
        app_session_id = str(uuid.uuid4())
        storage_path = self._get_chat_log_path(user_id, app_session_id)

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
            # Use storage backend's locking
            async with self.storage.lock(storage_path):
                # Write the initial event as JSONL (one JSON object per line)
                event_line = json.dumps(session_start_event) + '\n'
                await self.storage.write(storage_path, event_line)
            
            logger.info(f"Started session log for {app_session_id} at {storage_path}")
        except Exception as e:
            logger.error(f"Error starting session log for {app_session_id}: {e}")
            raise

        return app_session_id, storage_path

    async def log_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        message_number: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Logs a message to the specified session.

        Args:
            user_id: The user ID who owns the session.
            session_id: The application session ID.
            role: The role of the message sender (e.g., "participant", "character").
            content: The message content.
            message_number: The sequential number of the message in the session.
            metadata: Optional additional data for the message.
        """
        storage_path = self._get_chat_log_path(user_id, session_id)
        
        if not await self.storage.exists(storage_path):
            logger.error(f"Log file {storage_path} does not exist. Cannot log message.")
            raise StorageError(f"Session log file not found: {storage_path}")

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
            async with self.storage.lock(storage_path):
                # Append the message event as a new line
                event_line = json.dumps(message_event) + '\n'
                await self.storage.append(storage_path, event_line)
            
            logger.debug(f"Logged message to {storage_path} (Msg#: {message_number}, Role: {role})")
        except Exception as e:
            logger.error(f"Error logging message to {storage_path}: {e}")
            raise

    async def end_session(
        self,
        user_id: str,
        session_id: str,
        total_messages: int,
        duration_seconds: float,
        reason: Optional[str] = None,
        final_state: Optional[Dict[str, Any]] = None
    ) -> None:
        """Logs the end of a session."""
        storage_path = self._get_chat_log_path(user_id, session_id)
        
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
            async with self.storage.lock(storage_path):
                # Append the session end event
                event_line = json.dumps(session_end_event) + '\n'
                await self.storage.append(storage_path, event_line)
            
            logger.info(f"Ended session log for {session_id}")
        except Exception as e:
            logger.error(f"Error ending session log for {session_id}: {e}")
            raise

    async def list_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Lists all sessions for a given user by parsing their JSONL files.
        """
        sessions_summary = []
        
        # List all chat logs for the user
        chat_logs_prefix = f"users/{user_id}/chat_logs/"
        log_keys = await self.storage.list_keys(chat_logs_prefix)
        
        for log_key in log_keys:
            try:
                events = await self._parse_jsonl_file(log_key)
                
                if events:
                    # First event should be session start
                    start_event = events[0]
                    if start_event.get("type") == "session_start":
                        # Count messages using parsed events
                        message_count = sum(1 for event in events if event.get("type") == "message")

                        sessions_summary.append({
                            "session_id": start_event.get("app_session_id"),
                            "user_id": start_event.get("user_id"),
                            "participant_name": start_event.get("participant_name"),
                            "scenario_name": start_event.get("scenario_name"),
                            "character_name": start_event.get("character_name"),
                            "created_at": start_event.get("timestamp"),
                            "storage_path": log_key,
                            "message_count": message_count
                        })
            except Exception as e:
                logger.error(f"Error reading session summary from {log_key}: {e}")
        
        # Sort by creation time (newest first)
        sessions_summary.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return sessions_summary

    async def get_session_end_info(self, user_id: str, session_id: str) -> Dict[str, Any]:
        """
        Gets the end information for a session if it exists.
        
        Returns:
            Dict with 'ended_at' and 'reason' if session was ended, empty dict otherwise.
        """
        storage_path = self._get_chat_log_path(user_id, session_id)
        
        try:
            events = await self._parse_jsonl_file(storage_path)
            
            # Look for session_end event (usually last event)
            for event in reversed(events):
                if event.get("type") == "session_end":
                    return {
                        "ended_at": event.get("timestamp"),
                        "reason": event.get("reason", "Session ended"),
                        "total_messages": event.get("total_messages", 0),
                        "duration_seconds": event.get("duration_seconds", 0)
                    }
            
            # No session_end event found
            return {}
        except StorageError as e:
            logger.warning(f"Session log not found for {session_id}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error getting session end info for {session_id}: {e}")
            return {}

    async def get_session_messages(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        """
        Gets all messages from a session's JSONL log.
        
        Returns:
            List of message dictionaries with role, content, timestamp, and message_number.
        """
        storage_path = self._get_chat_log_path(user_id, session_id)
        messages = []
        
        try:
            events = await self._parse_jsonl_file(storage_path)
            
            # Filter and transform message events
            for event in events:
                if event.get("type") == "message":
                    messages.append({
                        "role": event.get("role"),
                        "content": event.get("content"),
                        "timestamp": event.get("timestamp"),
                        "message_number": event.get("message_number", 0)
                    })
            
            return messages
        except StorageError as e:
            logger.warning(f"Session log not found for {session_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting session messages for {session_id}: {e}")
            raise

    async def delete_session(self, user_id: str, session_id: str) -> None:
        """
        Deletes a session's JSONL log file completely.
        
        Args:
            user_id: The user ID who owns the session
            session_id: The session ID to delete
        """
        storage_path = self._get_chat_log_path(user_id, session_id)
        
        try:
            async with self.storage.lock(storage_path, timeout=10.0):
                await self.storage.delete(storage_path)
            
            logger.info(f"Deleted session log for {session_id}")
        except StorageError as e:
            logger.warning(f"Session log not found for deletion {session_id}: {e}")
            # Don't raise error if file doesn't exist - it's already "deleted"
        except Exception as e:
            logger.error(f"Error deleting session log for {session_id}: {e}")
            raise

    async def export_session_text(self, user_id: str, session_id: str) -> str:
        """Exports a session as a human-readable text transcript."""
        storage_path = self._get_chat_log_path(user_id, session_id)
        
        if not await self.storage.exists(storage_path):
            logger.warning(f"Attempted to export non-existent session: {storage_path}")
            return "Session log file not found."

        lines = []
        session_info = {}
        messages = []
        session_ended_info = {}

        try:
            events = await self._parse_jsonl_file(storage_path)
            
            # Categorize events
            for event in events:
                entry_type = event.get("type")
                if entry_type == "session_start":
                    session_info = event
                elif entry_type == "message":
                    messages.append(event)
                elif entry_type == "session_end":
                    session_ended_info = event
        except Exception as e:
            logger.error(f"Error reading session file {storage_path} for export: {e}")
            return f"Error processing session file: {str(e)}"

        # Format the transcript
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
                "character": session_info.get('character_name', 'Character'),
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