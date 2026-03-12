"""
Shopify GraphQL Router
Endpoints für Shopify GraphQL API Integration
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging

from app.database import get_db
from app.models.shop import Shop
from app.models.product import Product
from app.services.shopify_graphql_service import ShopifyGraphQLService
from app.services.shopify_variant_detector import VariantDetector
from app.services.shopify_rate_limiter import rate_limiter
from app.services.shopify_error_handler import ShopifyErrorHandler
from app.services.price_history_service import PriceHistoryService
from app.services.recommendation_service import RecommendationService
from app.utils.encryption import decrypt_token
from app.core.shop_context import get_shop_context, ShopContext
from app.middleware.rate_limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shopify", tags=["shopify"])


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class ApplyPriceRequest(BaseModel):
    """Request Model für Apply Price"""
    product_id: int  # DB Product ID
    recommended_price: float
    variant_id: Optional[str] = None  # Optional: Auto-Detection falls nicht angegeben
    recommendation_id: Optional[int] = None  # Optional: Für Status-Update
    force: Optional[bool] = False  # Admin: Bypass Rate Limits


class ApplyPriceResponse(BaseModel):
    success: bool
    new_price: float
    variant_id: str
    message: Optional[str] = None


class BulkUpdateRequest(BaseModel):
    updates: List[dict]  # [{"variant_id": "...", "new_price": 99.99}]


# ============================================
# ENDPOINTS
# ============================================

@router.get("/products")
async def get_shopify_products(
    shop_id: int = Query(..., description="Shop ID aus der Datenbank"),
    first: int = Query(50, ge=1, le=250, description="Anzahl Produkte"),
    db: Session = Depends(get_db)
):
    """
    Produkte von Shopify via GraphQL holen
    
    Args:
        shop_id: Shop ID aus der Datenbank
        first: Anzahl Produkte (max 250)
        
    Returns:
        Liste von Produkten mit Varianten & Preisen
    """
    try:
        # Shop aus DB holen
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        # Access Token entschlüsseln
        try:
            access_token = decrypt_token(shop.access_token)
        except Exception as e:
            logger.error(f"Fehler beim Entschlüsseln des Access Tokens: {e}")
            raise HTTPException(status_code=500, detail="Fehler beim Entschlüsseln des Access Tokens")
        
        # GraphQL Service initialisieren
        service = ShopifyGraphQLService(
            shop_url=shop.shop_url,
            access_token=access_token
        )
        
        # Produkte holen
        result = await service.get_products(first=first)
        
        # Transformiere GraphQL Response zu einfachem Format
        products = []
        for edge in result.get("edges", []):
            node = edge.get("node", {})
            variants = []
            for variant_edge in node.get("variants", {}).get("edges", []):
                variant_node = variant_edge.get("node", {})
                variants.append({
                    "id": variant_node.get("id"),
                    "price": float(variant_node.get("price", 0)),
                    "compare_at_price": float(variant_node.get("compareAtPrice", 0)) if variant_node.get("compareAtPrice") else None,
                    "sku": variant_node.get("sku"),
                    "inventory_quantity": variant_node.get("inventoryQuantity", 0),
                    "title": variant_node.get("title")
                })
            
            products.append({
                "id": node.get("id"),
                "title": node.get("title"),
                "handle": node.get("handle"),
                "status": node.get("status"),
                "vendor": node.get("vendor"),
                "product_type": node.get("productType"),
                "variants": variants
            })
        
        return {
            "products": products,
            "page_info": result.get("pageInfo", {}),
            "total": len(products)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fehler beim Laden der Shopify Produkte: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fehler beim Laden der Produkte: {str(e)}")


@router.post("/apply-price")
@limiter.limit("10/minute")  # Max 10 price changes per minute per IP/shop
async def apply_price(
    request: Request,  # WICHTIG: Request parameter für Limiter (muss ERSTER Parameter sein)
    apply_request: ApplyPriceRequest,  # Request Body
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Wendet Preis auf Shopify an (mit Variant-Detection und Rate Limiting).
    
    Workflow:
    1. Finde Product in DB
    2. Lade Shopify Service
    3. Auto-Detect Variant (falls nicht angegeben)
    4. Update Preis mit Rate Limiting + Retry
    5. Track in Price History
    6. Mark Recommendation as Applied (falls vorhanden)
    
    Features:
    - Intelligente Variant-Detection
    - Rate Limiting (2 Requests/Sekunde)
    - Retry Logic (3x mit Exponential Backoff)
    - Price History Integration
    - Recommendation Status Update
    """
    # 1. Finde Product
    product = db.query(Product).filter(
        Product.id == apply_request.product_id,
        Product.shop_id == shop_context.active_shop_id
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Product {apply_request.product_id} nicht gefunden"
        )
    
    # Demo-Shop Check
    if shop_context.is_demo_mode:
        raise HTTPException(
            status_code=400,
            detail="Apply Price nicht verfügbar im Demo-Modus. Nutze Live-Shop."
        )
    
    # 2. Lade Shopify Service
    shop = db.query(Shop).filter(Shop.id == shop_context.active_shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop nicht gefunden")
    
    access_token = decrypt_token(shop.access_token)
    service = ShopifyGraphQLService(shop.shop_url, access_token)
    
    # 3. Variant-Detection
    variant_id = apply_request.variant_id
    
    if not variant_id:
        # Auto-Detect beste Variant
        try:
            shopify_product = await service.get_product_by_id(product.shopify_product_id)
            
            if not shopify_product or not shopify_product.get("variants", {}).get("edges"):
                raise HTTPException(
                    status_code=404,
                    detail=f"Keine Variants für Produkt {product.shopify_product_id} gefunden"
                )
            
            # Extrahiere Variants aus GraphQL Format
            variant_edges = shopify_product["variants"]["edges"]
            variants = [edge["node"] for edge in variant_edges]
            
            detector = VariantDetector()
            best_variant = detector.find_best_variant(variants)
            
            if not best_variant:
                raise HTTPException(
                    status_code=400,
                    detail="Konnte keine passende Variant finden"
                )
            
            variant_id = best_variant.get('id')
            logger.info(f"✅ Auto-detected Variant: {variant_id}")
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Fehler bei Variant Detection: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Variant Detection fehlgeschlagen: {str(e)}"
            )
    else:
        # Validate User-provided Variant
        try:
            shopify_product = await service.get_product_by_id(product.shopify_product_id)
            if shopify_product and shopify_product.get("variants", {}).get("edges"):
                variant_edges = shopify_product["variants"]["edges"]
                variants = [edge["node"] for edge in variant_edges]
                detector = VariantDetector()
                
                if not detector.validate_variant({'id': variant_id}, variants):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Variant {variant_id} existiert nicht für dieses Produkt"
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Konnte Variant nicht validieren: {e}")
    
    # 4. Update Preis mit Rate Limiting + Retry
    async def update_price_with_retry():
        """Wrapper für Rate Limiting"""
        return await service.update_variant_price(
            variant_id=variant_id,
            new_price=apply_request.recommended_price
        )
    
    try:
        if apply_request.force:
            # Admin Bypass: Ohne Rate Limiting
            logger.warning(f"⚠️ FORCE MODE: Bypass Rate Limiting")
            result = await service.update_variant_price(
                variant_id=variant_id,
                new_price=apply_request.recommended_price
            )
        else:
            # Normal: Mit Rate Limiting
            result = await rate_limiter.execute_with_retry(
                update_price_with_retry,
                max_retries=3
            )
    except Exception as e:
        # Parse Shopify Error
        error_info = ShopifyErrorHandler.log_error(e, context={
            'product_id': apply_request.product_id,
            'variant_id': variant_id,
            'price': apply_request.recommended_price
        })
        
        # Bestimme HTTP Status Code basierend auf Error Type
        status_code = 500
        if error_info['error_code'] == 'THROTTLED':
            status_code = 429
        elif error_info['error_code'] in ['PRODUCT_NOT_FOUND', 'VARIANT_NOT_FOUND']:
            status_code = 404
        elif error_info['error_code'] in ['INVALID_PRICE', 'PERMISSION_DENIED']:
            status_code = 400
        
        raise HTTPException(
            status_code=status_code,
            detail={
                'error': error_info['error_code'],
                'message': error_info['message'],
                'details': error_info.get('details'),
                'retry_after': error_info.get('retry_after')
            }
        )
    
    # 5. Check Errors
    user_errors = result.get('userErrors', [])
    if user_errors:
        error_messages = [err.get('message', 'Unknown error') for err in user_errors]
        raise HTTPException(
            status_code=400,
            detail=f"Shopify Fehler: {', '.join(error_messages)}"
        )
    
    # 6. Update Product in DB
    product_variant = result.get('productVariant', {})
    new_price = float(product_variant.get('price', apply_request.recommended_price))
    old_price = product.price
    
    product.price = new_price
    db.commit()
    
    # 7. Track in Price History
    try:
        price_service = PriceHistoryService(db)
        price_service.track_price_change(
            product_id=product.id,
            shop_id=product.shop_id,
            new_price=new_price,
            previous_price=float(old_price) if old_price else None,
            triggered_by="apply_price",
            meta_data={
                'variant_id': variant_id,
                'recommended_price': apply_request.recommended_price,
                'applied_price': new_price,
                'recommendation_id': apply_request.recommendation_id
            }
        )
        logger.info(f"✅ Price Change getrackt: {old_price} → {new_price}")
    except Exception as e:
        logger.warning(f"⚠️ Fehler beim Tracken der Preisänderung: {e}")
    
    # 8. Mark Recommendation as Applied (falls vorhanden)
    if apply_request.recommendation_id:
        try:
            rec_service = RecommendationService(db)
            rec_service.mark_as_applied(
                recommendation_id=apply_request.recommendation_id,
                applied_price=new_price
            )
            logger.info(f"✅ Recommendation {apply_request.recommendation_id} als 'applied' markiert")
        except Exception as e:
            logger.warning(f"⚠️ Fehler beim Markieren der Recommendation: {e}")
    
    return {
        "success": True,
        "product_id": apply_request.product_id,
        "variant_id": variant_id,
        "old_price": float(old_price) if old_price else None,
        "new_price": new_price,
        "applied_price": new_price,
        "recommendation_id": apply_request.recommendation_id,
        "message": "Preis erfolgreich auf Shopify aktualisiert"
    }


