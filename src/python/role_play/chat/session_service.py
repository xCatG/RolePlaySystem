"""Custom session service for roleplay with JSONL logging."""
import json
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class SessionService:
    """Service for managing roleplay sessions with JSONL logging.
    
    This service extends the concept of ADK's SessionService but is
    tailored for roleplay-specific needs with JSONL format for easy evaluation.
    """
    
    def __init__(self, storage_path: str = "./storage/sessions"):
        """Initialize session service.
        
        Args:
            storage_path: Path to store session JSONL files
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._active_sessions: Dict[str, Dict] = {}
    
    def create_session(
        self,
        user_id: str,
        participant_name: str,
        scenario_id: str,
        scenario_name: str,
        character_id: str,
        character_name: str
    ) -> Dict[str, Any]:
        """Create a new roleplay session.
        
        Args:
            user_id: ID of the user (operator) creating the session
            participant_name: Name of the participant being evaluated
            scenario_id: ID of the scenario
            scenario_name: Name of the scenario
            character_id: ID of the character
            character_name: Name of the character
            
        Returns:
            Session information including session_id and jsonl_filename
        """
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Create JSONL filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        jsonl_filename = f"{user_id}_{participant_name}_{scenario_id}_{timestamp}.jsonl"
        jsonl_path = self.storage_path / jsonl_filename
        
        # Create session metadata
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "participant_name": participant_name,
            "scenario_id": scenario_id,
            "scenario_name": scenario_name,
            "character_id": character_id,
            "character_name": character_name,
            "created_at": datetime.utcnow().isoformat(),
            "jsonl_filename": jsonl_filename,
            "jsonl_path": str(jsonl_path),
            "message_count": 0,
            "messages": []
        }
        
        # Store in active sessions
        self._active_sessions[session_id] = session_data
        
        # Write initial session entry to JSONL
        self._append_to_jsonl(jsonl_path, {
            "type": "session_start",
            "timestamp": session_data["created_at"],
            "session_id": session_id,
            "participant": participant_name,
            "scenario": scenario_name,
            "character": character_name,
            "operator": user_id
        })
        
        logger.info(f"Created session {session_id} for {participant_name}")
        return session_data
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Add a message to the session and log to JSONL.
        
        Args:
            session_id: ID of the session
            role: Role of the speaker ("participant" or "character")
            content: Message content
            metadata: Optional metadata for the message
            
        Returns:
            Updated session data
            
        Raises:
            ValueError: If session not found
        """
        if session_id not in self._active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self._active_sessions[session_id]
        timestamp = datetime.utcnow().isoformat()
        
        # Create message entry
        message = {
            "type": "message",
            "timestamp": timestamp,
            "role": role,
            "content": content,
            "message_number": session["message_count"] + 1
        }
        
        if metadata:
            message["metadata"] = metadata
        
        # Append to JSONL file
        self._append_to_jsonl(session["jsonl_path"], message)
        
        # Update session data
        session["message_count"] += 1
        session["messages"].append(message)
        session["last_message_at"] = timestamp
        
        logger.debug(f"Added message to session {session_id}: {role}")
        return session
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data by ID.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Session data or None if not found
        """
        return self._active_sessions.get(session_id)
    
    def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all sessions for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of session data for the user
        """
        return [
            session for session in self._active_sessions.values()
            if session["user_id"] == user_id
        ]
    
    def end_session(self, session_id: str) -> None:
        """End a session and write final entry to JSONL.
        
        Args:
            session_id: ID of the session to end
        """
        if session_id not in self._active_sessions:
            return
        
        session = self._active_sessions[session_id]
        
        # Write session end entry
        self._append_to_jsonl(session["jsonl_path"], {
            "type": "session_end",
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "total_messages": session["message_count"],
            "duration_seconds": self._calculate_duration(session)
        })
        
        logger.info(f"Ended session {session_id}")
    
    def export_session_text(self, session_id: str) -> str:
        """Export session as readable text format.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Session transcript as text
            
        Raises:
            ValueError: If session not found
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        lines = []
        lines.append(f"Roleplay Session Transcript")
        lines.append("=" * 50)
        lines.append(f"Session ID: {session_id}")
        lines.append(f"Participant: {session['participant_name']}")
        lines.append(f"Scenario: {session['scenario_name']}")
        lines.append(f"Character: {session['character_name']}")
        lines.append(f"Started: {session['created_at']}")
        lines.append(f"Messages: {session['message_count']}")
        lines.append("=" * 50)
        lines.append("")
        
        # Add messages
        for msg in session["messages"]:
            if msg["type"] == "message":
                speaker = session['participant_name'] if msg["role"] == "participant" else session['character_name'].split(' - ')[0]
                lines.append(f"{speaker}: {msg['content']}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _append_to_jsonl(self, filepath: Path, data: Dict) -> None:
        """Append data to JSONL file.
        
        Args:
            filepath: Path to JSONL file
            data: Data to append
        """
        with open(filepath, 'a') as f:
            f.write(json.dumps(data) + '\n')
    
    def _calculate_duration(self, session: Dict) -> int:
        """Calculate session duration in seconds.
        
        Args:
            session: Session data
            
        Returns:
            Duration in seconds
        """
        if "last_message_at" not in session:
            return 0
        
        start = datetime.fromisoformat(session["created_at"])
        end = datetime.fromisoformat(session["last_message_at"])
        return int((end - start).total_seconds())

# Global session service instance
_session_service = None

def get_session_service() -> SessionService:
    """Get or create the session service instance.
    
    Returns:
        Session service instance
    """
    global _session_service
    if _session_service is None:
        from ..server.config_loader import get_config
        config = get_config()
        # Use sessions subdirectory under the configured storage path
        storage_path = Path(config.storage_path).expanduser() / "sessions"
        _session_service = SessionService(str(storage_path))
    return _session_service