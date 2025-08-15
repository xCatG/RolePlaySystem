"""Evaluation handler for session analysis and export."""
import json
import logging
from typing import List, Annotated, Optional, Dict, Any

from fastapi import HTTPException, Depends, APIRouter
from fastapi.responses import PlainTextResponse
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.genai.types import Content, Part
from pydantic import BaseModel

from ..chat.chat_logger import ChatLogger
from ..common.models import BaseResponse, User
from ..common.time_utils import utc_now_isoformat
import uuid
from ..dev_agents.evaluator_agent.agent import create_evaluator_agent
from ..dev_agents.evaluator_agent.model import FinalReviewReport
from ..chat.models import ChatInfo
from ..server.base_handler import BaseHandler
from ..server.dependencies import require_user_or_higher, get_chat_logger, get_adk_session_service, get_storage_backend
from ..common.storage import StorageBackend

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

class EvaluationReportSummary(BaseModel):
    """Summary of an evaluation report."""
    report_id: str
    chat_session_id: str
    created_at: str
    evaluation_type: str

class EvaluationReportListResponse(BaseResponse):
    """Response containing list of evaluation reports."""
    reports: List[EvaluationReportSummary]
    
class StoredEvaluationReport(BaseResponse):
    """Full evaluation report with metadata."""
    report_id: str
    chat_session_id: str
    created_at: str
    evaluation_type: str
    report: FinalReviewReport

