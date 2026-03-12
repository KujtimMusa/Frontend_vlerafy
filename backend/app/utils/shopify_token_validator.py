"""
Shopify Session Token Validator
Validates session tokens from shopify.idToken() (App Bridge / frontend)
"""
import jwt
from app.config.settings import settings


def validate_shopify_session_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.SHOPIFY_CLIENT_SECRET,
            algorithms=["HS256"],
            audience=settings.SHOPIFY_CLIENT_ID,
        )
        return payload
    except Exception as e:
        raise ValueError(f"Invalid session token: {e}")
