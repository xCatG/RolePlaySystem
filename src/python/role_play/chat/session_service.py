"""Custom session service for roleplay with JSONL logging."""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from google.adk.sessions import BaseSessionService, Session, State
from google.adk.sessions.base_session_service import GetSessionConfig, ListSessionsResponse
from google.adk.events import Event

logger = logging.getLogger(__name__)

class RoleplaySessionService(BaseSessionService):
    """Service for managing roleplay sessions with JSONL logging.
    
    This service extends ADK's BaseSessionService and is tailored for 
    roleplay-specific needs with JSONL format for easy evaluation.
    """
    
    def __init__(self, storage_path: str = "./storage/sessions"):
        """Initialize session service.
        
        Args:
            storage_path: Path to store session JSONL files
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._active_sessions: Dict[str, Session] = {}
    
    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        """Create a new roleplay session.
        
        Args:
            app_name: The name of the app (will be 'roleplay' for our use)
            user_id: ID of the user (operator) creating the session
            state: Initial state containing roleplay metadata
            session_id: Optional client-provided session ID
            
        Returns:
            ADK Session object
        """
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Extract roleplay metadata from state
        if not state or not all(k in state for k in ['participant_name', 'scenario_id', 'character_id']):
            raise ValueError("State must contain participant_name, scenario_id, and character_id")
        
        # Create JSONL filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        participant_name = state['participant_name']
        scenario_id = state['scenario_id']
        jsonl_filename = f"{user_id}_{participant_name}_{scenario_id}_{timestamp}.jsonl"
        jsonl_path = self.storage_path / jsonl_filename
        
        # Add JSONL path to state
        state['jsonl_filename'] = jsonl_filename
        state['jsonl_path'] = str(jsonl_path)
        
        # Create ADK Session object
        session = Session(
            app_name=app_name,
            user_id=user_id,
            id=session_id,
            state=State(state, dict())
        )
        
        # Store in active sessions
        self._active_sessions[session_id] = session
        
        # Write initial session entry to JSONL
        self._append_to_jsonl(jsonl_path, {
            "type": "session_start",
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "participant": state.get('participant_name'),
            "scenario": state.get('scenario_name'),
            "character": state.get('character_name'),
            "operator": user_id
        })
        
        logger.info(f"Created session {session_id} for {participant_name}")
        return session
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Session:
        """Add a message to the session and log to JSONL.
        
        Args:
            session_id: ID of the session
            role: Role of the speaker ("participant" or "character")
            content: Message content
            metadata: Optional metadata for the message
            
        Returns:
            Updated session
            
        Raises:
            ValueError: If session not found
        """
        session = self._active_sessions.get(session_id)
        if not isinstance(session, Session):
            raise ValueError(f"Session {session_id} not found")
        
        timestamp = datetime.utcnow().isoformat()
        
        # Create message entry
        message = {
            "type": "message",
            "timestamp": timestamp,
            "role": role,
            "content": content,
            "message_number": session.state.get("message_count", 0) + 1
        }
        
        if metadata:
            message["metadata"] = metadata
        
        # Append to JSONL file
        jsonl_path = session.state.get("jsonl_path")
        if jsonl_path:
            self._append_to_jsonl(Path(jsonl_path), message)
        
        # Create an Event for ADK compatibility
        event = Event(
            event_type="message",
            timestamp=datetime.utcnow().timestamp(),
            data=message
        )
        
        # Update session state
        session.state.update({
            "message_count": session.state.get("message_count", 0) + 1,
            "last_message_at": timestamp
        })
        
        # Append event to session
        await self.append_event(session, event)
        
        logger.debug(f"Added message to session {session_id}: {role}")
        return session
    
    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> Optional[Session]:
        """Get session data by ID.
        
        Args:
            app_name: The name of the app
            user_id: ID of the user
            session_id: ID of the session
            config: Optional configuration for getting session
            
        Returns:
            Session object or None if not found
        """
        session = self._active_sessions.get(session_id)
        if session and session.user_id == user_id and session.app_name == app_name:
            # Apply config if provided
            if config and config.num_recent_events and session.events:
                session.events = session.events[-config.num_recent_events:]
            return session
        return None
    
    async def list_sessions(
        self, *, app_name: str, user_id: str
    ) -> ListSessionsResponse:
        """List all sessions for a user.
        
        Args:
            app_name: The name of the app
            user_id: ID of the user
            
        Returns:
            ListSessionsResponse with sessions (without events/states)
        """
        sessions = []
        for session in self._active_sessions.values():
            if isinstance(session, Session) and session.user_id == user_id and session.app_name == app_name:
                # Create a copy without events for listing
                session_copy = Session(
                    app_name=session.app_name,
                    user_id=session.user_id,
                    session_id=session.session_id,
                    state=session.state
                )
                sessions.append(session_copy)
        return ListSessionsResponse(sessions=sessions)
    
    async def delete_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> None:
        """Delete a session and write final entry to JSONL.
        
        Args:
            app_name: The name of the app
            user_id: ID of the user
            session_id: ID of the session to delete
        """
        session = self._active_sessions.get(session_id)
        if not session or session.user_id != user_id or session.app_name != app_name:
            return
        
        # Write session end entry
        jsonl_path = session.state.get("jsonl_path")
        if jsonl_path:
            self._append_to_jsonl(Path(jsonl_path), {
                "type": "session_end",
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "total_messages": session.state.get("message_count", 0),
                "duration_seconds": self._calculate_duration_from_session(session)
            })
        
        # Remove from active sessions
        del self._active_sessions[session_id]
        logger.info(f"Deleted session {session_id}")
    
    async def export_session_text(self, session_id: str) -> str:
        """Export session as readable text format.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Session transcript as text
            
        Raises:
            ValueError: If session not found
        """
        session = self._active_sessions.get(session_id)
        if not isinstance(session, Session):
            raise ValueError(f"Session {session_id} not found")
        
        lines = []
        lines.append(f"Roleplay Session Transcript")
        lines.append("=" * 50)
        lines.append(f"Session ID: {session_id}")
        lines.append(f"Participant: {session.state.get('participant_name', 'Unknown')}")
        lines.append(f"Scenario: {session.state.get('scenario_name', 'Unknown')}")
        lines.append(f"Character: {session.state.get('character_name', 'Unknown')}")
        lines.append(f"Started: {session.created_at.isoformat() if session.created_at else 'Unknown'}")
        lines.append(f"Messages: {session.state.get('message_count', 0)}")
        lines.append("=" * 50)
        lines.append("")
        
        # Add messages from events
        for event in session.events:
            if event.event_type == "message" and event.data:
                msg_data = event.data
                if isinstance(msg_data, dict) and msg_data.get("type") == "message":
                    speaker = session.state.get('participant_name') if msg_data.get("role") == "participant" else session.state.get('character_name', '').split(' - ')[0]
                    lines.append(f"{speaker}: {msg_data.get('content', '')}")
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
    
    def _calculate_duration_from_session(self, session: Session) -> int:
        """Calculate session duration in seconds.
        
        Args:
            session: ADK Session object
            
        Returns:
            Duration in seconds
        """
        last_message_at = session.state.get("last_message_at")
        if not last_message_at or not session.created_at:
            return 0
        
        start = session.created_at
        end = datetime.fromisoformat(last_message_at)
        return int((end - start).total_seconds())
    
    async def create_roleplay_session(
        self,
        user_id: str,
        participant_name: str,
        scenario_id: str,
        scenario_name: str,
        character_id: str,
        character_name: str
    ) -> Session:
        """Create a roleplay session with proper metadata.
        
        This is a convenience method that wraps the ADK create_session
        with roleplay-specific parameters.
        """
        state = {
            "participant_name": participant_name,
            "scenario_id": scenario_id,
            "scenario_name": scenario_name,
            "character_id": character_id,
            "character_name": character_name,
            "message_count": 0
        }
        
        return await self.create_session(
            app_name="roleplay",
            user_id=user_id,
            state=state
        )
    
    async def get_user_sessions(self, user_id: str) -> List[Session]:
        """Get all sessions for a user (convenience method)."""
        response = await self.list_sessions(app_name="roleplay", user_id=user_id)
        return response.sessions


# Global session service instance
_session_service = None

def get_session_service() -> RoleplaySessionService:
    """Get or create the session service instance.
    
    Returns:
        RoleplaySessionService instance
    """
    global _session_service
    if _session_service is None:
        from ..server.config_loader import get_config
        config = get_config()
        # Use sessions subdirectory under the configured storage path
        storage_path = Path(config.storage_path).expanduser() / "sessions"
        _session_service = RoleplaySessionService(str(storage_path))
    return _session_service