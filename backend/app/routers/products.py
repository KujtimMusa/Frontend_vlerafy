from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.shop import Shop
from app.models.product import Product
from app.utils.encryption import decrypt_token
from app.services.shopify_adapter import ShopifyDataAdapter
from app.services.csv_demo_shop_adapter import CSVDemoShopAdapter
from app.core.shop_context import get_shop_context, ShopContext
from app.config import settings
import logging

router = APIRouter(prefix="/products", tags=["products"])
logger = logging.getLogger(__name__)


@router.get("/")
async def get_products(
    request: Request,
    shop_id: Optional[int] = Query(None),  # Optional für Backward-Compatibility
    db: Session = Depends(get_db)
):
    """
    Lädt alle Produkte für den aktiven Shop (aus Shop-Context).
    Falls shop_id übergeben wird, wird dieser genutzt (Backward-Compatibility).
    """
    # Hole Shop-Context manuell, da Request nicht direkt als Dependency funktioniert
    from app.core.shop_context import get_session_id, ShopContext
    import logging
    
    logger = logging.getLogger(__name__)
    session_id = get_session_id(request)
    shop_context = ShopContext(session_id)
    
    logger.info(f"[PRODUCTS] ========== GET PRODUCTS ==========")
    logger.info(f"[PRODUCTS] Session ID: {session_id}")
    logger.info(f"[PRODUCTS] Context BEFORE reload: shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}")
    
    # ✅ CRITICAL: Force reload from Redis/Memory
    shop_context.load()
    
    logger.info(f"[PRODUCTS] Context AFTER reload: shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}")
    # Nutze shop_id aus Query-Parameter falls vorhanden, sonst aus Context
    if shop_id is None:
        # Nutze Shop-Context
        if shop_context.is_demo_mode:
            # Demo-Shop: Nutze CSV-Adapter
            adapter = CSVDemoShopAdapter()
            demo_products = adapter.load_products()
            
            # Konvertiere zu erwartetem Format
            # WICHTIG: Konvertiere Product IDs zu int für Frontend-Kompatibilität
            return [
                {
                    "id": int(p.get('id', 0)),  # Convert string to int!
                    "title": p.get('title', ''),
                    "price": p.get('price', 0),
                    "inventory": p.get('inventory_quantity', 0),
                    "shopify_product_id": p.get('shopify_product_id', ''),
                    "is_demo": True
                }
                for p in demo_products
            ]
        else:
            # Echter Shop: Aus DB laden
            active_shop_id = shop_context.active_shop_id
            logger.info(f"[PRODUCTS] Loading products for Live Shop ID: {active_shop_id}")
            
            shop = db.query(Shop).filter(Shop.id == active_shop_id).first()
            if not shop:
                logger.warning(f"[PRODUCTS] Shop {active_shop_id} nicht gefunden")
                raise HTTPException(status_code=404, detail="Shop nicht gefunden")
            
            products = db.query(Product).filter(Product.shop_id == shop.id).all()
            logger.info(f"[PRODUCTS] Returning {len(products)} products for shop_id={shop.id}")
            
            return [
                {
                    "id": p.id,
                    "title": p.title,
                    "price": p.price,
                    "inventory": p.inventory_quantity,
                    "shopify_product_id": p.shopify_product_id,
                    "is_demo": False
                }
                for p in products
            ]
    else:
        # Backward-Compatibility: Nutze shop_id aus Query-Parameter
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            raise HTTPException(status_code=404, detail="Shop nicht gefunden")
        
        products = db.query(Product).filter(Product.shop_id == shop_id).all()
        return [
            {
                "id": p.id,
                "title": p.title,
                "price": p.price,
                "inventory": p.inventory_quantity,
                "shopify_product_id": p.shopify_product_id,
                "is_demo": False
            }
            for p in products
        ]


