"""Evaluation handler for session analysis and export."""
import json
import logging
import re
from typing import List, Annotated, Optional, Dict, Any

from fastapi import HTTPException, Depends, APIRouter
from fastapi.responses import PlainTextResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from pydantic import BaseModel

from ..chat.chat_logger import ChatLogger
from ..chat.models import ScenarioInfo, CharacterInfo
from ..common.models import BaseResponse, User
from ..dev_agents.evaluator_agent.agent import create_evaluator_agent
from ..dev_agents.evaluator_agent.model import ChatInfo, FinalReviewReport
from ..server.base_handler import BaseHandler
from ..server.dependencies import require_user_or_higher, get_chat_logger, get_adk_session_service, get_content_loader
from ..chat.content_loader import ContentLoader

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

class StructuredEvaluationRequest(BaseModel):
    """Request to evaluate a session with structured output."""
    session_id: str

class StructuredEvaluationResponse(BaseResponse):
    """Response containing structured evaluation results."""
    session_id: str
    overall_score: float
    human_review_recommended: bool
    overall_assessment: str
    key_strengths_demonstrated: List[str]
    key_areas_for_development: List[str]
    actionable_next_steps: List[str]
    progress_notes_from_past_feedback: str

class EvaluationHandler(BaseHandler):
    """Handler for evaluation-related endpoints."""

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

        self._router.get("/sessions", response_model=SessionListResponse)(self.get_evaluation_sessions)
        self._router.get("/session/{session_id}/download")(self.download_session)
        self._router.post("/session/evaluate", response_model=EvaluationResponse)(self.evaluate_session)
        self._router.post("/session/{session_id}/evaluate", response_model=StructuredEvaluationResponse)(self.evaluate_session_structured)

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
    
    async def evaluate_session_structured(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
        content_loader: Annotated[ContentLoader, Depends(get_content_loader)],
        adk_session_service: Annotated[InMemorySessionService, Depends(get_adk_session_service)]
    ) -> StructuredEvaluationResponse:
        """Evaluate a roleplay session using the AI evaluator agent with structured output.
        
        Args:
            session_id: ID of the session to evaluate
            current_user: Authenticated user
            chat_logger: Chat logger instance
            content_loader: Content loader for scenario/character data
            adk_session_service: ADK session service for agent execution
            
        Returns:
            Structured evaluation results with FinalReviewReport
        """
        try:
            # Get session data in JSON format
            session_json = await chat_logger.export_session_text(
                user_id=current_user.id,
                session_id=session_id,
                format="json"
            )
            
            if session_json == "Session log file not found.":
                raise HTTPException(status_code=404, detail="Session not found")
            
            try:
                session_data = json.loads(session_json)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse session JSON: {e}")
                raise HTTPException(status_code=500, detail="Failed to parse session data")
            
            # Get user's language preference
            user_language = current_user.preferred_language
            
            # Load full scenario and character information
            scenario_id = session_data["scenario_info"]["id"]
            character_id = session_data["char_info"]["id"]
            
            if not scenario_id or not character_id:
                raise HTTPException(status_code=400, detail="Session missing scenario or character IDs")
            
            scenario_dict = content_loader.get_scenario_by_id(scenario_id, user_language)
            character_dict = content_loader.get_character_by_id(character_id, user_language)
            
            if not scenario_dict or not character_dict:
                raise HTTPException(status_code=400, detail="Scenario or character not found")
            
            # Build ChatInfo object with full information
            chat_info = ChatInfo(
                chat_language=user_language,
                chat_session_id=session_data["chat_session_id"],
                scenario_info=ScenarioInfo(
                    id=scenario_dict["id"],
                    name=scenario_dict["name"],
                    description=scenario_dict["description"],
                    compatible_character_count=len(scenario_dict.get("compatible_character_ids", []))
                ),
                goal=scenario_dict.get("goal", session_data["goal"]),
                char_info=CharacterInfo(
                    id=character_dict["id"],
                    name=character_dict["name"],
                    description=character_dict.get("description", "")
                ),
                transcript_text=session_data["transcript_text"],
                trainee_name=session_data["trainee_name"]
            )
            
            # Create evaluator agent with proper language and ChatInfo
            evaluator = create_evaluator_agent(
                language=user_language,
                chat_info=chat_info
            )
            
            # Create a unique evaluation session ID
            eval_session_id = f"eval_{session_id}"
            
            # Initialize ADK session for evaluation
            await adk_session_service.create_session(
                app_name="roleplay_evaluator",
                user_id=current_user.id,
                session_id=eval_session_id,
                state={
                    "chat_info": chat_info.dict(),
                    "user_language": user_language
                }
            )
            
            # Create runner with evaluator agent
            runner = Runner(
                app_name="roleplay_evaluator",
                agent=evaluator,
                session_service=adk_session_service
            )
            
            # Execute evaluation - send ChatInfo as structured data
            prompt = f"Please evaluate this roleplay session and provide a comprehensive review report."
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
            
            # Parse the response to extract FinalReviewReport
            # The evaluator agent should return a JSON structure we can parse
            try:
                # Look for JSON structure in the response
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    report_data = json.loads(json_match.group())
                    final_report = FinalReviewReport(**report_data)
                else:
                    # Fallback: create a basic report from the text response
                    final_report = FinalReviewReport(
                        chat_session_id=session_id,
                        overall_score=0.7,  # Default medium score
                        human_review_recommended=False,
                        overall_assessment=response_text[:500] if response_text else "Evaluation completed.",
                        key_strengths_demonstrated=["Session completed successfully"],
                        key_areas_for_development=["Continue practicing"],
                        actionable_next_steps=["Review the feedback", "Practice similar scenarios"],
                        progress_notes_from_past_feedback="First evaluation for this session."
                    )
            except Exception as parse_error:
                logger.error(f"Failed to parse evaluation response: {parse_error}")
                # Return a basic evaluation response
                final_report = FinalReviewReport(
                    chat_session_id=session_id,
                    overall_score=0.7,
                    human_review_recommended=False,
                    overall_assessment="Evaluation completed. The agent provided feedback but it could not be parsed into structured format.",
                    key_strengths_demonstrated=["Completed the roleplay session"],
                    key_areas_for_development=["Review the session transcript"],
                    actionable_next_steps=["Continue practicing", "Try different scenarios"],
                    progress_notes_from_past_feedback="Evaluation parsing error - please review manually."
                )
            
            return StructuredEvaluationResponse(
                success=True,
                session_id=session_id,
                overall_score=final_report.overall_score,
                human_review_recommended=final_report.human_review_recommended,
                overall_assessment=final_report.overall_assessment,
                key_strengths_demonstrated=final_report.key_strengths_demonstrated,
                key_areas_for_development=final_report.key_areas_for_development,
                actionable_next_steps=final_report.actionable_next_steps,
                progress_notes_from_past_feedback=final_report.progress_notes_from_past_feedback
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to evaluate session {session_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to evaluate session")