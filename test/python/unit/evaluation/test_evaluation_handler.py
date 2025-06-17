"""Unit tests for EvaluationHandler.evaluate_session method."""
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from fastapi import HTTPException

from role_play.evaluation.handler import (
    EvaluationHandler, 
    EvaluationRequest, 
    EvaluationResponse
)
from role_play.dev_agents.evaluator_agent.model import FinalReviewReport
from role_play.common.models import User, UserRole
from role_play.common.time_utils import utc_now_isoformat


class TestEvaluationHandlerEvaluateSession:
    """Test cases for EvaluationHandler.evaluate_session method."""

    @pytest.fixture
    def evaluation_handler(self):
        """Create EvaluationHandler instance."""
        return EvaluationHandler()

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        now = utc_now_isoformat()
        return User(
            id="test-user-123",
            username="testuser", 
            email="test@example.com",
            role=UserRole.USER,
            preferred_language="en",
            created_at=now,
            updated_at=now
        )

    @pytest.fixture
    def evaluation_request(self):
        """Create evaluation request."""
        return EvaluationRequest(
            session_id="test-session-123",
            evaluation_type="comprehensive"
        )

    @pytest.fixture
    def mock_chat_logger(self):
        """Create mock chat logger with valid session data."""
        logger = AsyncMock()
        
        # Valid ChatInfo JSON data with all required fields
        chat_info_data = {
            "chat_language": "en",
            "chat_session_id": "test-session-123",
            "scenario_info": {
                "id": "scenario-1",
                "name": "Pet Health Consultation",
                "description": "A veterinary consultation about pet health concerns",
                "compatible_character_count": 1
            },
            "goal": "Help the pet owner understand their pet's health issues",
            "char_info": {
                "id": "character-1", 
                "name": "Dr. Sarah Johnson",
                "description": "An experienced veterinarian with 15 years of practice"
            },
            "transcript_text": "Test conversation content",
            "participant_name": "Test User"
        }
        
        logger.export_session_text.return_value = json.dumps(chat_info_data)
        return logger

    @pytest.fixture
    def mock_adk_session_service(self):
        """Create mock ADK session service."""
        service = AsyncMock()
        
        # Mock successful session creation
        mock_session = Mock()
        mock_session.state = {
            "final_report": {
                "chat_session_id": "test-session-123",
                "overall_score": 0.85,
                "human_review_recommended": False,
                "overall_assessment": "Good performance overall",
                "key_strengths_demonstrated": ["Clear communication"],
                "key_areas_for_development": ["Ask more questions"],
                "actionable_next_steps": ["Practice active listening"],
                "progress_notes_from_past_feedback": "First evaluation"
            }
        }
        
        service.create_session.return_value = mock_session
        service.get_session.return_value = mock_session
        service.delete_session.return_value = None
        
        return service

    @pytest.fixture
    def mock_runner(self):
        """Create mock ADK runner."""
        runner = AsyncMock()
        
        # Mock async generator for run_async
        async def mock_run_async(*args, **kwargs):
            mock_event = Mock()
            mock_part = Mock()
            mock_part.text = "Evaluation in progress..."
            mock_event.content = Mock()
            mock_event.content.parts = [mock_part]
            yield mock_event
        
        runner.run_async = mock_run_async
        runner.close = AsyncMock()
        return runner

    @pytest.mark.asyncio
    async def test_evaluate_session_success(
        self, 
        evaluation_handler,
        evaluation_request,
        mock_user,
        mock_chat_logger,
        mock_adk_session_service,
        mock_runner
    ):
        """Test successful session evaluation."""
        with patch('role_play.evaluation.handler.create_evaluator_agent') as mock_create_agent, \
             patch('role_play.evaluation.handler.Runner') as mock_runner_class, \
             patch('role_play.evaluation.handler.utc_now_isoformat') as mock_time:
            
            mock_create_agent.return_value = Mock()
            mock_runner_class.return_value = mock_runner
            mock_time.return_value = "2024-01-01T12:00:00Z"
            
            response = await evaluation_handler.evaluate_session(
                request=evaluation_request,
                current_user=mock_user,
                chat_logger=mock_chat_logger,
                adk_session_service=mock_adk_session_service
            )
        
        # Verify response structure
        assert isinstance(response, EvaluationResponse)
        assert response.success is True
        assert response.session_id == "test-session-123"
        assert response.evaluation_type == "comprehensive"
        assert isinstance(response.report, FinalReviewReport)
        assert response.report.overall_score == 0.85
        assert response.report.human_review_recommended is False
        
        # Verify method calls
        mock_chat_logger.export_session_text.assert_called_once_with(
            user_id="test-user-123",
            session_id="test-session-123", 
            export_format="json"
        )
        
        mock_adk_session_service.create_session.assert_called_once_with(
            app_name=EvaluationHandler.ADK_APP_NAME,
            user_id="test-user-123",
            session_id="eval_test-session-123_2024-01-01T12:00:00Z",
            state={"chat_info": mock_chat_logger.export_session_text.return_value, "evaluation_type": "comprehensive"}
        )
        
        mock_adk_session_service.delete_session.assert_called_once()
        mock_runner.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_session_not_found(
        self,
        evaluation_handler,
        evaluation_request,
        mock_user,
        mock_adk_session_service
    ):
        """Test evaluation when session is not found."""
        mock_chat_logger = AsyncMock()
        mock_chat_logger.export_session_text.return_value = "Session log file not found."
        
        with pytest.raises(HTTPException) as exc_info:
            await evaluation_handler.evaluate_session(
                request=evaluation_request,
                current_user=mock_user,
                chat_logger=mock_chat_logger,
                adk_session_service=mock_adk_session_service
            )
        
        assert exc_info.value.status_code == 404
        assert "Session not found or access denied" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_evaluate_session_invalid_json(
        self,
        evaluation_handler,
        evaluation_request,
        mock_user,
        mock_adk_session_service
    ):
        """Test evaluation when session data is invalid JSON."""
        mock_chat_logger = AsyncMock()
        mock_chat_logger.export_session_text.return_value = "Invalid JSON data"
        
        with pytest.raises(HTTPException) as exc_info:
            await evaluation_handler.evaluate_session(
                request=evaluation_request,
                current_user=mock_user,
                chat_logger=mock_chat_logger,
                adk_session_service=mock_adk_session_service
            )
        
        assert exc_info.value.status_code == 500
        assert "Invalid session data format" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_evaluate_session_invalid_chat_info(
        self,
        evaluation_handler,
        evaluation_request,
        mock_user,
        mock_adk_session_service
    ):
        """Test evaluation when ChatInfo validation fails."""
        mock_chat_logger = AsyncMock()
        # Missing required fields for ChatInfo
        invalid_data = {"incomplete": "data"}
        mock_chat_logger.export_session_text.return_value = json.dumps(invalid_data)
        
        with pytest.raises(HTTPException) as exc_info:
            await evaluation_handler.evaluate_session(
                request=evaluation_request,
                current_user=mock_user,
                chat_logger=mock_chat_logger,
                adk_session_service=mock_adk_session_service
            )
        
        assert exc_info.value.status_code == 500
        assert "Invalid session data format" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_evaluate_session_missing_final_report(
        self,
        evaluation_handler,
        evaluation_request,
        mock_user,
        mock_chat_logger,
        mock_runner
    ):
        """Test evaluation when final report is missing from session state."""
        # Mock session service that returns session without final_report
        mock_adk_session_service = AsyncMock()
        mock_session = Mock()
        mock_session.state = {}  # No final_report key
        
        mock_adk_session_service.create_session.return_value = mock_session
        mock_adk_session_service.get_session.return_value = mock_session
        mock_adk_session_service.delete_session.return_value = None
        
        with patch('role_play.evaluation.handler.create_evaluator_agent') as mock_create_agent, \
             patch('role_play.evaluation.handler.Runner') as mock_runner_class:
            
            mock_create_agent.return_value = Mock()
            mock_runner_class.return_value = mock_runner
            
            with pytest.raises(HTTPException) as exc_info:
                await evaluation_handler.evaluate_session(
                    request=evaluation_request,
                    current_user=mock_user,
                    chat_logger=mock_chat_logger,
                    adk_session_service=mock_adk_session_service
                )
        
        assert exc_info.value.status_code == 500
        assert "Evaluation agent failed to generate report" in str(exc_info.value.detail)
        
        # Verify cleanup still happens
        mock_adk_session_service.delete_session.assert_called_once()
        mock_runner.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_session_invalid_report_format(
        self,
        evaluation_handler,
        evaluation_request,
        mock_user,
        mock_chat_logger,
        mock_runner
    ):
        """Test evaluation when final report format is invalid."""
        # Mock session service with invalid report format
        mock_adk_session_service = AsyncMock()
        mock_session = Mock()
        mock_session.state = {
            "final_report": {"invalid": "format"}  # Missing required FinalReviewReport fields
        }
        
        mock_adk_session_service.create_session.return_value = mock_session
        mock_adk_session_service.get_session.return_value = mock_session
        mock_adk_session_service.delete_session.return_value = None
        
        with patch('role_play.evaluation.handler.create_evaluator_agent') as mock_create_agent, \
             patch('role_play.evaluation.handler.Runner') as mock_runner_class:
            
            mock_create_agent.return_value = Mock()
            mock_runner_class.return_value = mock_runner
            
            with pytest.raises(HTTPException) as exc_info:
                await evaluation_handler.evaluate_session(
                    request=evaluation_request,
                    current_user=mock_user,
                    chat_logger=mock_chat_logger,
                    adk_session_service=mock_adk_session_service
                )
        
        assert exc_info.value.status_code == 500
        assert "Failed to parse evaluation report" in str(exc_info.value.detail)
        
        # Verify cleanup still happens
        mock_adk_session_service.delete_session.assert_called_once()
        mock_runner.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_session_cleanup_on_exception(
        self,
        evaluation_handler,
        evaluation_request,
        mock_user,
        mock_chat_logger,
        mock_runner
    ):
        """Test that cleanup happens even when exceptions occur."""
        # Mock session service that throws exception during evaluation
        mock_adk_session_service = AsyncMock()
        mock_adk_session_service.create_session.side_effect = Exception("ADK creation failed")
        mock_adk_session_service.delete_session.return_value = None
        
        with patch('role_play.evaluation.handler.create_evaluator_agent') as mock_create_agent, \
             patch('role_play.evaluation.handler.Runner') as mock_runner_class, \
             patch('role_play.evaluation.handler.utc_now_isoformat') as mock_time:
            
            mock_create_agent.return_value = Mock()
            mock_runner_class.return_value = mock_runner
            mock_time.return_value = "2024-01-01T12:00:00Z"
            
            with pytest.raises(HTTPException) as exc_info:
                await evaluation_handler.evaluate_session(
                    request=evaluation_request,
                    current_user=mock_user,
                    chat_logger=mock_chat_logger,
                    adk_session_service=mock_adk_session_service
                )
        
        assert exc_info.value.status_code == 500
        assert "Failed to evaluate session" in str(exc_info.value.detail)
        
        # Verify cleanup was attempted even though exception occurred
        # Note: delete_session won't be called because eval_session_id is None when exception occurs before creation
        mock_runner.close.assert_not_called()  # Runner wasn't created

    @pytest.mark.asyncio
    async def test_evaluate_session_cleanup_errors_logged(
        self,
        evaluation_handler,
        evaluation_request,
        mock_user,
        mock_chat_logger,
        mock_runner
    ):
        """Test that cleanup errors are properly logged."""
        # Mock session service where cleanup operations fail
        mock_adk_session_service = AsyncMock()
        mock_session = Mock()
        mock_session.state = {
            "final_report": {
                "chat_session_id": "test-session-123",
                "overall_score": 0.85,
                "human_review_recommended": False,
                "overall_assessment": "Test assessment",
                "key_strengths_demonstrated": ["Strength 1"],
                "key_areas_for_development": ["Area 1"],
                "actionable_next_steps": ["Step 1"],
                "progress_notes_from_past_feedback": "Notes"
            }
        }
        
        mock_adk_session_service.create_session.return_value = mock_session
        mock_adk_session_service.get_session.return_value = mock_session
        # Make cleanup operations fail
        mock_adk_session_service.delete_session.side_effect = Exception("Cleanup failed")
        mock_runner.close.side_effect = Exception("Runner close failed")
        
        with patch('role_play.evaluation.handler.create_evaluator_agent') as mock_create_agent, \
             patch('role_play.evaluation.handler.Runner') as mock_runner_class, \
             patch('role_play.evaluation.handler.logger') as mock_logger:
            
            mock_create_agent.return_value = Mock()
            mock_runner_class.return_value = mock_runner
            
            # Should still succeed despite cleanup errors
            response = await evaluation_handler.evaluate_session(
                request=evaluation_request,
                current_user=mock_user,
                chat_logger=mock_chat_logger,
                adk_session_service=mock_adk_session_service
            )
        
        assert response.success is True
        
        # Verify cleanup errors were logged
        assert mock_logger.error.call_count >= 1
        error_calls = [call for call in mock_logger.error.call_args_list if "cleanup" in str(call) or "close" in str(call)]
        assert len(error_calls) >= 1

    @pytest.mark.asyncio
    async def test_evaluate_session_runner_without_close_method(
        self,
        evaluation_handler,
        evaluation_request, 
        mock_user,
        mock_chat_logger,
        mock_adk_session_service
    ):
        """Test cleanup when runner doesn't have close method."""
        # Mock runner without close method  
        mock_runner = Mock()  # Use regular Mock instead of AsyncMock
        
        async def mock_run_async(*args, **kwargs):
            mock_event = Mock()
            mock_part = Mock()
            mock_part.text = "Evaluation complete"
            mock_event.content = Mock()
            mock_event.content.parts = [mock_part]
            yield mock_event
        
        mock_runner.run_async = mock_run_async
        # Explicitly ensure no close method exists
        del mock_runner.close  # Remove any auto-created close method
        
        with patch('role_play.evaluation.handler.create_evaluator_agent') as mock_create_agent, \
             patch('role_play.evaluation.handler.Runner') as mock_runner_class:
            
            mock_create_agent.return_value = Mock()
            mock_runner_class.return_value = mock_runner
            
            # Should succeed without trying to call close
            response = await evaluation_handler.evaluate_session(
                request=evaluation_request,
                current_user=mock_user,
                chat_logger=mock_chat_logger,
                adk_session_service=mock_adk_session_service
            )
        
        assert response.success is True
        # Verify no close method exists or was called
        assert not hasattr(mock_runner, 'close')