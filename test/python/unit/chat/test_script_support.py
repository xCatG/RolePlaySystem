"""Unit tests for script support in chat module."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from role_play.common.models import Script
from role_play.chat.models import CreateSessionRequest, SessionInfo
from role_play.chat.content_loader import ContentLoader
from role_play.chat.handler import ChatHandler
from fastapi import HTTPException


class TestScriptModel:
    """Test the Script model validation."""
    
    def test_script_model_creation(self):
        """Test creating a valid Script model."""
        script = Script(
            id="test_script",
            scenario_id="medical_interview",
            character_id="patient_acute",
            language="en",
            goal="Practice handling patient pain",
            script=[
                {"speaker": "character", "line": "I'm fine"},
                {"speaker": "participant", "line": "Tell me more"},
                {"speaker": "llm", "action": "stop"}
            ]
        )
        assert script.id == "test_script"
        assert script.scenario_id == "medical_interview"
        assert script.character_id == "patient_acute"
        assert script.language == "en"
        assert len(script.script) == 3
        
    def test_script_model_default_language(self):
        """Test Script model uses default language."""
        script = Script(
            id="test_script",
            scenario_id="medical_interview", 
            character_id="patient_acute",
            goal="Test goal",
            script=[]
        )
        assert script.language == "en"


class TestContentLoaderScripts:
    """Test ContentLoader script methods."""
    
    @pytest.fixture
    def mock_content_loader(self):
        """Create a ContentLoader with mocked data."""
        loader = ContentLoader()
        loader._data = {
            "en": {
                "scenarios": [
                    {"id": "medical_interview", "name": "Medical", "language": "en"}
                ],
                "characters": [
                    {"id": "patient_acute", "name": "John", "language": "en"}
                ],
                "scripts": [
                    {
                        "id": "medical_script_1",
                        "scenario_id": "medical_interview",
                        "character_id": "patient_acute",
                        "language": "en",
                        "goal": "Practice pain assessment",
                        "script": [
                            {"speaker": "character", "line": "I'm fine"},
                            {"speaker": "llm", "action": "stop"}
                        ]
                    }
                ]
            }
        }
        return loader
        
    def test_get_scripts(self, mock_content_loader):
        """Test getting all scripts for a language."""
        scripts = mock_content_loader.get_scripts("en")
        assert len(scripts) == 1
        assert scripts[0]["id"] == "medical_script_1"
        
    def test_get_script_by_id(self, mock_content_loader):
        """Test getting a specific script by ID."""
        script = mock_content_loader.get_script_by_id("medical_script_1", "en")
        assert script is not None
        assert script["id"] == "medical_script_1"
        assert script["goal"] == "Practice pain assessment"
        
    def test_get_script_by_id_not_found(self, mock_content_loader):
        """Test getting non-existent script returns None."""
        script = mock_content_loader.get_script_by_id("nonexistent", "en")
        assert script is None


class TestChatHandlerScriptSupport:
    """Test ChatHandler script support functionality."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for testing."""
        mock_user = MagicMock(id="user123", preferred_language="en")
        mock_chat_logger = AsyncMock()
        mock_adk_service = AsyncMock()
        mock_content_loader = MagicMock()
        
        return {
            "current_user": mock_user,
            "chat_logger": mock_chat_logger,
            "adk_session_service": mock_adk_service,
            "content_loader": mock_content_loader
        }
    
    @pytest.mark.asyncio
    async def test_create_session_with_script(self, mock_dependencies):
        """Test creating a session with a script."""
        handler = ChatHandler()
        
        # Setup mocks
        mock_dependencies["content_loader"].get_scenario_by_id.return_value = {
            "id": "medical_interview",
            "name": "Medical Interview",
            "compatible_characters": ["patient_acute"]
        }
        mock_dependencies["content_loader"].get_character_by_id.return_value = {
            "id": "patient_acute",
            "name": "John"
        }
        mock_dependencies["content_loader"].get_script_by_id.return_value = {
            "id": "test_script",
            "scenario_id": "medical_interview",
            "character_id": "patient_acute",
            "goal": "Test goal",
            "script": [{"speaker": "character", "line": "Hello"}]
        }
        
        mock_dependencies["chat_logger"].start_session.return_value = ("session123", "/path/to/log")
        
        request = CreateSessionRequest(
            scenario_id="medical_interview",
            character_id="patient_acute",
            participant_name="Doctor",
            script_id="test_script"
        )
        
        response = await handler.create_session(
            request,
            **mock_dependencies
        )
        
        # Verify script was validated
        mock_dependencies["content_loader"].get_script_by_id.assert_called_once_with("test_script", "en")
        
        # Verify session was created with script info
        create_session_call = mock_dependencies["adk_session_service"].create_session.call_args
        session_state = create_session_call.kwargs["state"]
        assert session_state["script_id"] == "test_script"
        assert session_state["script_progress"] == 0
        assert session_state["script_content"] == [{"speaker": "character", "line": "Hello"}]
        assert session_state["script_goal"] == "Test goal"
    
    @pytest.mark.asyncio
    async def test_create_session_invalid_script(self, mock_dependencies):
        """Test creating a session with invalid script ID."""
        handler = ChatHandler()
        
        # Setup mocks
        mock_dependencies["content_loader"].get_scenario_by_id.return_value = {
            "id": "medical_interview",
            "name": "Medical Interview",
            "compatible_characters": ["patient_acute"]
        }
        mock_dependencies["content_loader"].get_character_by_id.return_value = {
            "id": "patient_acute",
            "name": "John"
        }
        mock_dependencies["content_loader"].get_script_by_id.return_value = None  # Script not found
        
        request = CreateSessionRequest(
            scenario_id="medical_interview",
            character_id="patient_acute",
            participant_name="Doctor",
            script_id="invalid_script"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await handler.create_session(request, **mock_dependencies)
        
        assert exc_info.value.status_code == 400
        assert "Invalid script ID" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_create_session_incompatible_script(self, mock_dependencies):
        """Test creating a session with script not matching scenario/character."""
        handler = ChatHandler()
        
        # Setup mocks
        mock_dependencies["content_loader"].get_scenario_by_id.return_value = {
            "id": "medical_interview",
            "name": "Medical Interview",
            "compatible_characters": ["patient_acute"]
        }
        mock_dependencies["content_loader"].get_character_by_id.return_value = {
            "id": "patient_acute",
            "name": "John"
        }
        mock_dependencies["content_loader"].get_script_by_id.return_value = {
            "id": "test_script",
            "scenario_id": "customer_service",  # Wrong scenario
            "character_id": "patient_acute",
            "script": []
        }
        
        request = CreateSessionRequest(
            scenario_id="medical_interview",
            character_id="patient_acute",
            participant_name="Doctor",
            script_id="test_script"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await handler.create_session(request, **mock_dependencies)
        
        assert exc_info.value.status_code == 400
        assert "Script not compatible" in str(exc_info.value.detail)
    
    def test_create_roleplay_agent_with_script(self):
        """Test agent creation includes script guidance."""
        handler = ChatHandler()
        
        character = {
            "id": "patient_acute",
            "name": "John",
            "language": "en",
            "system_prompt": "You are John"
        }
        scenario = {
            "id": "medical_interview",
            "name": "Medical Interview",
            "description": "Practice medical interviews"
        }
        script_content = [
            {"speaker": "character", "line": "I'm fine"},
            {"speaker": "llm", "action": "stop"}
        ]
        
        agent = handler._create_roleplay_agent(character, scenario, script_content)
        
        # Check that script guidance is in the system prompt
        assert "SCRIPT GUIDANCE MODE" in agent.instruction
        assert "STOP_SEQUENCE" in agent.instruction
        assert '"action": "stop"' in agent.instruction
    
    def test_create_roleplay_agent_without_script(self):
        """Test agent creation without script works normally."""
        handler = ChatHandler()
        
        character = {
            "id": "patient_acute",
            "name": "John",
            "language": "en",
            "system_prompt": "You are John"
        }
        scenario = {
            "id": "medical_interview",
            "name": "Medical Interview",
            "description": "Practice medical interviews"
        }
        
        agent = handler._create_roleplay_agent(character, scenario)
        
        # Check that script guidance is NOT in the system prompt
        assert "SCRIPT GUIDANCE MODE" not in agent.instruction
        assert "STOP_SEQUENCE" not in agent.instruction


class TestSessionInfoWithScripts:
    """Test SessionInfo includes script information."""
    
    def test_session_info_with_script(self):
        """Test SessionInfo model includes script fields."""
        session_info = SessionInfo(
            session_id="session123",
            scenario_name="Medical Interview",
            character_name="John",
            participant_name="Doctor",
            created_at="2024-01-01T00:00:00",
            message_count=5,
            jsonl_filename="/path/to/log",
            is_active=True,
            script_id="test_script",
            script_progress=2,
            goal="Practice pain assessment"
        )
        
        assert session_info.script_id == "test_script"
        assert session_info.script_progress == 2
        assert session_info.goal == "Practice pain assessment"
    
    def test_session_info_without_script(self):
        """Test SessionInfo model works without script fields."""
        session_info = SessionInfo(
            session_id="session123",
            scenario_name="Medical Interview",
            character_name="John",
            participant_name="Doctor",
            created_at="2024-01-01T00:00:00",
            message_count=5,
            jsonl_filename="/path/to/log",
            is_active=True
        )
        
        assert session_info.script_id is None
        assert session_info.script_progress == 0
        assert session_info.goal is None