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
from ..dev_agents.evaluator_agent.agent import (
    create_evaluator_agent,
    root_agent as evaluator_agent,
)
from ..dev_agents.evaluator_agent.model import FinalReviewReport, ChatInfo
from ..chat.models import ScenarioInfo, CharacterInfo
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
    evaluation_type: str = "comprehensive"  # comprehensive, quick, custom
    custom_criteria: Optional[List[str]] = None


class EvaluationResponse(BaseResponse):
    """Response containing evaluation results."""
    session_id: str
    evaluation_type: str
    feedback: str
    strengths: List[str]


class TranscriptEvaluationRequest(BaseModel):
    """Request to evaluate a raw chat transcript."""
    chat_session_id: str
    transcript_text: str
    scenario: ScenarioInfo
    character: CharacterInfo
    trainee_name: str
    goal: str
    language: str = "en"


class TranscriptEvaluationResponse(BaseResponse):
    """Evaluation response for transcript analysis."""
    report: FinalReviewReport

class EvaluationHandler(BaseHandler):
    """Handler for evaluation-related endpoints."""

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

        self._router.get("/sessions", response_model=SessionListResponse)(self.get_evaluation_sessions)
        self._router.get("/session/{session_id}/download")(self.download_session)
        self._router.post("/session/evaluate", response_model=EvaluationResponse)(self.evaluate_session)
        self._router.post("/transcript/evaluate", response_model=TranscriptEvaluationResponse)(self.evaluate_transcript)

        return self._router

    @property
    def prefix(self) -> str:
        return "/eval"

    def _create_evaluator_agent(self, request: TranscriptEvaluationRequest):
        """Create an evaluator agent for a given transcript request."""
        chat_info = ChatInfo(
            chat_language=request.language,
            chat_session_id=request.chat_session_id,
            scenario_info=request.scenario,
            goal=request.goal,
            char_info=request.character,
            transcript_text=request.transcript_text,
            trainee_name=request.trainee_name,
        )
        return create_evaluator_agent(request.language, chat_info)
    
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
        try:
            # Get the session transcript
            transcript = await chat_logger.export_session_text(
                user_id=current_user.id,
                session_id=request.session_id
            )
            
            if transcript == "Session log file not found.":
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Create a unique evaluation session ID
            eval_session_id = f"eval_{request.session_id}"
            
            # Initialize ADK session for evaluation
            await adk_session_service.create_session(
                app_name="roleplay_evaluator",
                user_id=current_user.id,
                session_id=eval_session_id,
                state={"transcript": transcript, "evaluation_type": request.evaluation_type}
            )
            
            # Create runner with evaluator agent
            runner = Runner(
                app_name="roleplay_evaluator",
                agent=evaluator_agent,
                session_service=adk_session_service
            )
            
            # Prepare evaluation prompt based on type
            if request.evaluation_type == "quick":
                prompt = f"""Please provide a quick evaluation of this roleplay session transcript:

{transcript}

Focus on the key strengths and areas for improvement. Provide numerical scores for:
- Character Consistency (0-10)
- Engagement Quality (0-10)
- Scenario Adherence (0-10)
- Overall Quality (0-10)"""
            elif request.evaluation_type == "custom" and request.custom_criteria:
                criteria_list = "\n".join(f"- {criterion}" for criterion in request.custom_criteria)
                prompt = f"""Please evaluate this roleplay session transcript based on these specific criteria:

{criteria_list}

Transcript:
{transcript}

Also provide standard numerical scores for character consistency, engagement quality, scenario adherence, and overall quality (0-10 scale)."""
            else:  # comprehensive
                prompt = f"""Please provide a comprehensive evaluation of this roleplay session transcript:

{transcript}

Analyze:
1. Character consistency and authenticity
2. Quality of engagement and responses
3. Adherence to the scenario
4. Language appropriateness
5. Immersion maintenance
6. Conversation flow and pacing
7. Meeting participant needs

Provide:
- Detailed feedback
- Specific examples from the transcript
- Numerical scores (0-10) for character consistency, engagement quality, scenario adherence, and overall quality
- List of strengths
- List of areas for improvement"""
            
            # Execute evaluation
            content = Content(role="user", parts=[Part(text=prompt)])
            
            response_text = ""
            try:
                async for event in runner.run_async(
                    new_message=content,
                    session_id=eval_session_id,
                    user_id=current_user.id
                ):
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                response_text += part.text
            finally:
                # Clean up
                await adk_session_service.delete_session(
                    app_name="roleplay_evaluator",
                    user_id=current_user.id,
                    session_id=eval_session_id
                )
                if hasattr(runner, 'close') and callable(runner.close):
                    try:
                        await runner.close()
                    except Exception as close_err:
                        logger.error(f"Error closing evaluator runner: {close_err}")

        return EvaluationResponse(
            success=True,
            session_id=request.session_id,
            evaluation_type=request.evaluation_type,
            feedback=response_text,
            strengths=[],
        )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to evaluate session {request.session_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to evaluate session")

    async def evaluate_transcript(
        self,
        request: TranscriptEvaluationRequest,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)],
    ) -> TranscriptEvaluationResponse:
        """Evaluate a raw transcript using the evaluator agent."""
        eval_session_id = f"eval_{request.chat_session_id}"
        agent = self._create_evaluator_agent(request)
        runner = Runner(
            app_name="roleplay_evaluator",
            agent=agent,
            session_service=adk_session_service,
        )

        await adk_session_service.create_session(
            app_name="roleplay_evaluator",
            user_id=current_user.id,
            session_id=eval_session_id,
            state={"transcript": request.transcript_text},
        )

        content = Content(role="user", parts=[Part(text="evaluate")])
        response_text = ""
        try:
            async for event in runner.run_async(
                new_message=content,
                session_id=eval_session_id,
                user_id=current_user.id,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_text += part.text
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
                    logger.error(f"Error closing evaluator runner: {close_err}")

        try:
            report = FinalReviewReport.model_validate_json(response_text)
        except Exception as e:
            logger.error(f"Failed to parse evaluator output: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to parse evaluation result")

        return TranscriptEvaluationResponse(success=True, report=report)
