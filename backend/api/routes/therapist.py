"""
Therapist API routes - Dashboard and patient monitoring endpoints.
"""

from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
import io
import json
import csv
from datetime import datetime, timedelta

from models.schemas import (
    TherapistDashboardResponse,
    PatientOverview,
    RiskEventResponse,
    SessionTranscriptResponse,
    SessionResponse,
    MessageResponse,
    SkillCompletionResponse,
    SessionSummaryResponse
)
from utils.database import get_db


router = APIRouter()
db = get_db()


@router.get("/dashboard/{therapist_email}", response_model=TherapistDashboardResponse)
async def get_dashboard(therapist_email: str):
    """
    Get therapist dashboard with patient overview and recent flags.
    """

    # Get therapist
    therapist = await db.get_therapist_by_email(therapist_email)

    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Therapist not found"
        )

    # Get dashboard data
    dashboard_data = await db.get_therapist_dashboard(therapist["id"])

    patients = [PatientOverview(**p) for p in dashboard_data["patients"]]
    recent_flags = [RiskEventResponse(**f) for f in dashboard_data["recent_flags"]]

    total_unreviewed = sum(p.unreviewed_risk_events for p in patients)

    return TherapistDashboardResponse(
        therapist_id=therapist["id"],
        therapist_name=therapist["name"],
        patients=patients,
        total_unreviewed_flags=total_unreviewed,
        recent_flags=recent_flags
    )


@router.get("/session/{session_id}/transcript", response_model=SessionTranscriptResponse)
async def get_session_transcript(
    session_id: str,
    therapist_email: str = Query(...)
):
    """
    Get full transcript of a session for therapist review.
    """

    # Verify therapist access
    therapist = await db.get_therapist_by_email(therapist_email)
    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Therapist not found"
        )

    # Get session
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Verify therapist has access to this patient
    patients = await db.get_therapist_patients(therapist["id"])
    patient_ids = [p["patients"]["id"] for p in patients]

    if session["patient_id"] not in patient_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this session"
        )

    # Get full transcript
    transcript = await db.get_session_transcript(session_id)

    return SessionTranscriptResponse(
        session=SessionResponse(**transcript["session"]),
        messages=[MessageResponse(**m) for m in transcript["messages"]],
        risk_events=[RiskEventResponse(**r) for r in transcript["risk_events"]],
        skill_completions=[SkillCompletionResponse(**s) for s in transcript["skill_completions"]]
    )


@router.get("/patient/{patient_id}/sessions", response_model=List[SessionResponse])
async def get_patient_sessions(
    patient_id: str,
    therapist_email: str = Query(...),
    limit: int = 20
):
    """Get all sessions for a patient."""

    # Verify therapist access
    therapist = await db.get_therapist_by_email(therapist_email)
    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Therapist not found"
        )

    # Verify access
    patients = await db.get_therapist_patients(therapist["id"])
    patient_ids = [p["patients"]["id"] for p in patients]

    if patient_id not in patient_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    # Get sessions
    sessions = await db.get_patient_sessions(patient_id, limit=limit)

    return [SessionResponse(**s) for s in sessions]


@router.get("/patient/{patient_id}/skills", response_model=List[SkillCompletionResponse])
async def get_patient_skills(
    patient_id: str,
    therapist_email: str = Query(...),
    skill_type: Optional[str] = None,
    limit: int = 50
):
    """Get skill completions for a patient."""

    # Verify therapist access
    therapist = await db.get_therapist_by_email(therapist_email)
    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Therapist not found"
        )

    # Get skills
    skills = await db.get_patient_skill_completions(
        patient_id=patient_id,
        skill_type=skill_type,
        limit=limit
    )

    return [SkillCompletionResponse(**s) for s in skills]


@router.post("/risk-event/{risk_event_id}/review")
async def review_risk_event(
    risk_event_id: str,
    therapist_email: str = Query(...),
    notes: Optional[str] = None
):
    """Mark a risk event as reviewed by therapist."""

    # Verify therapist
    therapist = await db.get_therapist_by_email(therapist_email)
    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Therapist not found"
        )

    # Mark as reviewed
    await db.mark_risk_event_reviewed(risk_event_id, therapist_notes=notes)

    return {"status": "success", "message": "Risk event reviewed"}


@router.get("/flags/unreviewed", response_model=List[RiskEventResponse])
async def get_unreviewed_flags(therapist_email: str = Query(...)):
    """Get all unreviewed risk events for a therapist's patients."""

    therapist = await db.get_therapist_by_email(therapist_email)
    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Therapist not found"
        )

    flags = await db.get_unreviewed_risk_events(therapist["id"])

    return [RiskEventResponse(**f) for f in flags]


