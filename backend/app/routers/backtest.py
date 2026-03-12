from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.shop import Shop
from app.models.product import Product
from app.utils.encryption import decrypt_token
from app.services.shopify_adapter import ShopifyDataAdapter
from app.services.backtest import AdvancedBacktester
from app.config import settings
import logging

router = APIRouter(prefix="/backtest", tags=["backtest"])
logger = logging.getLogger(__name__)


@router.post("/extended/{product_id}")
async def run_extended_backtest(
    product_id: int,
    strategy: str = "dynamic_seasonal",
    days_back: int = 730,
    db: Session = Depends(get_db)
):
    """Backtesting mit erweiterten historischen Daten (read_all_orders)"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    
    shop = db.query(Shop).filter(Shop.id == product.shop_id).first()
    if not shop or not shop.is_active:
        raise HTTPException(status_code=400, detail="Shop nicht aktiv")
    
    try:
        access_token = decrypt_token(shop.access_token)
        adapter = ShopifyDataAdapter(
            shop_id=shop.id,
            shop_url=shop.shop_url,
            access_token=access_token,
            api_version=settings.SHOPIFY_API_VERSION
        )
        
        logger.info(f"Lade {days_back} Tage Historie für Produkt {product.shopify_product_id}")
        sales_data = adapter.load_product_sales_history_extended(
            product.shopify_product_id,
            days_back=days_back
        )
        
        if len(sales_data) < 180:
            raise HTTPException(
                status_code=400,
                detail=f"Zu wenig Daten: {len(sales_data)} Tage (min 180)"
            )
        
        backtester = AdvancedBacktester()
        results = backtester.analyze_extended(
            product.shopify_product_id,
            sales_data,
            strategy
        )
        
        return {
            "success": True,
            "data": results,
            "message": f"Backtest mit {len(sales_data)} Tagen historischen Daten"
        }
    
    except Exception as e:
        logger.error(f"Fehler beim Backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shop-stats/{shop_id}")
async def get_shop_statistics(shop_id: int, days_back: int = 365, db: Session = Depends(get_db)):
    """Shop-weite Statistiken mit read_all_orders"""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop or not shop.is_active:
        raise HTTPException(status_code=400, detail="Shop nicht aktiv")
    
    try:
        access_token = decrypt_token(shop.access_token)
        adapter = ShopifyDataAdapter(
            shop_id=shop.id,
            shop_url=shop.shop_url,
            access_token=access_token,
            api_version=settings.SHOPIFY_API_VERSION
        )
        
        stats = adapter.get_shop_sales_stats(days_back)
        return {"success": True, "data": stats}
    
    except Exception as e:
        logger.error(f"Fehler bei Shop-Stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