class EvaluationHandler(BaseHandler):
    """Handler for evaluation-related endpoints."""

    ADK_APP_NAME="roleplay_evaluator"
    
    async def _get_latest_report(
        self, 
        user_id: str, 
        session_id: str, 
        storage: StorageBackend
    ) -> Optional[Dict[str, Any]]:
        """Get the latest evaluation report for a session.
        
        Handles race conditions where a report might be deleted between listing
        and reading by trying the next most recent report.
        
        Returns:
            Report data dict if found, None if no reports exist or all reads failed
        """
        try:
            reports_prefix = f"users/{user_id}/eval_reports/{session_id}/"
            report_keys = await storage.list_keys(reports_prefix)
            
            if not report_keys:
                return None
            
            # Sort by key (timestamp is part of the key) and get latest
            sorted_keys = sorted(report_keys, reverse=True)
            
            # Try to read reports in order, handling race conditions
            for i, key in enumerate(sorted_keys):
                try:
                    report_json = await storage.read(key)
                    report_data = json.loads(report_json)
                    
                    # Extract report ID from the path
                    report_id = key.split('/')[-1]
                    report_data['report_id'] = report_id
                    
                    return report_data
                    
                except Exception as read_error:
                    # Log the race condition or read failure
                    logger.warning(
                        f"Failed to read report {key} (attempt {i+1}/{len(sorted_keys)}): {read_error}. "
                        f"Possible race condition - report may have been deleted."
                    )
                    # Continue to try the next most recent report
                    continue
            
            # If we exhausted all keys without success, it's a server error
            logger.error(
                f"Failed to read any evaluation report for session {session_id} after {len(sorted_keys)} attempts. "
                f"All reads failed, indicating a storage issue or race condition."
            )
            # Return None here to let the caller handle it as 500, not 404
            return None
            
        except Exception as e:
            logger.error(f"Failed to list evaluation reports: {e}")
            return None
    
    async def _list_reports(
        self, 
        user_id: str, 
        session_id: str, 
        storage: StorageBackend
    ) -> List[EvaluationReportSummary]:
        """List all evaluation reports for a session."""
        try:
            reports_prefix = f"users/{user_id}/eval_reports/{session_id}/"
            report_keys = await storage.list_keys(reports_prefix)
            
            reports = []
            for key in sorted(report_keys, reverse=True):  # Newest first
                try:
                    report_json = await storage.read(key)
                    report_data = json.loads(report_json)
                    
                    # Extract report ID from the path
                    report_id = key.split('/')[-1]
                    
                    reports.append(EvaluationReportSummary(
                        report_id=report_id,
                        chat_session_id=session_id,
                        created_at=report_data.get('created_at', ''),
                        evaluation_type=report_data.get('evaluation_type', 'comprehensive')
                    ))
                except Exception as e:
                    logger.error(f"Failed to read report {key}: {e}")
                    continue
            
            return reports
            
        except Exception as e:
            logger.error(f"Failed to list reports: {e}")
            return []
    
    async def _get_report_by_id(
        self, 
        user_id: str, 
        report_id: str, 
        storage: StorageBackend
    ) -> Optional[Dict[str, Any]]:
        """Get a specific evaluation report by ID."""
        try:
            # Find the report by searching all user's reports
            user_reports_prefix = f"users/{user_id}/eval_reports/"
            report_keys = await storage.list_keys(user_reports_prefix)
            
            for key in report_keys:
                if key.endswith(report_id):
                    report_json = await storage.read(key)
                    report_data = json.loads(report_json)
                    report_data['report_id'] = report_id
                    return report_data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get report by ID: {e}")
            return None

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

        # New API design endpoints
        self._router.get("/session/{session_id}/report", response_model=StoredEvaluationReport)(self.get_latest_report_endpoint)
        self._router.post("/session/{session_id}/evaluate", response_model=EvaluationResponse)(self.create_new_evaluation)
        self._router.get("/session/{session_id}/all_reports", response_model=EvaluationReportListResponse)(self.list_all_reports)
        self._router.get("/reports/{report_id}", response_model=StoredEvaluationReport)(self.get_report_by_id_endpoint)

        return self._router

    @property
    def prefix(self) -> str:
        return "/eval"
    

    async def evaluate_session(
        self,
        request: EvaluationRequest,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)],
        adk_session_service: Annotated[BaseSessionService, Depends(get_adk_session_service)],
        storage: Annotated[StorageBackend, Depends(get_storage_backend)]
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
            
            # Create unique evaluation session ID with timestamp
            timestamp = utc_now_isoformat()
            # Replace colons with underscores for filesystem compatibility
            safe_timestamp = timestamp.replace(':', '_')
            unique_id = str(uuid.uuid4())[:8]
            eval_session_id = f"eval_{request.session_id}_{safe_timestamp}_{unique_id}"
            
            # Generate storage path for this evaluation
            storage_id = f"{safe_timestamp}_{unique_id}"  # Format: 2024-01-10T12_34_56.789Z_abcd1234
            
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

            # Store the evaluation report
            report_path = f"users/{current_user.id}/eval_reports/{request.session_id}/{storage_id}"
            report_data = {
                "eval_session_id": eval_session_id,
                "chat_session_id": request.session_id,
                "user_id": current_user.id,
                "created_at": timestamp,
                "evaluation_type": request.evaluation_type,
                "report": report_response.model_dump(mode="json")
            }
            
            try:
                await storage.write(report_path, json.dumps(report_data, sort_keys=True))
                logger.info(f"Stored evaluation report at {report_path}")
            except Exception as store_err:
                # Log error but don't fail the request since report was generated
                logger.error(f"Failed to store evaluation report: {store_err}")
            
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
    
    async def get_latest_report_endpoint(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        storage: Annotated[StorageBackend, Depends(get_storage_backend)]
    ) -> StoredEvaluationReport:
        """Get the latest evaluation report for a session, or 404 if none exists."""
        # First check if any reports exist
        reports_prefix = f"users/{current_user.id}/eval_reports/{session_id}/"
        try:
            report_keys = await storage.list_keys(reports_prefix)
            if not report_keys:
                # No reports exist - return 404
                raise HTTPException(status_code=404, detail="No evaluation report found for this session")
        except HTTPException:
            # Re-raise HTTP exceptions (like 404) without wrapping them
            raise
        except Exception as e:
            logger.error(f"Failed to list reports for session {session_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to access evaluation reports")
        
        # Reports exist, try to get the latest one
        report_data = await self._get_latest_report(current_user.id, session_id, storage)
        
        if not report_data:
            # We know reports exist but couldn't read any - this is a 500 error
            raise HTTPException(
                status_code=500, 
                detail="Failed to read evaluation reports. Possible storage issue or concurrent deletion."
            )
        
        return StoredEvaluationReport(
            success=True,
            report_id=report_data['report_id'],
            chat_session_id=report_data['chat_session_id'],
            created_at=report_data['created_at'],
            evaluation_type=report_data['evaluation_type'],
            report=FinalReviewReport(**report_data['report'])
        )
    
    async def create_new_evaluation(
        self,
        session_id: str,
        evaluation_type: str = "comprehensive",
        current_user: Annotated[User, Depends(require_user_or_higher)] = None,
        chat_logger: Annotated[ChatLogger, Depends(get_chat_logger)] = None,
        adk_session_service: Annotated[BaseSessionService, Depends(get_adk_session_service)] = None,
        storage: Annotated[StorageBackend, Depends(get_storage_backend)] = None
    ) -> EvaluationResponse:
        """Create a new evaluation for a session (always generates a new report)."""
        # Create evaluation request from path parameter
        request = EvaluationRequest(
            session_id=session_id,
            evaluation_type=evaluation_type
        )
        
        # Call the existing evaluate_session method
        return await self.evaluate_session(request, current_user, chat_logger, adk_session_service, storage)
    
    async def list_all_reports(
        self,
        session_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        storage: Annotated[StorageBackend, Depends(get_storage_backend)]
    ) -> EvaluationReportListResponse:
        """List all evaluation reports for a session."""
        reports = await self._list_reports(current_user.id, session_id, storage)
        
        return EvaluationReportListResponse(
            success=True,
            reports=reports
        )
    
    async def get_report_by_id_endpoint(
        self,
        report_id: str,
        current_user: Annotated[User, Depends(require_user_or_higher)],
        storage: Annotated[StorageBackend, Depends(get_storage_backend)]
    ) -> StoredEvaluationReport:
        """Get a specific evaluation report by ID."""
        report_data = await self._get_report_by_id(current_user.id, report_id, storage)
        
        if not report_data:
            raise HTTPException(status_code=404, detail="Report not found")
        
        return StoredEvaluationReport(
            success=True,
            report_id=report_data['report_id'],
            chat_session_id=report_data['chat_session_id'],
            created_at=report_data['created_at'],
            evaluation_type=report_data['evaluation_type'],
            report=FinalReviewReport(**report_data['report'])
        )