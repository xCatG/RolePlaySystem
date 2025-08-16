import logging

from fastapi import HTTPException, Depends, APIRouter, Query

from ..server.base_handler import BaseHandler
from ..server.dependencies import (
    require_user_or_higher,
    get_chat_logger,
    get_adk_session_service,
    get_resource_loader,
)


logger = logging.getLogger(__name__)

class VoiceHandler(BaseHandler):
    """Handler for chat-related endpoints - Simplified & Stateless."""

    # All dependencies (ResourceLoader, ChatLogger, InMemorySessionService)
    # will be injected via FastAPI's Depends in the route methods.

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self._router = APIRouter()

        return self._router

    @property
    def prefix(self) -> str:
        return "/voice"

