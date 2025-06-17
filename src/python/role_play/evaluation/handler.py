"""Evaluation handler for session analysis and export."""
import json
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
from ..common.time_utils import utc_now_isoformat
from ..dev_agents.evaluator_agent.agent import create_evaluator_agent
from ..dev_agents.evaluator_agent.model import FinalReviewReport
from ..chat.models import ChatInfo
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
    evaluation_type: str = "comprehensive"  # comprehensive, quick, custom, currently ignored
    custom_criteria: Optional[List[str]] = None


class EvaluationResponse(BaseResponse):
    """Response containing evaluation results."""
    session_id: str
    evaluation_type: str
    report: FinalReviewReport

class EvaluationHandler(BaseHandler):
    """Handler for evaluation-related endpoints."""

    ADK_APP_NAME="roleplay_evaluator"

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

        self._router.get("/sessions", response_model=SessionListResponse)(self.get_evaluation_sessions)
        self._router.get("/session/{session_id}/download")(self.download_session)
        self._router.get("/session/{session_id}/chat-info")(self.get_session_chat_info)
        self._router.post("/session/evaluate", response_model=EvaluationResponse)(self.evaluate_session)

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
    
    async def get_session_chat_info(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)]
    ):
        """Get session data in ChatInfo format for evaluator agent.
        
        Args:
            session_id: ID of the session to get
            current_user: Authenticated user
            chat_logger: Chat logger instance
            
        Returns:
            Session data formatted as ChatInfo JSON
        """
        try:
            # Export session as JSON format with complete data
            chat_info_json = await chat_logger.export_session_text(
                user_id=current_user.id,
                session_id=session_id,
                export_format="json"
            )
            
            if chat_info_json == "Session log file not found.":
                raise HTTPException(status_code=404, detail="Session not found")
            
            return {
                "success": True,
                "session_id": session_id,
                "chat_info": chat_info_json
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get session chat info: {e}")
            raise HTTPException(status_code=500, detail="Failed to get session data")

    async def evaluate_session(
        self,
        request: EvaluationRequest,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)]
    ) -> EvaluationResponse:
        """Evaluate a roleplay session using the AI evaluator agent.
        
        Args:
            request: Evaluation request details
            current_user: Authenticated user
            chat_logger: Chat logger instance
            adk_session_service: ADK session service for agent execution
            
        Returns:
            Evaluation results with scores and feedback
        """
        eval_session_id = None
        runner = None
        
        try:
            # Validate session ownership and load session data
            chat_info_json = await chat_logger.export_session_text(
                user_id=current_user.id,
                session_id=request.session_id,
                export_format="json"
            )
            
            if chat_info_json == "Session log file not found.":
                raise HTTPException(status_code=404, detail="Session not found or access denied")
            
            # Parse and validate ChatInfo data
            try:
                chat_info_data = json.loads(chat_info_json)
                chat_info = ChatInfo(**chat_info_data)
            except (json.JSONDecodeError, ValueError) as parse_err:
                logger.error(f"Failed to parse session data for {request.session_id}: {parse_err}")
                raise HTTPException(status_code=500, detail="Invalid session data format")
            
            # Create unique evaluation session for ADK
            eval_session_id = f"eval_{request.session_id}_{utc_now_isoformat()}"
            
            current_session = await adk_session_service.create_session(
                app_name=EvaluationHandler.ADK_APP_NAME,
                user_id=current_user.id,
                session_id=eval_session_id,
                state={"chat_info": chat_info_json, "evaluation_type": request.evaluation_type}
            )

            # Create evaluator agent and runner
            evaluator_agent = create_evaluator_agent(chat_info.chat_language, chat_info)
            runner = Runner(
                app_name=EvaluationHandler.ADK_APP_NAME,
                agent=evaluator_agent,
                session_service=adk_session_service
            )
            
            # Execute evaluation with evaluator agent
            prompt = "Please evaluate this roleplay session and provide review."
            content = Content(role="user", parts=[Part(text=prompt)])

            async for event in runner.run_async(
                new_message=content,
                session_id=eval_session_id,
                user_id=current_user.id
            ):
                # Process evaluation events (response text accumulated in agent state)
                pass

            # Retrieve final evaluation report from session state
            completed_session = await adk_session_service.get_session(
                app_name=EvaluationHandler.ADK_APP_NAME,
                user_id=current_user.id,
                session_id=eval_session_id
            )
            
            if "final_report" not in completed_session.state:
                raise HTTPException(status_code=500, detail="Evaluation agent failed to generate report")
            
            try:
                report_response = FinalReviewReport(**completed_session.state["final_report"])
            except ValueError as report_err:
                logger.error(f"Invalid evaluation report format: {report_err}")
                raise HTTPException(status_code=500, detail="Failed to parse evaluation report")

            return EvaluationResponse(
                success=True,
                session_id=request.session_id,
                evaluation_type=request.evaluation_type,
                report=report_response
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to evaluate session {request.session_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to evaluate session")
        finally:
            # Cleanup evaluation resources
            if eval_session_id:
                try:
                    await adk_session_service.delete_session(
                        app_name=EvaluationHandler.ADK_APP_NAME,
                        user_id=current_user.id,
                        session_id=eval_session_id
                    )
                except Exception as cleanup_err:
                    logger.error(f"Failed to cleanup evaluation session {eval_session_id}: {cleanup_err}")
            
            if runner and hasattr(runner, 'close') and callable(runner.close):
                try:
                    await runner.close()
                except Exception as close_err:
                    logger.error(f"Error closing evaluator runner: {close_err}")