"""Unit tests for new evaluation API endpoints."""
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.testclient import TestClient
from fastapi import FastAPI

from role_play.evaluation.handler import (
    EvaluationHandler,
    StoredEvaluationReport,
    EvaluationReportListResponse,
    EvaluationReportSummary
)
from role_play.dev_agents.evaluator_agent.model import FinalReviewReport
from role_play.common.models import User, UserRole
from role_play.common.time_utils import utc_now_isoformat


class TestEvaluationEndpoints:
    """Test cases for new evaluation API endpoints."""

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
    def mock_storage(self):
        """Create mock storage backend."""
        storage = AsyncMock()
        storage.write = AsyncMock()
        storage.read = AsyncMock()
        storage.list_keys = AsyncMock()
        return storage

    @pytest.fixture
    def sample_report_data(self):
        """Sample evaluation report data."""
        return {
            "eval_session_id": "eval_test-session_2024-01-01T12_00_00Z_abcd1234",
            "chat_session_id": "test-session-123",
            "user_id": "test-user-123",
            "created_at": "2024-01-01T12:00:00Z",
            "evaluation_type": "comprehensive",
            "report": {
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

    @pytest.mark.asyncio
    async def test_get_latest_report_success(
        self,
        evaluation_handler,
        mock_user,
        mock_storage,
        sample_report_data
    ):
        """Test successfully getting the latest report."""
        mock_storage.list_keys.return_value = [
            "users/test-user-123/eval_reports/test-session-123/2024-01-01T10_00_00Z_xyz789",
            "users/test-user-123/eval_reports/test-session-123/2024-01-01T12_00_00Z_abcd1234"
        ]
        mock_storage.read.return_value = json.dumps(sample_report_data)

        response = await evaluation_handler.get_latest_report_endpoint(
            session_id="test-session-123",
            current_user=mock_user,
            storage=mock_storage
        )

        assert isinstance(response, StoredEvaluationReport)
        assert response.success is True
        assert response.report_id == "2024-01-01T12_00_00Z_abcd1234"
        assert response.chat_session_id == "test-session-123"
        assert response.report.overall_score == 0.85

    @pytest.mark.asyncio
    async def test_get_latest_report_not_found(
        self,
        evaluation_handler,
        mock_user,
        mock_storage
    ):
        """Test getting latest report when none exists."""
        mock_storage.list_keys.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await evaluation_handler.get_latest_report_endpoint(
                session_id="test-session-123",
                current_user=mock_user,
                storage=mock_storage
            )

        assert exc_info.value.status_code == 404
        assert "No evaluation report found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_all_reports_success(
        self,
        evaluation_handler,
        mock_user,
        mock_storage,
        sample_report_data
    ):
        """Test listing all reports for a session."""
        mock_storage.list_keys.return_value = [
            "users/test-user-123/eval_reports/test-session-123/2024-01-01T10_00_00Z_xyz789",
            "users/test-user-123/eval_reports/test-session-123/2024-01-01T12_00_00Z_abcd1234"
        ]
        
        # Return different reports for each read
        older_report = sample_report_data.copy()
        older_report["created_at"] = "2024-01-01T10:00:00Z"
        
        mock_storage.read.side_effect = [
            json.dumps(older_report),
            json.dumps(sample_report_data)
        ]

        response = await evaluation_handler.list_all_reports(
            session_id="test-session-123",
            current_user=mock_user,
            storage=mock_storage
        )

        assert isinstance(response, EvaluationReportListResponse)
        assert response.success is True
        assert len(response.reports) == 2
        # Should be sorted newest first
        assert response.reports[0].report_id == "2024-01-01T12_00_00Z_abcd1234"
        assert response.reports[1].report_id == "2024-01-01T10_00_00Z_xyz789"

    @pytest.mark.asyncio
    async def test_list_all_reports_empty(
        self,
        evaluation_handler,
        mock_user,
        mock_storage
    ):
        """Test listing reports when none exist."""
        mock_storage.list_keys.return_value = []

        response = await evaluation_handler.list_all_reports(
            session_id="test-session-123",
            current_user=mock_user,
            storage=mock_storage
        )

        assert isinstance(response, EvaluationReportListResponse)
        assert response.success is True
        assert len(response.reports) == 0

    @pytest.mark.asyncio
    async def test_get_report_by_id_success(
        self,
        evaluation_handler,
        mock_user,
        mock_storage,
        sample_report_data
    ):
        """Test getting a specific report by ID."""
        mock_storage.list_keys.return_value = [
            "users/test-user-123/eval_reports/test-session-123/2024-01-01T12_00_00Z_abcd1234"
        ]
        mock_storage.read.return_value = json.dumps(sample_report_data)

        response = await evaluation_handler.get_report_by_id_endpoint(
            report_id="2024-01-01T12_00_00Z_abcd1234",
            current_user=mock_user,
            storage=mock_storage
        )

        assert isinstance(response, StoredEvaluationReport)
        assert response.success is True
        assert response.report_id == "2024-01-01T12_00_00Z_abcd1234"
        assert response.report.overall_score == 0.85

    @pytest.mark.asyncio
    async def test_get_report_by_id_not_found(
        self,
        evaluation_handler,
        mock_user,
        mock_storage
    ):
        """Test getting report by ID when it doesn't exist."""
        mock_storage.list_keys.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await evaluation_handler.get_report_by_id_endpoint(
                report_id="nonexistent-report",
                current_user=mock_user,
                storage=mock_storage
            )

        assert exc_info.value.status_code == 404
        assert "Report not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_new_evaluation(
        self,
        evaluation_handler,
        mock_user,
        mock_storage
    ):
        """Test creating a new evaluation."""
        mock_chat_logger = AsyncMock()
        mock_adk_session_service = AsyncMock()
        
        # Mock the evaluate_session method
        with patch.object(evaluation_handler, 'evaluate_session') as mock_evaluate:
            mock_response = Mock()
            mock_response.success = True
            mock_response.session_id = "test-session-123"
            mock_response.evaluation_type = "comprehensive"
            mock_response.report = Mock()
            mock_evaluate.return_value = mock_response

            response = await evaluation_handler.create_new_evaluation(
                session_id="test-session-123",
                evaluation_type="comprehensive",
                current_user=mock_user,
                chat_logger=mock_chat_logger,
                adk_session_service=mock_adk_session_service,
                storage=mock_storage
            )

            # Verify evaluate_session was called with correct parameters
            mock_evaluate.assert_called_once()
            call_args = mock_evaluate.call_args[0]
            assert call_args[0].session_id == "test-session-123"
            assert call_args[0].evaluation_type == "comprehensive"
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_get_latest_report_storage_error(
        self,
        evaluation_handler,
        mock_user,
        mock_storage
    ):
        """Test handling storage errors when getting latest report."""
        mock_storage.list_keys.side_effect = Exception("Storage error")

        # Should return None instead of raising exception
        result = await evaluation_handler._get_latest_report(
            user_id="test-user-123",
            session_id="test-session-123",
            storage=mock_storage
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_list_reports_with_read_error(
        self,
        evaluation_handler,
        mock_user,
        mock_storage,
        sample_report_data
    ):
        """Test listing reports when some reads fail."""
        mock_storage.list_keys.return_value = [
            "users/test-user-123/eval_reports/test-session-123/2024-01-01T10_00_00Z_xyz789",
            "users/test-user-123/eval_reports/test-session-123/2024-01-01T12_00_00Z_abcd1234"
        ]
        
        # First read fails, second succeeds
        mock_storage.read.side_effect = [
            Exception("Read error"),
            json.dumps(sample_report_data)
        ]

        reports = await evaluation_handler._list_reports(
            user_id="test-user-123",
            session_id="test-session-123",
            storage=mock_storage
        )

        # Should skip the failed read and return the successful one
        assert len(reports) == 1
        assert reports[0].report_id == "2024-01-01T10_00_00Z_xyz789"