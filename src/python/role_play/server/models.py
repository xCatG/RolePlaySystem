"""
Pydantic models for API request and response data
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

class ModelProvider(str, Enum):
    """Enum for supported model providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"

class ChatMode(str, Enum):
    """Enum for chat modes"""
    NORMAL = "normal"
    ROLE_PLAY = "role_play"
    EVALUATION = "evaluation"

class ChatMessage(BaseModel):
    """Chat message model"""
    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")
    name: Optional[str] = Field(None, description="Optional name for the message")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, description="Message timestamp")

class ChatRequest(BaseModel):
    """Request model for chat completion"""
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    provider: ModelProvider = Field(default=ModelProvider.ANTHROPIC, description="Model provider")
    model: Optional[str] = Field(None, description="Specific model to use")
    temperature: Optional[float] = Field(0.7, description="Temperature for generation")
    max_tokens: Optional[int] = Field(1000, description="Maximum tokens to generate")
    mode: ChatMode = Field(default=ChatMode.NORMAL, description="Chat mode")
    script_id: Optional[str] = Field(None, description="Script ID for role play mode")

class ChatResponse(BaseModel):
    """Response model for chat completion"""
    message: ChatMessage = Field(..., description="Generated assistant message")
    usage: Dict[str, Any] = Field(default_factory=dict, description="Usage information")
    request_id: str = Field(..., description="Request ID for tracking")

class ScriptRequest(BaseModel):
    """Request model for script generation"""
    prompt: str = Field(..., description="Prompt for script generation")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional parameters")
    provider: ModelProvider = Field(default=ModelProvider.ANTHROPIC, description="Model provider")

class ScriptResponse(BaseModel):
    """Response model for script generation"""
    script_id: str = Field(..., description="Generated script ID")
    script_content: Dict[str, Any] = Field(..., description="Generated script content")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")

class EvaluationRequest(BaseModel):
    """Request model for conversation evaluation"""
    conversation: List[ChatMessage] = Field(..., description="Conversation to evaluate")
    script_id: Optional[str] = Field(None, description="Script ID for role play evaluation")
    criteria: Optional[List[str]] = Field(None, description="Evaluation criteria")

class EvaluationResponse(BaseModel):
    """Response model for evaluation results"""
    scores: Dict[str, float] = Field(..., description="Evaluation scores")
    feedback: str = Field(..., description="Feedback on the conversation")
    evaluation_id: str = Field(..., description="Evaluation ID for tracking")

class StatusResponse(BaseModel):
    """API status response"""
    status: str = Field("ok", description="API status")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Environment (development, staging, production)")
    providers: Dict[str, bool] = Field(..., description="Available model providers")
    timestamp: datetime = Field(default_factory=datetime.now, description="Server timestamp")
