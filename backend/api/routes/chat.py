"""
Chat API routes - Patient-facing endpoints for CBT conversations.
Opzione C: Uses adaptive ConversationManager instead of rigid state machine.
"""

from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
import yaml

from models.schemas import (
    ChatMessageRequest,
    ChatResponse,
    CreateSessionRequest,
    EndSessionRequest,
    SessionResponse,
    MessageResponse,
    MessageRole,
    AdaptiveConversationContext,
    TherapistBrief,
    PreferredTechniques,
    ClinicalSensitivities,
    TherapistLanguage,
    RiskLevel,
    DistressLevel,
    ConversationMode,
    DisclaimerType,
    AlertLevel,
)
from services.conversation_manager import ConversationManager
from services.risk_detector import RiskDetector
from services.distress_assessor import DistressAssessor
from services.llm_service import LLMService
from utils.database import get_db
from datetime import datetime


router = APIRouter()

# Initialize services
llm_service = LLMService()
risk_detector = RiskDetector(llm_service=llm_service)
distress_assessor = DistressAssessor(llm_service=llm_service)

# Load base prompt from prompts.yaml
def load_base_prompt() -> str:
    """Load base prompt from prompts.yaml"""
    with open("config/prompts.yaml", "r", encoding="utf-8") as f:
        prompts = yaml.safe_load(f)
    return prompts["system_prompts"]["base"]

base_prompt = load_base_prompt()
conversation_manager = ConversationManager(
    llm_service=llm_service,
    risk_detector=risk_detector,
    distress_assessor=distress_assessor,
    base_prompt=base_prompt
)

db = get_db()


