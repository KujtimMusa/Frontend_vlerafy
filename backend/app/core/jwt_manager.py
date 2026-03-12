"""
JWT Token Manager für Session Management
"""
import os
import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional
from fastapi import HTTPException, status

from app.config import settings

# JWT Configuration
JWT_SECRET = getattr(settings, 'JWT_SECRET', os.getenv('JWT_SECRET', os.getenv('SECRET_KEY', 'default-secret-key-change-in-production')))
JWT_ALGORITHM = getattr(settings, 'JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv('ACCESS_TOKEN_EXPIRE_HOURS', '24'))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', '7'))


def create_access_token(shop_id: int, shop_url: str) -> str:
    """
    Create JWT Access Token (24h lifetime)
    
    Args:
        shop_id: Shop ID
        shop_url: Shop URL
    
    Returns:
        JWT token string
    """
    payload = {
        "shop_id": shop_id,
        "shop_url": shop_url,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(shop_id: int) -> str:
    """
    Create JWT Refresh Token (7 days lifetime)
    
    Args:
        shop_id: Shop ID
    
    Returns:
        JWT token string
    """
    payload = {
        "shop_id": shop_id,
        "type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str, token_type: str = "access") -> Dict:
    """
    Verify JWT Token and return payload
    
    Args:
        token: JWT token string
        token_type: "access" or "refresh"
    
    Returns:
        Token payload dict
    
    Raises:
        HTTPException: If token invalid or expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        # Check token type
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {token_type}"
            )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired. Please login again."
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )


def refresh_access_token(refresh_token: str, db) -> str:
    """
    Create new access token from refresh token
    
    Args:
        refresh_token: Valid refresh token
        db: Database session
    
    Returns:
        New access token
    """
    from app.models.shop import Shop
    
    payload = verify_token(refresh_token, token_type="refresh")
    
    # Get shop from DB
    shop = db.query(Shop).filter_by(id=payload["shop_id"]).first()
    
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    return create_access_token(shop.id, shop.shop_url)
