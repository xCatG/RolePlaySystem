import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Optional, Any
import sys # Import sys for sys.modules patching

# --- Mock google.adk before other application imports ---
# This is to prevent ModuleNotFoundError if google.adk is not installed
# The actual behavior of these ADK components will be mocked by fixtures later.
mock_adk_module = MagicMock(name="google_adk_mock")
mock_adk_sessions_module = MagicMock(name="google_adk_sessions_mock")
mock_adk_runners_module = MagicMock(name="google_adk_runners_mock")
mock_adk_agents_module = MagicMock(name="google_adk_agents_mock")
mock_adk_tools_module = MagicMock(name="google_adk_tools_mock") # For google.adk.tools

# Mock specific classes that are imported by the handler or tests
ADKSessionMock = MagicMock(name="ADKSessionMock")
mock_adk_sessions_module.InMemorySessionService = MagicMock(name="InMemorySessionServiceMock")
mock_adk_sessions_module.Session = ADKSessionMock

# Configure Runner mock (class and instance)
RunnerClassMock = MagicMock(name="RunnerClassMock")
RunnerInstanceMock = MagicMock(name="RunnerInstanceMock")
mock_event_content_part = MagicMock(text="Mocked LLM response")
mock_event_content = MagicMock()
mock_event_content.parts = [mock_event_content_part]
mock_event = MagicMock()
mock_event.content = mock_event_content
# Define an async generator function
async def mock_run_async_generator_obj_producer(*args, **kwargs):
    yield mock_event

# If Runner.run_async is a regular method that returns an async iterable
RunnerInstanceMock.run_async = MagicMock(return_value=mock_run_async_generator_obj_producer())
RunnerInstanceMock.close = AsyncMock()
RunnerClassMock.return_value = RunnerInstanceMock
mock_adk_runners_module.Runner = RunnerClassMock # Runner(...) will return RunnerInstanceMock

mock_adk_agents_module.Agent = MagicMock(name="AgentMock")
mock_adk_tools_module.FunctionTool = MagicMock(name="FunctionToolMock")

# sys.modules['google'] = MagicMock(name="google_mock") # Avoid mocking top-level 'google'
sys.modules['google.adk'] = mock_adk_module
sys.modules['google.adk.sessions'] = mock_adk_sessions_module
sys.modules['google.adk.runners'] = mock_adk_runners_module
sys.modules['google.adk.agents'] = mock_adk_agents_module
sys.modules['google.adk.tools'] = mock_adk_tools_module # Add tools mock to sys.modules
# --- End of google.adk mocking ---

# --- Mock Content and Part for handler ---
class MockContent:
    def __init__(self, *, role: str, parts: list):
        self.role = role
        self.parts = parts

class MockPart:
    def __init__(self, *, text: str):
        self.text = text

# Patch Content and Part in the handler module's namespace
# These patches will be active for the duration of the test session
# if not started/stopped around specific tests or fixtures.
# It's often better to manage patches with .start() and .stop() in setup/teardown
# or use `with patch(...)` in individual tests if they trigger the usage.
# For now, let's apply them globally for collection purposes.
# The handler module is 'role_play.chat.handler'
# The objects Content and Part are imported there.

# It's safer to patch where the object is looked up.
# In handler.py, it's `from google.ai.generativelanguage.v1beta.types import Content, Part`
# So, we need to ensure that this import statement resolves to our mocks.
# This can be done by patching 'google.ai.generativelanguage.v1beta.types.Content' and '.Part'
# OR by patching 'role_play.chat.handler.Content' and 'role_play.chat.handler.Part'
# if the import into handler.py is successful.

# Given the import `from google.ai.generativelanguage.v1beta.types import Content, Part` in handler.py,
# we should patch these names within the handler.py module itself.
# However, if that import itself fails, this won't help.
# The ModuleNotFoundError for 'google.ai.generativelanguage.v1beta' means we first need to
# make that path exist in sys.modules, then patch Content/Part on it.

# We want the real google.ai, google.ai.generativelanguage, google.ai.generativelanguage.v1beta
# to be resolved by Python from the installed packages if possible.
# We only want to mock the final 'types' module under v1beta, or Content/Part themselves.

mock_genai_beta_types_module = MagicMock(name="google_ai_genlang_v1beta_types_mock")
mock_genai_beta_types_module.Content = MockContent
mock_genai_beta_types_module.Part = MockPart

