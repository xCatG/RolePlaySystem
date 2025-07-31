import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import asyncio

from src.python.run_server import app, init_app
from src.python.role_play.common.models import User

@pytest.fixture(scope="module", autouse=True)
def setup_app():
    asyncio.run(init_app())

@pytest.fixture
def client():
    return TestClient(app)

import datetime

@pytest.fixture
def mock_user():
    return User(id="testuser", username="testuser", email="test@example.com", full_name="Test User", created_at=datetime.datetime.now(), updated_at=datetime.datetime.now())

def test_get_scripts(client, mock_user):
    with patch("src.python.role_play.server.dependencies.get_current_user", return_value=mock_user):
        response = client.get("/chat/content/scripts")
        assert response.status_code == 200
        data = response.json()
        assert data["success"]
        assert "scripts" in data
        assert len(data["scripts"]) > 0
        script = data["scripts"][0]
        assert "id" in script
        assert "goal" in script
        assert "scenario_id" in script
        assert "character_id" in script

def test_create_session_with_script(client, mock_user):
    with patch("src.python.role_play.server.dependencies.get_current_user", return_value=mock_user):
        response = client.post(
            "/chat/session",
            json={
                "scenario_id": "medical_interview",
                "character_id": "patient_acute",
                "participant_name": "Test Participant",
                "script_id": "medical_acute_frustration_simple"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"]
        assert "session_id" in data
        session_id = data["session_id"]

        # Now send a message and check if the script is handled
        with patch("src.python.role_play.chat.handler.ChatHandler._generate_character_response", return_value="Test response"):
                with patch("src.python.role_play.chat.handler.ChatHandler.end_session") as mock_end_session:
                # This is a bit of a hack, we are not actually checking the script progression
                # but we are checking that the end_session is called when the script ends
                with patch("src.python.role_play.chat.handler.ChatHandler._validate_active_session", new_callable=MagicMock) as mock_validate:
                    mock_validate.return_value.state = {
                        "script": {
                            "id": "medical_acute_frustration_simple",
                            "script": [
                                {"speaker": "character", "line": "I'm fine, doc. Just a little tweak."},
                                {"speaker": "participant", "line": "Describe the pain for me."},
                                {"speaker": "character", "line": "(Sighs) Okay, it's more of a sharp pain. A 6 or 7 maybe."},
                                {"speaker": "llm", "action": "stop"}
                            ]
                        },
                        "script_index": 3
                    }
                    response = client.post(
                        f"/chat/session/{session_id}/message",
                        json={"message": "Hello"}
                    )
                    assert response.status_code == 200
                    mock_end_session.assert_called_once()
