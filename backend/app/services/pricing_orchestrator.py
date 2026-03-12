"""
Pricing Orchestrator - Routes zwischen OLD und NEW ML Engine
basierend auf Feature Flags
"""

from typing import Dict, Any, Optional, List
import random
import logging
import hashlib
from app.config.settings import settings

logger = logging.getLogger(__name__)


class PricingOrchestrator:
    """
    Orchestrator: Entscheidet ob OLD oder NEW ML Engine verwendet wird
    
    Basierend auf:
    - USE_NEW_ML_ENGINE (Master Switch)
    - ML_ENGINE_ROLLOUT_PCT (Gradual Rollout 0-100%)
    """
    
    def __init__(self):
        # Lazy loading (erst bei Bedarf)
        self._old_engine = None
        self._new_service = None
        
        engine_version = "NEW_v1.2" if settings.USE_NEW_ML_ENGINE else "LEGACY"
        logger.info(f"[ORCHESTRATOR INIT] {engine_version} ({settings.ML_ENGINE_ROLLOUT_PCT}% rollout)")
    
    @property
    def old_engine(self):
        """Lazy load old MLPricingEngine"""
        if self._old_engine is None:
            try:
                from app.services.ml.ml_pricing_engine import MLPricingEngine
                from app.services.pricing_engine import PricingEngine
                from app.database import get_db
                
                # Create base engine
                db = next(get_db())
                base_engine = PricingEngine(db=db)
                
                # Create ML engine
                self._old_engine = MLPricingEngine(base_engine, models_dir="models/ml")
                logger.info("Loaded OLD MLPricingEngine")
            except Exception as e:
                logger.warning(f"Could not load OLD engine: {e}")
                self._old_engine = None
        return self._old_engine
    
    @property
    def new_service(self):
        """Lazy load new MLPricingService"""
        if self._new_service is None:
            print("[ORCHESTRATOR] Attempting to load NEW MLPricingService...", flush=True)
            logger.critical("[ORCHESTRATOR] Attempting to load NEW MLPricingService...")
            try:
                print("[ORCHESTRATOR] Importing get_ml_pricing_service...", flush=True)
                logger.critical("[ORCHESTRATOR] Importing get_ml_pricing_service...")
                from app.services.ml_pricing_service import get_ml_pricing_service
                from app.database import get_db
                
                print("[ORCHESTRATOR] Import successful, getting DB session...", flush=True)
                logger.critical("[ORCHESTRATOR] Import successful, getting DB session...")
                db = next(get_db())
                print(f"[ORCHESTRATOR] DB session obtained: {db is not None}", flush=True)
                logger.critical(f"[ORCHESTRATOR] DB session obtained: {db is not None}")
                
                print("[ORCHESTRATOR] Calling get_ml_pricing_service...", flush=True)
                logger.critical("[ORCHESTRATOR] Calling get_ml_pricing_service...")
                self._new_service = get_ml_pricing_service(db=db)
                print(f"[ORCHESTRATOR] NEW service loaded successfully: {self._new_service is not None}", flush=True)
                logger.critical(f"[ORCHESTRATOR] NEW service loaded successfully: {self._new_service is not None}")
                if self._new_service:
                    print(f"[ORCHESTRATOR] NEW service type: {type(self._new_service).__name__}", flush=True)
                    logger.critical(f"[ORCHESTRATOR] NEW service type: {type(self._new_service).__name__}")
                    print(f"[ORCHESTRATOR] NEW service has XGBoost: {hasattr(self._new_service, 'xgb_model')}", flush=True)
                    logger.critical(f"[ORCHESTRATOR] NEW service has XGBoost: {hasattr(self._new_service, 'xgb_model')}")
                    print(f"[ORCHESTRATOR] NEW service has Meta: {hasattr(self._new_service, 'meta_model')}", flush=True)
                    logger.critical(f"[ORCHESTRATOR] NEW service has Meta: {hasattr(self._new_service, 'meta_model')}")
                else:
                    print("[ORCHESTRATOR] WARNING: get_ml_pricing_service returned None!", flush=True)
                    logger.critical("[ORCHESTRATOR] WARNING: get_ml_pricing_service returned None!")
            except ImportError as e:
                print("=" * 80, flush=True)
                print(f"[ORCHESTRATOR] Import error loading NEW service: {e}", flush=True)
                logger.critical(f"[ORCHESTRATOR] Import error loading NEW service: {e}")
                import traceback
                print(f"[ORCHESTRATOR] Import traceback:\n{traceback.format_exc()}", flush=True)
                logger.critical(f"[ORCHESTRATOR] Import traceback:\n{traceback.format_exc()}")
                print("=" * 80, flush=True)
                self._new_service = None
            except Exception as e:
                print("=" * 80, flush=True)
                print(f"[ORCHESTRATOR] Exception loading NEW service: {type(e).__name__}: {str(e)}", flush=True)
                logger.critical(f"[ORCHESTRATOR] Exception loading NEW service: {type(e).__name__}: {str(e)}")
                import traceback
                print(f"[ORCHESTRATOR] Full traceback:\n{traceback.format_exc()}", flush=True)
                logger.critical(f"[ORCHESTRATOR] Full traceback:\n{traceback.format_exc()}")
                print("=" * 80, flush=True)
                self._new_service = None
        else:
            print(f"[ORCHESTRATOR] NEW service already loaded: {self._new_service is not None}", flush=True)
            logger.critical(f"[ORCHESTRATOR] NEW service already loaded: {self._new_service is not None}")
        return self._new_service
    
    async def get_price_recommendation(
        self,
        product_data: Dict[str, Any],
        product: Optional[Any] = None,  # Product model instance (for FeatureEngineeringService)
        competitor_data: Optional[List[Dict]] = None,  # Competitor data for feature extraction
        force_new: bool = False,
        force_old: bool = False
    ) -> Dict[str, Any]:
        """
        Get pricing recommendation from OLD or NEW engine
        
        Args:
            product_data: Product data dict (must contain 'id', 'current_price', etc.)
            product: Product model instance (optional, for FeatureEngineeringService)
            competitor_data: Competitor data list (optional, for feature extraction)
            force_new: Force use NEW engine (for testing)
            force_old: Force use OLD engine (for testing)
        
        Returns:
            Pricing recommendation dict (compatible with frontend)
        """
        
        product_id = product_data.get('id', 'unknown')
        
        # ═══════════════════════════════════════════════════════════════
        # DECISION LOGIC: OLD vs NEW
        # ═══════════════════════════════════════════════════════════════
        
        use_new_engine = False
        reason = ""
        
        # Force flags (for testing)
        if force_new:
            use_new_engine = True
            reason = "forced_new"
        elif force_old:
            use_new_engine = False
            reason = "forced_old"
        
        # Master switch OFF → Always use OLD
        elif not settings.USE_NEW_ML_ENGINE:
            use_new_engine = False
            reason = "feature_flag_off"
            logger.info(f"[ORCHESTRATOR] Product {product_id}: Master switch OFF")
        
        # Gradual rollout
        else:
            rollout_pct = settings.ML_ENGINE_ROLLOUT_PCT
            
            if rollout_pct >= 100:
                # 100% rollout → Always NEW
                use_new_engine = True
                reason = "rollout_100pct"
                print(f"[ORCHESTRATOR] Product {product_id}: 100% rollout -> NEW engine", flush=True)
                logger.critical(f"[ORCHESTRATOR] Product {product_id}: 100% rollout -> NEW engine")
            
            elif rollout_pct <= 0:
                # 0% rollout → Always OLD
                use_new_engine = False
                reason = "rollout_0pct"
                logger.info(f"[ORCHESTRATOR] Product {product_id}: 0% rollout -> OLD engine")
            
            else:
                # Gradual rollout (0-100%)
                # Random selection based on product_id (deterministic per product)
                # This ensures same product always gets same engine during rollout
                
                # Hash product_id to get consistent random value
                hash_value = int(hashlib.md5(str(product_id).encode()).hexdigest(), 16)
                random_value = (hash_value % 100) + 1  # 1-100
                
                use_new_engine = random_value <= rollout_pct
                reason = f"rollout_{rollout_pct}pct_{'selected' if use_new_engine else 'not_selected'}"
                logger.info(f"[ORCHESTRATOR] Product {product_id}: {rollout_pct}% rollout -> {'NEW' if use_new_engine else 'OLD'}")
        
        # ═══════════════════════════════════════════════════════════════
        # EXECUTE: Call OLD or NEW Engine
        # ═══════════════════════════════════════════════════════════════
        
        if use_new_engine:
            print(f"[ORCHESTRATOR] Product {product_id}: Using NEW engine ({reason})", flush=True)
            logger.critical(f"[ORCHESTRATOR] Product {product_id}: Using NEW engine ({reason})")
            
            try:
                print(f"[ORCHESTRATOR] Checking NEW service availability...", flush=True)
                logger.critical(f"[ORCHESTRATOR] Checking NEW service availability...")
                print(f"[ORCHESTRATOR] _new_service is None: {self._new_service is None}", flush=True)
                logger.critical(f"[ORCHESTRATOR] _new_service is None: {self._new_service is None}")
                
                print(f"[ORCHESTRATOR] About to access self.new_service property (will trigger lazy loading)...", flush=True)
                logger.critical(f"[ORCHESTRATOR] About to access self.new_service property (will trigger lazy loading)...")
                new_service_result = self.new_service
                print(f"[ORCHESTRATOR] self.new_service returned: {new_service_result is not None}", flush=True)
                logger.critical(f"[ORCHESTRATOR] self.new_service returned: {new_service_result is not None}")
                
                if new_service_result is None:
                    print(f"[ORCHESTRATOR] NEW service is None after lazy loading attempt", flush=True)
                    logger.critical(f"[ORCHESTRATOR] NEW service is None after lazy loading attempt")
                    raise Exception("NEW service failed to load - check logs above for details")
                
                print(f"[ORCHESTRATOR] NEW service available: {new_service_result is not None}", flush=True)
                logger.critical(f"[ORCHESTRATOR] NEW service available: {new_service_result is not None}")
                print(f"[ORCHESTRATOR] NEW service type: {type(new_service_result).__name__}", flush=True)
                logger.critical(f"[ORCHESTRATOR] NEW service type: {type(new_service_result).__name__}")
                print(f"[ORCHESTRATOR] Calling new_service.predict_optimal_price()...", flush=True)
                logger.critical(f"[ORCHESTRATOR] Calling new_service.predict_optimal_price()...")
                print(f"[ORCHESTRATOR] Product object available: {product is not None}", flush=True)
                logger.critical(f"[ORCHESTRATOR] Product object available: {product is not None}")
                print(f"[ORCHESTRATOR] Competitor data available: {competitor_data is not None and len(competitor_data) > 0 if competitor_data else False}", flush=True)
                logger.critical(f"[ORCHESTRATOR] Competitor data available: {competitor_data is not None and len(competitor_data) > 0 if competitor_data else False}")
                result = new_service_result.predict_optimal_price(
                    product=product,  # Pass product object for FeatureEngineeringService
                    product_data=product_data,
                    competitor_data=competitor_data,  # Pass competitor data for feature extraction
                    confidence_threshold=settings.ML_CONFIDENCE_THRESHOLD,
                    business_constraints={
                        'min_margin_pct': settings.ML_MIN_MARGIN_PCT,
                        'max_price_change_pct': settings.ML_MAX_PRICE_CHANGE_PCT,
                        'competitor_ceiling_pct': settings.ML_COMPETITOR_CEILING_PCT,
                        'psychological_pricing': settings.ML_PSYCHOLOGICAL_PRICING
                    }
                )
                
                # Add tracking field
                result['_ml_engine'] = 'NEW_v1.2'
                result['_routing_reason'] = reason
                
                logger.critical(f"[ORCHESTRATOR] NEW engine succeeded for {product_id}")
                return result
                
            except Exception as e:
                print("=" * 80, flush=True)
                print(f"[ORCHESTRATOR] NEW engine failed for {product_id}: {type(e).__name__}: {str(e)[:200]}", flush=True)
                logger.critical(f"[ORCHESTRATOR] NEW engine failed for {product_id}: {type(e).__name__}: {str(e)[:200]}")
                import traceback
                print(f"[ORCHESTRATOR] Full traceback:\n{traceback.format_exc()}", flush=True)
                logger.critical(f"[ORCHESTRATOR] Full traceback:\n{traceback.format_exc()}")
                print("=" * 80, flush=True)
                # Fallback to OLD on error
                use_new_engine = False
                reason = "new_engine_error_fallback"
                print(f"[ORCHESTRATOR] Falling back to OLD engine (reason: {reason})", flush=True)
                logger.critical(f"[ORCHESTRATOR] Falling back to OLD engine (reason: {reason})")
        
        if not use_new_engine:
            logger.critical(f"[ORCHESTRATOR] Product {product_id}: Using OLD engine ({reason})")
            
            try:
                if self.old_engine is None:
                    raise Exception("OLD engine not loaded")
                
                # Convert product_data to Product model if needed
                from app.models.product import Product
                
                # For OLD engine, we need Product model or proper format
                # This is a simplified version - adjust based on actual OLD engine interface
                product = None
                if 'id' in product_data:
                    # Try to get from DB or create mock
                    try:
                        from app.database import get_db
                        db = next(get_db())
                        product = db.query(Product).filter(Product.id == int(product_data['id'])).first()
                    except:
                        pass
                
                # Call OLD engine (adjust based on actual interface)
                # This is a placeholder - adjust to actual OLD engine method
                if product:
                    recommendation = self.old_engine.generate_ml_enhanced_recommendation(
                        product=product,
                        sales_data=None,
                        competitor_data=product_data.get('competitor_data')
                    )
                else:
                    # Fallback if product not found
                    raise Exception("Product not found for OLD engine")
                
                # Ensure compatible response structure
                if not isinstance(recommendation, dict):
                    recommendation = {'price': float(recommendation) if recommendation else 0.0}
                
                # Add tracking fields
                recommendation['_ml_engine'] = 'OLD_legacy'
                recommendation['_routing_reason'] = reason
                
                # Ensure required fields exist (backward compatibility)
                if 'confidence' not in recommendation:
                    recommendation['confidence'] = 0.5  # Default for old engine
                if 'strategy' not in recommendation:
                    recommendation['strategy'] = 'LEGACY'
                if 'price' not in recommendation and 'recommended_price' in recommendation:
                    recommendation['price'] = recommendation['recommended_price']
                
                return recommendation
                
            except Exception as e:
                logger.error(f"OLD ML Engine failed for {product_id}: {e}")
                
                # Ultimate fallback: Simple breakeven + margin
                breakeven = product_data.get('breakeven_price', 0.0)
                fallback_price = max(breakeven * 1.20, 1.0)
                
                return {
                    'price': fallback_price,
                    'confidence': 0.0,
                    'strategy': 'ULTIMATE_FALLBACK',
                    '_ml_engine': 'NONE_error',
                    '_routing_reason': 'both_engines_failed',
                    'error': str(e)
                }
    
    def get_engine_status(self) -> Dict[str, Any]:
        """
        Get current status of ML engines (for monitoring)
        
        Returns:
            Status dict with configuration and loaded engines
        """
        return {
            'feature_flags': {
                'USE_NEW_ML_ENGINE': settings.USE_NEW_ML_ENGINE,
                'ML_ENGINE_ROLLOUT_PCT': settings.ML_ENGINE_ROLLOUT_PCT,
                'ML_CONFIDENCE_THRESHOLD': settings.ML_CONFIDENCE_THRESHOLD
            },
            'business_constraints': {
                'min_margin_pct': settings.ML_MIN_MARGIN_PCT,
                'max_price_change_pct': settings.ML_MAX_PRICE_CHANGE_PCT,
                'competitor_ceiling_pct': settings.ML_COMPETITOR_CEILING_PCT,
                'psychological_pricing': settings.ML_PSYCHOLOGICAL_PRICING
            },
            'loaded_engines': {
                'old_engine_loaded': self._old_engine is not None,
                'new_service_loaded': self._new_service is not None
            },
            'expected_traffic_split': {
                'old_engine_pct': 100 - settings.ML_ENGINE_ROLLOUT_PCT if settings.USE_NEW_ML_ENGINE else 100,
                'new_engine_pct': settings.ML_ENGINE_ROLLOUT_PCT if settings.USE_NEW_ML_ENGINE else 0
            }
        }


# Singleton instance
pricing_orchestrator = PricingOrchestrator()