# To ensure that 'from google.ai.generativelanguage.v1beta.types import Content, Part' works,
# we need to make sure 'google.ai.generativelanguage.v1beta.types' is our mock module.
# This still requires 'google.ai.generativelanguage.v1beta' to be seen as a package.

# If the real 'google.ai.generativelanguage.v1beta' cannot be found, then mocking its 'types' submodule is hard.
# Let's assume the 'google-ai-generativelanguage' package correctly installs the path up to 'v1beta'.
# We will then place our mock 'types' module into it.

# Create parent modules if they don't exist as real packages, but make them behave like packages.
# This is delicate. If 'google.ai' is a real namespace package, sys.modules['google.ai'] might already exist.
g_parent = sys.modules.setdefault('google', MagicMock(name='google_root_mock', __path__=['dummy_google_path']))
# If 'google.ai' doesn't exist or isn't a package, create it as such.
# This is getting risky as it might hide real submodules of 'google.ai' if 'google.ai' itself is a real namespace.
# The error "ModuleNotFoundError: No module named 'google.ai.generativelanguage_v1beta'; 'google.ai' is not a package"
# implies that 'google.ai' was a mock, not a package. This happened because of:
# sys.modules['google.ai'] = mock_google_ai_module (from previous attempt)
# I should *not* mock 'google.ai' itself if it's a real namespace package.

# Clean approach:
# 1. Ensure 'google.ai.generativelanguage.v1beta.types' is in sys.modules and points to our mock.
# This means Python must be able to resolve 'google', 'google.ai', 'google.ai.generativelanguage',
# 'google.ai.generativelanguage.v1beta' as packages/modules.
# The 'google-ai-generativelanguage' package *should* provide these.
# The error " 'google.ai' is not a package " means a higher-level mock of 'google.ai' was bad.

# Let's remove the broad `sys.modules['google.ai'] = ...` and only mock the specific `types` module.
# Python's import system should then find the real `google.ai...v1beta` path, and we replace `types` at the end.
# This requires `google-ai-generativelanguage` to be correctly installed and on path.

# Create a dummy module structure for `google.ai.generativelanguage.v1beta.types`
# This will be put into sys.modules.
# This ensures that when `handler.py` does `from google.ai.generativelanguage.v1beta.types import Content, Part`
# it finds our mocked `Content` and `Part`.
final_types_module_mock = MagicMock(name="MockedBetaTypesModule")
final_types_module_mock.Content = MockContent
final_types_module_mock.Part = MockPart

# Ensure the parent modules exist in sys.modules as actual modules or mocks that behave like modules.
# The key is that the real `google-ai-generativelanguage` package should make `google.ai.generativelanguage.v1beta` available.
# We are essentially replacing what `google.ai.generativelanguage.v1beta.types` would be.
# This still might fail if `google.ai.generativelanguage.v1beta` itself is not found due to some path / namespace issue.
# The most robust way is to patch Content and Part directly where they are used, if the import path itself is unreliable.

# Given the ongoing import issues, patching directly in the handler's namespace after it's imported
# might be more stable if the handler can be imported at all (i.e., other imports in handler are OK).
# Let's try that approach first, assuming the ModuleNotFoundError for the *path* is the primary problem.
# The previous error was "ModuleNotFoundError: No module named 'google.ai.generativelanguage_v1beta'".
# This means the path itself is failing. So, we *do* need to ensure this path resolves.
# The most minimal sys.modules intervention for the path, then:
sys.modules['google.ai.generativelanguage.v1beta.types'] = final_types_module_mock
# This line above assumes 'google.ai.generativelanguage.v1beta' is a findable package/module.
# If not, then we need to mock that too.
# The error "'google.ai' is not a package" suggests that 'google.ai' was previously mocked.
# Let's ensure 'google.ai' and 'google.ai.generativelanguage' are NOT mocked by this test file directly.
# The `google-ai-generativelanguage` pip package should make them available.

# --- End of Content/Part Mocking ---


from fastapi import HTTPException

# Models to import - adjust paths as necessary if running tests from a different root
from role_play.common.models import User, UserRole
from role_play.chat.models import CreateSessionRequest, ChatMessageRequest, ChatMessageResponse
from role_play.chat.handler import ChatHandler
from role_play.chat.content_loader import ContentLoader
from role_play.chat.chat_logger import ChatLogger
# Use the mocked ADKSession for type hinting if needed, or rely on MagicMock
# from google.adk.sessions import InMemorySessionService, Session as ADKSession # This line would now import mocks


