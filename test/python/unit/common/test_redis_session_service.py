"""Unit tests for the RedisSessionService."""

import pytest
import fakeredis.aioredis
from src.python.role_play.common.redis_session_service import RedisSessionService
from google.adk.events.event import Event

@pytest.fixture
def mock_redis(monkeypatch):
    """Mocks the redis connection with fakeredis."""
    fake_redis_client = fakeredis.aioredis.FakeRedis()
    monkeypatch.setattr("redis.asyncio.from_url", lambda *args, **kwargs: fake_redis_client)
    return fake_redis_client

@pytest.fixture
async def session_service(mock_redis):
    """Creates a RedisSessionService instance with a mocked redis client."""
    return RedisSessionService()

@pytest.mark.asyncio
async def test_create_and_get_session(session_service: RedisSessionService):
    """Test creating a new session and retrieving it."""
    app_name = "test_app"
    user_id = "test_user"
    session = await session_service.create_session(app_name, user_id)

    retrieved_session = await session_service.get_session(app_name, user_id, session.id)

    assert retrieved_session is not None
    assert retrieved_session.id == session.id
    assert retrieved_session.user_id == user_id

@pytest.mark.asyncio
async def test_delete_session(session_service: RedisSessionService):
    """Test deleting a session."""
    app_name = "test_app"
    user_id = "test_user"
    session = await session_service.create_session(app_name, user_id)

    await session_service.delete_session(app_name, user_id, session.id)

    retrieved_session = await session_service.get_session(app_name, user_id, session.id)
    assert retrieved_session is None

@pytest.mark.asyncio
async def test_list_sessions(session_service: RedisSessionService):
    """Test listing sessions for a user."""
    app_name = "test_app"
    user_id = "test_user"

    await session_service.create_session(app_name, user_id)
    await session_service.create_session(app_name, user_id)

    sessions = await session_service.list_sessions(app_name, user_id)
    assert len(sessions) == 2

@pytest.mark.asyncio
async def test_append_event(session_service: RedisSessionService):
    """Test appending an event to a session."""
    app_name = "test_app"
    user_id = "test_user"
    session = await session_service.create_session(app_name, user_id)

    event = Event(author="user", content={"parts": [{"text": "test_data"}]})
    await session_service.append_event(app_name, user_id, session.id, event.model_dump())

    retrieved_session = await session_service.get_session(app_name, user_id, session.id)
    assert len(retrieved_session.events) == 1
    assert retrieved_session.events[0].content.parts[0].text == "test_data"
