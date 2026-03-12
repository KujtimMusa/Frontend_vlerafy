"""
Authentication and Authorization Dependencies
"""

import logging
from typing import Optional
from fastapi import Depends, HTTPException, Header, Request, Cookie
from sqlalchemy.orm import Session
from app.core.jwt_manager import verify_token
from app.database import get_db
from app.models.shop import Shop
from app.config import settings

logger = logging.getLogger(__name__)


async def get_current_shop(
    request: Request,
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
) -> str:
    """
    Extract and validate shop_id from JWT token (Cookie or Header)
    
    Priority:
    1. JWT Token from Cookie (access_token)
    2. JWT Token from Authorization Header (Bearer token)
    3. Session-based auth (legacy)
    4. Query param (DEV MODE only)
    
    Args:
        request: FastAPI Request object
        authorization: Authorization header (Bearer token)
        access_token: JWT token from cookie
        db: Database session
    
    Returns:
        shop_id (string)
    
    Raises:
        HTTPException: 401 if unauthorized, 403 if forbidden
    """
    
    token = None
    token_source = None
    
    # Strategy 1: JWT Token from Cookie (preferred)
    if access_token:
        token = access_token
        token_source = "cookie"
    
    # Strategy 2: JWT Token from Authorization Header
    elif authorization and authorization.startswith('Bearer '):
        token = authorization.replace('Bearer ', '')
        token_source = "header"
    
    if token:
        try:
            # Strategy 2a: Shopify Session Token (shopify.idToken() from App Bridge)
            # Check for "dest" claim = Shopify Session Token format
            try:
                from app.utils.shopify_token_validator import validate_shopify_session_token
                shopify_payload = validate_shopify_session_token(token)
                if shopify_payload.get("dest"):
                    # dest format: "https://shop-name.myshopify.com"
                    dest = shopify_payload["dest"]
                    shop_url = dest.replace("https://", "").replace("http://", "").strip().rstrip("/")
                    shop = db.query(Shop).filter(Shop.shop_url == shop_url).first()
                    if not shop:
                        logger.error(f"Shop {shop_url} from session token not found")
                        raise HTTPException(status_code=403, detail="Shop not found")
                    if not shop.is_active:
                        raise HTTPException(status_code=403, detail="Shop is inactive")
                    try:
                        import sentry_sdk
                        sentry_sdk.set_user({
                            "id": str(shop.id),
                            "shop_url": shop.shop_url,
                            "shop_name": shop.shop_name or shop.shop_url
                        })
                    except ImportError:
                        pass
                    logger.info(f"Authenticated shop: {shop.id} (via Shopify session token)")
                    return str(shop.id)
            except ValueError:
                pass  # Not a Shopify token, continue to app JWT
            except HTTPException:
                raise

            # Strategy 2b: App JWT Token (verify_token)
            payload = verify_token(token, token_type="access")
            
            # Extract shop_id from payload
            shop_id = payload.get('shop_id')
            
            if not shop_id:
                logger.error("JWT token missing shop_id")
                raise HTTPException(status_code=401, detail="Invalid token: missing shop_id")
            
            # Verify shop exists and is active
            shop = db.query(Shop).filter(Shop.id == shop_id).first()
            
            if not shop:
                logger.error(f"Shop {shop_id} not found in database")
                raise HTTPException(status_code=403, detail="Shop not found")
            
            if not shop.is_active:
                logger.warning(f"Shop {shop_id} is inactive")
                raise HTTPException(status_code=403, detail="Shop is inactive")
            
            # Set Sentry User Context
            try:
                import sentry_sdk
                sentry_sdk.set_user({
                    "id": str(shop.id),
                    "shop_url": shop.shop_url,
                    "shop_name": shop.shop_name or shop.shop_url
                })
            except ImportError:
                pass  # Sentry not installed
            
            logger.info(f"Authenticated shop: {shop_id} (via {token_source})")
            return str(shop.id)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid token")
    
    # Strategy 3: Session-based auth (legacy - for backward compatibility)
    shop_id_from_session = request.cookies.get('shop_id') if hasattr(request, 'cookies') else None
    
    if shop_id_from_session:
        shop = db.query(Shop).filter(Shop.id == shop_id_from_session).first()
        
        if not shop:
            logger.error(f"Shop {shop_id_from_session} from session not found")
            raise HTTPException(status_code=403, detail="Shop not found")
        
        if not shop.is_active:
            raise HTTPException(status_code=403, detail="Shop is inactive")
        
        # Set Sentry User Context
        try:
            import sentry_sdk
            sentry_sdk.set_user({
                "id": str(shop.id),
                "shop_url": shop.shop_url,
                "shop_name": shop.shop_name or shop.shop_url
            })
        except ImportError:
            pass
        
        logger.info(f"Authenticated shop from session: {shop_id_from_session}")
        return str(shop.id)
    
    # Strategy 4: Dev/Testing mode - shop_id from query param (REMOVE IN PRODUCTION!)
    shop_id_param = request.query_params.get('shop_id')
    if shop_id_param:
        logger.warning(f"Using shop_id from query param (DEV MODE): {shop_id_param}")
        # In production, comment out or remove this block
        return shop_id_param
    
    # No valid auth found
    logger.error("No valid authentication found")
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide Bearer token or valid session."
    )


async def get_current_admin(
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db)
) -> Shop:
    """
    Get current shop with admin verification
    Useful for admin-only endpoints
    
    Args:
        shop_id: Authenticated shop ID
        db: Database session
    
    Returns:
        Shop object
    
    Raises:
        HTTPException: 403 if not admin
    """
    
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Check if shop has admin privileges (adjust based on your model)
    if not getattr(shop, 'is_admin', False):
        logger.warning(f"Shop {shop_id} attempted admin action without privileges")
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    return shop


# Optional: Dependency for optional auth (won't raise exception)
async def get_current_shop_optional(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[str]:
    """
    Get shop_id if authenticated, otherwise return None
    Useful for endpoints that work with or without auth
    """
    try:
        return await get_current_shop(request, authorization, db)
    except HTTPException:
        return None






