# --- Test Fixtures ---
@pytest.fixture
def mock_user() -> User:
    # Ensure datetime objects for User model
    from datetime import datetime, timezone
    return User(
        id="test_user_123",
        username="testuser",
        email="test@example.com",
        role=UserRole.USER,
        preferred_language="en",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        is_active=True
    )

@pytest.fixture
def mock_content_loader() -> MagicMock:
    loader = MagicMock(spec=ContentLoader)

    # Default scenario
    loader.get_scenario_by_id.return_value = {
        "id": "test_scenario", "name": "Test Scenario", "language": "en",
        "description": "A test scenario", "compatible_characters": ["test_char"]
    }
    # Default character
    loader.get_character_by_id.return_value = {
        "id": "test_char", "name": "Test Character", "language": "en",
        "description": "A test character", "system_prompt": "You are a test character."
    }
    # Default script (can be overridden in tests)
    loader.get_script_by_id.return_value = None
    return loader

@pytest.fixture # Corrected to use MagicMock for the class, AsyncMock for methods
def mock_chat_logger() -> MagicMock:
    logger = MagicMock(spec=ChatLogger)
    logger.start_session = AsyncMock(return_value=("session_log_123", "/path/to/session_log_123.jsonl"))
    logger.log_message = AsyncMock()
    logger.end_session = AsyncMock()
    logger.get_session_end_info = AsyncMock(return_value={}) # For _validate_active_session
    return logger

@pytest.fixture # Corrected to use MagicMock for the class, AsyncMock for methods
def mock_adk_session_service() -> MagicMock:
    # service = AsyncMock(spec=InMemorySessionService) # Using MagicMock as base for clearer spec on mocked instance
    # The class itself is mocked in sys.modules, here we mock an instance of it.
    # Removed spec as sys.modules mock is already a MagicMock.
    service = MagicMock()
    service.create_session = AsyncMock()
    service.get_session = AsyncMock(return_value=None) # Default to session not found
    service.delete_session = AsyncMock()
    return service

@pytest.fixture # Renamed from chat_handler_with_mocks to chat_handler as per request
def chat_handler(
    # No direct injection here as handler is stateless
) -> ChatHandler:
    handler = ChatHandler()
    return handler


# --- Helper to create a mock ADK Session ---
# Note: ADKSession type hint below will resolve to our ADKSessionMock via sys.modules
def create_mock_adk_session(session_id: str, user_id: str, initial_state: Dict[str, Any]) -> MagicMock: # Return type changed
    # ADKSession typically takes app_name, user_id, session_id, state, loop
    # For tests, we mainly care about the state.
    # Removed spec as sys.modules['google.adk.sessions'].Session is already a MagicMock (ADKSessionMock)
    mock_session = MagicMock()
    mock_session.session_id = session_id
    mock_session.user_id = user_id
    mock_session.state = initial_state.copy() # Crucial: copy the state
    return mock_session


# --- Test Cases ---

@pytest.mark.asyncio
async def test_create_session_normal(
    chat_handler: ChatHandler, # Corrected fixture name
    mock_user: User,
    mock_content_loader: MagicMock,
    mock_chat_logger: MagicMock, # Corrected type hint
    mock_adk_session_service: MagicMock # Corrected type hint
):
    handler = chat_handler # Renamed fixture
    request = CreateSessionRequest(
        scenario_id="test_scenario",
        character_id="test_char",
        participant_name="Test Participant"
    )

    response = await handler.create_session(
        request=request,
        current_user=mock_user,
        chat_logger=mock_chat_logger,
        adk_session_service=mock_adk_session_service,
        content_loader=mock_content_loader
    )

    assert response.success
    assert response.session_id == "session_log_123"
    mock_chat_logger.start_session.assert_called_once()
    mock_adk_session_service.create_session.assert_called_once()

    # Check state passed to ADK create_session
    _, kwargs = mock_adk_session_service.create_session.call_args
    adk_state = kwargs.get("state", {})
    assert adk_state.get("scenario_id") == "test_scenario"
    assert adk_state.get("character_id") == "test_char"
    assert "script_id" not in adk_state # No script in this test

    # Verify content_loader calls
    mock_content_loader.get_scenario_by_id.assert_called_with(request.scenario_id, mock_user.preferred_language)
    mock_content_loader.get_character_by_id.assert_called_with(request.character_id, mock_user.preferred_language)

