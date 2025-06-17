"""Tests for the evaluation handler."""
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from role_play.evaluation.handler import EvaluationHandler, StructuredEvaluationResponse
from role_play.common.models import User, UserRole
from role_play.chat.models import Message
from role_play.common.time_utils import utc_now_isoformat


@pytest.fixture
def evaluation_handler():
    """Create an evaluation handler instance."""
    return EvaluationHandler()


@pytest.fixture
def mock_user():
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
def mock_chat_logger():
    """Create a mock chat logger."""
    logger = AsyncMock()
    
    # Mock session data in JSON format
    session_data = {
        "chat_language": "en",
        "chat_session_id": "test-session-123",
        "scenario_info": {
            "id": "scenario-1",
            "name": "Pet Health Consultation",
            "description": "",
            "compatible_character_count": 1
        },
        "goal": "Help the pet owner understand their pet's health issues",
        "char_info": {
            "id": "character-1",
            "name": "Dr. Sarah Johnson",
            "description": ""
        },
        "transcript_text": "Test User: Hello, I need help with my pet.\nDr. Sarah Johnson: Hello! I'm happy to help. What seems to be the issue with your pet?\nTest User: My cat has been acting strangely lately.\nDr. Sarah Johnson: I understand. Can you describe what kind of strange behavior you've noticed?",
        "trainee_name": "Test User",
        "_metadata": {
            "user_id": "test-user-123",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "message_count": 4,
            "is_ended": False,
            "ended_at": None,
            "ended_reason": None
        }
    }
    
    # Mock export_session_text to return JSON
    logger.export_session_text.return_value = json.dumps(session_data)
    
    return logger


@pytest.fixture
def mock_content_loader():
    """Create a mock content loader."""
    loader = Mock()
    
    # Mock scenario
    loader.get_scenario_by_id.return_value = {
        "id": "scenario-1",
        "name": "Pet Health Consultation",
        "description": "A veterinary consultation about pet health concerns",
        "goal": "Help the pet owner understand their pet's health issues",
        "compatible_character_ids": ["character-1"],
        "language": "en"
    }
    
    # Mock character
    loader.get_character_by_id.return_value = {
        "id": "character-1",
        "name": "Dr. Sarah Johnson",
        "description": "An experienced veterinarian with 15 years of practice",
        "language": "en"
    }
    
    return loader


@pytest.fixture
def mock_adk_session_service():
    """Create a mock ADK session service."""
    service = AsyncMock()
    service.create_session.return_value = None
    service.delete_session.return_value = None
    return service


@pytest.fixture
def mock_runner():
    """Create a mock ADK runner."""
    runner = AsyncMock()
    
    # Mock the async generator for run_async
    async def mock_run_async(*args, **kwargs):
        # Create a mock event with the evaluation response
        mock_event = Mock()
        mock_part = Mock()
        mock_part.text = json.dumps({
            "chat_session_id": "test-session-123",
            "overall_score": 0.85,
            "human_review_recommended": False,
            "overall_assessment": "The trainee demonstrated good communication skills.",
            "key_strengths_demonstrated": [
                "Clear communication",
                "Empathetic responses"
            ],
            "key_areas_for_development": [
                "Could ask more follow-up questions"
            ],
            "actionable_next_steps": [
                "Practice active listening",
                "Review questioning techniques"
            ],
            "progress_notes_from_past_feedback": "First evaluation session."
        })
        mock_event.content = Mock()
        mock_event.content.parts = [mock_part]
        
        yield mock_event
    
    runner.run_async = mock_run_async
    runner.close = AsyncMock()
    return runner


