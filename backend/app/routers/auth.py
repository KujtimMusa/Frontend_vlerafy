from fastapi import APIRouter, Depends, HTTPException, Request, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.shop import Shop
from app.utils.encryption import encrypt_token, decrypt_token
from app.core.jwt_manager import create_access_token, create_refresh_token, refresh_access_token
from app.core.shop_context import get_redis_client, ShopContext
from app.config import settings
from datetime import datetime
import shopify
import requests
import hmac
import hashlib
import logging
import secrets
import asyncio
import json
import uuid
from typing import Optional
from urllib.parse import urlencode

router = APIRouter(prefix="/auth/shopify", tags=["auth"])
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# OAuth State Storage (Redis with in-memory fallback)
# ═══════════════════════════════════════════════════════
_oauth_memory_fallback = {}

async def save_oauth_state(state: str, shop: str, redis_client, host: str = "") -> None:
    data = json.dumps({"shop": shop, "host": host or ""})
    if redis_client:
        await asyncio.to_thread(redis_client.setex, f"oauth_state:{state}", 600, data)
    else:
        _oauth_memory_fallback[state] = {"shop": shop, "host": host or ""}

async def get_oauth_state(state: str, redis_client) -> Optional[dict]:
    if redis_client:
        value = await asyncio.to_thread(redis_client.get, f"oauth_state:{state}")
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {"shop": value, "host": ""}  # legacy plain shop string
        return None
    return _oauth_memory_fallback.get(state)

async def delete_oauth_state(state: str, redis_client) -> None:
    if redis_client:
        await asyncio.to_thread(redis_client.delete, f"oauth_state:{state}")
    else:
        _oauth_memory_fallback.pop(state, None)


@router.get("/install")
async def shopify_install(shop: str, host: str = None, request: Request = None):
    """
    Startet den Shopify OAuth Install Flow.
    host wird für Embedded-Callback gespeichert.
    """
    try:
        state = secrets.token_urlsafe(32)
        redis_client = get_redis_client()
        await save_oauth_state(state, shop, redis_client, host or "")

        from app.utils.oauth import generate_install_url

        oauth_url = generate_install_url(shop, state)

        logger.info(f"🔵 OAuth Redirect: {shop} (host={host or '-'}) → {oauth_url[:80]}...")

        return RedirectResponse(url=oauth_url, status_code=302)

    except Exception as e:
        logger.error(f"Fehler beim Erstellen der OAuth-URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback")
