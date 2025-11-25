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


class AlertLevel(str, Enum):
    """Urgency level for therapist notifications."""
    LOW = "low"  # Keyword match only, no LLM confirmation
    MEDIUM = "medium"  # LLM detected concern, monitoring needed
    HIGH = "high"  # Clear risk, needs prompt attention
    CRITICAL = "critical"  # Active crisis, immediate action required


class DistressLevel(str, Enum):
    """Patient distress level for adaptive conversation."""
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRISIS = "crisis"


class TherapyStage(str, Enum):
    """Stage of therapy for treatment planning."""
    EARLY = "early"  # Building rapport, psychoeducation
    MIDDLE = "middle"  # Active CBT work
    LATE = "late"  # Consolidation, relapse prevention


class ConversationMode(str, Enum):
    """Conversation style for session."""
    ADAPTIVE = "adaptive"  # Opzione C - flexible, context-aware
    STRUCTURED = "structured"  # Old state machine - fixed steps


class NotificationType(str, Enum):
    """Types of notifications sent to therapists."""
    RISK_ALERT = "risk_alert"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_SUMMARY = "weekly_summary"
    PRE_SESSION_REPORT = "pre_session_report"
    PATIENT_MESSAGE = "patient_message"


class NotificationPriority(str, Enum):
    """Priority level for notifications."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DisclaimerType(str, Enum):
    """Types of boundary/disclaimer reminders."""
    INITIAL_CONSENT = "initial_consent"
    PERIODIC_REMINDER = "periodic_reminder"
    CRISIS_BOUNDARY = "crisis_boundary"
    THERAPY_REFERRAL = "therapy_referral"
    HIGH_DEPENDENCY = "high_dependency"


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


# ============================================================================
# OPZIONE C - THERAPIST BRIEF SCHEMAS
# ============================================================================

class PreferredTechniques(BaseModel):
    """CBT techniques preferred by therapist for a patient."""
    cognitive_restructuring: bool = True
    behavioral_activation: bool = True
    exposure: bool = False
    distress_tolerance: bool = True
    schema_work: bool = False


class ClinicalSensitivities(BaseModel):
    """Important clinical sensitivities for patient care."""
    trauma_history: Optional[str] = None  # "childhood abuse - avoid direct questions"
    pacing: Optional[str] = "moderate"  # slow, moderate, fast
    topics_to_avoid: List[str] = Field(default_factory=list)


class TherapistLanguage(BaseModel):
    """Metaphors, coping statements, and terms therapist uses with patient."""
    metaphors: List[str] = Field(default_factory=list)  # ["worry radio", "anxiety alarm"]
    coping_statements: List[str] = Field(default_factory=list)  # ["feelings aren't facts"]
    preferred_terms: Dict[str, str] = Field(default_factory=dict)  # {"panic": "intense anxiety"}


class TherapistBrief(BaseModel):
    """Complete therapist brief for patient-specific treatment approach."""
    case_formulation: Optional[str] = None
    presenting_problems: List[str] = Field(default_factory=list)
    treatment_goals: List[str] = Field(default_factory=list)
    therapy_stage: TherapyStage = TherapyStage.EARLY
    preferred_techniques: PreferredTechniques = Field(default_factory=PreferredTechniques)
    sensitivities: ClinicalSensitivities = Field(default_factory=ClinicalSensitivities)
    therapist_language: TherapistLanguage = Field(default_factory=TherapistLanguage)
    contraindications: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class UpdateTherapistBriefRequest(BaseModel):
    """Request to update therapist brief for a patient."""
    patient_id: str
    therapist_email: str
    brief: TherapistBrief


# ============================================================================
# NOTIFICATION SCHEMAS
# ============================================================================

class NotificationPreferences(BaseModel):
    """Therapist notification preferences."""
    email_enabled: bool = True
    sms_enabled: bool = False
    high_risk_immediate: bool = True
    daily_summary: bool = False
    weekly_summary: bool = True


class NotificationResponse(BaseModel):
    """Response schema for notifications."""
    id: str
    therapist_id: str
    notification_type: NotificationType
    priority: NotificationPriority
    patient_id: Optional[str] = None
    session_id: Optional[str] = None
    subject: str
    message_body: str
    email_sent: bool
    sms_sent: bool
    read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateNotificationRequest(BaseModel):
    """Request to create a notification."""
    therapist_id: str
    notification_type: NotificationType
    priority: NotificationPriority
    patient_id: Optional[str] = None
    session_id: Optional[str] = None
    risk_event_id: Optional[str] = None
    subject: str
    message_body: str


class MarkNotificationReadRequest(BaseModel):
    """Request to mark notification as read."""
    notification_id: str
    therapist_id: str


# ============================================================================
# APPOINTMENT SCHEMAS
# ============================================================================

class AppointmentResponse(BaseModel):
    """Response schema for appointments."""
    id: str
    therapist_id: str
    patient_id: str
    scheduled_at: datetime
    duration_minutes: int
    appointment_type: str
    report_generated: bool
    report_sent: bool
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateAppointmentRequest(BaseModel):
    """Request to create an appointment."""
    therapist_id: str
    patient_id: str
    scheduled_at: datetime
    duration_minutes: int = 50
    appointment_type: str = "regular"
    notes: Optional[str] = None


class PreSessionReport(BaseModel):
    """Pre-session report generated 24h before appointment."""
    appointment_id: str
    patient_id: str
    patient_name: str
    scheduled_at: datetime

    # Recent activity summary
    sessions_since_last_appointment: int
    total_messages: int
    skills_practiced: List[Dict[str, Any]]

    # Mood trends
    avg_mood_start: Optional[float] = None
    avg_mood_end: Optional[float] = None
    mood_trend: Optional[str] = None

    # Risk indicators
    risk_events_count: int
    unreviewed_high_risk_events: int

    # Key themes
    top_triggers: List[str]
    common_emotions: List[str]

    # AI-generated summary
    ai_summary: str

    # Notable sessions (high risk, significant progress, etc.)
    notable_sessions: List[Dict[str, Any]]


# ============================================================================
# DISCLAIMER SCHEMAS
# ============================================================================

class DisclaimerLogResponse(BaseModel):
    """Response schema for disclaimer logs."""
    id: str
    session_id: str
    patient_id: str
    disclaimer_type: DisclaimerType
    content: str
    triggered_by: str
    patient_acknowledged: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShowDisclaimerRequest(BaseModel):
    """Request to show disclaimer to patient."""
    session_id: str
    patient_id: str
    disclaimer_type: DisclaimerType
    triggered_by: str


# ============================================================================
# ENHANCED PATIENT SCHEMAS
# ============================================================================

class PatientWithBrief(BaseModel):
    """Patient data including therapist brief."""
    id: str
    access_code: str
    preferred_name: Optional[str] = None
    country_code: str
    therapist_brief: Optional[TherapistBrief] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# DISTRESS ASSESSMENT SCHEMAS
# ============================================================================

class DistressAssessment(BaseModel):
    """Result of distress level assessment."""
    distress_level: DistressLevel
    reasoning: str
    signals_detected: List[str]  # ["rapid breathing", "can't focus", "overwhelming"]
    requires_grounding: bool
    grounding_technique_suggested: Optional[str] = None


class GroundingExerciseRequest(BaseModel):
    """Request for grounding exercise."""
    session_id: str
    patient_id: str
    distress_level: DistressLevel
    preferred_technique: Optional[str] = None  # "5-4-3-2-1", "breathing", "body_scan"


class GroundingExerciseResponse(BaseModel):
    """Response with grounding exercise content."""
    technique_name: str
    instructions: str
    estimated_duration_seconds: int
    follow_up_message: str


# ============================================================================
# ENHANCED RISK EVENT SCHEMAS
# ============================================================================

class EnhancedRiskEventResponse(RiskEventResponse):
    """Extended risk event with alert level and notification info."""
    alert_level: AlertLevel
    notification_sent: bool
    notification_sent_at: Optional[datetime] = None
    patient_state_at_event: Optional[Dict[str, Any]] = None


# ============================================================================
# ENHANCED DASHBOARD SCHEMAS
# ============================================================================

class EnhancedPatientOverview(PatientOverview):
    """Enhanced patient overview with Opzione C features."""
    therapy_stage: Optional[TherapyStage] = None
    case_formulation: Optional[str] = None
    critical_alerts: int = 0
    unread_notifications: int = 0
    next_appointment_at: Optional[datetime] = None
    last_high_risk_date: Optional[datetime] = None


class EnhancedTherapistDashboardResponse(BaseModel):
    """Enhanced therapist dashboard with notifications and appointments."""
    therapist_id: str
    therapist_name: str
    patients: List[EnhancedPatientOverview]
    total_unreviewed_flags: int
    total_critical_alerts: int
    unread_notifications: int
    recent_flags: List[EnhancedRiskEventResponse]
    upcoming_appointments: List[AppointmentResponse]
    notifications: List[NotificationResponse]


# ============================================================================
# ADAPTIVE CONVERSATION SCHEMAS
# ============================================================================

class ConversationDecision(BaseModel):
    """Decision made by ConversationManager about how to respond."""
    response_mode: str  # "grounding", "cbt_skill", "clarification", "crisis_protocol"
    distress_level: DistressLevel
    technique_to_apply: Optional[str] = None
    reasoning: str


class AdaptiveConversationContext(ConversationContext):
    """Extended conversation context for adaptive mode."""
    conversation_mode: ConversationMode = ConversationMode.ADAPTIVE
    therapist_brief: Optional[TherapistBrief] = None
    distress_level: DistressLevel = DistressLevel.NONE
    grounding_count: int = 0
    disclaimer_shown_count: int = 0
    last_disclaimer_at: Optional[datetime] = None

    # Track adaptive flow
    recent_topics: List[str] = Field(default_factory=list)
    current_cbt_focus: Optional[str] = None  # "challenging catastrophic thought", "planning exposure"
