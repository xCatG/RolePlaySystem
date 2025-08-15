"""Data models for the chat module."""
from enum import Enum

from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Any, Optional
from ..common.models import BaseResponse

class CreateSessionRequest(BaseModel):
    """Request to create a new chat session."""
    scenario_id: str
    character_id: Optional[str] = Field(default=None, description="Optional character ID - required if no script_id provided")
    participant_name: str
    script_id: Optional[str] = Field(default=None, description="Optional script ID - required if no character_id provided")
    
    @model_validator(mode="after")
    def validate_character_or_script(self) -> "CreateSessionRequest":
        """Ensure at least one of character_id or script_id is provided."""
        if not self.character_id and not self.script_id:
            raise ValueError("Either character_id or script_id must be provided")
        return self

class CreateSessionResponse(BaseResponse):
    """Response after creating a chat session."""
    session_id: str
    scenario_name: str
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
    scenario_name: str
    character_name: str
    participant_name: str
    created_at: str
    message_count: int
    jsonl_filename: str
    is_active: bool = True  # Whether the session is currently active in the session service
    goal: Optional[str] = Field(default=None, description="Goal of this session, could be written in local language.")
    ended_at: Optional[str] = None
    ended_reason: Optional[str] = None
    script_id: Optional[str] = Field(default=None, description="Optional Script ID of this session.")

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
    name: str = Field(description="The name of the character.")
    description: str = Field(description="The description of the character. Could contain age, gender, character traits or brief bio")

class CharacterListResponse(BaseResponse):
    """Response containing list of characters."""
    characters: List[CharacterInfo]

class ScriptRole(str, Enum):
    CHARACTER = "character"
    PARTICIPANT = "participant"
    SYSTEM = "System"


class ScriptLine(BaseModel):
    """A line in a script."""
    speaker: ScriptRole = Field(description="The speaker of the line. Can only be a valid ScriptRole")
    line: Optional[str] = Field(default=None, description="The actual message string representing the line (mutually exclusive with action)")
    action: Optional[str] = Field(default=None, description="An action to take (e.g., 'stop') - mutually exclusive with line")

    @model_validator(mode="after")
    def at_least_one_present(self) -> "ScriptLine":
        if self.line is None and self.action is None:
            raise ValueError("At least one of action or line must be specified")
        return self

class ScriptInfo(BaseModel):
    """Information about a script."""
    id: str
    scenario_id: str = Field(description="The ID of the scenario this script belongs to.")
    character_id: str = Field(description="The ID of the character this script is intended for")
    language: str
    goal: Optional[str] = Field(default=None, description="The goal of this session, could be written in local language.")
    script: List[ScriptLine] = Field(description="The list of lines this script belongs to, in the order they appear in the script.")

class ScriptListResponse(BaseResponse):
    """Response containing list of scripts."""
    scripts: List[ScriptInfo]


class SessionStatusResponse(BaseResponse):
    """Response containing session status."""
    status: str  # "active" or "ended"
    ended_at: Optional[str] = None
    ended_reason: Optional[str] = None

class Message(BaseModel):
    """A single message in a chat session."""
    role: str  # "participant" or "character"
    content: str
    timestamp: str
    message_number: int

class MessagesListResponse(BaseResponse):
    """Response containing list of messages for a session."""
    messages: List[Message]
    session_id: str


class ChatInfo(BaseModel):
    chat_language: str = Field(description="The language of the chat. Use full language name such as 'English' or 'Traditional Chinese'.")
    chat_session_id: str
    scenario_info: ScenarioInfo
    goal: Optional[str] = Field(default=None, description="To goal or situation of this session. Could be in local language.")
    char_info: CharacterInfo
    transcript_text: str = Field(description="The text of the session transcript.")
    participant_name: str = Field(description="The name of the participant")
