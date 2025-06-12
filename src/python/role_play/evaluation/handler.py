"""Evaluation handler for session analysis and export."""
import logging
from typing import List, Annotated, Optional

from fastapi import HTTPException, Depends, APIRouter
from fastapi.responses import PlainTextResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from pydantic import BaseModel

from ..chat.chat_logger import ChatLogger
from ..common.models import BaseResponse, User
from ..dev_agents.evaluator_agent import tools as eval_tools
from ..dev_agents.evaluator_agent.agent import create_evaluator_agent
from ..server.base_handler import BaseHandler
from ..server.dependencies import require_user_or_higher, get_chat_logger, get_adk_session_service

logger = logging.getLogger(__name__)

class SessionSummary(BaseResponse):
    """Summary of a session available for evaluation."""
    session_id: str
    participant: str
    scenario: str
    character: str
    message_count: int
    started: str
    storage_path: str

class SessionListResponse(BaseResponse):
    """Response containing list of sessions for evaluation."""
    sessions: List[SessionSummary]

class EvaluationRequest(BaseModel):
    """Request to evaluate a session."""
    session_id: str
    language: str = "English"


class EvaluationResponse(BaseResponse):
    """Response containing evaluation results."""
    report: dict

class EvaluationHandler(BaseHandler):
    """Handler for evaluation-related endpoints."""

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

        self._router.get("/sessions", response_model=SessionListResponse)(self.get_evaluation_sessions)
        self._router.get("/session/{session_id}/download")(self.download_session)
        self._router.post("/{session_id}/request", response_model=BaseResponse)(self.request_evaluation)
        self._router.get("/{session_id}", response_model=EvaluationResponse)(self.get_evaluation)

        return self._router

    @property
    def prefix(self) -> str:
        return "/eval"
    
    async def get_evaluation_sessions(
        self, 
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)]
    ) -> SessionListResponse:
        """Get all sessions available for evaluation.
        
        Args:
            current_user: Authenticated user
            chat_logger: Chat logger instance
            
        Returns:
            List of sessions ready for evaluation
        """
        try:
            # Get all sessions for the current user from ChatLogger
            sessions_data = await chat_logger.list_user_sessions(current_user.id)
            
            sessions = []
            for session_data in sessions_data:
                sessions.append(SessionSummary(
                    success=True,
                    session_id=session_data["session_id"],
                    participant=session_data.get("participant_name", "Unknown"),
                    scenario=session_data.get("scenario_name", "Unknown"),
                    character=session_data.get("character_name", "Unknown"),
                    message_count=session_data.get("message_count", 0),
                    started=session_data.get("created_at", "Unknown"),
                    storage_path=session_data.get("storage_path", "")
                ))
            
            return SessionListResponse(
                success=True,
                sessions=sessions
            )
            
        except Exception as e:
            logger.error(f"Failed to get evaluation sessions: {e}")
            raise HTTPException(status_code=500, detail="Failed to get sessions")
    
    async def download_session(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)]
    ):
        """Download session transcript as text file.
        
        Args:
            session_id: ID of the session to download
            current_user: Authenticated user
            chat_logger: Chat logger instance
            
        Returns:
            Text file download response
        """
        try:
            # Export session as text using ChatLogger
            text_content = await chat_logger.export_session_text(
                user_id=current_user.id,
                session_id=session_id
            )
            
            if text_content == "Session log file not found.":
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Return as downloadable text file
            return PlainTextResponse(
                content=text_content,
                media_type="text/plain",
                headers={
                    "Content-Disposition": f"attachment; filename=transcript_{session_id}.txt"
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to download session: {e}")
            raise HTTPException(status_code=500, detail="Failed to download session")
    
    async def request_evaluation(
        self,
        session_id: str,
        request: EvaluationRequest,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)],
    ) -> BaseResponse:
        """Kick off an evaluation. For now this runs synchronously."""
        await self._run_evaluation(session_id, request.language, current_user, chat_logger, adk_session_service)
        return BaseResponse(success=True)

    async def get_evaluation(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)],
    ) -> EvaluationResponse:
        """Return the stored evaluation report."""
        path = f"users/{current_user.id}/evaluations/{session_id}.json"
        try:
            data = await chat_logger.storage.read(path)
            report = json.loads(data)
        except Exception:
            raise HTTPException(status_code=404, detail="Report not found")
        return EvaluationResponse(success=True, report=report)

    async def _run_evaluation(
        self,
        session_id: str,
        language: str,
        current_user: User,
        chat_logger: ChatLogger,
        adk_session_service: InMemorySessionService,
    ) -> None:
        """Internal helper that executes the evaluator agent."""
        eval_tools.configure_tools(
            chat_logger=chat_logger,
            storage=chat_logger.storage,
            user_id=current_user.id,
        )

        agent = create_evaluator_agent(language)
        eval_session_id = f"eval_{session_id}"
        await adk_session_service.create_session(
            app_name="roleplay_evaluator",
            user_id=current_user.id,
            session_id=eval_session_id,
        )
        runner = Runner(
            app_name="roleplay_evaluator",
            agent=agent,
            session_service=adk_session_service,
        )

        try:
            async for _ in runner.run_async(
                new_message=Content(role="user", parts=[Part(text="evaluate")]),
                session_id=eval_session_id,
                user_id=current_user.id,
            ):
                pass
        finally:
            await adk_session_service.delete_session(
                app_name="roleplay_evaluator",
                user_id=current_user.id,
                session_id=eval_session_id,
            )
            if hasattr(runner, "close") and callable(runner.close):
                try:
                    await runner.close()
                except Exception as close_err:
                    logger.error("Error closing evaluator runner: %s", close_err)

