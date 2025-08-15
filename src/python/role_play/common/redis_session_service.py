"""Redis-based session service for distributed session management."""
import asyncio
import copy
import logging
import json
import redis.asyncio as redis
from typing import Optional, Dict, Any, List
from uuid import uuid4

from google.adk.sessions import Session, BaseSessionService, State

logger = logging.getLogger(__name__)

class RedisSessionService(BaseSessionService):
    """A Redis-based implementation of the session service."""

    def __init__(self, redis_url: str = "redis://localhost"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.user_prefix = "user_sessions"
        self.app_prefix = "app_sessions"

    async def _get_session_key(self, app_name: str, user_id: str, session_id: str) -> str:
        return f"{self.app_prefix}:{app_name}:{self.user_prefix}:{user_id}:{session_id}"

    async def create_session(
        self,
        app_name: str,
        user_id: str,
        state: Optional[State] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        session_id = session_id or str(uuid4())
        session_key = await self._get_session_key(app_name, user_id, session_id)
        
        initial_state = {
            "id": session_id,
            "user_id": user_id,
            "app_name": app_name,
            "state": json.dumps(state or {}),
            "events": json.dumps([]),
        }
        
        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.hset(session_key, mapping=initial_state)
            await pipe.expire(session_key, 3600)  # 1-hour expiration
            await pipe.execute()
            
        logger.info(f"Created Redis session {session_id} for user {user_id}")
        
        # Deserialize state for the returned Session object
        final_state = initial_state.copy()
        final_state['state'] = state or {}
        final_state['events'] = []
        return Session(**final_state)

    async def get_session(
        self, app_name: str, user_id: str, session_id: str
    ) -> Optional[Session]:
        session_key = await self._get_session_key(app_name, user_id, session_id)
        session_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in (await self.redis.hgetall(session_key)).items()}
        
        if not session_data:
            return None
            
        # Deserialize state and events
        if 'state' in session_data and isinstance(session_data['state'], str):
            session_data['state'] = json.loads(session_data['state'])
        if 'events' in session_data and isinstance(session_data['events'], str):
            session_data['events'] = json.loads(session_data['events'])
        
        return Session(**session_data)

    async def delete_session(self, app_name: str, user_id: str, session_id: str):
        session_key = await self._get_session_key(app_name, user_id, session_id)
        await self.redis.delete(session_key)
        logger.info(f"Deleted Redis session {session_id}")

    async def list_sessions(self, app_name: str, user_id: str) -> List[Session]:
        sessions = []
        pattern = f"{self.app_prefix}:{app_name}:{self.user_prefix}:{user_id}:*"
        async for key in self.redis.scan_iter(pattern):
            session_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in (await self.redis.hgetall(key)).items()}
            if session_data:
                if 'state' in session_data and isinstance(session_data['state'], str):
                    session_data['state'] = json.loads(session_data['state'])
                if 'events' in session_data and isinstance(session_data['events'], str):
                    session_data['events'] = json.loads(session_data['events'])
                sessions.append(Session(**session_data))
        return sessions

    async def append_event(
        self, app_name: str, user_id: str, session_id: str, event: Dict[str, Any]
    ):
        session_key = await self._get_session_key(app_name, user_id, session_id)
        
        # Use a transaction to safely append the event
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(session_key)
                    
                    current_events_str = await pipe.hget(session_key, "events")
                    current_events = json.loads(current_events_str) if current_events_str else []
                    current_events.append(event)
                    
                    pipe.multi()
                    pipe.hset(session_key, "events", json.dumps(current_events))
                    await pipe.execute()
                    break
                except redis.WatchError:
                    continue

    # Sync methods for compatibility
    def create_session_sync(self, *args, **kwargs):
        logger.warning("Using sync method for async Redis service. Consider switching to async.")
        return asyncio.run(self.create_session(*args, **kwargs))

    def get_session_sync(self, *args, **kwargs):
        logger.warning("Using sync method for async Redis service. Consider switching to async.")
        return asyncio.run(self.get_session(*args, **kwargs))
