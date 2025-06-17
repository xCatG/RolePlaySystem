import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
import uuid # Required for uuid.UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.adk.sessions import InMemorySessionService

from src.python.role_play.common.models import User
from src.python.role_play.evaluation.handler import EvaluationHandler, EvaluateTranscriptRequest
from src.python.role_play.dev_agents.evaluator_agent.model import FinalReviewReport

# Base mock data for fields other than chat_session_id
BASE_MOCK_REPORT_FIELDS = {
    "overall_score": 0.85,
    "human_review_recommended": False,
    "overall_assessment": "Good performance overall.",
    "key_strengths_demonstrated": ["Clarity", "Scenario Adherence"],
    "key_areas_for_development": ["Empathy", "Pacing"],
    "actionable_next_steps": ["Practice active listening exercises.", "Review scenario pacing guidelines."],
    "progress_notes_from_past_feedback": "Shows improvement in topic adherence from previous sessions."
}

MOCK_USER = User(id="testuser", username="testuser", email="test@example.com", role="user", disabled=False)

@pytest.fixture
def mock_adk_session_service():
    service = AsyncMock(spec=InMemorySessionService)
    service.create_session = AsyncMock()
    service.delete_session = AsyncMock()
    return service

@pytest.fixture
def handler_under_test():
    return EvaluationHandler()

@pytest.fixture
def client(handler_under_test: EvaluationHandler, mock_adk_session_service: AsyncMock):
    app = FastAPI()

    # Mock dependencies for the handler
    # Assuming EvaluationHandler has a 'deps' object that holds dependency functions
    # If not, these dependencies need to be available in a way FastAPI can find them globally
    # or the router needs to be created with explicit dependencies.
    # For this setup, we rely on FastAPI's dependency overrides.

    # These are functions that FastAPI's Depends() will call.
    # They need to be registered with app.dependency_overrides using the actual dependency functions
    # that are used in the handler's route method signatures.

    # To get the actual dependency functions, we would typically import them here
    # or access them if they are part of the handler instance (e.g., handler_under_test.deps.require_user_or_higher)
    # For now, let's assume we can get them from handler_under_test.deps if it's structured that way.
    # If handler.deps is not how dependencies are stored, this part needs adjustment.
    # The key is that the key for dependency_overrides must be the actual callable used in Depends().

    # This requires `src.python.role_play.server.dependencies` to be importable
    # or for handler_under_test to expose these dependencies.
    from src.python.role_play.server.dependencies import require_user_or_higher, get_adk_session_service

    app.dependency_overrides[require_user_or_higher] = lambda: MOCK_USER
    app.dependency_overrides[get_adk_session_service] = lambda: mock_adk_session_service

    app.include_router(handler_under_test.router, prefix=handler_under_test.prefix)
    return TestClient(app)

# Async generator for mocking runner.run_async
async def mock_run_async_generator(response_text: str | None, success: bool = True):
    if success and response_text is not None:
        event_mock = MagicMock()
        event_mock.content = MagicMock()
        event_mock.content.parts = [MagicMock()]
        event_mock.content.parts[0].text = response_text
        yield event_mock
    elif not success:
        raise Exception("Simulated run_async error")

