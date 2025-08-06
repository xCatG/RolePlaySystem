"""Chat handler for roleplay conversations - Simplified & Stateless."""
from typing import List, Annotated, Dict, Optional, Any
from fastapi import HTTPException, Depends, APIRouter, Query
from fastapi.responses import PlainTextResponse
from google.adk.runners import Runner
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
import logging
import os
from pathlib import Path

from ..dev_agents.roleplay_agent.agent import get_production_agent
from ..server.base_handler import BaseHandler
from ..server.dependencies import (
    require_user_or_higher,
    get_chat_logger,
    get_adk_session_service,
    get_resource_loader,
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
    CharacterInfo,
    ScriptListResponse,
    ScriptInfo,
    SessionStatusResponse,
    Message,
    MessagesListResponse
)
from ..common.resource_loader import ResourceLoader
from .chat_logger import ChatLogger

logger = logging.getLogger(__name__)

class ChatHandler(BaseHandler):
    """Handler for chat-related endpoints - Simplified & Stateless."""

    # All dependencies (ResourceLoader, ChatLogger, InMemorySessionService)
    # will be injected via FastAPI's Depends in the route methods.

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

            self._router.get("/content/scenarios", tags=["Content"], response_model=ScenarioListResponse)(self.get_scenarios)
            self._router.get("/content/scenarios/{scenario_id}/characters", tags=["Content"],
                             response_model=CharacterListResponse)(self.get_scenario_characters)
            self._router.get("/content/scenarios/{scenario_id}/scripts", tags=["Content"],
                             response_model=ScriptListResponse)(self.get_scenario_scripts)

            self._router.post("/session", tags=["Session"], response_model=CreateSessionResponse)(self.create_session)
            self._router.get("/sessions", tags=["Session"], response_model=SessionListResponse)(self.get_sessions)
            self._router.post("/session/{session_id}/message", tags=["Session"], response_model=ChatMessageResponse)(self.send_message)
            self._router.get("/session/{session_id}/export-text", tags=["Session"])(self.export_session_text)
            self._router.post("/session/{session_id}/end", tags=["Session"], status_code=204)(self.end_session)
            self._router.get("/session/{session_id}/status", tags=["Session"])(self.get_session_status)
            self._router.get("/session/{session_id}/messages", tags=["Session"])(self.get_session_messages)
            self._router.delete("/session/{session_id}", tags=["Session"], status_code=204)(self.delete_session)

        return self._router

    @property
    def prefix(self) -> str:
        return "/chat"

    async def _validate_active_session(self, session_id: str, user_id: str, 
                                      adk_session_service: InMemorySessionService,
                                      chat_logger: ChatLogger) -> Any:
        """
        Validate that a session exists and is active, returning the ADK session.
        
        Args:
            session_id: The session ID to validate
            user_id: The user ID who owns the session
            adk_session_service: ADK session service
            chat_logger: Chat logger for checking ended sessions
            
        Returns:
            The active ADK session
            
        Raises:
            HTTPException: 403 if session is ended, 404 if not found
        """
        adk_session = await adk_session_service.get_session(
            app_name="roleplay_chat", user_id=user_id, session_id=session_id
        )
        if not adk_session:
            end_info = await chat_logger.get_session_end_info(user_id, session_id)
            if end_info:
                raise HTTPException(status_code=403, detail="Cannot access ended session.")
            else:
                raise HTTPException(status_code=404, detail="Session not found or access denied.")
        return adk_session

    async def _log_participant_message(self, adk_session: Any, message: str, user_id: str, 
                                       session_id: str, chat_logger: ChatLogger) -> int:
        """Log participant message and return message number."""
        adk_session.state["message_count"] += 1
        participant_msg_num = adk_session.state["message_count"]
        await chat_logger.log_message(
            user_id=user_id, session_id=session_id, role="participant",
            content=message, message_number=participant_msg_num
        )
        return participant_msg_num

    async def _log_character_message(self, adk_session: Any, response_text: str, user_id: str,
                                    session_id: str, chat_logger: ChatLogger) -> int:
        """Log character response and return message number."""
        adk_session.state["message_count"] += 1
        character_msg_num = adk_session.state["message_count"]
        await chat_logger.log_message(
            user_id=user_id, session_id=session_id, role="character",
            content=response_text, message_number=character_msg_num
        )
        return character_msg_num

    async def _load_session_content(self, adk_session: Any, resource_loader: ResourceLoader) -> tuple[Dict, Dict]:
        """Load and validate scenario and character content for the session."""
        character_dict = await resource_loader.get_character_by_id(
            adk_session.state.get("character_id"), 
            adk_session.state.get("language", "en")
        )
        scenario_dict = await resource_loader.get_scenario_by_id(
            adk_session.state.get("scenario_id"),
            adk_session.state.get("language", "en")
        )
        if not character_dict or not scenario_dict:
            raise HTTPException(status_code=500, detail="Failed to load session character/scenario configuration.")
        return character_dict, scenario_dict

    async def _generate_character_response(self, adk_session: Any, message: str, user_id: str,
                                          session_id: str, character_dict: Dict, scenario_dict: Dict,
                                          adk_session_service: InMemorySessionService) -> str:
        """Generate character response using ADK Runner."""
        # Get character, scenario IDs and language from session state
        character_id = adk_session.state.get("character_id")
        scenario_id = adk_session.state.get("scenario_id")
        language = adk_session.state.get("language", "en")
        
        # Use get_production_agent from roleplay_agent module
        agent = await get_production_agent(character_id, scenario_id, language)
        if not agent:
            raise HTTPException(status_code=500, detail="Failed to create roleplay agent")
            
        runner = Runner(
            app_name="roleplay_chat", agent=agent, session_service=adk_session_service
        )

        response_text = ""
        try:
            # Create Content object with the user's message
            content = Content(role="user", parts=[Part(text=message)])
            async for event in runner.run_async(
                new_message=content, session_id=session_id, user_id=user_id
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
        
        return response_text

    async def get_scenarios(
        self,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        resource_loader: Annotated[ResourceLoader, Depends(get_resource_loader)],
        language: str = Query("en", description="Language code for scenarios"),
    ) -> ScenarioListResponse:
        """Get all available scenarios for the specified language."""
        try:
            scenarios = await resource_loader.get_scenarios(language)
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
        resource_loader: Annotated[ResourceLoader, Depends(get_resource_loader)],
        language: str = Query("en", description="Language code for characters"),
    ) -> CharacterListResponse:
        """Get characters compatible with a scenario for the specified language."""
        try:
            scenario = await resource_loader.get_scenario_by_id(scenario_id, language)
            if not scenario:
                raise HTTPException(status_code=404, detail=f"Scenario with ID '{scenario_id}' not found.")

            compatible_character_ids = scenario.get("compatible_characters", [])
            all_characters = await resource_loader.get_characters(language)
            
            compatible_characters = [
                char for char in all_characters if char["id"] in compatible_character_ids
            ]
            
            character_infos = [
                CharacterInfo(id=char["id"], name=char["name"], description=char["description"])
                for char in compatible_characters
            ]
            return CharacterListResponse(success=True, characters=character_infos)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get scenario characters for '{scenario_id}' in language '{language}': {e}")
            raise HTTPException(status_code=500, detail="Failed to load characters")

    async def get_scenario_scripts(
        self,
        scenario_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        resource_loader: Annotated[ResourceLoader, Depends(get_resource_loader)],
        language: str = Query("en", description="Language code for scripts"),
    ) -> ScriptListResponse:
        """Get scripts available for a scenario in the specified language."""
        try:
            # Verify scenario exists
            scenario = await resource_loader.get_scenario_by_id(scenario_id, language)
            if not scenario:
                raise HTTPException(status_code=404, detail=f"Scenario with ID '{scenario_id}' not found.")

            # Get all scripts and filter by scenario_id
            all_scripts = await resource_loader.get_scripts(language)
            scenario_scripts = [
                script for script in all_scripts if script.get("scenario_id") == scenario_id
            ]
            
            script_infos = [
                ScriptInfo(
                    id=script["id"],
                    scenario_id=script["scenario_id"],
                    character_id=script["character_id"],
                    language=script["language"],
                    goal=script.get("goal"),
                    script=script["script"]
                )
                for script in scenario_scripts
            ]
            return ScriptListResponse(success=True, scripts=script_infos)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get scenario scripts for '{scenario_id}' in language '{language}': {e}")
            raise HTTPException(status_code=500, detail="Failed to load scripts")

    async def create_session(
        self,
        request: CreateSessionRequest,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)],
        resource_loader: Annotated[ResourceLoader, Depends(get_resource_loader)],
    ) -> CreateSessionResponse:
        """Create a new chat session (ADK session in memory, log via ChatLogger)."""
        try:
            # Use user's preferred language for content loading
            user_language = getattr(current_user, 'preferred_language', 'en')
            
            # Load scenario (always required)
            scenario = await resource_loader.get_scenario_by_id(request.scenario_id, user_language)
            if not scenario:
                raise HTTPException(status_code=400, detail=f"Invalid scenario ID: {request.scenario_id}")

            # Determine character_id and validate script/character consistency
            character_id, script_data = await self._resolve_character_and_script(
                request, resource_loader, user_language, scenario
            )
            
            # Load character data
            character = await resource_loader.get_character_by_id(character_id, user_language)
            if not character:
                raise HTTPException(status_code=400, detail=f"Invalid character ID: {character_id}")

            # Validate character compatibility with scenario
            if character_id not in scenario.get("compatible_characters", []):
                raise HTTPException(status_code=400, detail="Character not compatible with scenario")

            # Extract goal from script if available
            goal = script_data.get("goal") if script_data else None

            app_session_id, storage_path = await chat_logger.start_session(
                user_id=current_user.id,
                participant_name=request.participant_name,
                scenario_id=request.scenario_id,
                scenario_name=scenario["name"],
                character_id=character_id,
                character_name=character["name"],
                session_language=user_language,
                script_id=request.script_id,
                goal=goal
            )

            initial_adk_state = {
                "app_session_id": app_session_id,
                "storage_path": storage_path,
                "user_id": current_user.id,
                "participant_name": request.participant_name,
                "scenario_id": request.scenario_id,
                "scenario_name": scenario["name"],
                "character_id": character_id,
                "character_name": character["name"],
                "language": user_language,
                "script_id": request.script_id,
                "script_data": script_data,
                "goal": goal,
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

    async def _resolve_character_and_script(
        self, 
        request: CreateSessionRequest, 
        resource_loader: ResourceLoader, 
        user_language: str, 
        scenario: Dict
    ) -> tuple[str, Optional[Dict]]:
        """
        Resolve character_id and script data based on the three supported modes:
        1. Script-only: derive character_id from script
        2. Character-only: use provided character_id, no script
        3. Both provided: validate consistency
        
        Returns: (character_id, script_data_or_None)
        """
        script_data = None
        
        # Load script if script_id is provided
        if request.script_id:
            script_data = await resource_loader.get_script_id(request.script_id, user_language)
            if not script_data:
                raise HTTPException(status_code=400, detail=f"Invalid script ID: {request.script_id}")
            
            # Validate script belongs to the requested scenario
            if script_data.get("scenario_id") != request.scenario_id:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Script '{request.script_id}' is not compatible with scenario '{request.scenario_id}'"
                )
        
        # Determine final character_id based on the three modes
        if request.character_id and request.script_id:
            # Mode 3: Both provided - validate consistency
            script_character_id = script_data.get("character_id")
            if request.character_id != script_character_id:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Character ID mismatch: provided '{request.character_id}' but script requires '{script_character_id}'"
                )
            character_id = request.character_id
        elif request.script_id:
            # Mode 1: Script-only - derive character from script
            character_id = script_data.get("character_id")
            if not character_id:
                raise HTTPException(status_code=400, detail=f"Script '{request.script_id}' missing character_id")
        else:
            # Mode 2: Character-only - use provided character
            character_id = request.character_id
        
        return character_id, script_data

    async def get_sessions(
        self,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)],
    ) -> SessionListResponse:
        """Get all sessions for the current user by listing logs from ChatLogger."""
        try:
            sessions_data = await chat_logger.list_user_sessions(current_user.id)
            session_infos = []
            
            for s_data in sessions_data:
                session_id = s_data["session_id"]
                
                # Check if session is still active in ADK memory
                adk_session = await adk_session_service.get_session(
                    app_name="roleplay_chat", user_id=current_user.id, session_id=session_id
                )
                is_active = adk_session is not None
                
                # If session is not active, try to get end info
                ended_at = None
                ended_reason = None
                if not is_active:
                    end_info = await chat_logger.get_session_end_info(current_user.id, session_id)
                    ended_at = end_info.get("ended_at")
                    ended_reason = end_info.get("reason")
                
                session_info = SessionInfo(
                    session_id=session_id,
                    scenario_name=s_data.get("scenario_name", "Unknown"),
                    character_name=s_data.get("character_name", "Unknown"),
                    participant_name=s_data.get("participant_name", "Unknown"),
                    created_at=s_data.get("created_at", ""),
                    message_count=s_data.get("message_count", 0),
                    jsonl_filename=s_data.get("storage_path", ""),
                    is_active=is_active,
                    ended_at=ended_at,
                    ended_reason=ended_reason,
                    script_id=s_data.get("script_id", "")
                )
                session_infos.append(session_info)
            
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
        resource_loader: Annotated[ResourceLoader, Depends(get_resource_loader)],
    ) -> ChatMessageResponse:
        """Send a message, creating the Runner on-demand."""
        try:
            adk_session = await self._validate_active_session(
                session_id, current_user.id, adk_session_service, chat_logger
            )

            storage_path = adk_session.state.get("storage_path")
            if not storage_path:
                raise HTTPException(status_code=500, detail="Session state missing storage path.")

            # Log participant message
            await self._log_participant_message(
                adk_session, request.message, current_user.id, session_id, chat_logger
            )
            
            # Load session content
            character_dict, scenario_dict = await self._load_session_content(adk_session, resource_loader)
            
            # Generate character response
            response_text = await self._generate_character_response(
                adk_session, request.message, current_user.id, session_id, 
                character_dict, scenario_dict, adk_session_service
            )
            
            # Log character response
            await self._log_character_message(
                adk_session, response_text, current_user.id, session_id, chat_logger
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

    async def get_session_status(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
    ) -> SessionStatusResponse:
        """Get the status of a session (active or ended)."""
        try:
            # Check if session exists in ADK InMemorySessionService
            adk_session = await adk_session_service.get_session(
                app_name="roleplay_chat", user_id=current_user.id, session_id=session_id
            )
            
            if adk_session:
                # Session is active
                return SessionStatusResponse(
                    success=True,
                    status="active"
                )
            else:
                # Session is ended - try to get end info from JSONL logs
                ended_info = await chat_logger.get_session_end_info(user_id=current_user.id, session_id=session_id)
                
                return SessionStatusResponse(
                    success=True,
                    status="ended",
                    ended_at=ended_info.get("ended_at"),
                    ended_reason=ended_info.get("reason", "Session ended")
                )
        except Exception as e:
            logger.error(f"Failed to get session status for {session_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to get session status")

    async def get_session_messages(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
    ) -> MessagesListResponse:
        """Get all messages for a session from JSONL logs."""
        try:
            messages = await chat_logger.get_session_messages(user_id=current_user.id, session_id=session_id)
            
            return MessagesListResponse(
                success=True,
                messages=messages,
                session_id=session_id
            )
        except Exception as e:
            logger.error(f"Failed to get messages for session {session_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to get session messages")

    async def delete_session(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
    ):
        """Delete a session completely (both from memory and storage)."""
        try:
            # First remove from ADK memory if it exists
            adk_session = await adk_session_service.get_session(
                app_name="roleplay_chat", user_id=current_user.id, session_id=session_id
            )
            if adk_session:
                await adk_session_service.delete_session(
                    app_name="roleplay_chat", user_id=current_user.id, session_id=session_id
                )
                logger.info(f"Removed active session {session_id} from ADK memory")
            
            # Delete the JSONL log file
            await chat_logger.delete_session(user_id=current_user.id, session_id=session_id)
            logger.info(f"Deleted session {session_id} for user {current_user.id}")
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete session")