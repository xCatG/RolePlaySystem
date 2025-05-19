"""
Pydantic models for API request and response data
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timezone

class ChatMessage(BaseModel):
    message: str = Field(..., description="Message content")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00","Z"), description="Timestamp of the message")


class ChatResponse(BaseModel):
    messages: List[ChatMessage] = Field(..., description="List of chat messages")

class ChatRequest(BaseModel):
    message: str = Field(..., description="Message content")

class StatusResponse(BaseModel):
    status: str = Field(..., description="Status of the server")
    version: str = Field(..., description="Version of the server")
    environment: str = Field(..., description="Environment in which the server is running")
    providers: Dict[str, bool] = Field(..., description="Information about available API providers")