@router.post("/session/create", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create a new chat session for a patient."""

    # Verify patient exists
    patient = await db.get_patient_by_access_code(request.patient_access_code)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid access code"
        )

    # Create session with adaptive conversation mode
    session = await db.create_session(
        patient_id=patient["id"],
        session_goal=request.session_goal,
        conversation_mode=ConversationMode.ADAPTIVE.value  # Opzione C
    )

    # Show initial disclaimer
    disclaimer_content = """Welcome! I'm here to help you practice CBT skills between therapy sessions.

**Important to know:**
- I'm a skills practice tool, not a therapist
- I can't provide diagnosis, treatment decisions, or crisis support
- If you're in crisis, please contact emergency services or a crisis helpline
- The insights you discover here are valuable to share with your therapist

Ready to get started?"""

    # Log disclaimer
    await db.create_disclaimer_log(
        session_id=session["id"],
        patient_id=patient["id"],
        disclaimer_type=DisclaimerType.INITIAL_CONSENT.value,
        content=disclaimer_content,
        triggered_by="session_start"
    )

    return SessionResponse(**session)


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatMessageRequest):
    """
    Send a message in a chat session.
    Main endpoint for patient-assistant interaction using adaptive ConversationManager.
    """

    # Verify patient
    patient = await db.get_patient_by_access_code(request.patient_access_code)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid access code"
        )

    # Get or create session
    if request.session_id:
        session = await db.get_session(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
    else:
        # Create new session
        session = await db.create_session(
            patient_id=patient["id"],
            conversation_mode=ConversationMode.ADAPTIVE.value
        )

    # Check if session is ended or terminated
    if session["status"] in ["terminated"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is {session['status']}. Please start a new session."
        )

    # Load therapist brief for this patient
    therapist_brief = await _load_therapist_brief(patient)

    # Build conversation context
    conversation_history = await db.get_session_messages(session["id"])
    history_formatted = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation_history
    ]

    context = AdaptiveConversationContext(
        session_id=session["id"],
        patient_id=patient["id"],
        current_state=session.get("current_state", "menu"),
        session_goal=session.get("session_goal"),
        user_name=patient.get("preferred_name"),
        country_code=patient.get("country_code", "US"),
        history=history_formatted,
        therapist_brief=therapist_brief,
        conversation_mode=ConversationMode.ADAPTIVE,
        distress_level=DistressLevel(session.get("distress_level", "none")),
        grounding_count=session.get("grounding_count", 0),
        disclaimer_shown_count=session.get("disclaimer_shown_count", 0),
        last_disclaimer_at=session.get("last_disclaimer_at")
    )

    # HANDLE MESSAGE with ConversationManager
    result = await conversation_manager.handle_message(
        message=request.message,
        context=context,
        therapist_brief=therapist_brief
    )

    # Save user message to database
    user_msg = await db.create_message(
        session_id=session["id"],
        role=MessageRole.USER.value,
        content=request.message,
        risk_scan_performed=True,
        risk_level=result["risk_detection"]["level"],
        risk_keywords=result["risk_detection"]["triggers"]
    )

    # Save assistant response to database
    assistant_msg = await db.create_message(
        session_id=session["id"],
        role=MessageRole.ASSISTANT.value,
        content=result["response"],
        model_used=result.get("model_used", "deepseek-chat"),
        tokens_used=result.get("tokens_used"),
    )

    # Handle risk events
    if result["risk_detection"]["should_escalate"]:
        risk_level = result["risk_detection"]["level"]

        # Determine alert level
        alert_level = AlertLevel.HIGH if risk_level == "high" else AlertLevel.MEDIUM

        # Create risk event
        risk_event = await db.create_risk_event(
            session_id=session["id"],
            patient_id=patient["id"],
            message_id=user_msg["id"],
            risk_level=risk_level,
            alert_level=alert_level.value,
            risk_type="detected_by_conversation_manager",
            detected_keywords=result["risk_detection"]["triggers"],
            full_message_content=request.message,
            ai_reasoning=result["risk_detection"]["reasoning"],
            escalation_flow_triggered=True,
            session_terminated=result.get("should_end_session", False),
            resources_provided=result.get("should_end_session", False),
            patient_state_at_event={
                "distress_level": result["distress_assessment"]["level"],
                "signals_detected": result["distress_assessment"]["signals_detected"]
            }
        )

        # Notification will be created automatically by database trigger

    # Update session with new state
    await db.update_session(
        session_id=session["id"],
        distress_level=result["distress_assessment"]["level"],
        grounding_performed=result.get("grounding_offered", False),
        grounding_count=context.grounding_count,
        disclaimer_shown_count=context.disclaimer_shown_count,
        last_disclaimer_at=context.last_disclaimer_at,
        risk_level=result["risk_detection"]["level"],
        risk_flagged=result["risk_detection"]["should_escalate"],
        status="flagged" if result.get("should_end_session") else session["status"]
    )

    # Log disclaimer if shown
    if result.get("disclaimer_shown"):
        await db.create_disclaimer_log(
            session_id=session["id"],
            patient_id=patient["id"],
            disclaimer_type=result["disclaimer_type"],
            content="Disclaimer shown in response",
            triggered_by=f"message_count_{len(history_formatted) // 2}"
        )

    # Determine resources to return to client
    resources_payload = None
    if result["risk_detection"]["should_escalate"]:
        resources_payload = _get_crisis_resources(patient.get("country_code", "US"))

    # Build response
    return ChatResponse(
        session_id=session["id"],
        message=MessageResponse(
            id=assistant_msg["id"],
            role=MessageRole.ASSISTANT,
            content=result["response"],
            created_at=assistant_msg["created_at"],
            risk_level=RiskLevel(result["risk_detection"]["level"])
        ),
        session_status=session["status"],
        current_state=session.get("current_state", "menu"),
        risk_detected=result["risk_detection"]["should_escalate"],
        risk_level=RiskLevel(result["risk_detection"]["level"]),
        risk_reasoning=result["risk_detection"]["reasoning"],
        risk_triggers=result["risk_detection"]["triggers"],
        distress_reasoning=result["distress_assessment"]["reasoning"],
        distress_signals=result["distress_assessment"]["signals_detected"],
        should_end_session=result.get("should_end_session", False),
        resources=resources_payload
    )


@router.post("/session/end", response_model=SessionResponse)
async def end_session(request: EndSessionRequest):
    """End a chat session."""

    # Verify patient
    patient = await db.get_patient_by_access_code(request.patient_access_code)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid access code"
        )

    # Get session
    session = await db.get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Update session
    await db.update_session(
        session_id=session["id"],
        status="completed",
        ended_at=datetime.now()
    )

    return SessionResponse(**session)


@router.get("/session/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(session_id: str, patient_access_code: str):
    """Get all messages in a session."""

    # Verify patient
    patient = await db.get_patient_by_access_code(patient_access_code)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid access code"
        )

    # Get messages
    messages = await db.get_session_messages(session_id)

    return [MessageResponse(**msg) for msg in messages]


@router.post("/prompts/reload")
async def reload_prompts():
    """Reload prompts from prompts.yaml without restarting server."""
    global base_prompt, conversation_manager

    try:
        base_prompt = load_base_prompt()
        conversation_manager.base_prompt = base_prompt

        return {
            "status": "success",
            "message": "Prompts reloaded successfully",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload prompts: {str(e)}"
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def _load_therapist_brief(patient: dict) -> Optional[TherapistBrief]:
    """
    Load therapist brief for patient from database.

    Returns None if no brief configured (patient will use default CBT approach).
    """
    if not patient.get("case_formulation"):
        return None

    # Build TherapistBrief from patient data
    brief = TherapistBrief(
        case_formulation=patient.get("case_formulation"),
        presenting_problems=patient.get("presenting_problems", []),
        treatment_goals=patient.get("treatment_goals", []),
        therapy_stage=patient.get("therapy_stage", "early"),
        preferred_techniques=PreferredTechniques(
            **(patient.get("preferred_techniques", {}))
        ) if patient.get("preferred_techniques") else PreferredTechniques(),
        sensitivities=ClinicalSensitivities(
            **(patient.get("sensitivities", {}))
        ) if patient.get("sensitivities") else ClinicalSensitivities(),
        therapist_language=TherapistLanguage(
            **(patient.get("therapist_language", {}))
        ) if patient.get("therapist_language") else TherapistLanguage(),
        contraindications=patient.get("contraindications", [])
    )

    return brief


def _get_crisis_resources(country_code: str) -> dict:
    """Get country-specific crisis resources."""
    resources_map = {
        "US": {
            "hotline": "988 Suicide & Crisis Lifeline",
            "phone": "988",
            "text": "Text 'HELLO' to 741741",
            "emergency": "911"
        },
        "UK": {
            "hotline": "Samaritans",
            "phone": "116 123",
            "text": "Text 'SHOUT' to 85258",
            "emergency": "999"
        },
        "IT": {
            "hotline": "Telefono Amico",
            "phone": "02 2327 2327",
            "text": "Telefono Azzurro: 19696",
            "emergency": "112"
        },
    }

    return resources_map.get(country_code, resources_map["US"])
