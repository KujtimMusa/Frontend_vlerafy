"""
Factory für Shop-Adapter
Ermöglicht einfachen Wechsel zwischen Demo-Shop (CSV) und echtem Shopify-Shop
"""
from typing import Union, Optional
import logging

from app.services.csv_demo_shop_adapter import CSVDemoShopAdapter
from app.services.shopify_adapter import ShopifyDataAdapter

logger = logging.getLogger(__name__)


def get_shop_adapter(
    shop_id: Optional[int] = None,
    shop_url: Optional[str] = None,
    access_token: Optional[str] = None,
    api_version: str = "2025-10",
    use_demo: bool = False,
    db: Optional[object] = None
) -> Union[CSVDemoShopAdapter, ShopifyDataAdapter]:
    """
    Factory: Gibt entweder Demo-Shop oder echten Shopify-Shop zurück.
    
    Args:
        shop_id: Shop ID (WICHTIG für echten Shop!)
        shop_url: Shopify Shop URL (nur für echten Shop)
        access_token: Shopify Access Token (nur für echten Shop)
        api_version: Shopify API Version (nur für echten Shop)
        use_demo: Wenn True, nutze CSV-Demo-Shop
        db: Optional DB Session (wird nicht verwendet, aber für Kompatibilität)
    
    Returns:
        CSVDemoShopAdapter oder ShopifyDataAdapter (beide haben identische API)
    
    Usage:
        # Development/Testing mit Demo-Daten
        adapter = get_shop_adapter(use_demo=True)
        products = adapter.load_products()
        
        # Production mit echtem Shopify-Shop
        adapter = get_shop_adapter(
            shop_id=1,
            shop_url="my-shop.myshopify.com",
            access_token="shpat_xxx",
            use_demo=False
        )
        products = adapter.load_products()
    
    Beide Adapter haben identische API → kein Code-Change in Pricing Engine nötig!
    """
    if use_demo or shop_id == 999:
        # Demo-Shop: CSV-Adapter (kein DB-Zugriff)
        logger.info("Nutze Demo-Shop-Adapter (CSV)")
        return CSVDemoShopAdapter()
    else:
        if not shop_url or not access_token:
            raise ValueError("shop_url und access_token müssen für echten Shopify-Shop angegeben werden")
        
        if not shop_id:
            raise ValueError("shop_id muss für echten Shopify-Shop angegeben werden")
        
        logger.info(f"Nutze Shopify-Adapter für {shop_url} (Shop ID: {shop_id})")
        return ShopifyDataAdapter(
            shop_id=shop_id,
            shop_url=shop_url,
            access_token=access_token,
            api_version=api_version
        )













