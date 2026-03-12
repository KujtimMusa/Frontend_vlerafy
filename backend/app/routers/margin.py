"""
Margin Calculator API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from app.dependencies import get_current_shop_optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.core.shop_context import ShopContext, get_shop_context
from app.services.margin_calculator_service import MarginCalculatorService
from app.dependencies import get_current_shop_optional

router = APIRouter(prefix="/margin", tags=["margin"])


# ==========================================
# REQUEST/RESPONSE MODELS
# ==========================================

class ProductCostCreate(BaseModel):
    product_id: str = Field(..., description="Shopify Product ID")
    purchase_cost: float = Field(..., gt=0, description="Einkaufspreis netto in €")
    shipping_cost: float = Field(0.0, ge=0, description="Versandkosten pro Einheit")
    packaging_cost: float = Field(0.0, ge=0, description="Verpackungskosten pro Einheit")
    payment_provider: str = Field("stripe", description="stripe, paypal, klarna, custom")
    payment_fee_percentage: Optional[float] = Field(None, ge=0, le=100, description="Payment fee % (optional, uses provider default)")
    payment_fee_fixed: Optional[float] = Field(None, ge=0, description="Fixed payment fee in € (optional)")
    country_code: str = Field("DE", description="DE, AT, CH, US, GB, etc.")
    category: Optional[str] = Field(None, description="fashion, electronics, beauty, etc.")


class ProductCostUpdate(BaseModel):
    purchase_cost: Optional[float] = Field(None, gt=0)
    shipping_cost: Optional[float] = Field(None, ge=0)
    packaging_cost: Optional[float] = Field(None, ge=0)
    payment_provider: Optional[str] = None
    payment_fee_percentage: Optional[float] = Field(None, ge=0, le=100)
    payment_fee_fixed: Optional[float] = Field(None, ge=0)
    country_code: Optional[str] = None
    category: Optional[str] = None


class MarginCalculationRequest(BaseModel):
    selling_price: float = Field(..., gt=0)
    save_to_history: bool = True
    triggered_by: str = "manual"


class BulkMarginRequest(BaseModel):
    """Request for bulk margin calculation"""
    product_ids: List[str] = Field(..., min_items=1, max_items=100)


class MarginValidationRequest(BaseModel):
    product_id: str
    recommended_price: float = Field(..., gt=0)


# ==========================================
# ENDPOINTS
# ==========================================

@router.post("/costs")
async def save_product_costs(
    cost_data: ProductCostCreate,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Save or update cost data for a product
    """
    
    shop_id = shop_context.active_shop_id or "demo"
    
    service = MarginCalculatorService(db=db)
    
    try:
        cost_record = service.save_product_costs(
            product_id=cost_data.product_id,
            shop_id=shop_id,
            purchase_cost=cost_data.purchase_cost,
            shipping_cost=cost_data.shipping_cost,
            packaging_cost=cost_data.packaging_cost,
            payment_provider=cost_data.payment_provider,
            payment_fee_percentage=cost_data.payment_fee_percentage,
            payment_fee_fixed=cost_data.payment_fee_fixed,
            country_code=cost_data.country_code,
            category=cost_data.category
        )
        
        return {
            "success": True,
            "message": "Kostendaten gespeichert",
            "cost_id": cost_record.id,
            "product_id": cost_record.product_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/costs/{product_id}")
async def get_product_costs(
    product_id: str,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context),
    shop_id_auth: Optional[str] = Depends(get_current_shop_optional)
):
    """
    Get cost data for a product
    """
    
    # Use authenticated shop_id if available, otherwise fall back to shop_context
    shop_id = shop_id_auth or (shop_context.active_shop_id if shop_context else None) or "demo"
    
    service = MarginCalculatorService(db=db)
    cost_data = service.get_product_costs(product_id, shop_id)
    
    if not cost_data:
        raise HTTPException(status_code=404, detail="Keine Kostendaten gefunden")
    
    return {
        "product_id": cost_data.product_id,
        "purchase_cost": float(cost_data.purchase_cost),
        "shipping_cost": float(cost_data.shipping_cost),
        "packaging_cost": float(cost_data.packaging_cost),
        "payment_provider": cost_data.payment_provider,
        "payment_fee_percentage": float(cost_data.payment_fee_percentage),
        "payment_fee_fixed": float(cost_data.payment_fee_fixed),
        "vat_rate": float(cost_data.vat_rate * 100),  # as percentage
        "country_code": cost_data.country_code,
        "category": cost_data.category,
        "last_updated": cost_data.last_updated.isoformat() if cost_data.last_updated else None,
        "created_at": cost_data.created_at.isoformat() if cost_data.created_at else None
    }


