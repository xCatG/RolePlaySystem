import pytest
from unittest.mock import AsyncMock, Mock

from role_play.common.models import Script
from role_play.chat.content_loader import ContentLoader
from role_play.chat.handler import ChatHandler
from role_play.chat.models import CreateSessionRequest


def test_script_model_validation():
    data = {
        "id": "s1",
        "scenario_id": "medical_interview",
        "character_id": "patient_acute",
        "goal": "Test",
        "script": [
            {"speaker": "character", "line": "hi"},
            {"speaker": "llm", "action": "stop"}
        ]
    }
    script = Script(**data)
    assert script.id == "s1"
    assert script.language == "en"


def test_content_loader_scripts():
    loader = ContentLoader(supported_languages=["en"])
    scripts = loader.get_scripts("en")
    assert isinstance(scripts, list)
    if scripts:
        script = loader.get_script_by_id(scripts[0]["id"], "en")
        assert script["id"] == scripts[0]["id"]


@pytest.mark.asyncio
async def test_create_session_invalid_script():
    handler = ChatHandler()
    mock_user = Mock()
    mock_user.id = "user1"
    mock_user.preferred_language = "en"

    chat_logger = AsyncMock()
    session_service = AsyncMock()
    loader = Mock()
    loader.get_scenario_by_id.return_value = {"id": "sc1", "name": "Scenario", "compatible_characters": ["char"]}
    loader.get_character_by_id.return_value = {"id": "char", "name": "Char"}
    loader.get_script_by_id.return_value = None

    req = CreateSessionRequest(scenario_id="sc1", character_id="char", participant_name="P1", script_id="bad")

    with pytest.raises(Exception):
        await handler.create_session(
            request=req,
            current_user=mock_user,
            chat_logger=chat_logger,
            adk_session_service=session_service,
            content_loader=loader,
        )

