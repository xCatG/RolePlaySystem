"""Evaluation handler for session analysis and export."""
from typing import List
from pathlib import Path
from fastapi import HTTPException, Depends, APIRouter
from fastapi.responses import PlainTextResponse, FileResponse
from ..server.base_handler import BaseHandler
from ..server.auth_decorators import auth_required
from ..common.auth import TokenData
from ..common.models import BaseResponse
from .export import ExportUtility
import logging

logger = logging.getLogger(__name__)

class SessionSummary(BaseResponse):
    """Summary of a session available for evaluation."""
    session_id: str
    participant: str
    scenario: str
    character: str
    message_count: int
    started: str
    jsonl_filename: str

class SessionListResponse(BaseResponse):
    """Response containing list of sessions for evaluation."""
    sessions: List[SessionSummary]

class EvaluationHandler(BaseHandler):
    """Handler for evaluation-related endpoints."""

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

        self._router.get("/sessions", response_model=SessionListResponse)(self.get_evaluation_sessions)
        self._router.get("/session/{session_id}/download")(self.download_session)

        return self._router

    @property
    def prefix(self) -> str:
        return "/eval"

    def __init__(self):
        """Initialize evaluation handler."""
        super().__init__()
        self.sessions_path = Path("./storage/sessions")
        self.sessions_path.mkdir(parents=True, exist_ok=True)
        self.export_util = ExportUtility()
    
    @auth_required
    async def get_evaluation_sessions(
        self, 
        token_data: TokenData = Depends()
    ) -> SessionListResponse:
        """Get all sessions available for evaluation.
        
        Args:
            token_data: Authenticated user token data
            
        Returns:
            List of sessions ready for evaluation
        """
        try:
            sessions = []
            
            # Find all JSONL files for this user
            pattern = f"{token_data.user_id}_*.jsonl"
            for jsonl_file in self.sessions_path.glob(pattern):
                try:
                    # Get summary from JSONL
                    summary = self.export_util.get_session_summary(jsonl_file)
                    
                    if summary["session_id"]:
                        sessions.append(SessionSummary(
                            success=True,
                            session_id=summary["session_id"],
                            participant=summary["participant"] or "Unknown",
                            scenario=summary["scenario"] or "Unknown",
                            character=summary["character"] or "Unknown",
                            message_count=summary["message_count"],
                            started=summary["started"] or "Unknown",
                            jsonl_filename=jsonl_file.name
                        ))
                except Exception as e:
                    logger.warning(f"Failed to process file {jsonl_file}: {e}")
                    continue
            
            # Sort by start time (newest first)
            sessions.sort(key=lambda s: s.started, reverse=True)
            
            return SessionListResponse(
                success=True,
                sessions=sessions
            )
            
        except Exception as e:
            logger.error(f"Failed to get evaluation sessions: {e}")
            raise HTTPException(status_code=500, detail="Failed to get sessions")
    
    @auth_required
    async def download_session(
        self,
        session_id: str,
        token_data: TokenData = Depends()
    ):
        """Download session transcript as text file.
        
        Args:
            session_id: ID of the session to download
            token_data: Authenticated user token data
            
        Returns:
            Text file download response
        """
        try:
            # Find the JSONL file for this session
            jsonl_file = None
            pattern = f"{token_data.user_id}_*.jsonl"
            
            for file_path in self.sessions_path.glob(pattern):
                try:
                    # Check if this file contains the requested session
                    with open(file_path, 'r') as f:
                        first_line = f.readline()
                        if first_line:
                            import json
                            entry = json.loads(first_line)
                            if entry.get("session_id") == session_id:
                                jsonl_file = file_path
                                break
                except:
                    continue
            
            if not jsonl_file:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Convert to text
            text_content = self.export_util.jsonl_to_text(jsonl_file)
            
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