@pytest.mark.asyncio
async def test_create_session_with_valid_script(
    chat_handler: ChatHandler, # Renamed fixture
    mock_user: User,
    mock_content_loader: MagicMock,
    mock_chat_logger: MagicMock, # Corrected type hint
    mock_adk_session_service: MagicMock
):
    handler = chat_handler # Renamed fixture
    script_id = "script123"
    mock_content_loader.get_script_by_id.return_value = { # Ensure this matches expected structure by handler
        "id": script_id, # Other fields like language, goal, script might be checked by handler if used
        # For create_session, only existence is checked, but good to be somewhat complete
        "language": mock_user.preferred_language,
        "goal": "A test goal",
        "script": []
    }
    request = CreateSessionRequest(
        scenario_id="test_scenario",
        character_id="test_char",
        participant_name="Test Participant",
        script_id=script_id
    )

    await handler.create_session(
        request=request, current_user=mock_user, chat_logger=mock_chat_logger,
        adk_session_service=mock_adk_session_service, content_loader=mock_content_loader
    )

    mock_adk_session_service.create_session.assert_called_once()
    _, kwargs = mock_adk_session_service.create_session.call_args
    adk_state = kwargs.get("state", {})
    assert adk_state.get("script_id") == script_id
    assert adk_state.get("script_progress") == 0
    mock_content_loader.get_script_by_id.assert_called_with(script_id, mock_user.preferred_language)
    # Also assert that scenario and character lookups were done
    mock_content_loader.get_scenario_by_id.assert_called_with(request.scenario_id, mock_user.preferred_language)
    mock_content_loader.get_character_by_id.assert_called_with(request.character_id, mock_user.preferred_language)


@pytest.mark.asyncio
async def test_create_session_with_invalid_script_id(
    chat_handler: ChatHandler, # Renamed fixture
    mock_user: User,
    mock_content_loader: MagicMock,
    mock_chat_logger: MagicMock,
    mock_adk_session_service: MagicMock
):
    handler = chat_handler # Renamed fixture
    mock_content_loader.get_script_by_id.return_value = None # Script not found
    script_id = "non_existent_script"

    # Ensure scenario and character are found, to isolate script_id failure
    mock_content_loader.get_scenario_by_id.return_value = {"id": "s1", "name": "Scenario 1", "compatible_characters": ["c1"]}
    mock_content_loader.get_character_by_id.return_value = {"id": "c1", "name": "Char 1"}

    request = CreateSessionRequest(
        scenario_id="s1", # Align with mocked scenario
        character_id="c1", # Align with mocked character
        participant_name="Test Participant",
        script_id=script_id
    )

    with pytest.raises(HTTPException) as exc_info:
        await handler.create_session(
            request=request, current_user=mock_user, chat_logger=mock_chat_logger,
            adk_session_service=mock_adk_session_service, content_loader=mock_content_loader
        )
    assert exc_info.value.status_code == 400
    assert f"Invalid script ID: {script_id}" in exc_info.value.detail
    mock_content_loader.get_script_by_id.assert_called_with(script_id, mock_user.preferred_language)


# More tests to come for send_message, prompt generation, STOP_SEQUENCE etc.
# For prompt generation, we might need to patch RolePlayAgent or its call within ChatHandler._create_roleplay_agent
# or ChatHandler._generate_character_response

