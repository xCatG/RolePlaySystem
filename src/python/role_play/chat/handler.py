"""Chat handler for roleplay conversations."""
from typing import List, Annotated
from fastapi import HTTPException, Depends, APIRouter
from ..server.base_handler import BaseHandler
from ..server.dependencies import get_current_user
from ..common.models import User
from .models import (
    CreateSessionRequest,
    CreateSessionResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    SessionListResponse,
    SessionInfo,
    ScenarioListResponse,
    ScenarioInfo,
    CharacterListResponse,
    CharacterInfo
)
from .content_loader import ContentLoader
from .session_service import get_session_service
from .adk_client import get_adk_client
import logging

logger = logging.getLogger(__name__)

class ChatHandler(BaseHandler):
    """Handler for chat-related endpoints."""

    def __init__(self):
        """Initialize chat handler."""
        super().__init__()
        self.content_loader = ContentLoader()
        self.session_service = get_session_service()
        self.adk_client = get_adk_client()

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

        self._router.get("/content/scenarios", tags=["Content"], response_model=ScenarioListResponse)(self.get_scenarios)
        self._router.get("/content/scenarios/{scenario_id}/characters", tags=["Content"],
                         response_model=CharacterListResponse)(self.get_scenario_characters)

        # Session endpoints
        self._router.post("/session", tags=["Session"], response_model=CreateSessionResponse)(self.create_session)
        self._router.get("/sessions", tags=["Session"], response_model=SessionListResponse)(self.get_sessions)
        self._router.post("/session/{session_id}/message", tags=["Session"], response_model=ChatMessageResponse)(self.send_message)
        self._router.get("/session/{session_id}/export-text", tags=["Session"])(self.export_session_text)

        return self._router

    @property
    def prefix(self) -> str:
        return "/chat"

    async def get_scenarios(self, current_user: Annotated[User, Depends(get_current_user)]) -> ScenarioListResponse:
        """Get all available scenarios.
        
        Args:
            token_data: Authenticated user token data
            
        Returns:
            List of available scenarios
        """
        try:
            scenarios = self.content_loader.get_scenarios()
            scenario_infos = []
            
            for scenario in scenarios:
                compatible_chars = len(scenario.get("compatible_characters", []))
                scenario_infos.append(ScenarioInfo(
                    id=scenario["id"],
                    name=scenario["name"],
                    description=scenario["description"],
                    compatible_character_count=compatible_chars
                ))
            
            return ScenarioListResponse(
                success=True,
                scenarios=scenario_infos
            )
        except Exception as e:
            logger.error(f"Failed to get scenarios: {e}")
            raise HTTPException(status_code=500, detail="Failed to load scenarios")
    
    async def get_scenario_characters(
        self, 
        scenario_id: str,
        current_user: Annotated[User, Depends(get_current_user)]
    ) -> CharacterListResponse:
        """Get characters compatible with a scenario.
        
        Args:
            scenario_id: ID of the scenario
            token_data: Authenticated user token data
            
        Returns:
            List of compatible characters
        """
        try:
            characters = self.content_loader.get_scenario_characters(scenario_id)
            
            if not characters:
                scenario = self.content_loader.get_scenario_by_id(scenario_id)
                if not scenario:
                    raise HTTPException(status_code=404, detail="Scenario not found")
            
            character_infos = [
                CharacterInfo(
                    id=char["id"],
                    name=char["name"],
                    description=char["description"]
                )
                for char in characters
            ]
            
            return CharacterListResponse(
                success=True,
                characters=character_infos
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get scenario characters: {e}")
            raise HTTPException(status_code=500, detail="Failed to load characters")
    
    async def create_session(
        self,
        request: CreateSessionRequest,
        current_user: Annotated[User, Depends(get_current_user)]
    ) -> CreateSessionResponse:
        """Create a new chat session.
        
        Args:
            request: Session creation request
            token_data: Authenticated user token data
            
        Returns:
            Created session information
        """
        try:
            # Validate scenario and character
            scenario = self.content_loader.get_scenario_by_id(request.scenario_id)
            if not scenario:
                raise HTTPException(status_code=400, detail="Invalid scenario ID")
            
            character = self.content_loader.get_character_by_id(request.character_id)
            if not character:
                raise HTTPException(status_code=400, detail="Invalid character ID")
            
            # Check if character is compatible with scenario
            if request.character_id not in scenario.get("compatible_characters", []):
                raise HTTPException(
                    status_code=400, 
                    detail="Character not compatible with scenario"
                )
            
            # Create session
            session_data = self.session_service.create_session(
                user_id=current_user.id,
                participant_name=request.participant_name,
                scenario_id=request.scenario_id,
                scenario_name=scenario["name"],
                character_id=request.character_id,
                character_name=character["name"]
            )
            
            # Initialize ADK agent for the session
            await self.adk_client.create_roleplay_agent(character, scenario)
            
            return CreateSessionResponse(
                success=True,
                session_id=session_data["session_id"],
                scenario_name=scenario["name"],
                character_name=character["name"],
                jsonl_filename=session_data["jsonl_filename"]
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise HTTPException(status_code=500, detail="Failed to create session")
    
    async def get_sessions(self, current_user: Annotated[User, Depends(get_current_user)]) -> SessionListResponse:
        """Get all sessions for the current user.
        
        Args:
            token_data: Authenticated user token data
            
        Returns:
            List of user's sessions
        """
        try:
            sessions = self.session_service.get_user_sessions(current_user.id)
            
            session_infos = [
                SessionInfo(
                    session_id=session["session_id"],
                    scenario_name=session["scenario_name"],
                    character_name=session["character_name"],
                    participant_name=session["participant_name"],
                    created_at=session["created_at"],
                    message_count=session["message_count"],
                    jsonl_filename=session["jsonl_filename"]
                )
                for session in sessions
            ]
            
            return SessionListResponse(
                success=True,
                sessions=session_infos
            )
            
        except Exception as e:
            logger.error(f"Failed to get sessions: {e}")
            raise HTTPException(status_code=500, detail="Failed to get sessions")
    
    async def send_message(
        self,
        session_id: str,
        request: ChatMessageRequest,
        current_user: Annotated[User, Depends(get_current_user)]
    ) -> ChatMessageResponse:
        """Send a message in a chat session.
        
        Args:
            session_id: ID of the session
            request: Message request
            token_data: Authenticated user token data
            
        Returns:
            Chat response
        """
        try:
            # Get session
            session = self.session_service.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Verify user owns the session
            if session["user_id"] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")
            
            # Add participant message
            self.session_service.add_message(
                session_id=session_id,
                role="participant",
                content=request.message
            )
            
            # Generate AI response
            response = await self.adk_client.generate_response(
                user_message=request.message,
                session_context=session
            )
            
            # Add character response
            updated_session = self.session_service.add_message(
                session_id=session_id,
                role="character",
                content=response
            )
            
            return ChatMessageResponse(
                success=True,
                response=response,
                session_id=session_id,
                message_count=updated_session["message_count"]
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise HTTPException(status_code=500, detail="Failed to send message")
    
    async def export_session_text(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(get_current_user)]
    ) -> str:
        """Export session as text file.
        
        Args:
            session_id: ID of the session
            token_data: Authenticated user token data
            
        Returns:
            Text transcript of the session
        """
        try:
            # Get session
            session = self.session_service.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Verify user owns the session
            if session["user_id"] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")
            
            # Export as text
            text_content = self.session_service.export_session_text(session_id)
            
            # Return as plain text response
            # from fastapi.responses import PlainTextResponse
            # return PlainTextResponse(
            #     content=text_content,
            #     media_type="text/plain",
            #     headers={
            #         "Content-Disposition": f"attachment; filename=session_{session_id}.txt"
            #     }
            # )
            return text_content

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to export session: {e}")
            raise HTTPException(status_code=500, detail="Failed to export session")