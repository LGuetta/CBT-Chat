"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    FLAGGED = "flagged"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SkillType(str, Enum):
    THOUGHT_RECORD = "thought_record"
    BEHAVIORAL_ACTIVATION = "behavioral_activation"
    EXPOSURE = "exposure"
    COPING = "coping"
    PSYCHOEDUCATION = "psychoeducation"


class ConversationState(str, Enum):
    CONSENT = "consent"
    INTAKE = "intake"
    MENU = "menu"
    THOUGHT_RECORD = "thought_record"
    BEHAVIORAL_ACTIVATION = "behavioral_activation"
    EXPOSURE = "exposure"
    COPING = "coping"
    LEARN = "learn"
    RISK_ESCALATION = "risk_escalation"
    ENDED = "ended"


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class ChatMessageRequest(BaseModel):
    """Request schema for sending a chat message."""
    session_id: Optional[str] = None
    patient_access_code: str = Field(..., description="Patient's access code")
    message: str = Field(..., min_length=1, description="User's message")


class CreateSessionRequest(BaseModel):
    """Request schema for creating a new session."""
    patient_access_code: str = Field(..., description="Patient's access code")
    session_goal: Optional[str] = None


class EndSessionRequest(BaseModel):
    """Request schema for ending a session."""
    session_id: str
    patient_access_code: str


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class MessageResponse(BaseModel):
    """Response schema for a single message."""
    id: str
    role: MessageRole
    content: str
    created_at: datetime
    risk_level: Optional[RiskLevel] = None

    model_config = ConfigDict(from_attributes=True)


class SessionResponse(BaseModel):
    """Response schema for session data."""
    id: str
    patient_id: str
    status: SessionStatus
    current_state: ConversationState
    current_skill: Optional[str] = None
    session_goal: Optional[str] = None
    risk_flagged: bool
    risk_level: RiskLevel
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_messages: int
    mood_start: Optional[int] = None
    mood_end: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    """Response schema for chat messages."""
    session_id: str
    message: MessageResponse
    session_status: SessionStatus
    current_state: ConversationState
    risk_detected: bool
    risk_level: RiskLevel
    should_end_session: bool = False
    resources: Optional[Dict[str, str]] = None


class RiskEventResponse(BaseModel):
    """Response schema for risk events."""
    id: str
    session_id: str
    patient_id: str
    risk_level: RiskLevel
    risk_type: Optional[str] = None
    detected_keywords: List[str]
    created_at: datetime
    therapist_reviewed: bool

    model_config = ConfigDict(from_attributes=True)


class SkillCompletionResponse(BaseModel):
    """Response schema for skill completions."""
    id: str
    skill_type: SkillType
    skill_name: Optional[str] = None
    data: Dict[str, Any]
    mood_before: Optional[int] = None
    mood_after: Optional[int] = None
    completion_status: str
    completed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionSummaryResponse(BaseModel):
    """Response schema for session summaries."""
    id: str
    patient_id: str
    period_start: datetime
    period_end: datetime
    total_sessions: int
    total_duration_minutes: int
    skills_practiced: List[Dict[str, Any]]
    completion_rate: Optional[float] = None
    avg_mood_start: Optional[float] = None
    avg_mood_end: Optional[float] = None
    mood_improvement_avg: Optional[float] = None
    top_triggers: List[str]
    risk_events_count: int
    ai_summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# THERAPIST DASHBOARD SCHEMAS
# ============================================================================

class PatientOverview(BaseModel):
    """Patient overview for therapist dashboard."""
    patient_id: str
    preferred_name: Optional[str] = None
    access_code: str
    total_sessions: int
    flagged_sessions: int
    last_session_date: Optional[datetime] = None
    last_flag_date: Optional[datetime] = None
    unreviewed_risk_events: int


class TherapistDashboardResponse(BaseModel):
    """Therapist dashboard data."""
    therapist_id: str
    therapist_name: str
    patients: List[PatientOverview]
    total_unreviewed_flags: int
    recent_flags: List[RiskEventResponse]


class SessionTranscriptResponse(BaseModel):
    """Full session transcript for therapist review."""
    session: SessionResponse
    messages: List[MessageResponse]
    risk_events: List[RiskEventResponse]
    skill_completions: List[SkillCompletionResponse]


# ============================================================================
# INTERNAL SCHEMAS (for state machine)
# ============================================================================

class ConversationContext(BaseModel):
    """Internal context for managing conversation state."""
    session_id: str
    patient_id: str
    current_state: ConversationState
    current_skill: Optional[SkillType] = None
    current_step: Optional[str] = None
    session_goal: Optional[str] = None
    user_name: Optional[str] = None
    country_code: str = "US"

    # Conversation history (for LLM context)
    history: List[Dict[str, str]] = Field(default_factory=list)

    # State-specific data (flexible storage)
    state_data: Dict[str, Any] = Field(default_factory=dict)

    # Risk tracking
    risk_level: RiskLevel = RiskLevel.NONE
    risk_escalation_active: bool = False


class RiskDetectionResult(BaseModel):
    """Result from risk detection analysis."""
    risk_level: RiskLevel
    reasoning: str
    triggers: List[str]
    should_escalate: bool
    should_end_session: bool
    confidence_score: Optional[float] = None


class LLMResponse(BaseModel):
    """Response from LLM service."""
    content: str
    model_used: str
    tokens_used: Optional[int] = None
    processing_time_ms: Optional[int] = None
    finish_reason: Optional[str] = None