@router.post("/bulk-update-prices")
async def bulk_update_prices(
    shop_id: int = Query(..., description="Shop ID"),
    request: BulkUpdateRequest = None,
    db: Session = Depends(get_db)
):
    """
    Mehrere Preise gleichzeitig aktualisieren
    
    Args:
        shop_id: Shop ID
        request: Liste von Updates
        
    Returns:
        Liste von Ergebnissen
    """
    try:
        # Shop aus DB holen
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        # Access Token entschlüsseln
        try:
            access_token = decrypt_token(shop.access_token)
        except Exception as e:
            logger.error(f"Fehler beim Entschlüsseln des Access Tokens: {e}")
            raise HTTPException(status_code=500, detail="Fehler beim Entschlüsseln des Access Tokens")
        
        # GraphQL Service
        service = ShopifyGraphQLService(
            shop_url=shop.shop_url,
            access_token=access_token
        )
        
        # Bulk Update
        results = await service.bulk_update_prices(request.updates)
        
        return {
            "success": True,
            "results": results,
            "total": len(results),
            "successful": sum(1 for r in results if r.get("success", False))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fehler beim Bulk Update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fehler beim Bulk Update: {str(e)}")


@router.get("/product/{product_id}")
async def get_shopify_product(
    product_id: str,
    shop_id: int = Query(..., description="Shop ID"),
    db: Session = Depends(get_db)
):
    """
    Einzelnes Produkt von Shopify holen
    
    Args:
        product_id: Shopify Product ID (gid://shopify/Product/123456 oder nur 123456)
        shop_id: Shop ID
        
    Returns:
        Produkt-Details
    """
    try:
        # Shop aus DB holen
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        # Access Token entschlüsseln
        try:
            access_token = decrypt_token(shop.access_token)
        except Exception as e:
            logger.error(f"Fehler beim Entschlüsseln des Access Tokens: {e}")
            raise HTTPException(status_code=500, detail="Fehler beim Entschlüsseln des Access Tokens")
        
        # GraphQL Service
        service = ShopifyGraphQLService(
            shop_url=shop.shop_url,
            access_token=access_token
        )
        
        # Produkt holen
        product = await service.get_product_by_id(product_id)
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found on Shopify")
        
        return product
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fehler beim Laden des Produkts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fehler beim Laden des Produkts: {str(e)}")

