"""Evaluation handler for session analysis and export."""
import logging
import yaml
from typing import List, Annotated, Optional, Dict, Any

from fastapi import HTTPException, Depends, APIRouter, BackgroundTasks, Request as FastAPIRequest
from fastapi.responses import PlainTextResponse, JSONResponse
# from google.adk.runners import Runner # Not used in new version
# from google.adk.sessions import InMemorySessionService # Not used in new version
# from google.genai.types import Content, Part # Not used in new version
from pydantic import BaseModel, Field

from ..chat.chat_logger import ChatLogger
from ..common.models import BaseResponse, User
# from ..dev_agents.evaluator_agent.agent import evaluator_agent # Assuming this is replaced
from ..server.base_handler import BaseHandler
from ..server.dependencies import require_user_or_higher, get_chat_logger #, get_adk_session_service # Not used in new version

# New imports for evaluation agents and models
from src.python.role_play.evaluation.agents import ReviewCoordinatorAgent, SpecializedReviewAgent, LlmAgent
from src.python.role_play.evaluation.models import FinalReviewReport # SkillScore, ConfidenceScore are enums, SpecializedAssessment is used by agents

logger = logging.getLogger(__name__)

# In-memory store for evaluation status (replace with persistent store in production)
EVALUATION_STATUS_STORE: Dict[str, Any] = {}


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


# New Pydantic models for request/response
class EvaluationSubmitRequest(BaseModel):
    user_id: str = Field(description="User ID for the session being evaluated.")
    scenario_id: str = Field(description="Scenario ID for context.")
    # session_id is now a path parameter for /request endpoint

class EvaluationRequestResponse(BaseResponse):
    """Response after submitting an evaluation request."""
    session_id: str
    status: str = Field(default="pending", description="Initial status of the evaluation.")
    message: str


class EvaluationStatusResponse(BaseResponse):
    """Response containing the status or result of an evaluation."""
    session_id: str
    status: str = Field(description="Current status: pending, processing, completed, error.")
    report: Optional[FinalReviewReport] = Field(default=None, description="The final evaluation report if status is 'completed'.")
    error_message: Optional[str] = Field(default=None, description="Error message if status is 'error'.")