@patch('role_play.chat.handler.RolePlayAgent') # Patching the class
@pytest.mark.asyncio
async def test_send_message_modifies_prompt_for_scripted_session(
    mock_role_play_agent_class: MagicMock, # This is the mock for the class itself
    chat_handler: ChatHandler, # Corrected fixture name
    mock_user: User,
    mock_content_loader: MagicMock,
    mock_chat_logger: MagicMock, # Corrected type hint
    mock_adk_session_service: MagicMock # Corrected type hint
):
    handler = chat_handler # Corrected assignment
    session_id = "scripted_session_1"
    script_id = "active_script"
    script_content_json = [{"speaker": "participant", "line": "Hello"}, {"speaker": "llm", "action": "stop"}]

    # Setup ContentLoader for this test
    mock_content_loader.get_script_by_id.return_value = {
        "id": script_id, "language": "en", "goal": "Goal", "script": script_content_json
    }
    # These are needed by _load_session_content
    mock_content_loader.get_character_by_id.return_value = {"id": "test_char", "name": "Test Character", "language": "en", "system_prompt": "Base prompt."}
    mock_content_loader.get_scenario_by_id.return_value = {"id": "test_scenario", "name": "Test Scenario", "language": "en", "description": "Desc."}

    # Setup ADK session state
    initial_adk_state = {
        "user_id": mock_user.id, "session_id": session_id, "storage_path": "/logs",
        "scenario_id": "test_scenario", "character_id": "test_char", "language": "en",
        "message_count": 0, "script_id": script_id, "script_progress": 0
    }
    mock_adk_session = create_mock_adk_session(session_id, mock_user.id, initial_adk_state)
    mock_adk_session_service.get_session.return_value = mock_adk_session

    # Mock the RolePlayAgent instance that will be created
    mock_agent_instance = AsyncMock() # RolePlayAgent is not async, but its methods might be if it were a true ADK agent.
                                   # For this test, we only care about constructor args.
    mock_role_play_agent_class.return_value = mock_agent_instance # When RolePlayAgent() is called, return our mock instance

    # Mock ADK Runner part within _generate_character_response
    # For simplicity, let _generate_character_response return a fixed text
    # We are testing the prompt passed to agent, not the full generation here.
    # Removed: with patch.object(handler, '_generate_character_response', new_callable=AsyncMock) as mock_gen_resp:
    # mock_gen_resp.return_value = "Test LLM response"

    request = ChatMessageRequest(message="Hello")
    await handler.send_message(
        session_id=session_id, request=request, current_user=mock_user,
        chat_logger=mock_chat_logger, adk_session_service=mock_adk_session_service,
        content_loader=mock_content_loader
    )

    # Assert that RolePlayAgent was called with the modified prompt
    mock_role_play_agent_class.assert_called_once()
    _, agent_kwargs = mock_role_play_agent_class.call_args
    system_prompt = agent_kwargs.get("instruction", "")

    expected_script_instruction_line = "You are following a pre-written script. When you reach a turn with `{\"action\": \"stop\"}` in the script, you MUST respond with the special sequence \"STOP_SEQUENCE\" and nothing else.\n"

    assert "**SCRIPT GUIDANCE MODE**" in system_prompt
    assert expected_script_instruction_line in system_prompt
    import json # For checking the script dump
    assert json.dumps(script_content_json, indent=2) in system_prompt

    # TODO: Verify that _generate_character_response was called, meaning the agent was constructed
    # and passed to the runner (which is inside _generate_character_response)
    # This is implicitly tested by mock_role_play_agent_class.assert_called_once()


# TODO: Add tests for STOP_SEQUENCE handling and script progression in send_message
# TODO: Add test for non-scripted session prompt in send_message

# Note: Testing the full flow of send_message, especially with script progression and
# STOP_SEQUENCE, will require more intricate mocking of ADKSession state changes
# and the return values of _generate_character_response based on script content.
# It might also involve patching `ChatHandler.end_session`.

@pytest.mark.asyncio
async def test_send_message_non_scripted_prompt( # Un-commented and decorator removed
    chat_handler: ChatHandler,
    mock_user: User,
    mock_content_loader: MagicMock,
    mock_chat_logger: MagicMock,
    mock_adk_session_service: MagicMock
):
    handler = chat_handler
    session_id = "normal_session_1"

    with patch('role_play.chat.handler.RolePlayAgent') as mock_agent_class_local: # Removed autospec=True
        mock_agent_instance_local = MagicMock()
        mock_agent_class_local.return_value = mock_agent_instance_local

        # Ensure no script is loaded for this session
        mock_content_loader.get_script_by_id.return_value = None
        # Standard scenario/character setup
        mock_content_loader.get_character_by_id.return_value = {"id": "test_char", "name": "Test Character", "language": "en", "system_prompt": "Base prompt."}
        mock_content_loader.get_scenario_by_id.return_value = {"id": "test_scenario", "name": "Test Scenario", "language": "en", "description": "Desc."}

        initial_adk_state = { # No script_id or script_progress
            "user_id": mock_user.id, "session_id": session_id, "storage_path": "/logs",
            "scenario_id": "test_scenario", "character_id": "test_char", "language": "en",
            "message_count": 0
        }
        mock_adk_session = create_mock_adk_session(session_id, mock_user.id, initial_adk_state)
        mock_adk_session_service.get_session.return_value = mock_adk_session

        request = ChatMessageRequest(message="Hi there")
        await handler.send_message(
            session_id=session_id, request=request, current_user=mock_user,
            chat_logger=mock_chat_logger, adk_session_service=mock_adk_session_service,
            content_loader=mock_content_loader
        )

        mock_agent_class_local.assert_called_once()
        _, agent_kwargs = mock_agent_class_local.call_args
        system_prompt = agent_kwargs.get("instruction", "")

        assert "**SCRIPT GUIDANCE MODE**" not in system_prompt
        assert "Base prompt." in system_prompt

