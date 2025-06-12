"""Tool functions for the multi-agent evaluator."""

from __future__ import annotations

import json
from typing import List, Dict, Any

from role_play.chat.chat_logger import ChatLogger
from role_play.chat.content_loader import ContentLoader
from role_play.common.storage import StorageBackend


# Globals that will be configured by the evaluation handler
CHAT_LOGGER: ChatLogger | None = None
STORAGE: StorageBackend | None = None
CURRENT_USER_ID: str | None = None

content_loader = ContentLoader(supported_languages=["en", "zh-TW", "ja"])


def configure_tools(*, chat_logger: ChatLogger, storage: StorageBackend, user_id: str) -> None:
    """Configure global dependencies for the tool functions."""
    global CHAT_LOGGER, STORAGE, CURRENT_USER_ID
    CHAT_LOGGER = chat_logger
    STORAGE = storage
    CURRENT_USER_ID = user_id


async def get_chat_history(session_id: str) -> str:
    """Retrieve the full chat history for a session as a formatted string."""
    if CHAT_LOGGER is None or CURRENT_USER_ID is None:
        raise RuntimeError("Tools not configured")
    messages = await CHAT_LOGGER.get_session_messages(CURRENT_USER_ID, session_id)
    return "\n".join(f"{m['role']}: {m['content']}" for m in messages)


async def get_scenario_details(scenario_id: str, language: str) -> Dict[str, Any]:
    """Fetch scenario details in the requested language."""
    scenario = content_loader.get_scenario_by_id(scenario_id, language)
    return scenario or {}


async def get_user_past_summaries(user_id: str) -> List[Dict[str, Any]]:
    """Retrieve past evaluation summaries for the user."""
    if STORAGE is None:
        raise RuntimeError("Tools not configured")
    prefix = f"users/{user_id}/evaluations/"
    keys = await STORAGE.list_keys(prefix)
    summaries = []
    for key in keys:
        try:
            data = await STORAGE.read(key)
            summaries.append(json.loads(data))
        except Exception:
            continue
    return summaries


async def store_final_review(user_id: str, session_id: str, review: Dict[str, Any]) -> None:
    """Store the final review JSON for later retrieval."""
    if STORAGE is None:
        raise RuntimeError("Tools not configured")
    path = f"users/{user_id}/evaluations/{session_id}.json"
    await STORAGE.write(path, json.dumps(review, ensure_ascii=False))

