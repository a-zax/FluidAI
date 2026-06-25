from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ActionType(str, Enum):
    CREATE_TICKET = "create_ticket"
    GENERATE_REPORT = "generate_report"
    FETCH_EMPLOYEE = "fetch_employee"
    QUERY_KNOWLEDGE = "query_knowledge"
    PENDING_CONFIRMATION = "pending_confirmation"
    NONE = "none"


class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=120)
    enable_actions: bool = True
    business_action: Optional[str] = None

    @field_validator("question", mode="before")
    @classmethod
    def normalize_question(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("Question must be a string")
        normalized = " ".join(value.strip().split())
        if len(normalized) < 2:
            raise ValueError("Question must contain at least 2 characters")
        return normalized


class AskResponse(BaseModel):
    answer: str
    session_id: str
    action_performed: Optional[ActionType] = None
    action_result: Optional[Dict[str, Any]] = None
    retrieved_context: List[str] = []
    memory_used: bool = False
    latency_ms: float
    query_type: str
    tokens_used: int
    cached: bool = False
    pending_confirmation: Optional[Dict[str, Any]] = None


class ConversationTurn(BaseModel):
    question: str
    answer: str
    entities: Dict[str, Any]
    action_performed: Optional[str]
    created_at: str


class ActionDecision(BaseModel):
    action: ActionType
    parameters: Dict[str, Any] = {}
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class DocumentRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=160)
    body: str = Field(..., min_length=20, max_length=12000)
    source: str = Field(default="user", max_length=80)

    @field_validator("title", "body", "source", mode="before")
    @classmethod
    def normalize_text(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("Value must be a string")
        return " ".join(value.strip().split())


class ConfirmActionResponse(BaseModel):
    pending_action_id: str
    action_performed: ActionType
    action_result: Dict[str, Any]
    status: str