@patch('role_play.chat.handler.RolePlayAgent')
@patch.object(ChatHandler, 'end_session', new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_send_message_script_completes_naturally(
    mock_end_session: AsyncMock,
    mock_role_play_agent_class: MagicMock,
    chat_handler: ChatHandler,
    mock_user: User,
    mock_content_loader: MagicMock,
    mock_chat_logger: MagicMock,
    mock_adk_session_service: MagicMock
):
    handler = chat_handler
    session_id = "natural_completion_session"
    script_id = "short_script"
    script_content = [
        {"speaker": "participant", "line": "Hi"}, # Progress 0
        {"speaker": "character", "line": "Bye"}  # Progress 1
    ]
    final_character_line = "Bye"

    mock_content_loader.get_script_by_id.return_value = {
        "id": script_id, "language": "en", "goal": "Test natural completion", "script": script_content
    }
    # Standard scenario/character mocks
    mock_content_loader.get_character_by_id.return_value = {"id": "test_char", "name": "Test Character", "language": "en", "system_prompt": "Base prompt."}
    mock_content_loader.get_scenario_by_id.return_value = {"id": "test_scenario", "name": "Test Scenario", "language": "en", "description": "Desc."}

    # Initial ADK session state (start of script)
    initial_adk_state = {
        "user_id": mock_user.id, "session_id": session_id, "storage_path": "/logs",
        "scenario_id": "test_scenario", "character_id": "test_char", "language": "en",
        "message_count": 0, "script_id": script_id, "script_progress": 0
    }
    mock_adk_session = create_mock_adk_session(session_id, mock_user.id, initial_adk_state)
    mock_adk_session_service.get_session.return_value = mock_adk_session

    # Mock RolePlayAgent instance
    mock_agent_instance = MagicMock()
    mock_role_play_agent_class.return_value = mock_agent_instance

    # Configure Runner mock (used by _generate_character_response)
    # The runner_instance_mock is configured globally in sys.modules setup for general cases,
    # but for specific return text, we might need to adjust its behavior or mock _generate_character_response.
    # For this test, let's assume the global RunnerInstanceMock setup is sufficient if it returns any text,
    # OR, more robustly, patch _generate_character_response directly for this specific character response.

    # --- Turn 1: Participant says "Hi" ---
    # Script progress should move from 0 to 1 (after participant's line)
    with patch.object(handler, '_generate_character_response', new_callable=AsyncMock) as mock_gen_resp_turn1:
        mock_gen_resp_turn1.return_value = final_character_line # Character will say "Bye"

        request_p1 = ChatMessageRequest(message="Hi")
        response_p1 = await handler.send_message(
            session_id=session_id, request=request_p1, current_user=mock_user,
            chat_logger=mock_chat_logger, adk_session_service=mock_adk_session_service,
            content_loader=mock_content_loader
        )

    assert response_p1.response == final_character_line
    mock_chat_logger.log_message.assert_any_call(user_id=mock_user.id, session_id=session_id, role="participant", content="Hi", message_number=1)
    mock_chat_logger.log_message.assert_any_call(user_id=mock_user.id, session_id=session_id, role="character", content=final_character_line, message_number=2)
    assert mock_adk_session.state["script_progress"] == 2 # Progress: 0->P, 1->C. Script is length 2. Progress becomes 2.

    # Session should have ended because script_progress (2) >= len(script) (2)
    mock_end_session.assert_called_once_with(
        session_id, mock_user, mock_chat_logger, mock_adk_session_service,
        reason="Script completed"
    )

# Test for STOP_SEQUENCE and session ending
@patch('role_play.chat.handler.RolePlayAgent') # This patches the RolePlayAgent used by ChatHandler
@patch.object(ChatHandler, 'end_session', new_callable=AsyncMock) # Patch end_session
@pytest.mark.asyncio
async def test_send_message_stop_sequence_ends_session(
    mock_end_session: AsyncMock, # Comes first due to patching order
    mock_role_play_agent_class: MagicMock,
    chat_handler: ChatHandler, # Corrected fixture name
    mock_user: User,
    mock_content_loader: MagicMock,
    mock_chat_logger: MagicMock, # Corrected type hint
    mock_adk_session_service: MagicMock # Corrected type hint
):
    handler = chat_handler # Corrected assignment
    session_id = "stop_sequence_session"
    script_id = "stop_script"
    # Script where LLM is supposed to stop
    script_content = [
        {"speaker": "participant", "line": "Please stop now."}, # User says something
        {"speaker": "llm", "action": "stop"} # LLM should stop
    ]

    mock_content_loader.get_script_by_id.return_value = {
        "id": script_id, "language": "en", "goal": "Test stop", "script": script_content
    }
    mock_content_loader.get_character_by_id.return_value = {"id": "test_char", "name": "Test Character", "language": "en", "system_prompt": "Base prompt."}
    mock_content_loader.get_scenario_by_id.return_value = {"id": "test_scenario", "name": "Test Scenario", "language": "en", "description": "Desc."}

    initial_adk_state = {
        "user_id": mock_user.id, "session_id": session_id, "storage_path": "/logs",
        "scenario_id": "test_scenario", "character_id": "test_char", "language": "en",
        "message_count": 0, "script_id": script_id, "script_progress": 0 # Start of script
    }
    mock_adk_session = create_mock_adk_session(session_id, mock_user.id, initial_adk_state)
    mock_adk_session_service.get_session.return_value = mock_adk_session

    # Mock RolePlayAgent instance (not strictly needed for its constructor here, but good practice)
    mock_agent_instance = MagicMock()
    mock_role_play_agent_class.return_value = mock_agent_instance

    # Key: Mock _generate_character_response to return "STOP_SEQUENCE"
    # This simulates the LLM obeying the SCRIPT GUIDANCE prompt.
    with patch.object(handler, '_generate_character_response', new_callable=AsyncMock) as mock_gen_resp:
        mock_gen_resp.return_value = "STOP_SEQUENCE"

        request = ChatMessageRequest(message="Please stop now.") # Participant's message
        response = await handler.send_message(
            session_id=session_id, request=request, current_user=mock_user,
            chat_logger=mock_chat_logger, adk_session_service=mock_adk_session_service,
            content_loader=mock_content_loader
        )

    # Check that end_session was called
    mock_end_session.assert_called_once_with(
        session_id, mock_user, mock_chat_logger, mock_adk_session_service,
        reason="Script ended by LLM stop action"
    )

    # Check that the response indicates the session ended.
    # The actual message might be a canned "Okay, that's all..."
    assert response.success
    assert "Okay, that's all" in response.response # Or similar, based on handler logic for STOP_SEQUENCE

    # Check that script_progress was updated for the participant's turn
    # but not for the LLM's stop turn.
    # Participant spoke (progress 0 -> 1), then LLM stop (progress remains 1).
    assert mock_adk_session.state["script_progress"] == 1

    # Check that the character's "final message" (e.g. "Okay, that's all...") was logged
    # This requires checking the last call to mock_chat_logger.log_message
    # The first call is participant, second is character's final words.
    assert mock_chat_logger.log_message.call_count == 2
    _, character_log_kwargs = mock_chat_logger.log_message.call_args_list[1] # Second call
    assert character_log_kwargs['role'] == 'character'
    assert "Okay, that's all" in character_log_kwargs['content']

# TODO: Test script completion naturally (no STOP_SEQUENCE, script just runs out of lines)
# TODO: Test script_progress advancing correctly over multiple turns.

# This is a starting point. FastAPI's dependency injection means we don't usually
# mock the things passed into Depends() at the handler's __init__ level, but rather
# ensure they are correctly mocked when the route/method is called in the test.
# For direct method calls like these tests, we pass the mocks directly.
# Actual HTTP tests with TestClient would rely on overriding dependencies.

if __name__ == '__main__':
    # This allows running pytest via `python test_chat_handler.py`
    pytest.main([__file__])
