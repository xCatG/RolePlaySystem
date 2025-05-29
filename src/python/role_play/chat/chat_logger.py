"""Service for logging chat sessions to JSONL files with file locking."""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import logging
from filelock import FileLock, Timeout

logger = logging.getLogger(__name__)

class ChatLogger:
    """
    Manages the creation, writing, and reading of chat session logs
    in JSONL format. Implements file-level locking for concurrent access.
    """

    def __init__(self, storage_path_str: str = "./storage/chat_logs"):
        """
        Initialize ChatLogger.

        Args:
            storage_path_str: The base directory to store JSONL log files.
        """
        self.storage_path = Path(storage_path_str).resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"ChatLogger initialized. Log storage path: {self.storage_path}")

    def _get_jsonl_path(self, user_id: str, app_session_id: str) -> Path:
        """Constructs the full path for a session's JSONL file."""
        filename = f"{user_id}_{app_session_id}.jsonl"
        return self.storage_path / filename

    def _get_lock_path(self, jsonl_path: Path) -> Path:
        """Constructs the path for the lock file associated with a JSONL file."""
        return Path(f"{jsonl_path}.lock")

    def start_session(
        self,
        user_id: str,
        participant_name: str,
        scenario_id: str,
        scenario_name: str,
        character_id: str,
        character_name: str,
        goal: Optional[str] = None,
        initial_settings: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Path]:
        """
        Starts a new chat session log.

        Generates a unique session ID, creates the JSONL file, and writes
        the initial 'session_start' event.

        Returns:
            A tuple containing the (app_session_id, jsonl_file_path).
        """
        app_session_id = str(uuid.uuid4())
        jsonl_file_path = self._get_jsonl_path(user_id, app_session_id)
        lock_path = self._get_lock_path(jsonl_file_path)

        session_start_event = {
            "type": "session_start",
            "timestamp": datetime.utcnow().isoformat(),
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
            with FileLock(lock_path, timeout=5):
                with open(jsonl_file_path, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(session_start_event) + '\n')
            logger.info(f"Started session log for {app_session_id} at {jsonl_file_path}")
        except Timeout:
            logger.error(f"Timeout acquiring lock for {jsonl_file_path} during session start.")
            raise
        except Exception as e:
            logger.error(f"Error starting session log for {app_session_id} at {jsonl_file_path}: {e}")
            raise

        return app_session_id, jsonl_file_path

    def log_message(
        self,
        jsonl_path: Path,
        session_id: str,
        role: str,
        content: str,
        message_number: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Logs a message to the specified JSONL file.

        Args:
            jsonl_path: The Path object for the JSONL file.
            session_id: The application session ID.
            role: The role of the message sender (e.g., "participant", "character").
            content: The message content.
            message_number: The sequential number of the message in the session.
            metadata: Optional additional data for the message.
        """
        if not jsonl_path.exists():
            logger.error(f"Log file {jsonl_path} does not exist. Cannot log message.")
            raise FileNotFoundError(f"Session log file {jsonl_path} not found")

        lock_path = self._get_lock_path(jsonl_path)
        message_event = {
            "type": "message",
            "timestamp": datetime.utcnow().isoformat(),
            "app_session_id": session_id,
            "role": role,
            "content": content,
            "message_number": message_number,
            "metadata": metadata or {}
        }
        
        try:
            with FileLock(lock_path, timeout=5):
                with open(jsonl_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(message_event) + '\n')
            logger.debug(f"Logged message to {jsonl_path} (Msg#: {message_number}, Role: {role})")
        except Timeout:
            logger.error(f"Timeout acquiring lock for {jsonl_path} when logging message.")
            raise
        except Exception as e:
            logger.error(f"Error logging message to {jsonl_path}: {e}")
            raise

    def end_session(
        self,
        jsonl_path: Path,
        session_id: str,
        total_messages: int,
        duration_seconds: float,
        reason: Optional[str] = None,
        final_state: Optional[Dict[str, Any]] = None
    ) -> None:
        """Logs the end of a session."""
        lock_path = self._get_lock_path(jsonl_path)
        session_end_event = {
            "type": "session_end",
            "timestamp": datetime.utcnow().isoformat(),
            "app_session_id": session_id,
            "total_messages": total_messages,
            "duration_seconds": round(duration_seconds, 2),
            "reason": reason,
            "final_state": final_state or {}
        }
        
        try:
            with FileLock(lock_path, timeout=5):
                with open(jsonl_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(session_end_event) + '\n')
            logger.info(f"Ended session log for {session_id} at {jsonl_path}")
        except Timeout:
            logger.error(f"Timeout acquiring lock for {jsonl_path} during session end.")
            raise
        except Exception as e:
            logger.error(f"Error ending session log for {session_id} at {jsonl_path}: {e}")
            raise

    def list_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Lists all sessions for a given user by parsing their JSONL files.
        """
        sessions_summary = []
        for jsonl_file in self.storage_path.glob(f"{user_id}_*.jsonl"):
            lock_path = self._get_lock_path(jsonl_file)
            try:
                with FileLock(lock_path, timeout=1):
                    with open(jsonl_file, 'r', encoding='utf-8') as f:
                        first_line = f.readline()
                        if first_line:
                            start_event = json.loads(first_line)
                            if start_event.get("type") == "session_start":
                                message_count = 0
                                for line in f:
                                    try:
                                        entry = json.loads(line)
                                        if entry.get("type") == "message":
                                            message_count += 1
                                    except json.JSONDecodeError:
                                        continue

                                sessions_summary.append({
                                    "session_id": start_event.get("app_session_id"),
                                    "user_id": start_event.get("user_id"),
                                    "participant_name": start_event.get("participant_name"),
                                    "scenario_name": start_event.get("scenario_name"),
                                    "character_name": start_event.get("character_name"),
                                    "created_at": start_event.get("timestamp"),
                                    "jsonl_filename": jsonl_file.name,
                                    "message_count": message_count
                                })
            except Timeout:
                logger.warning(f"Timeout acquiring lock for reading {jsonl_file}, skipping.")
            except Exception as e:
                logger.error(f"Error reading session summary from {jsonl_file}: {e}")
        
        sessions_summary.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return sessions_summary

    def export_session_text(self, app_session_id: str, user_id: str) -> str:
        """Exports a session as a human-readable text transcript."""
        jsonl_file_path = self._get_jsonl_path(user_id, app_session_id)
        if not jsonl_file_path.exists():
            logger.warning(f"Attempted to export non-existent session: {jsonl_file_path}")
            return "Session log file not found."

        lines = []
        session_info = {}
        messages = []
        session_ended_info = {}
        lock_path = self._get_lock_path(jsonl_file_path)

        try:
            with FileLock(lock_path, timeout=1):
                with open(jsonl_file_path, 'r', encoding='utf-8') as f:
                    for line_num, log_line in enumerate(f):
                        try:
                            entry = json.loads(log_line.strip())
                            entry_type = entry.get("type")

                            if entry_type == "session_start":
                                session_info = entry
                            elif entry_type == "message":
                                messages.append(entry)
                            elif entry_type == "session_end":
                                session_ended_info = entry
                        except json.JSONDecodeError:
                            logger.warning(f"Skipping malformed JSON line {line_num+1} in {jsonl_file_path}")
                            continue
        except Timeout:
            logger.error(f"Timeout acquiring lock for exporting {jsonl_file_path}")
            return "Error: Could not acquire lock to read session file."
        except Exception as e:
            logger.error(f"Error reading session file {jsonl_file_path} for export: {e}")
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
                "character": session_info.get('character_name', 'Character').split(' - ')[0],
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