@router.get("/patient/{patient_id}/summary", response_model=SessionSummaryResponse)
async def get_patient_summary(
    patient_id: str,
    therapist_email: str = Query(...),
    period_days: int = 7
):
    """
    Generate a summary of patient activity over a time period.
    """

    therapist = await db.get_therapist_by_email(therapist_email)
    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Therapist not found"
        )

    # Get sessions in period
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=period_days)

    sessions = await db.get_patient_sessions(patient_id, limit=100)

    # Filter by date
    period_sessions = [
        s for s in sessions
        if datetime.fromisoformat(s["started_at"].replace("Z", "+00:00")) >= start_date
    ]

    # Get skills in period
    skills = await db.get_patient_skill_completions(patient_id, limit=100)
    period_skills = [
        s for s in skills
        if datetime.fromisoformat(s["completed_at"].replace("Z", "+00:00")) >= start_date
    ]

    # Calculate metrics
    total_sessions = len(period_sessions)
    total_duration = sum(s.get("total_duration_seconds", 0) for s in period_sessions) // 60

    # Count skills by type
    skill_counts = {}
    for skill in period_skills:
        skill_type = skill["skill_type"]
        skill_counts[skill_type] = skill_counts.get(skill_type, 0) + 1

    skills_practiced = [
        {"skill": k, "count": v}
        for k, v in skill_counts.items()
    ]

    # Mood trends
    mood_starts = [s.get("mood_start") for s in period_sessions if s.get("mood_start")]
    mood_ends = [s.get("mood_end") for s in period_sessions if s.get("mood_end")]

    avg_mood_start = sum(mood_starts) / len(mood_starts) if mood_starts else None
    avg_mood_end = sum(mood_ends) / len(mood_ends) if mood_ends else None

    mood_improvement = None
    if avg_mood_start and avg_mood_end:
        mood_improvement = avg_mood_end - avg_mood_start

    # Risk events
    risk_events = sum(1 for s in period_sessions if s.get("risk_flagged"))

    # Generate summary
    summary = {
        "id": f"summary_{patient_id}_{int(datetime.utcnow().timestamp())}",
        "patient_id": patient_id,
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "period_type": "weekly" if period_days == 7 else "custom",
        "total_sessions": total_sessions,
        "total_duration_minutes": total_duration,
        "skills_practiced": skills_practiced,
        "completion_rate": 1.0,  # Placeholder
        "avg_mood_start": avg_mood_start,
        "avg_mood_end": avg_mood_end,
        "mood_improvement_avg": mood_improvement,
        "mood_trend": "improving" if mood_improvement and mood_improvement > 0 else "stable",
        "top_triggers": [],  # TODO: Extract from thought records
        "common_emotions": [],  # TODO: Extract from thought records
        "risk_events_count": risk_events,
        "risk_events_severity": "none",
        "ai_summary": f"Patient completed {total_sessions} sessions and practiced {len(period_skills)} skills over {period_days} days.",
        "viewed_by_therapist": True,
        "viewed_at": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat()
    }

    return SessionSummaryResponse(**summary)


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================

@router.get("/patient/{patient_id}/export/json")
async def export_patient_data_json(
    patient_id: str,
    therapist_email: str = Query(...)
):
    """Export all patient data as JSON."""

    therapist = await db.get_therapist_by_email(therapist_email)
    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Therapist not found"
        )

    # Get all data
    sessions = await db.get_patient_sessions(patient_id, limit=1000)
    skills = await db.get_patient_skill_completions(patient_id, limit=1000)

    export_data = {
        "patient_id": patient_id,
        "export_date": datetime.utcnow().isoformat(),
        "sessions": sessions,
        "skill_completions": skills
    }

    # Create JSON file
    json_str = json.dumps(export_data, indent=2, default=str)
    buffer = io.BytesIO(json_str.encode())

    return StreamingResponse(
        buffer,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=patient_{patient_id}_export.json"
        }
    )


@router.get("/patient/{patient_id}/export/csv")
async def export_patient_data_csv(
    patient_id: str,
    therapist_email: str = Query(...)
):
    """Export patient skill completions as CSV."""

    therapist = await db.get_therapist_by_email(therapist_email)
    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Therapist not found"
        )

    # Get skills
    skills = await db.get_patient_skill_completions(patient_id, limit=1000)

    # Create CSV
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["completed_at", "skill_type", "mood_before", "mood_after", "completion_status"]
    )

    writer.writeheader()
    for skill in skills:
        writer.writerow({
            "completed_at": skill["completed_at"],
            "skill_type": skill["skill_type"],
            "mood_before": skill.get("mood_before", "N/A"),
            "mood_after": skill.get("mood_after", "N/A"),
            "completion_status": skill["completion_status"]
        })

    buffer = io.BytesIO(output.getvalue().encode())

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=patient_{patient_id}_skills.csv"
        }
    )