@router.put("/costs/{product_id}")
async def update_product_costs(
    product_id: str,
    cost_update: ProductCostUpdate,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context),
    shop_id_auth: Optional[str] = Depends(get_current_shop_optional)
):
    """
    Update cost data for a product
    """
    
    # Use authenticated shop_id if available, otherwise fall back to shop_context
    shop_id = shop_id_auth or (shop_context.active_shop_id if shop_context else None) or "demo"
    
    service = MarginCalculatorService(db=db)
    
    # Get existing cost data
    existing = service.get_product_costs(product_id, shop_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Keine Kostendaten gefunden")
    
    # Update only provided fields
    update_data = cost_update.dict(exclude_unset=True)
    
    # Get current values
    purchase_cost = update_data.get('purchase_cost', float(existing.purchase_cost))
    shipping_cost = update_data.get('shipping_cost', float(existing.shipping_cost))
    packaging_cost = update_data.get('packaging_cost', float(existing.packaging_cost))
    payment_provider = update_data.get('payment_provider', existing.payment_provider)
    payment_fee_percentage = update_data.get('payment_fee_percentage')
    payment_fee_fixed = update_data.get('payment_fee_fixed')
    country_code = update_data.get('country_code', existing.country_code)
    category = update_data.get('category', existing.category)
    
    cost_record = service.save_product_costs(
        product_id=product_id,
        shop_id=shop_id,
        purchase_cost=purchase_cost,
        shipping_cost=shipping_cost,
        packaging_cost=packaging_cost,
        payment_provider=payment_provider,
        payment_fee_percentage=payment_fee_percentage,
        payment_fee_fixed=payment_fee_fixed,
        country_code=country_code,
        category=category
    )
    
    return {
        "success": True,
        "message": "Kostendaten aktualisiert",
        "cost_id": cost_record.id
    }


@router.post("/calculate/{product_id}")
async def calculate_margin(
    product_id: str,
    request: MarginCalculationRequest,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context),
    shop_id_auth: Optional[str] = Depends(get_current_shop_optional)
):
    """
    Calculate margin for a product at a given selling price
    """
    
    # Use authenticated shop_id if available, otherwise fall back to shop_context
    shop_id = shop_id_auth or (shop_context.active_shop_id if shop_context else None) or "demo"
    
    service = MarginCalculatorService(db=db)
    
    result = service.calculate_margin(
        product_id=product_id,
        shop_id=shop_id,
        selling_price=request.selling_price,
        save_to_history=request.save_to_history,
        triggered_by=request.triggered_by
    )
    
    if not result.get('has_cost_data'):
        raise HTTPException(status_code=400, detail=result.get('message', 'Keine Kostendaten'))
    
    return result


@router.post("/validate")
async def validate_price_recommendation(
    request: MarginValidationRequest,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Validate if a recommended price is profitable
    Returns safety status and warnings
    """
    
    shop_id = shop_context.active_shop_id or "demo"
    
    service = MarginCalculatorService(db=db)
    
    result = service.validate_price_recommendation(
        product_id=request.product_id,
        shop_id=shop_id,
        recommended_price=request.recommended_price
    )
    
    return result


@router.get("/history/{product_id}")
async def get_margin_history(
    product_id: str,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context),
    shop_id_auth: Optional[str] = Depends(get_current_shop_optional)
):
    """
    Get margin history for a product
    """
    
    # Use authenticated shop_id if available, otherwise fall back to shop_context
    shop_id = shop_id_auth or (shop_context.active_shop_id if shop_context else None) or "demo"
    
    service = MarginCalculatorService(db=db)
    
    history = service.get_margin_history(
        product_id=product_id,
        shop_id=shop_id,
        days=days
    )
    
    return {
        "product_id": product_id,
        "days": days,
        "history": history
    }


@router.get("/category-defaults/{category}")
async def get_category_defaults(category: str):
    """
    Get default cost values for a product category
    """
    
    service = MarginCalculatorService()
    
    defaults = service.get_category_defaults(category)
    
    return defaults


@router.post("/estimate-costs")
async def estimate_costs_from_price(
    selling_price: float = Query(..., gt=0),
    category: str = Query(..., description="fashion, electronics, beauty, etc."),
    country_code: str = Query("DE", description="DE, AT, CH, US, GB")
):
    """
    Estimate costs from selling price and category
    Useful for quick onboarding
    """
    
    service = MarginCalculatorService()
    
    estimate = service.estimate_costs_from_price(
        selling_price=selling_price,
        category=category,
        country_code=country_code
    )
    
    return estimate


@router.get("/has-costs/{product_id}")
async def check_has_cost_data(
    product_id: str,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Check if product has cost data
    """
    
    shop_id = shop_context.active_shop_id or "demo"
    
    service = MarginCalculatorService(db=db)
    
    has_costs = service.has_cost_data(product_id, shop_id)
    
    return {
        "product_id": product_id,
        "has_cost_data": has_costs
    }