async def shopify_callback(
    code: str,
    shop: str,
    state: str = None,
    hmac_param: str = None,
    db: Session = Depends(get_db),
):
    """
    Shopify OAuth Callback - tauscht Code gegen Access Token
    """
    try:
        # HMAC-Validierung (optional, aber empfohlen)
        if hmac_param:
            # HMAC-Validierung implementieren
            pass
        
        # Token Exchange
        token_url = f"https://{shop}/admin/oauth/access_token"
        token_data = {
            "client_id": settings.SHOPIFY_CLIENT_ID,
            "client_secret": settings.SHOPIFY_CLIENT_SECRET,
            "code": code
        }
        
        logger.info(f"Tausche Code gegen Access Token für Shop: {shop}")
        response = requests.post(token_url, json=token_data)
        response.raise_for_status()
        
        token_response = response.json()
        access_token = token_response.get("access_token")
        granted_scopes = token_response.get("scope", "")
        
        if not access_token:
            raise Exception("Kein Access Token erhalten")
        
        logger.info(f"🟢 Token erhalten: {access_token[:10]}...")
        
        # Entferne https:// für Session (shopifyapi erwartet nur Domain)
        shop_domain = shop.replace('https://', '').replace('http://', '').strip()
        
        # Workaround für 2025-10 API Version
        api_version = settings.SHOPIFY_API_VERSION
        if api_version not in shopify.ApiVersion.versions:
            logger.warning(f"API Version {api_version} nicht in SDK, nutze trotzdem")
            try:
                class TempApiVersion:
                    def __init__(self, name):
                        self.name = name
                    
                    def api_path(self, url):
                        if url.startswith('http://') or url.startswith('https://'):
                            from urllib.parse import urlparse
                            parsed = urlparse(url)
                            path = parsed.path
                            api_path = f"/admin/api/{self.name}{path}"
                            return f"{parsed.scheme}://{parsed.netloc}{api_path}"
                        else:
                            return f"/admin/api/{self.name}{url}"
                
                temp_version = TempApiVersion(api_version)
                shopify.ApiVersion.versions[api_version] = temp_version
            except Exception as e:
                logger.warning(f"Konnte {api_version} nicht zur SDK hinzufügen: {e}")
        
        # Session erstellen und aktivieren
        logger.info(f"Erstelle Session für Shop: {shop_domain}, API Version: {api_version}")
        session = shopify.Session(shop_domain, api_version, access_token)
        shopify.ShopifyResource.activate_session(session)
        logger.info("Session aktiviert")
        
        # Shop Info laden
        try:
            shop_info = shopify.Shop.current()
            shop_name = shop_info.name if shop_info and hasattr(shop_info, 'name') else shop_domain
            logger.info(f"Shop Info geladen: {shop_name}")
        except Exception as e:
            logger.warning(f"Konnte Shop Info nicht laden: {e}")
            shop_name = shop_domain
        
        # Shop in DB speichern oder aktualisieren
        encrypted_token = encrypt_token(access_token)
        
        existing_shop = db.query(Shop).filter(Shop.shop_url == shop_domain).first()
        if existing_shop:
            existing_shop.shop_name = shop_name
            existing_shop.access_token = encrypted_token
            existing_shop.scope = granted_scopes
            existing_shop.is_active = True
            # installed_at bleibt beim ersten Installationszeitpunkt
            db.commit()
            db.refresh(existing_shop)
            shop_obj = existing_shop
            logger.info(f"Shop aktualisiert: {shop_domain}")
        else:
            shop_obj = Shop(
                shop_url=shop_domain,
                shop_name=shop_name,
                access_token=encrypted_token,
                scope=granted_scopes,
                is_active=True,
                installed_at=datetime.utcnow(),  # NEU: Installationszeitpunkt
            )
            db.add(shop_obj)
            db.commit()
            db.refresh(shop_obj)
            logger.info(f"✅ Token gespeichert für {shop_domain}")
        
        # WICHTIG: Initiale Produktsync nach Installation
        try:
            logger.info(f"🔄 Starte initiale Produktsync für Shop {shop_obj.id}...")
            from app.services.shopify_adapter import ShopifyDataAdapter
            
            adapter = ShopifyDataAdapter(
                shop_id=shop_obj.id,
                shop_url=shop_domain,
                access_token=access_token,
                api_version=settings.SHOPIFY_API_VERSION
            )
            
            result = adapter.sync_products_to_db(db)
            logger.info(f"✅ Initiale Produktsync erfolgreich: {result['synced']} neu, {result['updated']} aktualisiert")
        except Exception as e:
            logger.error(f"❌ Initiale Produktsync fehlgeschlagen: {e}")
            # Nicht kritisch - User kann manuell syncen
        
        # Fix A: Session setzen – ShopContext + session_id Cookie
        session_id = str(uuid.uuid4())
        shop_context = ShopContext(session_id)
        shop_context.active_shop_id = shop_obj.id
        shop_context.is_demo_mode = False
        shop_context.save()
        logger.info(f"✅ ShopContext gesetzt: session={session_id[:8]}..., shop_id={shop_obj.id}, demo=False")

        # Redirect zu Frontend embedded Route (mit host für iFrame)
        redis_client = get_redis_client()
        stored = await get_oauth_state(state, redis_client) if state else None
        if stored:
            await delete_oauth_state(state, redis_client)
        if not stored:
            stored = {"shop": shop_domain, "host": ""}
        host = stored.get("host", "")
        if host:
            redirect_url = f"{settings.FRONTEND_URL}/?shop={stored['shop']}&host={host}&shop_id={shop_obj.id}&installed=true"
        else:
            redirect_url = f"{settings.FRONTEND_URL}/auth/callback?shop_id={shop_obj.id}&shop={stored['shop']}&installed=true"
        logger.info(f"Redirecting to frontend: {redirect_url}")

        response = RedirectResponse(url=redirect_url, status_code=302)
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=86400 * 7,  # 7 Tage
        )
        return response
    
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Fehler beim Token Exchange: {e}")
        error_detail = f"OAuth Error: {e.response.text if hasattr(e, 'response') else str(e)}"
        raise HTTPException(status_code=400, detail=error_detail)
    except Exception as e:
        logger.error(f"Fehler im OAuth Callback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OAuth Error: {str(e)}")


# ═══════════════════════════════════════════════════════
# SHOPIFY PUBLIC APP OAUTH ENDPOINTS
# ═══════════════════════════════════════════════════════

