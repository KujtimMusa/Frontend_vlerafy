"""
Shop-Management API Endpoints
Ermöglicht Wechsel zwischen Demo-Shop und echten Shopify-Shops
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Request as FastAPIRequest
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from pydantic import BaseModel
import logging

from app.database import get_db
from app.models.shop import Shop
from app.core.shop_context import ShopContext, get_session_id
from app.core.jwt_manager import create_access_token, create_refresh_token
from app.services.csv_demo_shop_adapter import CSVDemoShopAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shops", tags=["shops"])


# Pydantic Models
class ShopResponse(BaseModel):
    id: int
    name: str
    type: str  # "demo" or "shopify"
    shop_url: Optional[str]
    product_count: int
    is_active: bool


class ShopsResponse(BaseModel):
    shops: List[ShopResponse]
    active_shop_id: int
    is_demo_mode: bool


class SwitchShopRequest(BaseModel):
    shop_id: int
    use_demo: bool


class CurrentShopResponse(BaseModel):
    shop: ShopResponse
    is_demo_mode: bool


def get_shop_context(request: FastAPIRequest) -> ShopContext:
    """Dependency: Gibt Shop-Context für aktuelle Session zurück"""
    session_id = get_session_id(request)
    return ShopContext(session_id)


@router.get("", response_model=ShopsResponse)
async def get_available_shops(
    request: FastAPIRequest,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Liste alle verfügbaren Shops für die Session.
    Inkludiert Demo-Shop und alle installierten Shopify-Shops.
    """
    try:
        session_id = get_session_id(request)
        
        logger.info(f"[AVAILABLE_SHOPS] ========== GET AVAILABLE SHOPS ==========")
        logger.info(f"[AVAILABLE_SHOPS] Session ID: {session_id}")
        logger.info(f"[AVAILABLE_SHOPS] Context BEFORE reload: shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}")
        
        # ✅ CRITICAL: Force reload from Redis/Memory
        shop_context.load()
        
        logger.info(f"[AVAILABLE_SHOPS] Context AFTER reload: shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}")
        shops = []
        
        # 1. Demo Shop (immer verfügbar)
        demo_adapter = CSVDemoShopAdapter()
        demo_products = demo_adapter.load_products()
        
        # Demo Shop - Stelle sicher dass type="demo" und id=999
        shops.append(ShopResponse(
            id=999,
            name="Demo Shop",
            type="demo",  # WICHTIG: type muss "demo" sein!
            shop_url=None,
            product_count=len(demo_products),
            is_active=shop_context.is_demo_mode and shop_context.active_shop_id == 999
        ))
        logger.info(f"✅ Demo Shop hinzugefügt (ID=999, Products={len(demo_products)})")
        
        # 2. Echte Shopify-Shops aus DB
        db_shops = db.query(Shop).filter(Shop.is_active == True).all()
        logger.info(f"Gefundene aktive Shops in DB: {len(db_shops)}")
        
        for shop in db_shops:
            # WICHTIG: Überspringe Shop wenn id=999 (sollte nicht passieren, aber sicherheitshalber)
            if shop.id == 999:
                logger.warning(f"⚠️ Shop mit ID=999 in DB gefunden - überspringe!")
                continue
            
            logger.info(f"Verarbeite Shop: {shop.id} - {shop.shop_name or shop.shop_url}")
            # Zähle Produkte (vereinfacht, könnte optimiert werden)
            from app.models.product import Product
            product_count = db.query(Product).filter(Product.shop_id == shop.id).count()
            
            # is_active bedeutet hier: Ist dieser Shop aktuell der aktive Shop?
            is_currently_active = (
                not shop_context.is_demo_mode and 
                shop_context.active_shop_id == shop.id
            )
            
            shops.append(ShopResponse(
                id=shop.id,
                name=shop.shop_name or shop.shop_url,
                type="shopify",
                shop_url=shop.shop_url,
                product_count=product_count,
                is_active=is_currently_active
            ))
            logger.info(
                f"Shop {shop.id} zur Liste hinzugefügt: "
                f"{shop.shop_name or shop.shop_url}, "
                f"Products: {product_count}, Active: {is_currently_active}"
            )
        
        logger.info(f"✅ Insgesamt {len(shops)} Shops zurückgegeben (1 Demo + {len(db_shops)} Live)")
        
        return ShopsResponse(
            shops=shops,
            active_shop_id=shop_context.active_shop_id,
            is_demo_mode=shop_context.is_demo_mode
        )
        
    except Exception as e:
        logger.error(f"Fehler beim Laden der Shops: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/switch")
