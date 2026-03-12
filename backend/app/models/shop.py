from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from datetime import datetime
from app.database import Base


class Shop(Base):
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True, index=True)
    shop_url = Column(String, unique=True, index=True, nullable=False)
    access_token = Column(String, nullable=True)  # Verschlüsselt, nullable für OAuth
    scope = Column(String, nullable=True)  # OAuth Scopes (comma-separated)
    is_active = Column(Boolean, default=True)
    shop_name = Column(String, nullable=True)
    installed_at = Column(DateTime(timezone=True), nullable=True)  # OAuth installation timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())











