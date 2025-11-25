"""
Admin API routes - System administration and test data.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Optional
from datetime import datetime

from models.schemas import MessageRole, RiskLevel
from utils.database import get_db


router = APIRouter()
db = get_db()


@router.get("/health")
async def admin_health():
    """Admin health check endpoint."""
    return {
        "status": "healthy",
        "service": "CBT Chat Admin API"
    }


@router.post("/test-patient/create")
async def create_test_patient(
    preferred_name: str,
    country_code: str = "US"
):
    """Create a test patient (for development only)."""

    import uuid

    # Generate unique access code
    access_code = f"TEST{str(uuid.uuid4())[:8].upper()}"

    patient = await db.create_patient(
        access_code=access_code,
        preferred_name=preferred_name,
        country_code=country_code,
        communication_style="casual",
        onboarding_completed=False
    )

    return {
        "status": "success",
        "patient": patient,
        "access_code": access_code,
        "message": f"Test patient created. Use access code: {access_code}"
    }


@router.get("/stats")
async def get_system_stats():
    """Get system-wide statistics."""

    # TODO: Implement actual stats queries
    return {
        "total_patients": 0,
        "total_sessions": 0,
        "total_messages": 0,
        "active_sessions": 0,
        "flagged_events": 0
    }


@router.post("/test-risk-event")
async def create_test_risk_event(
    patient_access_code: str = "PATIENT001",
    message: str = "I want to kill myself",
    risk_level: RiskLevel = RiskLevel.HIGH
):
    """Create a sample session and high-risk event for testing dashboards."""

    patient = await db.get_patient_by_access_code(patient_access_code)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )

    session = await db.create_session(
        patient_id=patient["id"],
        session_goal="Risk escalation test",
        conversation_mode="adaptive"
    )

    user_message = await db.create_message(
        session_id=session["id"],
        role=MessageRole.USER.value,
        content=message,
        created_at=datetime.utcnow().isoformat(),
        risk_level=risk_level.value
    )

    risk_event = await db.create_risk_event(
        session_id=session["id"],
        patient_id=patient["id"],
        message_id=user_message["id"],
        risk_level=risk_level.value,
        alert_level="critical" if risk_level == RiskLevel.HIGH else "high",
        risk_type="manual_test_event",
        detected_keywords=["manual_seed"],
        full_message_content=message,
        ai_reasoning="Generated via /api/admin/test-risk-event endpoint for manual QA."
    )

    return {
        "status": "success",
        "session_id": session["id"],
        "risk_event_id": risk_event["id"],
        "message": "Test risk event created. Use therapist dashboard to verify visibility."
    }
