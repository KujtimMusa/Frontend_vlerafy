"""
API Endpoints für Competitor Price Tracking
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, HttpUrl
from datetime import datetime, timedelta
import logging

from app.database import get_db
from app.models.product import Product
from app.models.competitor import CompetitorPrice
from app.services.competitor_scraper import scrape_competitor_price, validate_url
from app.services.competitor_discovery import CompetitorDiscovery
from app.services.competitor_price_service import CompetitorPriceService
from app.core.shop_context import get_shop_context, ShopContext
from fastapi import Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/competitors", tags=["competitors"])


# Pydantic Models
class CompetitorCreate(BaseModel):
    competitor_name: str
    competitor_url: str  # HttpUrl validation happens in endpoint


class CompetitorResponse(BaseModel):
    id: int
    product_id: int
    competitor_name: str
    competitor_url: str
    price: Optional[float]
    in_stock: bool
    scrape_success: bool
    scraped_at: datetime
    last_error: Optional[str]
    
    class Config:
        from_attributes = True


class CompetitorAnalysis(BaseModel):
    has_data: bool
    current_price: float
    competitor_count: int
    competitor_avg: Optional[float]
    competitor_min: Optional[float]
    competitor_max: Optional[float]
    price_position: Optional[str]  # cheapest, below_average, average, above_average, most_expensive
    price_vs_avg_pct: Optional[float]
    competitors: List[CompetitorResponse]


def calculate_price_position(my_price: float, competitor_prices: List[float]) -> str:
    """
    Determine price position relative to competitors
    
    Args:
        my_price: Our product price
        competitor_prices: List of competitor prices
        
    Returns:
        Position string: cheapest, below_average, average, above_average, most_expensive
    """
    if not competitor_prices:
        return "unknown"
    
    avg = sum(competitor_prices) / len(competitor_prices)
    min_price = min(competitor_prices)
    max_price = max(competitor_prices)
    
    if my_price <= min_price:
        return "cheapest"
    elif my_price <= avg * 0.95:
        return "below_average"
    elif my_price <= avg * 1.05:
        return "average"
    elif my_price < max_price:
        return "above_average"
    else:
        return "most_expensive"


@router.post("/products/{product_id}/competitors", response_model=dict)
async def add_competitor(
    product_id: int,
    competitor: CompetitorCreate,
    db: Session = Depends(get_db)
):
    """
    Add competitor URL for a product.
    Immediately attempts first scrape.
    """
    
    # Validate product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Validate URL
    if not validate_url(competitor.competitor_url):
        raise HTTPException(status_code=400, detail="Invalid URL format")
    
    # Check if competitor URL already exists
    existing = db.query(CompetitorPrice).filter(
        CompetitorPrice.product_id == product_id,
        CompetitorPrice.competitor_url == competitor.competitor_url
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Competitor URL already exists for this product")
    
    # Attempt first scrape
    logger.info(f"Scraping competitor URL: {competitor.competitor_url}")
    scrape_result = scrape_competitor_price(competitor.competitor_url)
    
    # Save to database (even if scraping failed - for retry)
    new_competitor = CompetitorPrice(
        product_id=product_id,
        competitor_name=competitor.competitor_name,
        competitor_url=competitor.competitor_url,
        price=scrape_result.get('price'),
        scrape_success=scrape_result['success'],
        last_error=scrape_result.get('error'),
        scraped_at=scrape_result.get('scraped_at', datetime.utcnow()),
        in_stock=scrape_result.get('in_stock', False)
    )
    
    db.add(new_competitor)
    db.commit()
    db.refresh(new_competitor)
    
    logger.info(f"Competitor added: {new_competitor.id}, success: {scrape_result['success']}")
    
    return {
        "message": "Competitor added successfully",
        "competitor_id": new_competitor.id,
        "scrape_result": scrape_result
    }


@router.get("/products/{product_id}/competitors", response_model=List[CompetitorResponse])
async def list_competitors(
    product_id: int,
    db: Session = Depends(get_db)
):
    """Get all competitors for a product"""
    
    competitors = db.query(CompetitorPrice).filter(
        CompetitorPrice.product_id == product_id
    ).order_by(CompetitorPrice.scraped_at.desc()).all()
    
    return competitors


@router.delete("/competitors/{competitor_id}")
async def delete_competitor(
    competitor_id: int,
    db: Session = Depends(get_db)
):
    """Remove competitor tracking"""
    
    competitor = db.query(CompetitorPrice).filter(CompetitorPrice.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    db.delete(competitor)
    db.commit()
    
    logger.info(f"Competitor deleted: {competitor_id}")
    
    return {"message": "Competitor deleted"}


@router.get("/products/{product_id}/analysis", response_model=CompetitorAnalysis)
async def get_competitor_analysis(
    product_id: int,
    db: Session = Depends(get_db)
):
    """
    Get competitor price analysis for pricing engine.
    Only uses data from last 7 days.
    """
    
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get recent successful scrapes
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    competitors = db.query(CompetitorPrice).filter(
        CompetitorPrice.product_id == product_id,
        CompetitorPrice.scrape_success == True,
        CompetitorPrice.price.isnot(None),
        CompetitorPrice.scraped_at >= seven_days_ago
    ).all()
    
    if not competitors:
        return CompetitorAnalysis(
            has_data=False,
            current_price=product.price,
            competitor_count=0,
            competitors=[]
        )
    
    # Calculate statistics
    prices = [c.price for c in competitors if c.price is not None]
    
    if not prices:
        return CompetitorAnalysis(
            has_data=False,
            current_price=product.price,
            competitor_count=len(competitors),
            competitors=competitors
        )
    
    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)
    
    # Determine price position
    position = calculate_price_position(product.price, prices)
    
    # Price vs average percentage
    price_vs_avg_pct = ((product.price / avg_price) - 1) * 100
    
    return CompetitorAnalysis(
        has_data=True,
        current_price=product.price,
        competitor_count=len(competitors),
        competitor_avg=avg_price,
        competitor_min=min_price,
        competitor_max=max_price,
        price_position=position,
        price_vs_avg_pct=round(price_vs_avg_pct, 2),
        competitors=competitors
    )


@router.post("/competitors/{competitor_id}/rescrape")
async def rescrape_competitor(
    competitor_id: int,
    db: Session = Depends(get_db)
):
    """Manually trigger re-scrape for a competitor"""
    
    competitor = db.query(CompetitorPrice).filter(CompetitorPrice.id == competitor_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    # Scrape
    logger.info(f"Re-scraping competitor: {competitor.competitor_url}")
    result = scrape_competitor_price(competitor.competitor_url)
    
    # Update
    competitor.price = result.get('price')
    competitor.scrape_success = result['success']
    competitor.last_error = result.get('error')
    competitor.scraped_at = result.get('scraped_at', datetime.utcnow())
    competitor.in_stock = result.get('in_stock', False)
    
    db.commit()
    db.refresh(competitor)
    
    logger.info(f"Re-scrape completed: success={result['success']}, price={result.get('price')}")
    
    return {
        "message": "Re-scrape completed",
        "result": result
    }


@router.post("/products/{product_id}/auto-discover")
async def auto_discover_competitors(
    product_id: str,  # Kann String (demo_001) oder Int sein
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Automatische Wettbewerber-Erkennung für ein Produkt.
    Sucht automatisch nach Wettbewerbern und scraped deren Preise.
    Nutzt Shop-Context um zwischen Demo und echten Shops zu unterscheiden.
    """
    
    # ✅ NEU: Lade Produkt über Adapter (respektiert Shop-Context)
    adapter = shop_context.get_adapter()
    products = adapter.load_products()
    
    # Finde das richtige Produkt
    product = None
    for p in products:
        p_id = str(p.get('id', ''))
        p_shopify_id = str(p.get('shopify_product_id', ''))
        search_id = str(product_id)
        
        if p_id == search_id or p_shopify_id == search_id:
            product = p
            break
    
    if not product:
        logger.error(f"Product {product_id} not found in {'Demo Shop' if shop_context.is_demo_mode else 'Shopify'}")
        raise HTTPException(
            status_code=404, 
            detail=f"Product {product_id} not found in {'Demo Shop' if shop_context.is_demo_mode else 'Shopify'}"
        )
    
    logger.info(f"""
    {'='*70}
    🔍 AUTO-DISCOVER DEBUG
    {'='*70}
    Product ID (Request): {product_id}
    Shop Context:
      - Demo Mode: {shop_context.is_demo_mode}
      - Active Shop ID: {shop_context.active_shop_id}
    Adapter Type: {type(adapter).__name__}
    Product Found: {product.get('title')}
    {'='*70}
    """)
    
    # Starte automatische Erkennung
    discovery = CompetitorDiscovery()
    
    # Für Demo-Shop: Nutze String-ID, für Shopify: DB-ID
    # discover_and_scrape erwartet eine DB-ID, daher nutzen wir einen Fallback
    db_product_id = product_id
    if shop_context.is_demo_mode:
        # Demo-Produkte haben String-IDs, aber DB braucht Int
        # Für Demo-Shop: Nutze 999 als Fallback (wird nicht in DB gespeichert)
        db_product_id = 999
    
    result = discovery.discover_and_scrape(
        product_title=product.get('title', ''),
        product_id=db_product_id if isinstance(db_product_id, int) else 999,  # Fallback für Demo
        db=db
    )
    
    return {
        "message": "Automatische Wettbewerber-Erkennung abgeschlossen",
        "result": result,
        "shop_context": {
            "is_demo": shop_context.is_demo_mode,
            "shop_id": shop_context.active_shop_id
        }
    }


