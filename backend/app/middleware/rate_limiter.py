"""
API Rate Limiting Middleware
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, status
from fastapi.responses import JSONResponse

# Create limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per hour"]  # Global default
)


def get_shop_id_from_request(request: Request) -> str:
    """
    Extract shop_id from request for per-shop rate limiting
    Falls back to IP address if shop_id not available
    """
    # Try to get shop_id from cookies (JWT token)
    access_token = request.cookies.get('access_token')
    if access_token:
        try:
            from app.core.jwt_manager import verify_token
            payload = verify_token(access_token, token_type="access")
            return f"shop_{payload.get('shop_id', 'unknown')}"
        except:
            pass
    
    # Try to get shop_id from Authorization header
    authorization = request.headers.get('Authorization')
    if authorization and authorization.startswith('Bearer '):
        token = authorization.replace('Bearer ', '')
        try:
            from app.core.jwt_manager import verify_token
            payload = verify_token(token, token_type="access")
            return f"shop_{payload.get('shop_id', 'unknown')}"
        except:
            pass
    
    # Fallback to IP address
    return get_remote_address(request)


# Per-shop limiter (for authenticated requests)
shop_limiter = Limiter(
    key_func=get_shop_id_from_request,
    default_limits=["100 per minute"]  # Per shop default
)


def setup_rate_limiting(app):
    """
    Setup rate limiting for FastAPI app
    
    Args:
        app: FastAPI application instance
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # Custom rate limit exceeded handler with better error message
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        """
        Custom handler for rate limit exceeded errors
        """
        response = JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Limit: {exc.detail}",
                "retry_after": getattr(exc, 'retry_after', None)
            }
        )
        response.headers["Retry-After"] = str(getattr(exc, 'retry_after', 60))
        return response
