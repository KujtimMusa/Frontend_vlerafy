"""
Authentication and Authorization Dependencies

Einheitliche Priorität (wie get_active_shop_for_request, ohne Demo-Fallback):
1. Authorization: Bearer → Shopify Session Token (dest) oder App JWT
2. X-Shop-ID Header
3. X-Shop-Domain Header → Shop in DB
4. ?shop= Query Parameter → Shop in DB
5. session_id Cookie → ShopContext (KEIN Demo – raise 401)
6. Fallback: 401
"""

import logging
from typing import Optional
from fastapi import Depends, HTTPException, Header, Request, Cookie
from sqlalchemy.orm import Session
from app.core.jwt_manager import verify_token
from app.core.shop_context import (
    resolve_shop_by_domain,
    get_session_id,
    ShopContext,
)
from app.database import get_db
from app.models.shop import Shop

logger = logging.getLogger(__name__)


def _get_token_from_request(request: Request, authorization: Optional[str], access_token: Optional[str]) -> Optional[str]:
    """Token aus Header oder Cookie."""
    if authorization and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "").strip()
    if access_token:
        return access_token
    return None


def _resolve_shop_from_token(token: str, db: Session) -> Optional[Shop]:
    """Shop aus Bearer Token (Shopify Session oder App JWT)."""
    try:
        from app.utils.shopify_token_validator import validate_shopify_session_token
        payload = validate_shopify_session_token(token)
        if payload.get("dest"):
            shop_url = payload["dest"].replace("https://", "").replace("http://", "").strip().rstrip("/")
            shop = db.query(Shop).filter(Shop.shop_url == shop_url).first()
            return shop
    except (ValueError, Exception):
        pass
    try:
        payload = verify_token(token, token_type="access")
        shop_id = payload.get("shop_id")
        if shop_id:
            return db.query(Shop).filter(Shop.id == shop_id).first()
    except Exception:
        pass
    return None


def _set_sentry_user(shop: Shop) -> None:
    try:
        import sentry_sdk
        sentry_sdk.set_user({
            "id": str(shop.id),
            "shop_url": shop.shop_url,
            "shop_name": shop.shop_name or shop.shop_url,
        })
    except ImportError:
        pass


async def get_current_shop(
    request: Request,
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
) -> str:
    """
    Shop-ID ermitteln mit einheitlicher Priorität. KEIN Demo-Fallback – 401 wenn nicht authentifiziert.

    Priorität:
    1. Bearer Token (Shopify Session oder App JWT)
    2. X-Shop-ID Header
    3. X-Shop-Domain Header
    4. ?shop= Query Parameter
    5. session_id Cookie → ShopContext (nur echter Shop, kein Demo)
    6. 401
    """
    # 1. Bearer Token
    token = _get_token_from_request(request, authorization, access_token)
    if token:
        shop = _resolve_shop_from_token(token, db)
        if shop:
            if not shop.is_active:
                raise HTTPException(status_code=403, detail="Shop is inactive")
            _set_sentry_user(shop)
            logger.info(f"Authenticated shop: {shop.id} (via Bearer token)")
            return str(shop.id)

    # 2. X-Shop-ID Header
    x_shop_id = request.headers.get("X-Shop-ID")
    if x_shop_id:
        try:
            sid = int(x_shop_id.strip())
            if sid > 0 and sid != 999:
                shop = db.query(Shop).filter(Shop.id == sid).first()
                if shop and shop.is_active:
                    _set_sentry_user(shop)
                    logger.info(f"Authenticated shop: {sid} (via X-Shop-ID)")
                    return str(sid)
        except ValueError:
            pass

    # 3. X-Shop-Domain Header
    shop_domain = request.headers.get("X-Shop-Domain")
    if shop_domain:
        shop = resolve_shop_by_domain(shop_domain, db)
        if shop:
            _set_sentry_user(shop)
            logger.info(f"Authenticated shop: {shop.id} (via X-Shop-Domain)")
            return str(shop.id)

    # 4. ?shop= Query Parameter
    query_shop = request.query_params.get("shop")
    if query_shop:
        shop = resolve_shop_by_domain(query_shop, db)
        if shop:
            _set_sentry_user(shop)
            logger.info(f"Authenticated shop: {shop.id} (via ?shop=)")
            return str(shop.id)

    # 5. session_id Cookie → ShopContext (ohne Demo)
    session_id = get_session_id(request)
    context = ShopContext(session_id)
    context.load()
    if not context.is_demo_mode and context.active_shop_id != 999:
        shop = db.query(Shop).filter(Shop.id == context.active_shop_id).first()
        if shop and shop.is_active:
            _set_sentry_user(shop)
            logger.info(f"Authenticated shop: {shop.id} (via session)")
            return str(shop.id)

    # 6. Keine gültige Auth
    logger.warning("No valid authentication – 401")
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide Bearer token, X-Shop-Domain, or valid session.",
    )


async def get_current_admin(
    shop_id: str = Depends(get_current_shop),
    db: Session = Depends(get_db),
) -> Shop:
    """Shop mit Admin-Prüfung."""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    if not getattr(shop, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return shop


async def get_current_shop_optional(
    request: Request,
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
) -> Optional[str]:
    """
    shop_id wenn authentifiziert, sonst None. Demo-Fallback: bei Session mit Demo (999) wird "999" zurückgegeben.
    """
    try:
        return await get_current_shop(request, authorization, access_token, db)
    except HTTPException:
        session_id = get_session_id(request)
        context = ShopContext(session_id)
        context.load()
        if context.is_demo_mode and context.active_shop_id == 999:
            return "999"
        return None


