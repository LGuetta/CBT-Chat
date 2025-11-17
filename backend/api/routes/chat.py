"""
Chat API routes - Patient-facing endpoints for CBT conversations.
"""

from fastapi import APIRouter, HTTPException, status
from typing import List

from models.schemas import (
    ChatMessageRequest,
    ChatResponse,
    CreateSessionRequest,
    EndSessionRequest,
    SessionResponse,
    MessageResponse,
    MessageRole,
    ConversationContext,
    ConversationState,
    RiskLevel
)
from services.state_machine import get_state_machine
from services.risk_detector import get_risk_detector
from services.llm_service import get_llm_service
from utils.database import get_db
from utils.prompts import get_prompts
from datetime import datetime


router = APIRouter()
state_machine = get_state_machine()
risk_detector = get_risk_detector()
db = get_db()
prompts = get_prompts()


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

    # Create session
    session = await db.create_session(
        patient_id=patient["id"],
        session_goal=request.session_goal
    )

    return SessionResponse(**session)


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatMessageRequest):
    """
    Send a message in a chat session.
    Main endpoint for patient-assistant interaction.
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
            patient_id=patient["id"]
        )

    # Check if session is ended or flagged
    if session["status"] in ["terminated", "flagged"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is {session['status']}. Please start a new session."
        )

    # Save user message
    user_msg = await db.create_message(
        session_id=session["id"],
        role="user",
        content=request.message
    )

    # STEP 1: Risk Detection
    conversation_history = await db.get_session_messages(session["id"])
    history_for_risk = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation_history[-10:]  # Last 10 messages
    ]

    risk_result = await risk_detector.detect_risk(
        message=request.message,
        conversation_history=history_for_risk
    )

    # Update message with risk data
    await db.create_message(
        session_id=session["id"],
        role="user",
        content=request.message,
        risk_scan_performed=True,
        risk_level=risk_result.risk_level.value,
        risk_keywords=risk_result.triggers
    )

    # Handle HIGH risk - escalate immediately
    if risk_result.risk_level == RiskLevel.HIGH:
        # Create risk event
        await db.create_risk_event(
            session_id=session["id"],
            patient_id=patient["id"],
            message_id=user_msg["id"],
            risk_level="high",
            risk_type="acute_risk",
            detected_keywords=risk_result.triggers,
            full_message_content=request.message,
            ai_reasoning=risk_result.reasoning,
            confidence_score=risk_result.confidence_score,
            escalation_flow_triggered=True,
            session_terminated=True,
            resources_provided=True
        )

        # Update session status
        await db.update_session(
            session_id=session["id"],
            status="flagged",
            risk_level="high",
            risk_flagged=True
        )

        # Generate crisis response
        crisis_response = await _generate_crisis_response(patient.get("country_code", "US"))

        crisis_msg = await db.create_message(
            session_id=session["id"],
            role="assistant",
            content=crisis_response
        )

        return ChatResponse(
            session_id=session["id"],
            message=MessageResponse(**crisis_msg),
            session_status="flagged",
            current_state=ConversationState.ENDED,
            risk_detected=True,
            risk_level=RiskLevel.HIGH,
            should_end_session=True,
            resources=prompts.get_crisis_resources(patient.get("country_code", "US"))
        )

    # Handle MEDIUM risk - provide resources but continue with caution
    if risk_result.risk_level == RiskLevel.MEDIUM:
        await db.create_risk_event(
            session_id=session["id"],
            patient_id=patient["id"],
            message_id=user_msg["id"],
            risk_level="medium",
            risk_type="concerning_content",
            detected_keywords=risk_result.triggers,
            full_message_content=request.message,
            ai_reasoning=risk_result.reasoning,
            confidence_score=risk_result.confidence_score
        )

        # Add supportive message with resources
        medium_risk_message = prompts.get_risk_escalation_message("medium_response")
        medium_risk_message = prompts.format_with_resources(
            medium_risk_message,
            patient.get("country_code", "US")
        )

        await db.create_message(
            session_id=session["id"],
            role="assistant",
            content=medium_risk_message
        )

    # STEP 2: Build conversation context
    messages = await db.get_session_messages(session["id"])

    context = ConversationContext(
        session_id=session["id"],
        patient_id=patient["id"],
        current_state=ConversationState(session["current_state"]),
        current_skill=session.get("current_skill"),
        current_step=session.get("current_step"),
        session_goal=session.get("session_goal"),
        user_name=patient.get("preferred_name"),
        country_code=patient.get("country_code", "US"),
        history=[
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ],
        state_data=session.get("state_data", {}),
        risk_level=risk_result.risk_level
    )

    # STEP 3: Process message through state machine
    assistant_response, updated_context = await state_machine.process_message(
        context=context,
        user_message=request.message
    )

    # STEP 4: Save assistant response
    assistant_msg = await db.create_message(
        session_id=session["id"],
        role="assistant",
        content=assistant_response
    )

    # STEP 5: Update session state
    await db.update_session(
        session_id=session["id"],
        current_state=updated_context.current_state.value,
        current_skill=updated_context.current_skill.value if updated_context.current_skill else None,
        current_step=updated_context.current_step,
        session_goal=updated_context.session_goal
    )

    # Return response
    return ChatResponse(
        session_id=session["id"],
        message=MessageResponse(**assistant_msg),
        session_status=session["status"],
        current_state=updated_context.current_state,
        risk_detected=risk_result.risk_level != RiskLevel.NONE,
        risk_level=risk_result.risk_level,
        should_end_session=False
    )


@router.post("/session/end")
async def end_session(request: EndSessionRequest):
    """End a chat session."""

    # Verify patient owns this session
    session = await db.get_session(request.session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    patient = await db.get_patient_by_access_code(request.patient_access_code)

    if not patient or session["patient_id"] != patient["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    # End session
    await db.end_session(request.session_id)

    return {"status": "success", "message": "Session ended"}


@router.get("/session/{session_id}/history", response_model=List[MessageResponse])
async def get_session_history(session_id: str, access_code: str):
    """Get message history for a session."""

    # Verify access
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    patient = await db.get_patient_by_access_code(access_code)
    if not patient or session["patient_id"] != patient["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    messages = await db.get_session_messages(session_id)

    return [MessageResponse(**msg) for msg in messages]


@router.post("/prompts/reload")
async def reload_prompts():
    """
    Reload prompts from YAML file without restarting server.
    Useful for iterating on prompt templates.
    """
    try:
        prompts.reload()
        return {"status": "success", "message": "Prompts reloaded"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload prompts: {str(e)}"
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def _generate_crisis_response(country_code: str) -> str:
    """Generate crisis intervention response."""

    resources = prompts.get_crisis_resources(country_code)

    clarify_msg = prompts.get_risk_escalation_message("clarify")
    ground_msg = prompts.get_risk_escalation_message("ground_high")
    resources_msg = prompts.get_risk_escalation_message("resources")
    stop_msg = prompts.get_risk_escalation_message("stop_message")

    full_message = "\n\n".join([
        clarify_msg,
        ground_msg,
        resources_msg.format(**resources),
        stop_msg
    ])

    return full_message