class CompetitorSearchResponse(BaseModel):
    product_id: str  # Kann String (demo_001) oder Int sein
    product_title: str
    competitors: List[dict]
    summary: dict
    your_price: float
    shop_context: Optional[dict] = None


@router.post("/products/{product_id}/competitor-search", response_model=CompetitorSearchResponse)
async def search_competitors(
    product_id: str,  # Kann String (demo_001) oder Int sein
    max_results: int = 5,
    force_refresh: bool = False,
    request: Request = None,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Sucht automatisch nach Wettbewerber-Preisen über Serper API.
    Multi-Tenant Safe: Demo-Shop (999) vs. Live-Shop (DB-Query).
    """
    
    logger.info(f"{'='*70}")
    logger.info(f"COMPETITOR SEARCH (Multi-Tenant)")
    logger.info(f"{'='*70}")
    logger.info(f"Product ID: {product_id}")
    logger.info(f"Shop Context: Demo={shop_context.is_demo_mode}, Shop ID={shop_context.active_shop_id}")
    logger.info(f"{'='*70}")
    
    # ============================================================
    # LIVE SHOP LOGIC - Nutze Datenbank mit shop_id Filter
    # ============================================================
    if not shop_context.is_demo_mode:
        logger.info("🔵 LIVE SHOP MODE - Loading product from database...")
        
        # Validiere Product ID Format (Integer für Live-Shops)
        try:
            product_id_int = int(product_id)
        except ValueError:
            logger.error(f"❌ Invalid product ID format: {product_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid product ID format: {product_id} (expected integer)"
            )
        
        # ===== KRITISCH: Multi-Tenant Isolation =====
        # Query mit shop_id Filter für Tenant-Isolation
        db_product = db.query(Product).filter(
            Product.id == product_id_int,
            Product.shop_id == shop_context.active_shop_id  # ← TENANT ISOLATION
        ).first()
        
        if not db_product:
            logger.error(f"❌ Product {product_id} not found in Shop {shop_context.active_shop_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Product {product_id} not found in your shop"
            )
        
        logger.info(f"✅ Product found:")
        logger.info(f"   - DB ID: {db_product.id}")
        logger.info(f"   - Shop ID: {db_product.shop_id} (Active: {shop_context.active_shop_id})")
        logger.info(f"   - Title: {db_product.title}")
        logger.info(f"   - Price: €{db_product.price}")
        
        # Double-Check Security (Defense in Depth)
        if db_product.shop_id != shop_context.active_shop_id:
            logger.error(f"🚨 SECURITY: Shop ID mismatch!")
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )
        
        # Competitor Search
        service = CompetitorPriceService()
        competitors_data = service.find_competitor_prices(
            product_title=db_product.title,
            max_results=max_results,
            use_cache=not force_refresh
        )
        
        your_price = float(db_product.price) if db_product.price else 0.0
        
        # No competitors found
        if not competitors_data:
            logger.warning(f"⚠️ No competitors found for: {db_product.title}")
            return CompetitorSearchResponse(
                product_id=str(db_product.id),
                product_title=db_product.title,
                competitors=[],
                summary={
                    "found": 0,
                    "avg_price": 0.0,
                    "min_price": 0.0,
                    "max_price": 0.0,
                    "your_position": "unknown"
                },
                your_price=your_price,
                shop_context={
                    "is_demo": False,
                    "shop_id": shop_context.active_shop_id
                }
            )
        
        # Calculate statistics
        prices = [c.get("price") for c in competitors_data if c.get("price")]
        
        if not prices:
            return CompetitorSearchResponse(
                product_id=str(db_product.id),
                product_title=db_product.title,
                competitors=competitors_data,
                summary={
                    "found": len(competitors_data),
                    "avg_price": 0.0,
                    "min_price": 0.0,
                    "max_price": 0.0,
                    "your_position": "unknown"
                },
                your_price=your_price,
                shop_context={
                    "is_demo": False,
                    "shop_id": shop_context.active_shop_id
                }
            )
        
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        position = calculate_price_position(your_price, prices)
        
        logger.info(f"✅ Analysis complete: {len(competitors_data)} competitors, Avg: €{avg_price:.2f}, Position: {position}")
        
        return CompetitorSearchResponse(
            product_id=str(db_product.id),
            product_title=db_product.title,
            competitors=competitors_data,
            summary={
                "found": len(competitors_data),
                "avg_price": round(avg_price, 2),
                "min_price": round(min_price, 2),
                "max_price": round(max_price, 2),
                "your_position": position
            },
            your_price=your_price,
            shop_context={
                "is_demo": False,
                "shop_id": shop_context.active_shop_id
            }
        )
    
    # ============================================================
    # DEMO MODE LOGIC - Nutze CSV Adapter (shop_id=999)
    # ============================================================
    else:
        logger.info("🟢 DEMO SHOP MODE - Loading product from CSV adapter...")
        
        adapter = shop_context.get_adapter()  # Returns CSVDemoShopAdapter
        products = adapter.load_products()
        
        # Suche Produkt (String-IDs wie "demo_1001")
        product = None
        for p in products:
            p_id = str(p.get('id', ''))
            p_shopify_id = str(p.get('shopify_product_id', ''))
            search_id = str(product_id)
            
            if p_id == search_id or p_shopify_id == search_id:
                product = p
                break
        
        if not product:
            logger.error(f"❌ Product {product_id} not found in Demo Shop")
            logger.error(f"Available IDs: {[str(p.get('id', '')) for p in products[:5]]}")
            raise HTTPException(
                status_code=404,
                detail=f"Product {product_id} not found in Demo Shop"
            )
        
        logger.info(f"✅ Demo product found: {product.get('title', '')}")
        
        # Competitor Search
        service = CompetitorPriceService()
        competitors_data = service.find_competitor_prices(
            product_title=product.get('title', ''),
            max_results=max_results,
            use_cache=not force_refresh
        )
        
        your_price = float(product.get('price', 0.0)) if product.get('price') else 0.0
        
        if not competitors_data:
            return CompetitorSearchResponse(
                product_id=str(product.get('id', product_id)),
                product_title=product.get('title', ''),
                competitors=[],
                summary={
                    "found": 0,
                    "avg_price": 0.0,
                    "min_price": 0.0,
                    "max_price": 0.0,
                    "your_position": "unknown"
                },
                your_price=your_price,
                shop_context={
                    "is_demo": True,
                    "shop_id": 999
                }
            )
        
        prices = [c.get("price") for c in competitors_data if c.get("price")]
        
        if not prices:
            return CompetitorSearchResponse(
                product_id=str(product.get('id', product_id)),
                product_title=product.get('title', ''),
                competitors=competitors_data,
                summary={
                    "found": len(competitors_data),
                    "avg_price": 0.0,
                    "min_price": 0.0,
                    "max_price": 0.0,
                    "your_position": "unknown"
                },
                your_price=your_price,
                shop_context={
                    "is_demo": True,
                    "shop_id": 999
                }
            )
        
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        position = calculate_price_position(your_price, prices)
        
        return CompetitorSearchResponse(
            product_id=str(product.get('id', product_id)),
            product_title=product.get('title', ''),
            competitors=competitors_data,
            summary={
                "found": len(competitors_data),
                "avg_price": round(avg_price, 2),
                "min_price": round(min_price, 2),
                "max_price": round(max_price, 2),
                "your_position": position
            },
            your_price=your_price,
            shop_context={
                "is_demo": True,
                "shop_id": 999
            }
        )

