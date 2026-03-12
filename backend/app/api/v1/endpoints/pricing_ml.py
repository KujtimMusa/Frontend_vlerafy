"""
ML Pricing API Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import logging

from app.database import get_db
from app.models.product import Product
from app.services.ml_pricing_service import get_ml_pricing_service
from app.services.ml_monitoring_service import ml_monitoring

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class PricingRequest(BaseModel):
    """Request für ML Price Prediction"""
    product_id: Optional[int] = None
    product_data: Optional[Dict[str, Any]] = Field(None, description="Product data as dict (if product_id not available)")
    competitor_data: Optional[List[Dict[str, Any]]] = Field(None, description="Optional competitor data")
    confidence_threshold: float = Field(0.6, ge=0.0, le=1.0, description="Minimum confidence for ML prediction")


class PricingResponse(BaseModel):
    """Response für ML Price Prediction"""
    price: float = Field(..., description="Predicted optimal price")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence (0-1)")
    strategy: str = Field(..., description="Strategy used: ML_OPTIMIZED, FALLBACK_SAFE, or ERROR_FALLBACK")
    revenue_class: Optional[int] = Field(None, description="Predicted revenue class (0-3)")
    reason: Optional[str] = Field(None, description="Reason for strategy (e.g., low confidence)")
    model_versions: Optional[Dict[str, str]] = Field(None, description="Model versions used")
    error: Optional[str] = Field(None, description="Error message if strategy is ERROR_FALLBACK")


class ModelHealthResponse(BaseModel):
    """Response für Model Health Check"""
    status: str = Field(..., description="healthy or unhealthy")
    models: Optional[Dict[str, Any]] = Field(None, description="Model information")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/predict-price", response_model=PricingResponse)
async def predict_optimal_price(
    request: PricingRequest,
    db: Session = Depends(get_db)
):
    """
    ML-basierte Preis-Vorhersage
    
    Args:
        request: PricingRequest mit product_id oder product_data
        db: Database session
    
    Returns:
        PricingResponse mit predicted price, confidence, strategy
    """
    try:
        # Lade ML Service
        ml_service = get_ml_pricing_service(db=db)
        
        # Lade Product wenn product_id vorhanden
        product = None
        if request.product_id:
            product = db.query(Product).filter(Product.id == request.product_id).first()
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product with id {request.product_id} not found"
                )
        
        # ML Prediction
        result = ml_service.predict_optimal_price(
            product=product,
            product_data=request.product_data,
            competitor_data=request.competitor_data,
            confidence_threshold=request.confidence_threshold
        )
        
        # Log Prediction
        logger.info(
            f"Pricing prediction: product_id={request.product_id or 'N/A'}, "
            f"price={result['price']:.2f}, "
            f"confidence={result['confidence']:.2%}, "
            f"strategy={result['strategy']}"
        )
        
        return PricingResponse(**result)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pricing prediction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/model-health", response_model=ModelHealthResponse)
async def get_model_health():
    """
    Health-Check für ML Models
    
    Returns:
        ModelHealthResponse mit Status und Model-Informationen
    """
    try:
        ml_service = get_ml_pricing_service()
        model_info = ml_service.get_model_info()
        
        return ModelHealthResponse(
            status="healthy",
            models=model_info
        )
    
    except Exception as e:
        logger.error(f"Model health check failed: {e}", exc_info=True)
        return ModelHealthResponse(
            status="unhealthy",
            error=str(e)
        )


@router.get("/monitoring/stats")
async def get_monitoring_stats(hours: int = 24):
    """
    Hole Monitoring-Statistiken
    
    Args:
        hours: Zeitfenster in Stunden (default: 24)
    
    Returns:
        Dict mit Prediction-Statistiken
    """
    try:
        stats = ml_monitoring.get_prediction_statistics(hours=hours)
        return stats
    except Exception as e:
        logger.error(f"Failed to get monitoring stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/performance")
async def get_performance_metrics(hours: int = 24):
    """
    Hole Performance-Metriken
    
    Args:
        hours: Zeitfenster in Stunden (default: 24)
    
    Returns:
        Dict mit Performance-Metriken
    """
    try:
        metrics = ml_monitoring.get_performance_metrics(hours=hours)
        return metrics
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
