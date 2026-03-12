"""
Waitlist Model für Landing Page
Speichert E-Mail-Adressen von Nutzern, die sich für die Waitlist interessieren
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base


class WaitlistSubscriber(Base):
    __tablename__ = "waitlist_subscribers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    source = Column(String, nullable=True)  # z.B. "landing", "admin", "referral"
    extra_data = Column(JSON, nullable=True)  # Für zukünftige Erweiterungen (z.B. Referrer, UTM-Parameter)
