"""Data models for the chat module."""
from pydantic import BaseModel
from typing import List, Dict, Any
from ..common.models import BaseResponse

class CreateSessionRequest(BaseModel):
    """Request to create a new chat session."""
    scenario_id: str
    character_id: str
    participant_name: str

class CreateSessionResponse(BaseResponse):
    """Response after creating a chat session."""
    session_id: str
    scenario_id: str
    scenario_name: str
    character_id: str
    character_name: str
    jsonl_filename: str

class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""
    message: str

class ChatMessageResponse(BaseResponse):
    """Response after sending a chat message."""
    response: str
    session_id: str
    message_count: int

class SessionInfo(BaseModel):
    """Information about a chat session."""
    session_id: str
    scenario_id: str
    scenario_name: str
    character_id: str
    character_name: str
    participant_name: str
    created_at: str
    message_count: int
    jsonl_filename: str

class SessionListResponse(BaseResponse):
    """Response containing list of sessions."""
    sessions: List[SessionInfo]

class ScenarioInfo(BaseModel):
    """Information about a scenario."""
    id: str
    name: str
    description: str
    compatible_character_count: int

class ScenarioListResponse(BaseResponse):
    """Response containing list of scenarios."""
    scenarios: List[ScenarioInfo]

class CharacterInfo(BaseModel):
    """Information about a character."""
    id: str
    name: str
    description: str

class CharacterListResponse(BaseResponse):
    """Response containing list of characters."""
    characters: List[CharacterInfo]
