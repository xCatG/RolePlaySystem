import pytest
from src.python.role_play.chat.handler import ChatHandler

def test_create_roleplay_agent_with_script():
    handler = ChatHandler()
    character = {
        "id": "test_character",
        "name": "Test Character",
        "system_prompt": "You are a test character.",
        "language": "en"
    }
    scenario = {
        "id": "test_scenario",
        "name": "Test Scenario",
        "description": "This is a test scenario."
    }
    script = {
        "id": "test_script",
        "script": [
            {"speaker": "character", "line": "Hello"},
            {"speaker": "participant", "line": "Hi"},
            {"speaker": "llm", "action": "stop"}
        ]
    }

    agent = handler._create_roleplay_agent(character, scenario, script)
    assert agent.instruction is not None
    assert "You are a test character." in agent.instruction
    assert "This is a test scenario." in agent.instruction
    assert "Hello" in agent.instruction
