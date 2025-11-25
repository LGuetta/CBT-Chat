"""
Database connection and utility functions for Supabase.
"""

from supabase import create_client, Client
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

from config.settings import get_settings


settings = get_settings()


class Database:
    """Wrapper for Supabase database operations."""

    def __init__(self):
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_key
        )

    # ========================================================================
    # PATIENT OPERATIONS
    # ========================================================================

    async def get_patient_by_access_code(self, access_code: str) -> Optional[Dict]:
        """Get patient by access code."""
        response = self.client.table("patients").select("*").eq(
            "access_code", access_code
        ).single().execute()

        return response.data if response.data else None

    async def create_patient(self, access_code: str, **kwargs) -> Dict:
        """Create a new patient."""
        data = {
            "access_code": access_code,
            **kwargs
        }
        response = self.client.table("patients").insert(data).execute()
        return response.data[0]

    # ========================================================================
    # SESSION OPERATIONS
    # ========================================================================

    async def create_session(
        self,
        patient_id: str,
        session_goal: Optional[str] = None
    ) -> Dict:
        """Create a new chat session."""
        data = {
            "patient_id": patient_id,
            "session_goal": session_goal,
            "status": "active",
            "current_state": "consent"
        }
        response = self.client.table("sessions").insert(data).execute()
        return response.data[0]

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID."""
        response = self.client.table("sessions").select("*").eq(
            "id", session_id
        ).single().execute()

        return response.data if response.data else None

    async def update_session(
        self,
        session_id: str,
        **updates
    ) -> Dict:
        """Update session fields."""
        response = self.client.table("sessions").update(updates).eq(
            "id", session_id
        ).execute()
        return response.data[0]

    async def end_session(self, session_id: str) -> Dict:
        """End a session."""
        return await self.update_session(
            session_id,
            status="completed",
            ended_at=datetime.utcnow().isoformat()
        )

    async def get_patient_sessions(
        self,
        patient_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """Get recent sessions for a patient."""
        response = self.client.table("sessions").select("*").eq(
            "patient_id", patient_id
        ).order("started_at", desc=True).limit(limit).execute()

        return response.data

    # ========================================================================
    # MESSAGE OPERATIONS
    # ========================================================================

    async def create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **kwargs
    ) -> Dict:
        """Create a new message."""
        data = {
            "session_id": session_id,
            "role": role,
            "content": content,
            **kwargs
        }
        response = self.client.table("messages").insert(data).execute()
        return response.data[0]

    async def get_session_messages(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get messages for a session."""
        query = self.client.table("messages").select("*").eq(
            "session_id", session_id
        ).order("created_at", desc=False)

        if limit:
            query = query.limit(limit)

        response = query.execute()
        return response.data

    # ========================================================================
    # RISK EVENT OPERATIONS
    # ========================================================================

    async def create_risk_event(
        self,
        session_id: str,
        patient_id: str,
        message_id: Optional[str],
        risk_level: str,
        risk_type: Optional[str],
        detected_keywords: List[str],
        full_message_content: str,
        **kwargs
    ) -> Dict:
        """Create a risk event."""
        data = {
            "session_id": session_id,
            "patient_id": patient_id,
            "message_id": message_id,
            "risk_level": risk_level,
            "risk_type": risk_type,
            "detected_keywords": detected_keywords,
            "full_message_content": full_message_content,
            **kwargs
        }
        response = self.client.table("risk_events").insert(data).execute()
        return response.data[0]

    async def get_unreviewed_risk_events(
        self,
        therapist_id: str
    ) -> List[Dict]:
        """Get unreviewed risk events for a therapist's patients."""
        # This uses the view created in the schema
        response = self.client.table("v_recent_flags").select("*").eq(
            "therapist_id", therapist_id
        ).eq("therapist_reviewed", False).execute()

        return response.data

    async def mark_risk_event_reviewed(
        self,
        risk_event_id: str,
        therapist_notes: Optional[str] = None
    ) -> Dict:
        """Mark a risk event as reviewed by therapist."""
        updates = {
            "therapist_reviewed": True,
            "therapist_reviewed_at": datetime.utcnow().isoformat()
        }
        if therapist_notes:
            updates["therapist_notes"] = therapist_notes

        response = self.client.table("risk_events").update(updates).eq(
            "id", risk_event_id
        ).execute()
        return response.data[0]

    # ========================================================================
    # SKILL COMPLETION OPERATIONS
    # ========================================================================

    async def create_skill_completion(
        self,
        session_id: str,
        patient_id: str,
        skill_type: str,
        data: Dict[str, Any],
        **kwargs
    ) -> Dict:
        """Record a completed skill exercise."""
        record = {
            "session_id": session_id,
            "patient_id": patient_id,
            "skill_type": skill_type,
            "data": data,
            **kwargs
        }
        response = self.client.table("skill_completions").insert(record).execute()
        return response.data[0]

    async def get_patient_skill_completions(
        self,
        patient_id: str,
        skill_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Get recent skill completions for a patient."""
        query = self.client.table("skill_completions").select("*").eq(
            "patient_id", patient_id
        )

        if skill_type:
            query = query.eq("skill_type", skill_type)

        query = query.order("completed_at", desc=True).limit(limit)
        response = query.execute()
        return response.data

    # ========================================================================
    # MOOD TRACKING
    # ========================================================================

    async def create_mood_rating(
        self,
        patient_id: str,
        mood_score: int,
        context: str,
        session_id: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """Record a mood rating."""
        data = {
            "patient_id": patient_id,
            "mood_score": mood_score,
            "context": context,
            "session_id": session_id,
            **kwargs
        }
        response = self.client.table("mood_ratings").insert(data).execute()
        return response.data[0]

    # ========================================================================
    # THERAPIST DASHBOARD
    # ========================================================================

    async def get_therapist_dashboard(self, therapist_id: str) -> Dict:
        """Get dashboard data for a therapist."""
        # Get patient overview
        patients_response = self.client.table("v_therapist_dashboard").select("*").eq(
            "therapist_id", therapist_id
        ).execute()

        # Get recent flags
        flags_response = self.client.table("v_recent_flags").select("*").eq(
            "therapist_id", therapist_id
        ).limit(20).execute()

        return {
            "patients": patients_response.data,
            "recent_flags": flags_response.data
        }

    async def get_session_transcript(self, session_id: str) -> Dict:
        """Get full session transcript for therapist review."""
        session = await self.get_session(session_id)
        messages = await self.get_session_messages(session_id)

        # Get risk events for this session
        risk_events_response = self.client.table("risk_events").select("*").eq(
            "session_id", session_id
        ).execute()

        # Get skill completions for this session
        skills_response = self.client.table("skill_completions").select("*").eq(
            "session_id", session_id
        ).execute()

        return {
            "session": session,
            "messages": messages,
            "risk_events": risk_events_response.data,
            "skill_completions": skills_response.data
        }

    # ========================================================================
    # THERAPIST OPERATIONS
    # ========================================================================

    async def get_therapist_by_email(self, email: str) -> Optional[Dict]:
        """Get therapist by email."""
        response = self.client.table("therapists").select("*").eq(
            "email", email
        ).single().execute()

        return response.data if response.data else None

    async def get_therapist_patients(self, therapist_id: str) -> List[Dict]:
        """Get all patients for a therapist."""
        response = self.client.table("therapist_patients").select(
            "*, patients(*)"
        ).eq("therapist_id", therapist_id).eq("is_active", True).execute()

        return response.data

    # ========================================================================
    # OPZIONE C - NEW METHODS
    # ========================================================================

    async def create_disclaimer_log(
        self,
        session_id: str,
        patient_id: str,
        disclaimer_type: str,
        content: str,
        triggered_by: str,
        **kwargs
    ) -> Dict:
        """Create a disclaimer log entry."""
        data = {
            "session_id": session_id,
            "patient_id": patient_id,
            "disclaimer_type": disclaimer_type,
            "content": content,
            "triggered_by": triggered_by,
            **kwargs
        }
        response = self.client.table("disclaimer_logs").insert(data).execute()
        return response.data[0]

    async def get_patient_disclaimer_logs(
        self,
        patient_id: str,
        limit: int = 20
    ) -> List[Dict]:
        """Get disclaimer logs for a patient."""
        response = self.client.table("disclaimer_logs").select("*").eq(
            "patient_id", patient_id
        ).order("created_at", desc=True).limit(limit).execute()

        return response.data

    async def create_notification(
        self,
        therapist_id: str,
        notification_type: str,
        priority: str,
        subject: str,
        message_body: str,
        **kwargs
    ) -> Dict:
        """Create a notification for a therapist."""
        data = {
            "therapist_id": therapist_id,
            "notification_type": notification_type,
            "priority": priority,
            "subject": subject,
            "message_body": message_body,
            **kwargs
        }
        response = self.client.table("notifications").insert(data).execute()
        return response.data[0]

    async def get_therapist_notifications(
        self,
        therapist_id: str,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """Get notifications for a therapist."""
        query = self.client.table("notifications").select("*").eq(
            "therapist_id", therapist_id
        )

        if unread_only:
            query = query.eq("read", False)

        response = query.order("created_at", desc=True).limit(limit).execute()

        return response.data

    async def mark_notification_read(
        self,
        notification_id: str
    ) -> Dict:
        """Mark a notification as read."""
        response = self.client.table("notifications").update({
            "read": True,
            "read_at": datetime.utcnow().isoformat()
        }).eq("id", notification_id).execute()

        return response.data[0]

    async def create_appointment(
        self,
        therapist_id: str,
        patient_id: str,
        scheduled_at: datetime,
        **kwargs
    ) -> Dict:
        """Create an appointment."""
        data = {
            "therapist_id": therapist_id,
            "patient_id": patient_id,
            "scheduled_at": scheduled_at.isoformat() if isinstance(scheduled_at, datetime) else scheduled_at,
            **kwargs
        }
        response = self.client.table("appointments").insert(data).execute()
        return response.data[0]

    async def get_upcoming_appointments(
        self,
        therapist_id: Optional[str] = None,
        hours_ahead: int = 24
    ) -> List[Dict]:
        """Get appointments within specified hours."""
        from datetime import timedelta

        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours_ahead)

        query = self.client.table("appointments").select("*").gte(
            "scheduled_at", now.isoformat()
        ).lte("scheduled_at", cutoff.isoformat()).eq("status", "scheduled")

        if therapist_id:
            query = query.eq("therapist_id", therapist_id)

        response = query.execute()
        return response.data

    async def update_therapist_brief(
        self,
        patient_id: str,
        **brief_fields
    ) -> Dict:
        """Update therapist brief fields for a patient."""
        response = self.client.table("patients").update(brief_fields).eq(
            "id", patient_id
        ).execute()

        return response.data[0]


# Global database instance
db = Database()


def get_db() -> Database:
    """Get database instance."""
    return db