def _load_evaluation_agents(config_path: str = "config/evaluation_agents.yaml") -> List[LlmAgent]:
    """Loads specialized review agents based on YAML configuration."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            agent_configs = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Agent configuration file not found: {config_path}")
        return []
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {e}")
        return []

    specialized_agents = []
    for agent_conf in agent_configs.get("agents", []):
        specialized_agents.append(SpecializedReviewAgent(config=agent_conf))
    return specialized_agents

async def run_evaluation_in_background(session_id: str, user_id: str, scenario_id: str):
    """
    The actual evaluation process that runs in the background.
    Fetches data, runs ReviewCoordinatorAgent, and stores the result.
    """
    EVALUATION_STATUS_STORE[session_id] = {"status": "processing", "report": None, "error_message": None}
    logger.info(f"Starting background evaluation for session_id: {session_id}")
    try:
        # TODO: Replace with actual config loading for ReviewCoordinatorAgent if needed
        coordinator_config = {"name": "ReviewCoordinatorAgent"}

        specialized_agents = _load_evaluation_agents()
        if not specialized_agents:
            logger.error("No specialized agents loaded, aborting evaluation.")
            EVALUATION_STATUS_STORE[session_id] = {"status": "error", "report": None, "error_message": "Failed to load specialized agents."}
            return

        coordinator = ReviewCoordinatorAgent(config=coordinator_config, specialized_agents=specialized_agents)

        # The ReviewCoordinatorAgent's process method already handles storing the final review.
        # It returns a dict with {"status": "success", "report_id": session_id}
        # The actual report is stored via store_final_review within the coordinator.
        # We need to fetch it or rely on the fact that it's stored.
        # For now, we assume store_final_review makes it accessible via session_id.

        result = coordinator.process(session_id=session_id, user_id=user_id, scenario_id=scenario_id)

        if result.get("status") == "success":
            # Attempt to retrieve the stored report (placeholder, replace with actual retrieval if store_final_review doesn't update a shared store)
            # For now, we'll assume the report structure is available directly or via another call.
            # This part might need adjustment based on how store_final_review and data retrieval are implemented.
            # We'll update the status to completed. The actual report retrieval is handled by the GET endpoint.
            logger.info(f"Evaluation completed for session_id: {session_id}. Report ID: {result.get('report_id')}")
            EVALUATION_STATUS_STORE[session_id] = {"status": "completed", "report": None, "error_message": None} # Report fetched by GET
        else:
            logger.error(f"Evaluation failed for session_id: {session_id}. Result: {result}")
            EVALUATION_STATUS_STORE[session_id] = {"status": "error", "report": None, "error_message": result.get("message", "Unknown error during processing.")}

    except Exception as e:
        logger.error(f"Exception during background evaluation for session {session_id}: {e}", exc_info=True)
        EVALUATION_STATUS_STORE[session_id] = {"status": "error", "report": None, "error_message": str(e)}


class EvaluationHandler(BaseHandler):
    """Handler for evaluation-related endpoints."""

    def __init__(self):
        super().__init__()
        self._specialized_agents = _load_evaluation_agents()
        # TODO: Initialize ReviewCoordinatorAgent. For now, it's created on-demand in the background task.

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

        self._router.get("/sessions", response_model=SessionListResponse)(self.get_evaluation_sessions)
        self._router.get("/session/{session_id}/download")(self.download_session)
        # New Endpoints
        self._router.post("/api/v1/eval/{session_id}/request", response_model=EvaluationRequestResponse)(self.request_evaluation)
        self._router.get("/api/v1/eval/{session_id}", response_model=EvaluationStatusResponse)(self.get_evaluation_status)

        # self._router.post("/session/evaluate", response_model=EvaluationResponse)(self.evaluate_session) # Old endpoint, can be removed or deprecated

        return self._router

    @property
    def prefix(self) -> str:
        # Prefix for the entire handler, adjust if new endpoints have a different root
        return "/eval"
    
    async def get_evaluation_sessions(
        self, 
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)]
    ) -> SessionListResponse:
        """Get all sessions available for evaluation. (Kept from original)"""
        try:
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
            return SessionListResponse(success=True, sessions=sessions)
        except Exception as e:
            logger.error(f"Failed to get evaluation sessions: {e}")
            raise HTTPException(status_code=500, detail="Failed to get sessions")
    
    async def download_session(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)]
    ):
        """Download session transcript as text file. (Kept from original)"""
        try:
            text_content = await chat_logger.export_session_text(user_id=current_user.id, session_id=session_id)
            if text_content == "Session log file not found.":
                raise HTTPException(status_code=404, detail="Session not found")
            return PlainTextResponse(
                content=text_content,
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=transcript_{session_id}.txt"}
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to download session: {e}")
            raise HTTPException(status_code=500, detail="Failed to download session")

    async def request_evaluation(
        self,
        session_id: str,
        request_data: EvaluationSubmitRequest,
        background_tasks: BackgroundTasks,
        current_user: Annotated[User, Depends(require_user_or_higher)] # Assuming user needs to be authenticated
    ) -> EvaluationRequestResponse:
        """
        Submits a session for evaluation. The actual evaluation runs in the background.
        """
        # Check if session_id exists or is valid (e.g., using chat_logger)
        # For now, assume chat_logger can verify session_id or it's done elsewhere.
        # session_details = await chat_logger.get_session_details(request_data.user_id, session_id) # Example
        # if not session_details:
        #     raise HTTPException(status_code=404, detail=f"Session {session_id} not found for user {request_data.user_id}")

        if session_id in EVALUATION_STATUS_STORE and EVALUATION_STATUS_STORE[session_id]["status"] in ["pending", "processing"]:
            raise HTTPException(status_code=409, detail=f"Evaluation for session {session_id} is already in progress.")

        logger.info(f"Received evaluation request for session_id: {session_id}, user_id: {request_data.user_id}, scenario_id: {request_data.scenario_id}")
        
        EVALUATION_STATUS_STORE[session_id] = {"status": "pending", "report": None, "error_message": None}
        background_tasks.add_task(
            run_evaluation_in_background,
            session_id,
            request_data.user_id,
            request_data.scenario_id
        )

        return EvaluationRequestResponse(
            success=True,
            session_id=session_id,
            status="pending",
            message="Evaluation request received and scheduled for processing."
        )

    async def get_evaluation_status(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)] # Assuming user needs to be authenticated
    ) -> EvaluationStatusResponse:
        """
        Retrieves the status or result of an evaluation for a given session_id.
        """
        status_info = EVALUATION_STATUS_STORE.get(session_id)
        if not status_info:
            raise HTTPException(status_code=404, detail=f"Evaluation status for session {session_id} not found.")

        report_data = None
        if status_info["status"] == "completed":
            # TODO: This is where you'd retrieve the actual FinalReviewReport.
            # The current `run_evaluation_in_background` doesn't place the report directly into EVALUATION_STATUS_STORE.
            # It calls `store_final_review` which would save it to a DB.
            # For this example, we'll assume it could be fetched or that `store_final_review`
            # could update a more sophisticated shared cache/DB that this endpoint reads from.
            # Placeholder:
            # report_data = get_final_review_report_from_datastore(session_id) # This function needs to be implemented
            # If report_data is None, it means it's completed but report not found (should not happen ideally)
            # For now, we'll return None for the report as the current structure doesn't populate it here.
            # A more robust solution would involve a proper data store.
            logger.info(f"Fetching completed report for session {session_id}. Current store holds status only.")
            # This is a simplification. In a real system, you'd fetch the report from where store_final_review saved it.
            # For demonstration, let's assume store_final_review also updates a part of EVALUATION_STATUS_STORE or a similar cache.
            # If `store_final_review` in `agents.py` were to update a shared dict:
            # e.g. FINAL_REPORTS_CACHE[session_id] = final_report.dict()
            # Then here: report_dict = FINAL_REPORTS_CACHE.get(session_id)
            # if report_dict: report_data = FinalReviewReport(**report_dict)

            # For now, we'll just indicate it's completed. The actual report content is a TODO for robust storage/retrieval.
            pass


        return EvaluationStatusResponse(
            success=True, # Or determine based on status
            session_id=session_id,
            status=status_info["status"],
            report=report_data, # This will be None for now as per above comments
            error_message=status_info.get("error_message")
        )

    # The old evaluate_session method can be commented out or removed
    # async def evaluate_session( ... ) -> EvaluationResponse: ...