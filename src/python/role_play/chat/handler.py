"""Chat handler for roleplay conversations."""
from typing import List, Annotated, Dict, Optional
from fastapi import HTTPException, Depends, APIRouter
from fastapi.responses import PlainTextResponse
from google.adk.runners import Runner
from google.adk.agents import Agent
from ..server.base_handler import BaseHandler
from ..server.dependencies import require_user_or_higher
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
import logging
import os

logger = logging.getLogger(__name__)

# Default model for ADK
DEFAULT_MODEL = os.getenv("ADK_MODEL", "gemini-2.0-flash-lite-001")

class ChatHandler(BaseHandler):
    """Handler for chat-related endpoints with direct ADK integration."""

    def __init__(self):
        """Initialize chat handler."""
        super().__init__()
        self.content_loader = ContentLoader()
        self.session_service = get_session_service()
        self._adk_runners: Dict[str, Runner] = {}  # session_id -> Runner mapping

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

    def _create_roleplay_agent(self, character: Dict, scenario: Dict) -> Agent:
        """Create an ADK agent configured for a specific character and scenario.
        
        Args:
            character: Character configuration dict
            scenario: Scenario configuration dict
            
        Returns:
            Configured ADK Agent
        """
        # Combine character and scenario into a production-ready prompt
        system_prompt = f"""{character.get("system_prompt", "You are a helpful assistant.")}

**Current Scenario:**
{scenario.get("description", "No specific scenario description.")}

**Roleplay Instructions:**
-   **Stay fully in character.** Do NOT break character or mention you are an AI.
-   Respond naturally based on your character's personality and the scenario.
-   Engage with the user's messages within the roleplay context.
"""
        
        # Create agent with the roleplay configuration
        agent = Agent(
            name=f"roleplay_{character['id']}_{scenario['id']}",
            model=DEFAULT_MODEL,
            description=f"Roleplay agent for {character['name']} in {scenario['name']}",
            instruction=system_prompt,
            temperature=0.75,
            max_output_tokens=2000
        )
        
        return agent

    async def get_scenarios(self, current_user: Annotated[User, Depends(require_user_or_higher)]) -> ScenarioListResponse:
        """Get all available scenarios.
        
        Args:
            current_user: Authenticated user
            
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
        current_user: Annotated[User, Depends(require_user_or_higher)]
    ) -> CharacterListResponse:
        """Get characters compatible with a scenario.
        
        Args:
            scenario_id: ID of the scenario
            current_user: Authenticated user
            
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
        current_user: Annotated[User, Depends(require_user_or_higher)]
    ) -> CreateSessionResponse:
        """Create a new chat session.
        
        Args:
            request: Session creation request
            current_user: Authenticated user
            
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
            
            # Create session using the ADK-based session service
            session = await self.session_service.create_roleplay_session(
                user_id=current_user.id,
                participant_name=request.participant_name,
                scenario_id=request.scenario_id,
                scenario_name=scenario["name"],
                character_id=request.character_id,
                character_name=character["name"]
            )
            
            # Create ADK agent and runner for this session
            agent = self._create_roleplay_agent(character, scenario)
            runner = Runner(
                app_name="roleplay_chat",
                agent=agent,
                session_service=self.session_service
            )
            
            # Store runner for later use
            self._adk_runners[session.session_id] = runner
            
            logger.info(f"Created ADK runner for session {session.session_id}")
            
            return CreateSessionResponse(
                success=True,
                session_id=session.session_id,
                scenario_name=scenario["name"],
                character_name=character["name"],
                jsonl_filename=session.state.get("jsonl_filename", "")
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise HTTPException(status_code=500, detail="Failed to create session")
    
    async def get_sessions(self, current_user: Annotated[User, Depends(require_user_or_higher)]) -> SessionListResponse:
        """Get all sessions for the current user.
        
        Args:
            current_user: Authenticated user
            
        Returns:
            List of user's sessions
        """
        try:
            sessions = await self.session_service.get_user_sessions(current_user.id)
            
            session_infos = [
                SessionInfo(
                    session_id=session.session_id,
                    scenario_name=session.state.get("scenario_name", ""),
                    character_name=session.state.get("character_name", ""),
                    participant_name=session.state.get("participant_name", ""),
                    created_at=session.created_at.isoformat() if session.created_at else "",
                    message_count=session.state.get("message_count", 0),
                    jsonl_filename=session.state.get("jsonl_filename", "")
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
        current_user: Annotated[User, Depends(require_user_or_higher)]
    ) -> ChatMessageResponse:
        """Send a message in a chat session.
        
        Args:
            session_id: ID of the session
            request: Message request
            current_user: Authenticated user
            
        Returns:
            Chat response
        """
        try:
            # Get session
            session = await self.session_service.get_session(
                app_name="roleplay",
                user_id=current_user.id,
                session_id=session_id
            )
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Add participant message
            await self.session_service.add_message(
                session_id=session_id,
                role="participant",
                content=request.message
            )
            
            # Get or recreate ADK runner for this session
            runner = self._adk_runners.get(session_id)
            if not runner:
                # Recreate runner if not in memory (e.g., after server restart)
                character = self.content_loader.get_character_by_id(session.state.get("character_id"))
                scenario = self.content_loader.get_scenario_by_id(session.state.get("scenario_id"))
                
                if not character or not scenario:
                    raise HTTPException(status_code=500, detail="Failed to load session configuration")
                
                agent = self._create_roleplay_agent(character, scenario)
                runner = Runner(
                    app_name="roleplay",
                    agent=agent,
                    session_service=self.session_service
                )
                self._adk_runners[session_id] = runner
                logger.info(f"Recreated ADK runner for session {session_id}")
            
            # Generate response using ADK
            response_text = ""
            try:
                async for event in runner.run_async(
                    new_message=request.message,
                    session_id=session_id
                ):
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                response_text += part.text
                
                if not response_text:
                    # Fallback if no response generated
                    character_name = session.state.get("character_name", "Character")
                    response_text = f"[{character_name.split(' - ')[0]} responds thoughtfully to your message]"
                    logger.warning(f"ADK generated empty response for session {session_id}, using fallback")
                
            except Exception as e:
                logger.error(f"ADK runner error: {e}")
                # Fallback response on error
                character_name = session.state.get("character_name", "Character")
                response_text = f"[{character_name.split(' - ')[0]} responds in character]"
            
            # Add character response
            updated_session = await self.session_service.add_message(
                session_id=session_id,
                role="character",
                content=response_text
            )
            
            return ChatMessageResponse(
                success=True,
                response=response_text,
                session_id=session_id,
                message_count=updated_session.state.get("message_count", 0)
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise HTTPException(status_code=500, detail="Failed to send message")
    
    async def export_session_text(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)]
    ) -> PlainTextResponse:
        """Export session as text file.
        
        Args:
            session_id: ID of the session
            current_user: Authenticated user
            
        Returns:
            Text transcript of the session
        """
        try:
            # Get session to verify ownership
            session = await self.session_service.get_session(
                app_name="roleplay",
                user_id=current_user.id,
                session_id=session_id
            )
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Export as text
            text_content = await self.session_service.export_session_text(session_id)
            
            # Return as plain text response with download headers
            return PlainTextResponse(
                content=text_content,
                media_type="text/plain",
                headers={
                    "Content-Disposition": f"attachment; filename=session_{session_id}.txt"
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to export session: {e}")
            raise HTTPException(status_code=500, detail="Failed to export session")
    
    async def cleanup(self):
        """Cleanup ADK runners on shutdown."""
        for runner in self._adk_runners.values():
            try:
                await runner.close()
            except Exception as e:
                logger.error(f"Error closing ADK runner: {e}")
        self._adk_runners.clear()
        logger.info("Cleaned up all ADK runners")