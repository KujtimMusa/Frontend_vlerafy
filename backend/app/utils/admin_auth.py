"""
Admin Authentication Utilities
JWT-basierte Authentifizierung für Admin-Dashboard
"""

import os
import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", settings.JWT_SECRET or "change-me-in-production")
JWT_ALGORITHM = settings.JWT_ALGORITHM
JWT_EXPIRATION_HOURS = 24

# Admin Credentials (aus Environment-Variablen)
# ⚠️ WICHTIG: Setze diese in Railway Environment Variables!
# ADMIN_EMAIL=admin@vlerafy.com
# ADMIN_PASSWORD=Vlerafy2026!Secure#Admin
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@vlerafy.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Vlerafy2026!Secure#Admin")  # ⚠️ Default für MVP, in Production via ENV!

# HTTP Bearer Token Scheme
security = HTTPBearer()


def create_admin_token() -> str:
    """Erstellt JWT-Token für Admin-Session"""
    payload = {
        "sub": "admin",
        "email": ADMIN_EMAIL,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def verify_admin_token(token: str) -> dict:
    """Verifiziert JWT-Token und gibt Payload zurück"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token abgelaufen"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger Token"
        )


def verify_admin_credentials(email: str, password: str) -> bool:
    """Prüft Admin-Credentials"""
    return email == ADMIN_EMAIL and password == ADMIN_PASSWORD


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Dependency für geschützte Admin-Routen"""
    token = credentials.credentials
    payload = verify_admin_token(token)
    return payload
