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

    # Generate AI summary if not already cached
    ai_summary = await _generate_session_summary(transcript)

    return SessionTranscriptResponse(
        session=SessionResponse(**transcript["session"]),
        messages=[MessageResponse(**m) for m in transcript["messages"]],
        risk_events=[RiskEventResponse(**r) for r in transcript["risk_events"]],
        skill_completions=[SkillCompletionResponse(**s) for s in transcript["skill_completions"]],
        ai_summary=ai_summary
    )


async def _generate_session_summary(transcript: dict) -> str:
    """Generate a clinical summary of the session for the therapist."""
    messages = transcript.get("messages", [])
    risk_events = transcript.get("risk_events", [])
    skills = transcript.get("skill_completions", [])
    session = transcript.get("session", {})

    if not messages:
        return "No messages in this session."

    user_messages = [m for m in messages if m.get("role") == "user"]
    assistant_messages = [m for m in messages if m.get("role") == "assistant"]

    summary_parts = []

    # === SESSION OVERVIEW ===
    duration = "Unknown"
    if session.get("started_at") and session.get("ended_at"):
        try:
            from datetime import datetime
            start = datetime.fromisoformat(session["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(session["ended_at"].replace("Z", "+00:00"))
            duration = f"{int((end - start).total_seconds() / 60)} minutes"
        except:
            pass

    summary_parts.append(f"**📊 Session Overview:** {len(messages)} messages, Duration: {duration}")

    # === RISK ASSESSMENT ===
    if risk_events:
        risk_levels = [r.get("risk_level", "unknown") for r in risk_events]
        high_risk_count = sum(1 for r in risk_levels if r == "high")
        medium_risk_count = sum(1 for r in risk_levels if r == "medium")
        
        risk_keywords = []
        for r in risk_events:
            risk_keywords.extend(r.get("detected_keywords", []))
        unique_keywords = list(set(risk_keywords))[:5]  # Top 5
        
        if high_risk_count > 0:
            summary_parts.append(f"🚨 **Risk Assessment:** {high_risk_count} HIGH-RISK, {medium_risk_count} medium-risk events")
        elif medium_risk_count > 0:
            summary_parts.append(f"⚠️ **Risk Assessment:** {medium_risk_count} medium-risk events")
        
        if unique_keywords:
            summary_parts.append(f"   - Keywords detected: {', '.join(unique_keywords)}")
    else:
        summary_parts.append("✅ **Risk Assessment:** No risk events triggered")

    # === SKILLS PRACTICED ===
    if skills:
        skill_types = list(set(s.get("skill_type", "unknown") for s in skills))
        mood_changes = []
        for s in skills:
            if s.get("mood_before") is not None and s.get("mood_after") is not None:
                change = s["mood_after"] - s["mood_before"]
                mood_changes.append(change)
        
        skill_summary = f"🎯 **Skills Practiced:** {', '.join(skill_types)}"
        if mood_changes:
            avg_change = sum(mood_changes) / len(mood_changes)
            direction = "improved" if avg_change > 0 else "decreased" if avg_change < 0 else "stable"
            skill_summary += f" (Mood {direction}: avg {avg_change:+.1f})"
        summary_parts.append(skill_summary)

    # === CONTENT ANALYSIS ===
    if user_messages:
        summary_parts.append("\n**💬 Conversation Content:**")
        
        # Extract key themes from patient messages
        all_patient_text = " ".join([m.get("content", "") for m in user_messages])
        
        # Simple theme extraction (keywords)
        theme_keywords = {
            "anxiety": ["anxious", "worried", "nervous", "panic", "fear", "scared"],
            "depression": ["sad", "hopeless", "empty", "tired", "worthless", "depressed"],
            "relationships": ["friend", "partner", "family", "relationship", "people", "social"],
            "work/school": ["work", "job", "school", "exam", "interview", "boss", "colleague"],
            "self-esteem": ["failure", "stupid", "worthless", "inadequate", "not good enough"],
            "sleep": ["sleep", "insomnia", "tired", "exhausted", "awake"],
            "physical": ["pain", "body", "physical", "health", "sick"],
        }
        
        detected_themes = []
        text_lower = all_patient_text.lower()
        for theme, keywords in theme_keywords.items():
            if any(kw in text_lower for kw in keywords):
                detected_themes.append(theme)
        
        if detected_themes:
            summary_parts.append(f"   - **Main themes:** {', '.join(detected_themes)}")
        
        # First and last messages for context
        first_msg = user_messages[0].get("content", "")
        if len(first_msg) > 150:
            first_msg = first_msg[:150] + "..."
        summary_parts.append(f"   - **Session started with:** \"{first_msg}\"")
        
        if len(user_messages) > 1:
            last_msg = user_messages[-1].get("content", "")
            if len(last_msg) > 150:
                last_msg = last_msg[:150] + "..."
            summary_parts.append(f"   - **Session ended with:** \"{last_msg}\"")
        
        # Count questions asked by patient
        questions = sum(1 for m in user_messages if "?" in m.get("content", ""))
        if questions > 0:
            summary_parts.append(f"   - Patient asked {questions} questions during session")
    
    # === CLINICAL OBSERVATIONS ===
    summary_parts.append("\n**🔍 Clinical Observations:**")
    
    # Engagement level
    avg_msg_length = sum(len(m.get("content", "")) for m in user_messages) / max(len(user_messages), 1)
    if avg_msg_length > 200:
        summary_parts.append("   - High engagement (detailed responses)")
    elif avg_msg_length > 50:
        summary_parts.append("   - Moderate engagement")
    else:
        summary_parts.append("   - Brief responses (possible low engagement or distress)")
    
    # Session outcome
    status = session.get("status", "unknown")
    if status == "flagged":
        summary_parts.append("   - 🚩 **Session was flagged** - requires clinical review")
    elif status == "completed":
        summary_parts.append("   - ✓ Session completed normally")
    elif status == "terminated":
        summary_parts.append("   - ⚠️ Session was terminated (possibly due to crisis protocol)")

    return "\n".join(summary_parts)


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

    return PatientDetailsResponse(
        patient=PatientWithBrief(**details["patient"]),
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
