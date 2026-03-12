"""
API Endpoints für Demo-Shop
Ermöglicht Testing mit CSV-Daten ohne echten Shopify-Shop
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
import logging

from app.database import get_db
from app.services.shop_adapter_factory import get_shop_adapter
from app.services.csv_demo_shop_adapter import CSVDemoShopAdapter
from app.services.pricing_engine import PricingEngine
from app.services.ml.ml_pricing_engine import MLPricingEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo-shop", tags=["demo-shop"])


@router.get("/products")
async def get_demo_products():
    """
    Gibt alle Demo-Produkte zurück.
    Nutzt CSV-Demo-Shop-Adapter.
    """
    try:
        adapter = CSVDemoShopAdapter()
        products = adapter.load_products()
        
        return {
            "success": True,
            "count": len(products),
            "products": products
        }
    except Exception as e:
        logger.error(f"Fehler beim Laden der Demo-Produkte: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/sales-history")
async def get_demo_sales_history(product_id: str, days_back: int = 90):
    """
    Gibt Sales-Historie für ein Demo-Produkt zurück.
    
    Args:
        product_id: Product ID (String, z.B. "1" oder "demo_1001")
        days_back: Anzahl Tage zurück (default 90)
    """
    try:
        adapter = CSVDemoShopAdapter()
        history = adapter.load_product_sales_history(product_id, days_back=days_back)
        
        # Convert DataFrame to list of dicts
        history_list = history.to_dict('records') if not history.empty else []
        
        return {
            "success": True,
            "product_id": product_id,
            "days_back": days_back,
            "count": len(history_list),
            "sales_history": history_list
        }
    except Exception as e:
        logger.error(f"Fehler beim Laden der Sales-Historie: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/metrics")
async def get_demo_metrics(product_id: str):
    """
    Berechnet Metriken für ein Demo-Produkt.
    
    Returns:
        {
            'sales_7d': int,
            'sales_30d': int,
            'avg_daily_sales': float,
            'days_of_stock': float,
            'demand_growth': float
        }
    """
    try:
        adapter = CSVDemoShopAdapter()
        metrics = adapter.calculate_metrics(product_id)
        
        # Convert numpy types to native Python types
        return {
            "success": True,
            "product_id": product_id,
            "metrics": {
                "sales_7d": int(metrics['sales_7d']),
                "sales_30d": int(metrics['sales_30d']),
                "avg_daily_sales": float(metrics['avg_daily_sales']),
                "days_of_stock": float(metrics['days_of_stock']),
                "demand_growth": float(metrics['demand_growth'])
            }
        }
    except Exception as e:
        logger.error(f"Fehler beim Berechnen der Metriken: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products/{product_id}/recommendation")
async def generate_demo_recommendation(product_id: str):
    """
    Generiert Preisempfehlung für ein Demo-Produkt.
    Nutzt Demo-Shop-Adapter mit Pricing Engine.
    """
    try:
        # Demo-Adapter
        adapter = CSVDemoShopAdapter()
        products = adapter.load_products()
        
        # Finde Produkt
        product_data = next((p for p in products if str(p.get('id')) == str(product_id) or p.get('shopify_product_id') == product_id), None)
        
        if not product_data:
            raise HTTPException(status_code=404, detail=f"Produkt {product_id} nicht gefunden")
        
        # Erstelle Product Model (Mock)
        from app.models.product import Product
        product = Product(
            id=product_data.get('id', 0),
            shopify_product_id=product_data['shopify_product_id'],
            title=product_data['title'],
            price=product_data['price'],
            cost=product_data.get('cost'),
            inventory_quantity=product_data['inventory_quantity']
        )
        
        # Lade Sales-Daten
        sales_data = adapter.load_product_sales_history(product_data['shopify_product_id'], days_back=90)
        
        # Pricing Engine mit Demo-Adapter
        engine = PricingEngine(adapter=adapter)
        recommendation = engine.calculate_price(product, sales_data=sales_data)
        
        return {
            "success": True,
            "product_id": product_id,
            "recommendation": recommendation
        }
        
    except Exception as e:
        logger.error(f"Fehler beim Generieren der Demo-Empfehlung: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))