@router.post("/sync/{shop_id}")
async def sync_products(shop_id: int, db: Session = Depends(get_db)):
    """Synchronisiert Produkte von Shopify zu DB"""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop nicht gefunden")
    
    if not shop.is_active:
        raise HTTPException(status_code=400, detail="Shop ist nicht aktiv")
    
    try:
        access_token = decrypt_token(shop.access_token)
        
        adapter = ShopifyDataAdapter(
            shop_id=shop.id,  # WICHTIG!
            shop_url=shop.shop_url,
            access_token=access_token,
            api_version=settings.SHOPIFY_API_VERSION
        )
        
        result = adapter.sync_products_to_db(db)
        
        return {
            "success": True,
            "synced": result['synced'],
            "updated": result['updated'],
            "message": f"{result['synced']} neue Produkte, {result['updated']} aktualisiert"
        }
    
    except Exception as e:
        logger.error(f"Fehler beim Synchronisieren: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-sales/{product_id}")
async def sync_sales_history(
    product_id: int,
    days_back: int = Query(90, ge=1, le=730),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Synchronisiert Sales-Historie für ein Produkt.
    Funktioniert für Demo-Shop (CSV) UND Live-Shop (Shopify API).
    
    Args:
        product_id: Product ID (DB ID, nicht Shopify ID!)
        days_back: Anzahl Tage zurück (1-730, default 90)
        
    Returns:
        Success-Status, Shop-Info, Anzahl gespeicherter Records
    """
    from app.services.sales_history_service import SalesHistoryService
    from app.core.shop_context import get_session_id
    
    # Hole Shop-Context
    session_id = get_session_id(request) if request else "default"
    shop_context = ShopContext(session_id)
    
    # Finde Product
    # WICHTIG: Demo-Shop hat shop_id=999, Live-Shop hat echte shop_id
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.shop_id == shop_context.active_shop_id
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=404, 
            detail=f"Produkt {product_id} nicht gefunden im Shop {shop_context.active_shop_id}"
        )
    
    # Lade Adapter
    adapter = shop_context.get_adapter()
    
    # Sync Sales History
    if shop_context.is_demo_mode:
        # Demo: Lade aus CSV und speichere in DB
        # WICHTIG: CSV-Adapter hat jetzt sync_sales_history_to_db() Methode
        if hasattr(adapter, 'sync_sales_history_to_db'):
            saved_count = adapter.sync_sales_history_to_db(
                db=db,
                product_id=product.id,  # DB Product ID
                days_back=days_back,
                shop_id=999  # Demo Shop ID
            )
        else:
            # Fallback: Manuell synchronisieren
            sales_data = adapter.load_product_sales_history(
                product.shopify_product_id,
                days_back=days_back
            )
            service = SalesHistoryService(db)
            
            # Konvertiere zu Records-Format
            # WICHTIG: Datum wird bereits korrekt von load_product_sales_history() gefiltert
            # (relativ zu effective_now = max_date aus CSV)
            records = []
            for _, row in sales_data.iterrows():
                records.append({
                    'date': row['date'],
                    'quantity': int(row.get('quantity', row.get('quantity_sold', 0))),
                    'revenue': float(row.get('revenue', 0)),
                    'price': float(row.get('price', 0)),
                    'order_id': None,
                    'variant_id': None,
                    'meta_data': {'source': 'csv_demo'}
                })
            
            saved_count = service.bulk_save_sales(
                records,
                product_id=product.id,
                shop_id=999,  # Demo Shop ID
                aggregate_daily=True  # WICHTIG: CSV-Daten aggregieren (keine Order IDs)
            )
    else:
        # Live: Lade von Shopify API
        shop = db.query(Shop).filter(Shop.id == shop_context.active_shop_id).first()
        if not shop:
            raise HTTPException(status_code=404, detail="Shop nicht gefunden")
        
        access_token = decrypt_token(shop.access_token)
        
        shopify_adapter = ShopifyDataAdapter(
            shop_id=shop.id,
            shop_url=shop.shop_url,
            access_token=access_token,
            api_version=settings.SHOPIFY_API_VERSION
        )
        saved_count = shopify_adapter.sync_sales_history_to_db(
            db, 
            product.shopify_product_id, 
            days_back
        )
    
    return {
        "success": True,
        "product_id": product_id,
        "shop_id": shop_context.active_shop_id,
        "is_demo": shop_context.is_demo_mode,
        "saved_records": saved_count,
        "days_back": days_back
    }