@pytest.mark.asyncio
async def test_evaluate_session_structured_success(
    evaluation_handler,
    mock_user,
    mock_chat_logger,
    mock_content_loader,
    mock_adk_session_service,
    mock_runner
):
    """Test successful structured evaluation of a session."""
    session_id = "test-session-123"
    
    # Mock the create_evaluator_agent function
    with patch('role_play.evaluation.handler.create_evaluator_agent') as mock_create_agent:
        mock_create_agent.return_value = Mock()  # Return a mock agent
        
        # Mock the Runner class
        with patch('role_play.evaluation.handler.Runner') as mock_runner_class:
            mock_runner_class.return_value = mock_runner
            
            # Call the handler
            response = await evaluation_handler.evaluate_session_structured(
                session_id=session_id,
                current_user=mock_user,
                chat_logger=mock_chat_logger,
                content_loader=mock_content_loader,
                adk_session_service=mock_adk_session_service
            )
    
    # Verify the response
    assert isinstance(response, StructuredEvaluationResponse)
    assert response.success is True
    assert response.session_id == session_id
    assert response.overall_score == 0.85
    assert response.human_review_recommended is False
    assert "good communication skills" in response.overall_assessment
    assert len(response.key_strengths_demonstrated) == 2
    assert len(response.key_areas_for_development) == 1
    assert len(response.actionable_next_steps) == 2
    
    # Verify mock calls
    mock_chat_logger.export_session_text.assert_called_once_with(
        user_id=mock_user.id,
        session_id=session_id,
        format="json"
    )
    mock_content_loader.get_scenario_by_id.assert_called_once_with("scenario-1", "en")
    mock_content_loader.get_character_by_id.assert_called_once_with("character-1", "en")
    mock_adk_session_service.create_session.assert_called_once()
    mock_adk_session_service.delete_session.assert_called_once()


@pytest.mark.asyncio
async def test_evaluate_session_structured_no_messages(
    evaluation_handler,
    mock_user,
    mock_content_loader,
    mock_adk_session_service
):
    """Test evaluation fails when session has no messages."""
    session_id = "empty-session"
    
    # Mock chat logger with session not found
    mock_chat_logger = AsyncMock()
    mock_chat_logger.export_session_text.return_value = "Session log file not found."
    
    # Expect HTTPException
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await evaluation_handler.evaluate_session_structured(
            session_id=session_id,
            current_user=mock_user,
            chat_logger=mock_chat_logger,
            content_loader=mock_content_loader,
            adk_session_service=mock_adk_session_service
        )
    
    assert exc_info.value.status_code == 404
    assert "Session not found" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_evaluate_session_structured_invalid_json(
    evaluation_handler,
    mock_user,
    mock_content_loader,
    mock_adk_session_service
):
    """Test evaluation fails when session JSON is invalid."""
    session_id = "invalid-json-session"
    
    # Mock chat logger with invalid JSON
    mock_chat_logger = AsyncMock()
    mock_chat_logger.export_session_text.return_value = "Invalid JSON data"
    
    # Expect HTTPException
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await evaluation_handler.evaluate_session_structured(
            session_id=session_id,
            current_user=mock_user,
            chat_logger=mock_chat_logger,
            content_loader=mock_content_loader,
            adk_session_service=mock_adk_session_service
        )
    
    assert exc_info.value.status_code == 500
    assert "Failed to parse session data" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_evaluate_session_structured_fallback_parsing(
    evaluation_handler,
    mock_user,
    mock_chat_logger,
    mock_content_loader,
    mock_adk_session_service
):
    """Test evaluation falls back to basic report when JSON parsing fails."""
    session_id = "test-session-123"
    
    # Create a runner that returns non-JSON text
    mock_runner = AsyncMock()
    
    async def mock_run_async(*args, **kwargs):
        mock_event = Mock()
        mock_part = Mock()
        mock_part.text = "This is a plain text evaluation without JSON structure."
        mock_event.content = Mock()
        mock_event.content.parts = [mock_part]
        yield mock_event
    
    mock_runner.run_async = mock_run_async
    mock_runner.close = AsyncMock()
    
    # Mock the create_evaluator_agent function
    with patch('role_play.evaluation.handler.create_evaluator_agent') as mock_create_agent:
        mock_create_agent.return_value = Mock()
        
        # Mock the Runner class
        with patch('role_play.evaluation.handler.Runner') as mock_runner_class:
            mock_runner_class.return_value = mock_runner
            
            # Call the handler
            response = await evaluation_handler.evaluate_session_structured(
                session_id=session_id,
                current_user=mock_user,
                chat_logger=mock_chat_logger,
                content_loader=mock_content_loader,
                adk_session_service=mock_adk_session_service
            )
    
    # Verify fallback response
    assert response.success is True
    assert response.session_id == session_id
    assert response.overall_score == 0.7  # Default fallback score
    assert response.human_review_recommended is False
    assert "plain text evaluation" in response.overall_assessment
    assert len(response.key_strengths_demonstrated) > 0
    assert len(response.key_areas_for_development) > 0