@pytest.mark.asyncio
class TestEvaluateTranscriptEndpoint:

    @patch('src.python.role_play.evaluation.handler.uuid.uuid4')
    @patch('src.python.role_play.evaluation.handler.Runner')
    async def test_evaluate_transcript_comprehensive_success(
        self, mock_Runner_class, mock_uuid4, client: TestClient, mock_adk_session_service: AsyncMock
    ):
        fixed_uuid_str = "test-uuid-comprehensive"
        mock_uuid4.return_value = uuid.UUID(fixed_uuid_str) # uuid.uuid4() returns a UUID object

        expected_session_id = f"eval_transcript_{fixed_uuid_str}"

        # Dynamically create the report data that the agent is expected to return
        mock_agent_returned_report_data = {
            "chat_session_id": expected_session_id,
            **BASE_MOCK_REPORT_FIELDS
        }
        mock_agent_returned_json = json.dumps(mock_agent_returned_report_data)

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = AsyncMock(side_effect=lambda *args, **kwargs: mock_run_async_generator(mock_agent_returned_json))
        mock_runner_instance.close = AsyncMock()
        mock_Runner_class.return_value = mock_runner_instance

        request_data = EvaluateTranscriptRequest(
            chat_transcript="This is a comprehensive test transcript.",
            evaluation_type="comprehensive"
        )
        response = client.post("/eval/transcript", json=request_data.model_dump())

        assert response.status_code == 200

        # Expected response includes success=True from BaseResponse
        # and the fields from mock_agent_returned_report_data
        expected_response_json = {"success": True, **mock_agent_returned_report_data}
        assert response.json() == expected_response_json

        mock_adk_session_service.create_session.assert_called_once()
        create_args = mock_adk_session_service.create_session.call_args[1]
        assert create_args['app_name'] == "roleplay_evaluator_transcript"
        assert create_args['user_id'] == MOCK_USER.id
        assert create_args['session_id'] == expected_session_id
        assert create_args['state']['transcript'] == request_data.chat_transcript

        mock_adk_session_service.delete_session.assert_called_once_with(
            app_name="roleplay_evaluator_transcript",
            user_id=MOCK_USER.id,
            session_id=expected_session_id
        )

        run_async_call_args = mock_runner_instance.run_async.call_args
        prompt_text = run_async_call_args[1]['new_message'].parts[0].text
        assert "Please provide a comprehensive evaluation" in prompt_text
        assert request_data.chat_transcript in prompt_text
        assert "Analyze:" in prompt_text

    @patch('src.python.role_play.evaluation.handler.uuid.uuid4')
    @patch('src.python.role_play.evaluation.handler.Runner')
    async def test_evaluate_transcript_quick_success(
        self, mock_Runner_class, mock_uuid4, client: TestClient, mock_adk_session_service: AsyncMock
    ):
        fixed_uuid_str = "test-uuid-quick"
        mock_uuid4.return_value = uuid.UUID(fixed_uuid_str)
        expected_session_id = f"eval_transcript_{fixed_uuid_str}"

        mock_agent_returned_report_data = {"chat_session_id": expected_session_id, **BASE_MOCK_REPORT_FIELDS}
        mock_agent_returned_json = json.dumps(mock_agent_returned_report_data)

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = AsyncMock(side_effect=lambda *args, **kwargs: mock_run_async_generator(mock_agent_returned_json))
        mock_runner_instance.close = AsyncMock()
        mock_Runner_class.return_value = mock_runner_instance

        request_data = EvaluateTranscriptRequest(
            chat_transcript="This is a quick test transcript.",
            evaluation_type="quick"
        )
        response = client.post("/eval/transcript", json=request_data.model_dump())

        assert response.status_code == 200
        expected_response_json = {"success": True, **mock_agent_returned_report_data}
        assert response.json() == expected_response_json

        run_async_call_args = mock_runner_instance.run_async.call_args
        prompt_text = run_async_call_args[1]['new_message'].parts[0].text
        assert "Please provide a quick evaluation" in prompt_text
        assert "Focus on the key strengths" in prompt_text

    @patch('src.python.role_play.evaluation.handler.uuid.uuid4')
    @patch('src.python.role_play.evaluation.handler.Runner')
    async def test_evaluate_transcript_custom_success(
        self, mock_Runner_class, mock_uuid4, client: TestClient, mock_adk_session_service: AsyncMock
    ):
        fixed_uuid_str = "test-uuid-custom"
        mock_uuid4.return_value = uuid.UUID(fixed_uuid_str)
        expected_session_id = f"eval_transcript_{fixed_uuid_str}"

        mock_agent_returned_report_data = {"chat_session_id": expected_session_id, **BASE_MOCK_REPORT_FIELDS}
        mock_agent_returned_json = json.dumps(mock_agent_returned_report_data)

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = AsyncMock(side_effect=lambda *args, **kwargs: mock_run_async_generator(mock_agent_returned_json))
        mock_runner_instance.close = AsyncMock()
        mock_Runner_class.return_value = mock_runner_instance

        custom_criteria = ["Criterion 1: Empathy", "Criterion 2: Problem Solving"]
        request_data = EvaluateTranscriptRequest(
            chat_transcript="This is a custom test transcript.",
            evaluation_type="custom",
            custom_criteria=custom_criteria
        )
        response = client.post("/eval/transcript", json=request_data.model_dump())

        assert response.status_code == 200
        expected_response_json = {"success": True, **mock_agent_returned_report_data}
        assert response.json() == expected_response_json

        run_async_call_args = mock_runner_instance.run_async.call_args
        prompt_text = run_async_call_args[1]['new_message'].parts[0].text
        assert "evaluate this roleplay session transcript based on these specific criteria" in prompt_text
        for criterion in custom_criteria:
            assert criterion in prompt_text

    @patch('src.python.role_play.evaluation.handler.uuid.uuid4')
    @patch('src.python.role_play.evaluation.handler.Runner')
    async def test_evaluate_transcript_agent_empty_response(
        self, mock_Runner_class, mock_uuid4, client: TestClient, mock_adk_session_service: AsyncMock
    ):
        mock_uuid4.return_value = uuid.UUID("test-uuid-empty")
        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = AsyncMock(side_effect=lambda *args, **kwargs: mock_run_async_generator(None))
        mock_runner_instance.close = AsyncMock()
        mock_Runner_class.return_value = mock_runner_instance

        request_data = EvaluateTranscriptRequest(chat_transcript="Test transcript.")
        response = client.post("/eval/transcript", json=request_data.model_dump())

        assert response.status_code == 500
        assert "Evaluation agent returned an empty response" in response.json()["detail"]

    @patch('src.python.role_play.evaluation.handler.uuid.uuid4')
    @patch('src.python.role_play.evaluation.handler.Runner')
    async def test_evaluate_transcript_agent_invalid_json(
        self, mock_Runner_class, mock_uuid4, client: TestClient, mock_adk_session_service: AsyncMock
    ):
        mock_uuid4.return_value = uuid.UUID("test-uuid-invalid-json")
        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = AsyncMock(side_effect=lambda *args, **kwargs: mock_run_async_generator("this is not json"))
        mock_runner_instance.close = AsyncMock()
        mock_Runner_class.return_value = mock_runner_instance

        request_data = EvaluateTranscriptRequest(chat_transcript="Test transcript.")
        response = client.post("/eval/transcript", json=request_data.model_dump())

        assert response.status_code == 500
        assert "Failed to parse evaluation report from agent" in response.json()["detail"]

    @patch('src.python.role_play.evaluation.handler.uuid.uuid4')
    @patch('src.python.role_play.evaluation.handler.Runner')
    async def test_evaluate_transcript_agent_invalid_structure(
        self, mock_Runner_class, mock_uuid4, client: TestClient, mock_adk_session_service: AsyncMock
    ):
        mock_uuid4.return_value = uuid.UUID("test-uuid-invalid-structure")
        mock_runner_instance = MagicMock()
        # Valid JSON, but doesn't match FinalReviewReport (e.g. overall_score is wrong type)
        invalid_report_data = {"overall_score": "should be float", "unexpected_field": "some value"}
        invalid_report_json = json.dumps(invalid_report_data)
        mock_runner_instance.run_async = AsyncMock(side_effect=lambda *args, **kwargs: mock_run_async_generator(invalid_report_json))
        mock_runner_instance.close = AsyncMock()
        mock_Runner_class.return_value = mock_runner_instance

        request_data = EvaluateTranscriptRequest(chat_transcript="Test transcript.")
        response = client.post("/eval/transcript", json=request_data.model_dump())

        assert response.status_code == 500
        assert "Invalid report structure from agent" in response.json()["detail"]

    @patch('src.python.role_play.evaluation.handler.uuid.uuid4')
    @patch('src.python.role_play.evaluation.handler.Runner')
    async def test_evaluate_transcript_runner_close_exception(
        self, mock_Runner_class, mock_uuid4, client: TestClient, mock_adk_session_service: AsyncMock
    ):
        fixed_uuid_str = "test-uuid-runner-close-exc"
        mock_uuid4.return_value = uuid.UUID(fixed_uuid_str)
        expected_session_id = f"eval_transcript_{fixed_uuid_str}"

        mock_agent_returned_report_data = {"chat_session_id": expected_session_id, **BASE_MOCK_REPORT_FIELDS}
        mock_agent_returned_json = json.dumps(mock_agent_returned_report_data)

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = AsyncMock(side_effect=lambda *args, **kwargs: mock_run_async_generator(mock_agent_returned_json))
        mock_runner_instance.close = AsyncMock(side_effect=Exception("Close failed"))
        mock_Runner_class.return_value = mock_runner_instance

        request_data = EvaluateTranscriptRequest(chat_transcript="Transcript for runner close test.")
        response = client.post("/eval/transcript", json=request_data.model_dump())

        assert response.status_code == 200
        expected_response_json = {"success": True, **mock_agent_returned_report_data}
        assert response.json() == expected_response_json

        mock_runner_instance.close.assert_called_once()
        # Error logging for runner.close() is not asserted here but is expected to happen.

    @patch('src.python.role_play.evaluation.handler.uuid.uuid4')
    @patch('src.python.role_play.evaluation.handler.Runner')
    async def test_evaluate_transcript_adk_create_session_exception(
        self, mock_Runner_class, mock_uuid4, client: TestClient, mock_adk_session_service: AsyncMock
    ):
        mock_uuid4.return_value = uuid.UUID("test-uuid-adk-create-fail")
        mock_adk_session_service.create_session.side_effect = Exception("ADK Create Session Failed")

        request_data = EvaluateTranscriptRequest(chat_transcript="Test transcript for ADK failure.")
        response = client.post("/eval/transcript", json=request_data.model_dump())

        assert response.status_code == 500
        assert "Failed to evaluate transcript: ADK Create Session Failed" in response.json()["detail"]
        mock_Runner_class.assert_not_called()
        mock_adk_session_service.delete_session.assert_not_called()

    @patch('src.python.role_play.evaluation.handler.uuid.uuid4')
    @patch('src.python.role_play.evaluation.handler.Runner')
    async def test_evaluate_transcript_runner_run_async_exception(
        self, mock_Runner_class, mock_uuid4, client: TestClient, mock_adk_session_service: AsyncMock
    ):
        fixed_uuid_str = "test-uuid-run-async-fail"
        mock_uuid4.return_value = uuid.UUID(fixed_uuid_str)
        expected_session_id = f"eval_transcript_{fixed_uuid_str}"

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = AsyncMock(side_effect=Exception("Run Async Failed"))
        mock_runner_instance.close = AsyncMock()
        mock_Runner_class.return_value = mock_runner_instance

        request_data = EvaluateTranscriptRequest(chat_transcript="Test transcript for run_async failure.")
        response = client.post("/eval/transcript", json=request_data.model_dump())

        assert response.status_code == 500
        assert "Failed to evaluate transcript: Run Async Failed" in response.json()["detail"]

        mock_adk_session_service.create_session.assert_called_once_with(
            app_name="roleplay_evaluator_transcript",
            user_id=MOCK_USER.id,
            session_id=expected_session_id, # Ensure this matches the generated one
            state={"transcript": request_data.chat_transcript, "evaluation_type": request_data.evaluation_type}
        )
        mock_adk_session_service.delete_session.assert_called_once_with(
            app_name="roleplay_evaluator_transcript",
            user_id=MOCK_USER.id,
            session_id=expected_session_id
        )
        mock_runner_instance.close.assert_called_once()
pass