async def switch_active_shop(
    request: SwitchShopRequest,
    http_request: FastAPIRequest,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Wechsle den aktiven Shop für die Session.
    Setzt JWT Cookies für Live-Shops (nicht für Demo).
    
    Body:
    {
        "shop_id": 999,
        "use_demo": true
    }
    """
    try:
        session_id = get_session_id(http_request)
        
        logger.info(f"[SWITCH] ========== SWITCH REQUEST ==========")
        logger.info(f"[SWITCH] Session ID: {session_id}")
        logger.info(f"[SWITCH] Request: shop_id={request.shop_id}, use_demo={request.use_demo}")
        logger.info(f"[SWITCH] Context BEFORE: shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}")
        
        # ✅ CRITICAL: Force reload from Redis/Memory BEFORE update
        shop_context.load()
        
        logger.info(
            f"[SWITCH] Session {shop_context.session_id}: "
            f"BEFORE switch - shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}"
        )
        
        shop = None
        shop_name = None
        shop_type = None
        
        # Validiere Shop-ID
        if request.use_demo:
            if request.shop_id != 999:
                raise HTTPException(
                    status_code=400, 
                    detail="Für Demo-Mode muss shop_id=999 sein"
                )
            shop_context.is_demo_mode = True
            shop_context.active_shop_id = 999
            shop_name = "Demo Shop"
            shop_type = "demo"
        else:
            # Live Mode: Prüfe ob Shop existiert
            shop = db.query(Shop).filter(
                Shop.id == request.shop_id,
                Shop.is_active == True
            ).first()
            
            if not shop:
                # Kein Shop gefunden - setze trotzdem Live Mode (zeigt Connect Card)
                logger.info(f"Shop {request.shop_id} nicht gefunden, setze Live Mode ohne Shop")
                shop_context.is_demo_mode = False
                shop_context.active_shop_id = 0  # 0 = kein Shop aktiv
                return JSONResponse({
                    "success": True,
                    "message": "Live Mode aktiviert (kein Shop installiert)",
                    "is_demo_mode": False,
                    "active_shop_id": 0,
                    "active_shop": None
                })
            
            shop_context.is_demo_mode = False
            shop_context.active_shop_id = request.shop_id
            shop_name = shop.shop_name or shop.shop_url
            shop_type = "shopify"
        
        # ✅ CRITICAL: Save context to Redis/Memory
        shop_context.save()
        
        logger.info(f"[SWITCH] Context AFTER: shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}")
        logger.info(f"[SWITCH] ✅ Context saved to Redis/Memory")
        
        # Response Data
        response_data = {
            "success": True,
            "active_shop": {
                "id": shop_context.active_shop_id,
                "name": shop_name if request.use_demo or shop else None,
                "type": shop_type if request.use_demo or shop else None
            } if (request.use_demo or shop) else None,
            "is_demo_mode": shop_context.is_demo_mode,
            "active_shop_id": shop_context.active_shop_id
        }
        
        # Für Live-Shops: Setze JWT Cookies
        if not request.use_demo and shop:
            # Erstelle JWT Tokens
            access_token = create_access_token(shop.id, shop.shop_url)
            refresh_token = create_refresh_token(shop.id)
            
            # Erstelle Response mit Cookies
            response = JSONResponse(response_data)
            
            # Setze HTTP-only Cookies (SameSite="none" für Cross-Origin)
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
                max_age=7 * 60 * 60 * 24  # 7 Tage
            )
            
            logger.info(
                f"Session {shop_context.session_id}: Shop gewechselt zu {shop_name} "
                f"(ID: {request.shop_id}, Demo: {request.use_demo}) - JWT Cookies gesetzt"
            )
            
            return response
        
        # Demo Mode: Normale JSON Response (keine Cookies)
        logger.info(
            f"Session {shop_context.session_id}: Shop gewechselt zu {shop_name} "
            f"(ID: {request.shop_id}, Demo: {request.use_demo})"
        )
        
        return JSONResponse(response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fehler beim Wechseln des Shops: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/current", response_model=CurrentShopResponse)
async def get_current_shop(
    request: FastAPIRequest,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Gibt aktuell aktiven Shop zurück.
    Wird von Frontend genutzt um zu wissen welcher Shop aktiv ist.
    """
    try:
        session_id = get_session_id(request)
        
        logger.info(f"[CURRENT_SHOP] ========== GET CURRENT SHOP ==========")
        logger.info(f"[CURRENT_SHOP] Session ID: {session_id}")
        logger.info(f"[CURRENT_SHOP] Context BEFORE reload: shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}")
        
        # ✅ CRITICAL: Force reload from Redis/Memory
        shop_context.load()
        
        logger.info(f"[CURRENT_SHOP] Context AFTER reload: shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}")
        if shop_context.is_demo_mode:
            # Demo Shop
            demo_product_count = 20  # Default
            try:
                demo_adapter = CSVDemoShopAdapter()
                demo_products = demo_adapter.load_products()
                demo_product_count = len(demo_products) if demo_products else 20
            except Exception as e:
                logger.warning(f"Demo-Products konnten nicht geladen werden: {e}")
            
            shop = ShopResponse(
                id=999,
                name="Demo Shop",
                type="demo",
                shop_url=None,
                product_count=demo_product_count,
                is_active=True
            )
        else:
            # Echter Shopify-Shop
            logger.info(f"Lade Shop für active_shop_id: {shop_context.active_shop_id}")
            db_shop = db.query(Shop).filter(Shop.id == shop_context.active_shop_id).first()
            
            if not db_shop:
                logger.warning(f"Shop {shop_context.active_shop_id} nicht in DB gefunden - Fallback zu Demo")
                # Fallback zu Demo
                shop = ShopResponse(
                    id=999,
                    name="Demo Shop",
                    type="demo",
                    shop_url=None,
                    product_count=20,  # Default ohne CSV-Laden
                    is_active=True
                )
                shop_context.is_demo_mode = True
                shop_context.active_shop_id = 999
            else:
                logger.info(f"Shop gefunden: {db_shop.shop_name or db_shop.shop_url} (ID: {db_shop.id}, is_active: {db_shop.is_active})")
                from app.models.product import Product
                product_count = db.query(Product).filter(Product.shop_id == db_shop.id).count()
                logger.info(f"Shop {db_shop.id} hat {product_count} Produkte in DB")
                
                shop = ShopResponse(
                    id=db_shop.id,
                    name=db_shop.shop_name or db_shop.shop_url,
                    type="shopify",
                    shop_url=db_shop.shop_url,
                    product_count=product_count,
                    is_active=db_shop.is_active
                )
        
        return CurrentShopResponse(
            shop=shop,
            is_demo_mode=shop_context.is_demo_mode
        )
        
    except Exception as e:
        logger.error(f"Fehler beim Laden des aktuellen Shops: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
