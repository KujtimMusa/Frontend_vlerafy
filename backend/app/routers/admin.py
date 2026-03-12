"""
Admin API Router
Endpoints für Admin-Authentifizierung und Dashboard
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models.waitlist import WaitlistSubscriber
from app.utils.admin_auth import (
    verify_admin_credentials,
    create_admin_token,
    get_current_admin
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminLoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    error: Optional[str] = None


class AdminStatsResponse(BaseModel):
    total_subscribers: int
    subscribers_today: int
    subscribers_this_week: int
    subscribers_this_month: int


# ============================================================================
# Public Endpoints
# ============================================================================

@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest):
    """
    Admin-Login: Prüft Credentials und gibt JWT-Token zurück
    """
    try:
        if verify_admin_credentials(request.email, request.password):
            token = create_admin_token()
            logger.info(f"Admin-Login erfolgreich: {request.email}")
            return AdminLoginResponse(
                success=True,
                token=token
            )
        else:
            logger.warning(f"Admin-Login fehlgeschlagen: {request.email}")
            return AdminLoginResponse(
                success=False,
                error="Ungültige Anmeldedaten"
            )
    except Exception as e:
        logger.error(f"Admin-Login Fehler: {e}", exc_info=True)
        return AdminLoginResponse(
            success=False,
            error="Fehler beim Login"
        )


# ============================================================================
# Protected Endpoints
# ============================================================================

@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Gibt Statistiken für Admin-Dashboard zurück
    """
    try:
        from datetime import timedelta
        
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)
        
        total = db.query(WaitlistSubscriber).count()
        today = db.query(WaitlistSubscriber).filter(
            WaitlistSubscriber.created_at >= today_start
        ).count()
        this_week = db.query(WaitlistSubscriber).filter(
            WaitlistSubscriber.created_at >= week_start
        ).count()
        this_month = db.query(WaitlistSubscriber).filter(
            WaitlistSubscriber.created_at >= month_start
        ).count()
        
        return AdminStatsResponse(
            total_subscribers=total,
            subscribers_today=today,
            subscribers_this_week=this_week,
            subscribers_this_month=this_month
        )
    except Exception as e:
        logger.error(f"Admin Stats Fehler: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fehler beim Laden der Statistiken"
        )


@router.get("/verify")
async def verify_admin_token_endpoint(admin: dict = Depends(get_current_admin)):
    """
    Verifiziert Admin-Token (für Frontend-Check)
    """
    return {
        "success": True,
        "email": admin.get("email"),
        "exp": admin.get("exp")
    }
