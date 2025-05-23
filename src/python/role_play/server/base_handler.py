"""Base handler class for all Role Play System handlers."""

from abc import ABC, abstractmethod
from fastapi import APIRouter
from typing import Optional


class BaseHandler(ABC):
    """
    Abstract base class for all handlers in the Role Play System.
    
    Handlers are stateless and instantiated per request (HTTP) or per connection (WebSocket).
    Each handler defines its own routes and dependencies through FastAPI's dependency injection.
    """
    
    def __init__(self):
        """Initialize the handler. Subclasses should override to accept dependencies."""
        self._router: Optional[APIRouter] = None
    
    @property
    @abstractmethod
    def router(self) -> APIRouter:
        """
        Return the FastAPI router for this handler.
        
        Subclasses must implement this to define their routes.
        The router should be created lazily and cached.
        """
        pass
    
    @property
    @abstractmethod
    def prefix(self) -> str:
        """Return the URL prefix for this handler's routes (e.g., '/auth', '/chat')."""
        pass
    
    @property
    def tags(self) -> list[str]:
        """Return OpenAPI tags for this handler's routes. Override if needed."""
        return [self.__class__.__name__.replace("Handler", "").lower()]