@router.get("/shopify/install", tags=["OAuth"])
async def shopify_install_public(shop: str, request: Request):
    """
    OAuth Step 1: Initiate Shopify app installation
    
    Query params:
        shop: Shop domain (e.g. 'example.myshopify.com')
    
    Returns:
        Redirect to Shopify OAuth authorization page
    """
    # Validate shop parameter
    if not shop or not shop.endswith('.myshopify.com'):
        raise HTTPException(
            status_code=400,
            detail="Invalid shop parameter. Must end with .myshopify.com"
        )
    
    # Generate CSRF token
    state = secrets.token_urlsafe(32)
    redis_client = get_redis_client()
    await save_oauth_state(state, shop, redis_client)
    
    # Import OAuth utility
    from app.utils.oauth import generate_install_url
    
    # Generate OAuth URL
    install_url = generate_install_url(shop, state)
    
    return RedirectResponse(url=install_url)


@router.get("/shopify/callback", tags=["OAuth"])
async def shopify_callback_public(
    request: Request,
    code: str,
    state: str,
    shop: str,
    hmac: str,
    db: Session = Depends(get_db)
):
    """
    OAuth Step 2: Handle Shopify callback after user approval
    
    Query params:
        code: Authorization code
        state: CSRF token
        shop: Shop domain
        hmac: Security signature
    
    Returns:
        Redirect to frontend dashboard with shop_id
    """
    # Import utilities
    from app.utils.oauth import verify_hmac, exchange_code_for_token
    from app.utils.encryption import encrypt_token
    from app.models.shop import Shop
    
    # 1. Verify CSRF state
    redis_client = get_redis_client()
    stored = await get_oauth_state(state, redis_client)
    if not stored:
        raise HTTPException(
            status_code=400, 
            detail="Invalid or expired state parameter"
        )
    
    await delete_oauth_state(state, redis_client)
    stored_shop = stored.get("shop", "")
    if stored_shop != shop:
        raise HTTPException(
            status_code=400, 
            detail="Shop domain mismatch"
        )
    
    # 2. Verify HMAC signature
    params = dict(request.query_params)
    if not verify_hmac(params, hmac):
        raise HTTPException(
            status_code=400, 
            detail="Invalid HMAC signature"
        )
    
    # 3. Exchange code for token
    try:
        token_data = await exchange_code_for_token(shop, code)
        access_token = token_data['access_token']
        scope = token_data['scope']
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Token exchange failed: {str(e)}"
        )
    
    # 4. Encrypt token
    encrypted_token = encrypt_token(access_token)
    
    # 5. Save or update shop in database
    existing_shop = db.query(Shop).filter(Shop.shop_url == shop).first()
    
    if existing_shop:
        existing_shop.access_token = encrypted_token
        existing_shop.scope = scope
        existing_shop.is_active = True
        shop_record = existing_shop
    else:
        shop_record = Shop(
            shop_url=shop,
            access_token=encrypted_token,
            scope=scope,
            is_active=True
        )
        db.add(shop_record)
    
    db.commit()
    db.refresh(shop_record)
    
    # 6. Create JWT Tokens
    access_token = create_access_token(shop_record.id, shop_record.shop_url)
    refresh_token = create_refresh_token(shop_record.id)
    
    # 7. Create redirect response with cookies
    redirect_url = f"{settings.FRONTEND_URL}/auth/callback?shop_id={shop_record.id}&shop={shop}&installed=true"
    response = RedirectResponse(url=redirect_url, status_code=302)
    
    # Set HTTP-only cookies (SameSite="none" für Cross-Origin)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,  # Nur HTTPS in Production
        samesite="none",  # ✅ Erlaubt Cross-Origin (vercel.app → railway.app)
        max_age=24 * 60 * 60  # 24 Stunden
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="none",  # ✅ Erlaubt Cross-Origin (vercel.app → railway.app)
        max_age=7 * 24 * 60 * 60  # 7 Tage
    )
    
    return response


@router.get("/shopify/status", tags=["OAuth"])
async def shopify_auth_status(shop: str, db: Session = Depends(get_db)):
    """
    Check if shop is authenticated
    
    Query params:
        shop: Shop domain
    
    Returns:
        JSON with authentication status and shop details
    """
    from app.models.shop import Shop
    
    shop_record = db.query(Shop).filter(Shop.shop_url == shop).first()
    
    if not shop_record or not shop_record.is_active:
        return {"authenticated": False}
    
    return {
        "authenticated": True,
        "shop_id": shop_record.id,
        "scope": shop_record.scope
    }


@router.post("/refresh", tags=["auth"])
async def refresh_token_endpoint(
    refresh_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token
    
    Returns new access token as cookie
    """
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")
    
    try:
        # Create new access token
        new_access_token = refresh_access_token(refresh_token, db)
        
        # Set new cookie
        response = JSONResponse({"success": True, "message": "Token refreshed"})
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=24 * 60 * 60  # 24 Stunden
        )
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token refresh failed: {str(e)}")







