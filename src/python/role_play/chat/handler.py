"""Chat handler for roleplay conversations - Simplified & Stateless."""
from typing import List, Annotated, Dict, Optional
from fastapi import HTTPException, Depends, APIRouter, Query
from fastapi.responses import PlainTextResponse
from google.adk.runners import Runner
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
import logging
import os
from pathlib import Path

from ..server.base_handler import BaseHandler
from ..server.dependencies import (
    require_user_or_higher,
    get_chat_logger,
    get_adk_session_service,
    get_content_loader,
)
from ..common.models import User
from ..common.time_utils import utc_now_isoformat, parse_utc_datetime, utc_now
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
from .chat_logger import ChatLogger

logger = logging.getLogger(__name__)

# Default model for ADK
DEFAULT_MODEL = os.getenv("ADK_MODEL", "gemini-2.0-flash-lite-001")

class ChatHandler(BaseHandler):
    """Handler for chat-related endpoints - Simplified & Stateless."""

    def __init__(self):
        """Initialize chat handler (now stateless)."""
        super().__init__()
        # All dependencies (ContentLoader, ChatLogger, InMemorySessionService)
        # will be injected via FastAPI's Depends in the route methods.

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

            self._router.get("/content/scenarios", tags=["Content"], response_model=ScenarioListResponse)(self.get_scenarios)
            self._router.get("/content/scenarios/{scenario_id}/characters", tags=["Content"],
                             response_model=CharacterListResponse)(self.get_scenario_characters)

            self._router.post("/session", tags=["Session"], response_model=CreateSessionResponse)(self.create_session)
            self._router.get("/sessions", tags=["Session"], response_model=SessionListResponse)(self.get_sessions)
            self._router.post("/session/{session_id}/message", tags=["Session"], response_model=ChatMessageResponse)(self.send_message)
            self._router.get("/session/{session_id}/export-text", tags=["Session"])(self.export_session_text)
            self._router.post("/session/{session_id}/end", tags=["Session"], status_code=204)(self.end_session)

        return self._router

    @property
    def prefix(self) -> str:
        return "/chat"

    def _create_roleplay_agent(self, character: Dict, scenario: Dict) -> Agent:
        """Helper to create an ADK agent configured for a specific character and scenario."""
        # Get language information
        character_language = character.get("language", "en")
        language_names = {
            "en": "English",
            "zh-tw": "Traditional Chinese",
            "ja": "Japanese"
        }
        language_name = language_names.get(character_language, "English")
        
        system_prompt = f"""{character.get("system_prompt", "You are a helpful assistant.")}

**Current Scenario:**
{scenario.get("description", "No specific scenario description.")}

**Roleplay Instructions:**
-   **Stay fully in character.** Do NOT break character or mention you are an AI.
-   Respond naturally based on your character's personality and the scenario.
-   **IMPORTANT: Respond in {language_name} language as specified by your character and scenario.**
-   Engage with the user's messages within the roleplay context.
"""
        agent = Agent(
            name=f"roleplay_{character.get('id', 'unknown')}_{scenario.get('id', 'unknown')}",
            model=DEFAULT_MODEL,
            description=f"Roleplay agent for {character.get('name', 'Unknown Character')} in {scenario.get('name', 'Unknown Scenario')}",
            instruction=system_prompt
        )
        return agent

    async def get_scenarios(
        self,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        content_loader: Annotated[ContentLoader, Depends(get_content_loader)],
        language: str = Query("en", description="Language code for scenarios"),
    ) -> ScenarioListResponse:
        """Get all available scenarios for the specified language."""
        try:
            scenarios = content_loader.get_scenarios(language)
            scenario_infos = [
                ScenarioInfo(
                    id=scenario["id"],
                    name=scenario["name"],
                    description=scenario["description"],
                    compatible_character_count=len(scenario.get("compatible_characters", []))
                ) for scenario in scenarios
            ]
            return ScenarioListResponse(success=True, scenarios=scenario_infos)
        except Exception as e:
            logger.error(f"Failed to get scenarios for language '{language}': {e}")
            raise HTTPException(status_code=500, detail="Failed to load scenarios")

    async def get_scenario_characters(
        self,
        scenario_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        content_loader: Annotated[ContentLoader, Depends(get_content_loader)],
        language: str = Query("en", description="Language code for characters"),
    ) -> CharacterListResponse:
        """Get characters compatible with a scenario for the specified language."""
        try:
            characters = content_loader.get_scenario_characters(scenario_id, language)
            if not characters:
                scenario = content_loader.get_scenario_by_id(scenario_id, language)
                if not scenario:
                    raise HTTPException(status_code=404, detail=f"Scenario with ID '{scenario_id}' not found.")
            
            character_infos = [
                CharacterInfo(id=char["id"], name=char["name"], description=char["description"])
                for char in characters
            ]
            return CharacterListResponse(success=True, characters=character_infos)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get scenario characters for '{scenario_id}' in language '{language}': {e}")
            raise HTTPException(status_code=500, detail="Failed to load characters")

    async def create_session(
        self,
        request: CreateSessionRequest,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)],
        content_loader: Annotated[ContentLoader, Depends(get_content_loader)],
    ) -> CreateSessionResponse:
        """Create a new chat session (ADK session in memory, log via ChatLogger)."""
        try:
            # Use user's preferred language for content loading
            user_language = getattr(current_user, 'preferred_language', 'en')
            
            scenario = content_loader.get_scenario_by_id(request.scenario_id, user_language)
            if not scenario:
                raise HTTPException(status_code=400, detail=f"Invalid scenario ID: {request.scenario_id}")

            character = content_loader.get_character_by_id(request.character_id, user_language)
            if not character:
                raise HTTPException(status_code=400, detail=f"Invalid character ID: {request.character_id}")

            if request.character_id not in scenario.get("compatible_characters", []):
                raise HTTPException(status_code=400, detail="Character not compatible with scenario")

            app_session_id, storage_path = await chat_logger.start_session(
                user_id=current_user.id,
                participant_name=request.participant_name,
                scenario_id=request.scenario_id,
                scenario_name=scenario["name"],
                character_id=request.character_id,
                character_name=character["name"]
            )

            initial_adk_state = {
                "app_session_id": app_session_id,
                "storage_path": storage_path,
                "user_id": current_user.id,
                "participant_name": request.participant_name,
                "scenario_id": request.scenario_id,
                "scenario_name": scenario["name"],
                "character_id": request.character_id,
                "character_name": character["name"],
                "language": user_language,
                "message_count": 0,
                "session_creation_time_iso": utc_now_isoformat()
            }

            await adk_session_service.create_session(
                app_name="roleplay_chat",
                user_id=current_user.id,
                session_id=app_session_id,
                state=initial_adk_state
            )
            logger.info(f"Created ADK session {app_session_id} (Runner will be created on demand)")

            return CreateSessionResponse(
                success=True,
                session_id=app_session_id,
                scenario_name=scenario["name"],
                character_name=character["name"],
                jsonl_filename=storage_path
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create session: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create session")

    async def get_sessions(
        self,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
    ) -> SessionListResponse:
        """Get all sessions for the current user by listing logs from ChatLogger."""
        try:
            sessions_data = await chat_logger.list_user_sessions(current_user.id)
            session_infos = [
                SessionInfo(
                    session_id=s_data["session_id"],
                    scenario_name=s_data.get("scenario_name", "Unknown"),
                    character_name=s_data.get("character_name", "Unknown"),
                    participant_name=s_data.get("participant_name", "Unknown"),
                    created_at=s_data.get("created_at", ""),
                    message_count=s_data.get("message_count", 0),
                    jsonl_filename=s_data.get("storage_path", "")
                ) for s_data in sessions_data
            ]
            return SessionListResponse(success=True, sessions=session_infos)
        except Exception as e:
            logger.error(f"Failed to get sessions for user {current_user.id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to get sessions")

    async def send_message(
        self,
        session_id: str,
        request: ChatMessageRequest,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)],
        content_loader: Annotated[ContentLoader, Depends(get_content_loader)],
    ) -> ChatMessageResponse:
        """Send a message, creating the Runner on-demand."""
        try:
            adk_session = await adk_session_service.get_session(
                app_name="roleplay_chat", user_id=current_user.id, session_id=session_id
            )
            if not adk_session:
                raise HTTPException(status_code=404, detail="Active session not found or access denied.")

            storage_path = adk_session.state.get("storage_path")
            if not storage_path:
                raise HTTPException(status_code=500, detail="Session state missing storage path.")

            adk_session.state["message_count"] += 1
            participant_msg_num = adk_session.state["message_count"]
            await chat_logger.log_message(
                user_id=current_user.id, session_id=session_id, role="participant",
                content=request.message, message_number=participant_msg_num
            )

            character_dict = content_loader.get_character_by_id(
                adk_session.state.get("character_id"), 
                adk_session.state.get("language", "en")
            )
            scenario_dict = content_loader.get_scenario_by_id(
                adk_session.state.get("scenario_id"),
                adk_session.state.get("language", "en")
            )
            if not character_dict or not scenario_dict:
                raise HTTPException(status_code=500, detail="Failed to load session character/scenario configuration.")

            agent = self._create_roleplay_agent(character_dict, scenario_dict)
            runner = Runner(
                app_name="roleplay_chat", agent=agent, session_service=adk_session_service
            )

            response_text = ""
            try:
                # Create Content object with the user's message
                content = Content(role="user", parts=[Part(text=request.message)])
                async for event in runner.run_async(
                    new_message=content, session_id=session_id, user_id=current_user.id
                ):
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                response_text += part.text
                if not response_text:
                    response_text = f"[{adk_session.state.get('character_name', 'Character')} is thinking...]"
                    logger.warning(f"ADK generated empty response for session {session_id}, using fallback.")
            except Exception as e:
                logger.error(f"ADK runner error in session {session_id}: {e}", exc_info=True)
                response_text = f"[{adk_session.state.get('character_name', 'Character')} seems to be having trouble responding right now.]"
            finally:
                if hasattr(runner, 'close') and callable(runner.close):
                    try:
                        await runner.close()
                    except Exception as close_err:
                        logger.error(f"Error closing runner for session {session_id}: {close_err}")

            adk_session.state["message_count"] += 1
            character_msg_num = adk_session.state["message_count"]
            await chat_logger.log_message(
                user_id=current_user.id, session_id=session_id, role="character",
                content=response_text, message_number=character_msg_num
            )

            return ChatMessageResponse(
                success=True, response=response_text, session_id=session_id,
                message_count=adk_session.state["message_count"]
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to send message in session {session_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to send message")

    async def end_session(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)],
    ):
        """Ends a chat session, logging it and removing from ADK InMemory service."""
        try:
            adk_session = await adk_session_service.get_session(
                app_name="roleplay_chat", user_id=current_user.id, session_id=session_id
            )
            if not adk_session:
                logger.warning(f"Attempt to end session {session_id} not found in ADK InMemory service.")
                return

            storage_path = adk_session.state.get("storage_path")
            if not storage_path:
                logger.error(f"Cannot end session {session_id}: storage path missing from ADK state.")
                raise HTTPException(status_code=500, detail="Session state corrupted, cannot end session.")
            message_count = adk_session.state.get("message_count", 0)
            created_iso = adk_session.state.get("session_creation_time_iso")
            duration_seconds = 0
            if created_iso:
                try:
                    created_dt = parse_utc_datetime(created_iso)
                    duration_seconds = (utc_now() - created_dt).total_seconds()
                except ValueError:
                    logger.warning(f"Could not parse creation_time_iso: {created_iso} for session {session_id}")

            await chat_logger.end_session(
                user_id=current_user.id,
                session_id=session_id,
                total_messages=message_count,
                duration_seconds=duration_seconds,
                reason="User ended session"
            )

            await adk_session_service.delete_session(
                app_name="roleplay_chat", user_id=current_user.id, session_id=session_id
            )
            logger.info(f"Ended and removed session {session_id} from ADK InMemory service.")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to end session {session_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to end session.")

    async def export_session_text(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
    ) -> PlainTextResponse:
        """Export session as text file using ChatLogger."""
        try:
            text_content = await chat_logger.export_session_text(user_id=current_user.id, session_id=session_id)
            if text_content == "Session log file not found.":
                raise HTTPException(status_code=404, detail="Session log not found for export.")

            return PlainTextResponse(
                content=text_content,
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=session_{session_id}.txt"}
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to export session {session_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to export session")