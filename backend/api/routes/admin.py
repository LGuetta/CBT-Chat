"""
Admin API routes - System administration and test data.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Optional

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
