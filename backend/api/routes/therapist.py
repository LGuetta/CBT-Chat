"""
Therapist API routes - Dashboard and patient monitoring endpoints.
"""

from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
import io
import json
import csv
import logging
from datetime import datetime, timedelta

from models.schemas import (
    TherapistDashboardResponse,
    PatientOverview,
    RiskEventResponse,
    SessionTranscriptResponse,
    SessionResponse,
    MessageResponse,
    SkillCompletionResponse,
    SessionSummaryResponse,
    PatientDetailsResponse,
    PatientWithBrief,
    UpdateTherapistBriefRequest,
    TherapistBrief,
    PreferredTechniques,
    ClinicalSensitivities,
    TherapistLanguage,
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
    try:
        dashboard_data = await db.get_therapist_dashboard(therapist["id"])
        logging.info(f"DEBUG: Dashboard data received for therapist {therapist['id']}: patients={len(dashboard_data.get('patients', []))}, flags={len(dashboard_data.get('recent_flags', []))}")
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logging.error(f"DEBUG: Error in get_therapist_dashboard: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching dashboard data: {str(e)}"
        )

    # Normalize patient data - ensure all required fields exist and handle nulls
    patients: List[PatientOverview] = []
    for p in dashboard_data.get("patients", []):
        try:
            # Ensure all required fields have defaults if null
            patient_data = {
                "patient_id": p.get("patient_id", ""),
                "preferred_name": p.get("preferred_name"),
                "access_code": p.get("access_code", ""),
                "total_sessions": int(p.get("total_sessions", 0) or 0),
                "flagged_sessions": int(p.get("flagged_sessions", 0) or 0),
                "last_session_date": p.get("last_session_date"),
                "last_flag_date": p.get("last_flag_date") or p.get("last_high_risk_date"),  # Fallback to last_high_risk_date
                "unreviewed_risk_events": int(p.get("unreviewed_risk_events", 0) or 0),
            }
            logging.debug(f"DEBUG: Processing patient data: {patient_data}")
            patients.append(PatientOverview(**patient_data))
        except Exception as e:
            # Log but continue - don't fail entire dashboard if one patient has bad data
            import traceback
            logging.error(f"Error parsing patient data: {e}, patient: {p}, traceback: {traceback.format_exc()}")
            continue

    # Normalize risk flags - handle field mapping
    recent_flags_raw = dashboard_data.get("recent_flags", [])
    recent_flags: List[RiskEventResponse] = []
    for flag in recent_flags_raw:
        try:
            flag_data = flag.copy()
            # Map risk_event_id to id if needed
            if "risk_event_id" in flag_data and "id" not in flag_data:
                flag_data["id"] = flag_data.pop("risk_event_id")
            # Ensure required fields
            if "id" not in flag_data:
                logging.warning(f"DEBUG: Skipping flag without id: {flag_data}")
                continue  # Skip invalid flags
            # Ensure risk_level is valid
            if "risk_level" not in flag_data:
                logging.warning(f"DEBUG: Skipping flag without risk_level: {flag_data}")
                continue
            # Ensure detected_keywords is a list
            if "detected_keywords" not in flag_data:
                flag_data["detected_keywords"] = []
            elif not isinstance(flag_data["detected_keywords"], list):
                flag_data["detected_keywords"] = []
            logging.debug(f"DEBUG: Processing risk flag: {flag_data}")
            recent_flags.append(RiskEventResponse(**flag_data))
        except Exception as e:
            # Log but continue - don't fail entire dashboard if one flag has bad data
            import traceback
            logging.error(f"Error parsing risk flag: {e}, flag: {flag}, traceback: {traceback.format_exc()}")
            continue

    total_unreviewed = sum(p.unreviewed_risk_events for p in patients)

    logging.info(f"DEBUG: Returning dashboard with {len(patients)} patients, {len(recent_flags)} flags, {total_unreviewed} unreviewed")

    try:
        response = TherapistDashboardResponse(
            therapist_id=therapist["id"],
            therapist_name=therapist["name"],
            patients=patients,
            total_unreviewed_flags=total_unreviewed,
            recent_flags=recent_flags
        )
        logging.info("DEBUG: Dashboard response created successfully")
        return response
    except Exception as e:
        import traceback
        logging.error(f"DEBUG: Error creating TherapistDashboardResponse: {e}, traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating dashboard response: {str(e)}"
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


@router.get("/patient/{patient_id}/details", response_model=PatientDetailsResponse)
async def get_patient_details(
    patient_id: str,
    therapist_email: str = Query(...)
):
    """Get patient profile with sessions and risk history."""

    therapist = await db.get_therapist_by_email(therapist_email)
    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Therapist not found"
        )

    patients = await db.get_therapist_patients(therapist["id"])
    patient_ids = [p["patients"]["id"] for p in patients]

    if patient_id not in patient_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    details = await db.get_patient_details(patient_id)

    if not details["patient"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )

    patient_record = details["patient"]
    brief = _build_therapist_brief(patient_record)
    if brief:
        patient_record["therapist_brief"] = brief

    return PatientDetailsResponse(
        patient=PatientWithBrief(**patient_record),
        recent_sessions=[SessionResponse(**s) for s in details["sessions"]],
        recent_risk_events=[RiskEventResponse(**r) for r in details["risk_events"]]
    )


@router.put("/patient/{patient_id}/brief", response_model=PatientWithBrief)
async def update_patient_brief(
    patient_id: str,
    request: UpdateTherapistBriefRequest,
    therapist_email: str = Query(...)
):
    """Update therapist brief configuration for a patient."""

    therapist = await db.get_therapist_by_email(therapist_email)
    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Therapist not found"
        )

    patients = await db.get_therapist_patients(therapist["id"])
    patient_ids = [p["patients"]["id"] for p in patients]

    if patient_id not in patient_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    brief_payload = request.brief.model_dump()
    updated_patient = await db.update_therapist_brief(
        patient_id,
        case_formulation=brief_payload.get("case_formulation"),
        presenting_problems=brief_payload.get("presenting_problems"),
        treatment_goals=brief_payload.get("treatment_goals"),
        therapy_stage=brief_payload.get("therapy_stage"),
        preferred_techniques=brief_payload.get("preferred_techniques"),
        sensitivities=brief_payload.get("sensitivities"),
        therapist_language=brief_payload.get("therapist_language"),
        contraindications=brief_payload.get("contraindications"),
    )

    return PatientWithBrief(**updated_patient)


def _build_therapist_brief(patient: dict) -> Optional[dict]:
    """
    Build TherapistBrief data from patient record if present.
    """
    if not patient or not patient.get("case_formulation"):
        return None

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

    return brief.model_dump()

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
