"""
Waitlist API Router
Endpoints für Landing Page Waitlist-Funktionalität
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.waitlist import WaitlistSubscriber
from app.utils.admin_auth import get_current_admin
from app.services.email_service import EmailService
from app.config import settings
import logging
import asyncio

logger = logging.getLogger(__name__)

# Initialize email service
email_service = EmailService(settings)

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])


# ============================================================================
# Request/Response Models
# ============================================================================

class WaitlistRequest(BaseModel):
    email: EmailStr
    source: Optional[str] = "landing"


class WaitlistResponse(BaseModel):
    success: bool
    message: str


class WaitlistSubscriberResponse(BaseModel):
    id: int
    email: str
    created_at: datetime
    source: Optional[str]

    class Config:
        from_attributes = True


class WaitlistListResponse(BaseModel):
    subscribers: list[WaitlistSubscriberResponse]
    total: int


# ============================================================================
# Email Notification Helper
# ============================================================================

async def send_notification_emails(
    user_email: str,
    position: int,
    total_count: int,
    source: str = "landing"
):
    """
    Send both admin notification and user confirmation emails asynchronously
    This function runs in background and doesn't block the API response
    """
    try:
        # Format timestamp
        timestamp = datetime.now().strftime("%b %d, %Y %I:%M %P CET")
        
        # Send admin notification
        admin_sent = await email_service.send_admin_notification(
            user_email=user_email,
            timestamp=timestamp,
            total_count=total_count,
            source=source
        )
        
        if admin_sent:
            logger.info(f"✅ Admin notification sent for {user_email}")
        else:
            logger.warning(f"⚠️ Admin notification failed for {user_email}")
        
        # Send user confirmation
        user_sent = await email_service.send_user_confirmation(
            user_email=user_email,
            position=position
        )
        
        if user_sent:
            logger.info(f"✅ User confirmation sent to {user_email} (position #{position})")
        else:
            logger.warning(f"⚠️ User confirmation failed for {user_email}")
        
    except Exception as e:
        # Log error but don't fail the request
        logger.error(f"❌ Email sending failed for {user_email}: {e}", exc_info=True)


# ============================================================================
# Public Endpoints
# ============================================================================

@router.post("/", response_model=WaitlistResponse, status_code=status.HTTP_201_CREATED)
async def add_to_waitlist(
    request: WaitlistRequest,
    db: Session = Depends(get_db)
):
    """
    Fügt E-Mail zur Waitlist hinzu
    """
    try:
        # Prüfe ob E-Mail bereits existiert
        existing = db.query(WaitlistSubscriber).filter(
            WaitlistSubscriber.email == request.email
        ).first()
        
        if existing:
            logger.info(f"Waitlist: E-Mail bereits registriert: {request.email}")
            return WaitlistResponse(
                success=False,
                message="Diese E-Mail ist bereits auf der Waitlist."
            )
        
        # Erstelle neuen Subscriber
        subscriber = WaitlistSubscriber(
            email=request.email,
            source=request.source
        )
        
        db.add(subscriber)
        db.commit()
        db.refresh(subscriber)
        
        # Get stats for email
        total_count = db.query(WaitlistSubscriber).count()
        position = total_count  # User's position
        
        logger.info(f"Waitlist: Neue E-Mail hinzugefügt: {request.email} (Position: {position})")
        
        # Send emails asynchronously (don't block response)
        asyncio.create_task(send_notification_emails(
            user_email=request.email,
            position=position,
            total_count=total_count,
            source=request.source or "landing"
        ))
        
        return WaitlistResponse(
            success=True,
            message="Du bist auf der Waitlist! Wir melden uns bald bei dir."
        )
        
    except IntegrityError:
        db.rollback()
        logger.warning(f"Waitlist: IntegrityError für E-Mail: {request.email}")
        return WaitlistResponse(
            success=False,
            message="Diese E-Mail ist bereits auf der Waitlist."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Waitlist: Fehler beim Hinzufügen: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fehler beim Hinzufügen zur Waitlist"
        )


# ============================================================================
# Admin Endpoints (geschützt)
# ============================================================================

@router.get("/admin/list", response_model=WaitlistListResponse)
async def get_waitlist(
    admin: dict = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Gibt alle Waitlist-Subscriber zurück (nur für Admin)
    """
    try:
        subscribers = db.query(WaitlistSubscriber).order_by(
            WaitlistSubscriber.created_at.desc()
        ).all()
        
        return WaitlistListResponse(
            subscribers=[
                WaitlistSubscriberResponse(
                    id=s.id,
                    email=s.email,
                    created_at=s.created_at,
                    source=s.source
                )
                for s in subscribers
            ],
            total=len(subscribers)
        )
    except Exception as e:
        logger.error(f"Waitlist Admin: Fehler beim Laden: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fehler beim Laden der Waitlist"
        )
