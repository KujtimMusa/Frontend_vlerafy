from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import json
from app.database import get_db
from app.models.product import Product
from app.models.shop import Shop
from app.models.recommendation import Recommendation
from app.services.pricing_engine import PricingEngine
from app.services.ml.ml_pricing_engine import MLPricingEngine
from app.services.competitive_strategy import EnhancedCompetitiveStrategy
from app.routers.competitors import get_competitor_analysis
from app.core.shop_context import get_shop_context, ShopContext
from app.services.pricing_orchestrator import pricing_orchestrator
from fastapi import Request
from app.config import settings
from app.middleware.rate_limiter import limiter
import logging
import pandas as pd

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
logger = logging.getLogger(__name__)


# ==================== TEMPORARY: FEATURE AVAILABILITY ANALYSIS ====================

def analyze_feature_availability(product_id: int, db: Session, shop_context: ShopContext, competitor_data: Optional[List[Dict]] = None) -> Dict:
    """
    Analyze which features are actually available for this product.
    Run this for both Demo Shop and Live Shop products.
    
    TEMPORARY: For confidence system design analysis
    """
    logger.debug(f"[FEATURE ANALYSIS] Product {product_id}")
    logger.debug("="*70)
    
    # Get product
    if shop_context.is_demo_mode:
        adapter = shop_context.get_adapter()
        demo_products = adapter.load_products()
        product_data = next(
            (p for p in demo_products if p.get('id') == product_id or str(p.get('id')) == str(product_id)),
            None
        )
        if not product_data:
            logger.warning("Product not found")
            return {}
        
        # Create Product model for feature extraction
        product = Product(
            id=product_data.get('id', product_id),
            shopify_product_id=product_data.get('shopify_product_id', f'demo_{product_id}'),
            title=product_data.get('title', f'Product {product_id}'),
            price=product_data.get('price', 0),
            cost=product_data.get('cost'),
            inventory_quantity=product_data.get('inventory_quantity', 0),
            shop_id=999
        )
    else:
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.shop_id == shop_context.active_shop_id
        ).first()
        if not product:
            logger.warning("Product not found")
            return {}
    
    # Extract ALL features
    from app.services.feature_engineering_service import FeatureEngineeringService
    from app.services.confidence_analyzer import FeatureConfidenceAnalyzer
    
    fe_service = FeatureEngineeringService(db, shop_id=shop_context.active_shop_id)
    
    # 🔍 DEBUG: Log competitor data availability
    logger.debug(f"[FEATURE ANALYSIS] Competitor data provided: {len(competitor_data) if competitor_data else 0} competitors")
    if competitor_data:
        logger.debug(f"[FEATURE ANALYSIS] Competitor prices: {[c.get('price', 0) for c in competitor_data[:3]]}")
    else:
        logger.warning("[FEATURE ANALYSIS] NO competitor data - competitive features will be 0!")
    
    features = fe_service.extract_all_features(product, competitor_data=competitor_data)
    
    # Analyze confidence with detailed breakdown
    analyzer = FeatureConfidenceAnalyzer()
    confidence_data = analyzer.analyze_confidence(features, include_explanations=True)
    
    # Analyze each feature group
    feature_groups = {
        'sales': [k for k in features.keys() if 'sales' in k.lower() or 'demand' in k.lower() or 'revenue' in k.lower()],
        'inventory': [k for k in features.keys() if 'stock' in k.lower() or 'inventory' in k.lower()],
        'price': [k for k in features.keys() if 'price' in k.lower() and 'competitor' not in k.lower()],
        'competitor': [k for k in features.keys() if 'competitor' in k.lower()],
        'cost': [k for k in features.keys() if 'cost' in k.lower() or 'margin' in k.lower()],
        'seasonal': [k for k in features.keys() if 'seasonal' in k.lower() or 'month' in k.lower() or 'quarter' in k.lower() or 'weekend' in k.lower() or 'day_of_week' in k.lower()],
        'advanced': [k for k in features.keys() if 'elasticity' in k.lower() or 'trend' in k.lower() or 'lifecycle' in k.lower() or 'growth_rate' in k.lower()]
    }
    
    total_features = 0
    available_features = 0
    
    logger.debug("[FEATURE AVAILABILITY BREAKDOWN]")
    logger.debug("-"*70)
    
    group_stats = {}
    
    for group_name, feature_list in feature_groups.items():
        group_total = len(feature_list)
        group_available = sum(1 for f in feature_list if features.get(f) is not None and features.get(f) != 0)
        group_percentage = (group_available / group_total * 100) if group_total > 0 else 0
        
        total_features += group_total
        available_features += group_available
        
        logger.debug(f"{group_name.upper()}: {group_available}/{group_total} ({group_percentage:.1f}%)")
        
        # Show which features are available
        for feat in feature_list[:10]:  # Show first 10 to avoid spam
            value = features.get(feat)
            status = "✅" if (value is not None and value != 0) else "❌"
            logger.debug(f"  {feat}: {value}")
        if len(feature_list) > 10:
            logger.debug(f"  ... and {len(feature_list) - 10} more features")
        
        group_stats[group_name] = {
            'total': group_total,
            'available': group_available,
            'percentage': group_percentage
        }
    
    # Log detailed confidence breakdown
    logger.debug(f"[CONFIDENCE] Product {product_id}")
    logger.debug(f"Overall: {confidence_data['overall_confidence']:.1f}%")
    logger.debug(f"Available: {confidence_data['available_features']}/{confidence_data['total_features']} features")
    
    for category, data in confidence_data['categories'].items():
        status_emoji = {
            'excellent': '✅',
            'good': '✅',
            'ok': '⚠️',
            'low': '❌'
        }.get(data['status'], '⚠️')
        
        logger.debug(f"{category}: {data['percentage']:.1f}% ({data['available']}/{data['total']})")
        
        if data['missing_critical']:
            logger.warning(f"Critical missing: {', '.join(data['missing_critical'][:3])}")
        if data['not_implemented']:
            logger.debug(f"   Not implemented: {', '.join(data['not_implemented'][:2])}")
    
    if confidence_data['warnings']:
        logger.warning("Warnings:")
        for warning in confidence_data['warnings'][:3]:
            logger.debug(f"   - {warning}")
    
    logger.debug("="*70)
    
    return confidence_data


@router.get("/product/{product_id}")
async def get_recommendations(
    product_id: int,
    limit: int = Query(1, ge=1, le=10),  # Default: Nur neueste
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Lädt Preisempfehlungen für ein Produkt im aktiven Shop.
    Default: Nur die neueste Empfehlung (limit=1).
    """
    try:
        # ✅ CRITICAL: Load latest context from Redis/Memory
        shop_context.load()
        
        logger.info(
            f"[RECOMMENDATIONS] Session {shop_context.session_id}: "
            f"shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}"
        )
        
        # Hole Adapter aus Shop-Context
        adapter = shop_context.get_adapter()
        
        # Prüfe ob Produkt im aktiven Shop existiert
        if shop_context.is_demo_mode:
            # Demo-Shop: Prüfe in CSV-Adapter
            demo_products = adapter.load_products()
            product_data = next(
                (p for p in demo_products if p.get('id') == product_id or str(p.get('id')) == str(product_id)),
                None
            )
            if not product_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Produkt {product_id} nicht gefunden im Demo-Shop"
                )
            product_name = product_data.get('title', f'Product {product_id}')
            current_price = product_data.get('price', 0)
        else:
            # Live-Shop: Prüfe in DB
            product = db.query(Product).filter(
                Product.id == product_id,
                Product.shop_id == shop_context.active_shop_id
            ).first()
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Produkt {product_id} nicht gefunden im Shop {shop_context.active_shop_id}"
                )
            product_name = product.title
            current_price = product.price
        
        # Lade Recommendations mit Shop-Filter
        recommendations = db.query(Recommendation).filter(
            Recommendation.product_id == product_id,
            Recommendation.shop_id == shop_context.active_shop_id,
            Recommendation.is_demo == shop_context.is_demo_mode
        ).order_by(Recommendation.created_at.desc()).limit(limit).all()
        
        if not recommendations:
            return {
                "product_id": product_id,
                "product_name": product_name,
                "current_price": current_price,
                "recommendations": [],
                "message": "No recommendations yet. Generate one first.",
                "shop_context": {
                    "shop_id": shop_context.active_shop_id,
                    "is_demo": shop_context.is_demo_mode
                }
            }
        
        # Formatiere Recommendations
        formatted_recs = []
        for r in recommendations:
            # Parse reasoning falls vorhanden
            reasoning_text = ""
            if r.reasoning:
                try:
                    reasoning_dict = json.loads(r.reasoning) if isinstance(r.reasoning, str) else r.reasoning
                    if isinstance(reasoning_dict, dict):
                        reasoning_text = reasoning_dict.get('summary', str(reasoning_dict))
                    else:
                        reasoning_text = str(reasoning_dict)
                except:
                    reasoning_text = str(r.reasoning)
            
            formatted_recs.append({
                "id": r.id,
                "product_id": r.product_id,
                "product_name": product_name,
                "current_price": r.current_price or current_price,
                "recommended_price": r.recommended_price,
                "price_change_pct": r.price_change_pct or (
                    ((r.recommended_price - (r.current_price or current_price)) / (r.current_price or current_price) * 100)
                    if (r.current_price or current_price) > 0 else 0
                ),
                "strategy": r.strategy,
                "confidence": r.confidence,
                "reasoning": reasoning_text,
                "demand_growth": r.demand_growth,
                "days_of_stock": r.days_of_stock,
                "sales_7d": r.sales_7d,
                "competitor_avg_price": r.competitor_avg_price,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "applied_at": r.applied_at.isoformat() if r.applied_at else None
            })
        
        return {
            "product_id": product_id,
            "product_name": product_name,
            "current_price": current_price,
            "recommendations": formatted_recs,
            "shop_context": {
                "shop_id": shop_context.active_shop_id,
                "is_demo": shop_context.is_demo_mode
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fehler beim Laden der Recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/{product_id}")
@limiter.limit("100/minute")  # Max 100 recommendations per minute per IP/shop
async def generate_recommendation(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context),
    force_new: bool = Query(False, description="Force use NEW ML engine (for testing)"),
    force_old: bool = Query(False, description="Force use OLD ML engine (for testing)")
):
    """
    Generiert eine neue Preisempfehlung.
    Nutzt IMMER den aktiven Shop aus dem Shop-Context (Demo oder Live).
    """
    # CRITICAL: Print immediately to ensure visibility
    print("=" * 80, flush=True)
    print(f"[ENDPOINT] ========== POST /generate/{product_id} CALLED ==========", flush=True)
    print("=" * 80, flush=True)
    
    try:
        import traceback
        logger.critical(f"[ENDPOINT] ========== POST /generate/{product_id} CALLED ==========")
        logger.info(f"[ENDPOINT] Starting recommendation generation for product {product_id}")
        
        # ✅ CRITICAL: Load latest context from Redis/Memory
        shop_context.load()
        
        logger.info(
            f"[GENERATE RECOMMENDATION] Session {shop_context.session_id}: "
            f"shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}"
        )
        
        # 1. Hole Adapter aus Shop-Context (Demo oder Live)
        try:
            adapter = shop_context.get_adapter()
            logger.info(f"Generiere Recommendation für Produkt {product_id} in Shop {shop_context.active_shop_id} (Demo: {shop_context.is_demo_mode})")
        except Exception as adapter_error:
            # Fallback: Wenn Adapter nicht geladen werden kann (z.B. Encryption Key Mismatch)
            logger.error(
                f"ERROR: Cannot get adapter for Shop {shop_context.active_shop_id}\n"
                f"   Error: {type(adapter_error).__name__}: {str(adapter_error)}\n"
                f"   Fallback: Using Demo Mode"
            )
            # Force Demo Mode
            shop_context.is_demo_mode = True
            from app.services.shop_adapter_factory import get_shop_adapter
            adapter = get_shop_adapter(use_demo=True)
            logger.info(f"Using Demo Mode as fallback for Product {product_id}")
        
        # 2. Lade Produkt-Daten aus aktivem Shop
        product_data = None
        product = None
        
        if shop_context.is_demo_mode:
            # Demo-Shop: Lade aus CSV-Adapter
            demo_products = adapter.load_products()
            product_data = next(
                (p for p in demo_products if p.get('id') == product_id or str(p.get('id')) == str(product_id)),
                None
            )
            if not product_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Produkt {product_id} nicht gefunden im Demo-Shop"
                )
            
            # Erstelle Product Model für Pricing Engine
            product = Product(
                id=product_data.get('id', product_id),
                shopify_product_id=product_data.get('shopify_product_id', f'demo_{product_id}'),
                title=product_data.get('title', f'Product {product_id}'),
                price=product_data.get('price', 0),
                cost=product_data.get('cost'),
                inventory_quantity=product_data.get('inventory_quantity', 0),
                shop_id=999  # Demo Shop ID
            )
            product_id_str = str(product_data.get('shopify_product_id', f'demo_{product_id}'))
        else:
            # Live-Shop: Lade aus DB
            product = db.query(Product).filter(
                Product.id == product_id,
                Product.shop_id == shop_context.active_shop_id
            ).first()
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Produkt {product_id} nicht gefunden im Shop {shop_context.active_shop_id}"
                )
            product_id_str = product.shopify_product_id
        
        # 3. Lade Sales-Daten aus aktivem Shop
        sales_data = None
        try:
            sales_data = adapter.load_product_sales_history(product_id_str, days_back=60)
            logger.info(f"Sales-Daten geladen: {len(sales_data)} Einträge für Produkt {product_id_str}")
        except Exception as e:
            logger.warning(f"Konnte Sales-Daten nicht laden: {e}")
            sales_data = pd.DataFrame()
        
        # 4. Berechne Metriken für DB-Speicherung
        demand_growth = None
        days_of_stock = None
        sales_7d = None
        sales_30d = None  # WICHTIG: Initialisierung für Dashboard
        
        if not sales_data.empty and len(sales_data) > 0:
            try:
                sales_data["date"] = pd.to_datetime(sales_data["date"])
                end_date = datetime.now()
                start_7d = end_date - timedelta(days=7)
                start_30d = end_date - timedelta(days=30)
                
                sales_7d = int(sales_data[sales_data["date"] >= start_7d]["quantity"].sum())
                sales_30d = sales_data[sales_data["date"] >= start_30d]["quantity"].sum()
                sales_30d_avg_7d = (sales_30d / 30) * 7 if sales_30d > 0 else 0
                
                if sales_30d_avg_7d > 0:
                    demand_growth = (sales_7d - sales_30d_avg_7d) / sales_30d_avg_7d
                
                # Days of Stock
                if product.inventory_quantity and product.inventory_quantity > 0:
                    avg_daily_sales = sales_30d / 30 if sales_30d > 0 else 0
                    if avg_daily_sales > 0:
                        days_of_stock = product.inventory_quantity / avg_daily_sales
            except Exception as e:
                logger.warning(f"Fehler bei Metriken-Berechnung: {e}")
        
        # 5. Lade Competitor Analysis (falls verfügbar)
        competitor_analysis = None
        competitor_avg_price = None
        try:
            competitor_analysis = await get_competitor_analysis(product_id, db)
            if competitor_analysis and competitor_analysis.has_data:
                competitor_avg_price = competitor_analysis.competitor_avg
                logger.info(f"Competitor-Daten geladen: {competitor_analysis.competitor_count} Wettbewerber")
        except Exception as e:
            logger.warning(f"Konnte Competitor-Daten nicht laden: {e}")
        
        # 6. Erstelle Pricing Engine mit korrektem Adapter
        shop = None if shop_context.is_demo_mode else db.query(Shop).filter(Shop.id == shop_context.active_shop_id).first()
        # CRITICAL: Pass DB session to PricingEngine for feature extraction
        base_engine = PricingEngine(shop=shop, adapter=adapter, db=db)
        logger.info(f"✅ Created PricingEngine with DB session: {db is not None}")
        logger.debug(f"Created PricingEngine with DB session: {db is not None}")
        
        # 7. Competitive Strategy (mit echten Competitor-Daten von Serper API)
        logger.critical("[ROUTING] ========== BEFORE COMPETITOR FETCH ==========")
        competitive_rec = None
        competitor_prices = []
        competitor_avg_price = None
        
        # Lade Competitor-Daten über CompetitorPriceService (HYBRID: Live-API + optional DB-Save)
        try:
            from app.services.competitor_price_service import CompetitorPriceService
            
            # Hybrid-Architektur: Live-API mit optionaler DB-Speicherung für ML-Training
            # save_to_db=True speichert API-Results in DB (für historische Analyse)
            competitor_service = CompetitorPriceService(
                db_session=db,
                save_to_db=True,  # Optional: Speichere in DB für ML-Training
                product_id=product.id
            )
            
            logger.info(f"\n🔍 COMPETITOR-SUCHE (Hybrid: Live-API → Optional DB)")
            logger.info(f"   Suchbegriff: '{product.title}'")
            
            logger.info(f"🔍 DEBUG - Before Competitor API Call for '{product.title}'")
            competitor_prices = competitor_service.find_competitor_prices(
                product_title=product.title,
                max_results=5,
                use_cache=True  # WICHTIG: Cache aktiviert (TTL: 5 Min) für deterministische Ergebnisse
            )
            logger.info(f"DEBUG - Competitor API returned {len(competitor_prices)} prices: {[c.get('price') for c in competitor_prices[:3]]}")
            
            # 🔍 DEBUG: Add detailed competitor logging
            logger.debug("[COMPETITOR] API Call Result:")
            logger.debug(f"   - API Key exists: {bool(competitor_service.api_key)}")
            logger.debug(f"   - Competitors found: {len(competitor_prices)}")
            if competitor_prices:
                logger.debug(f"   - Prices: {[c.get('price', 0) for c in competitor_prices]}")
            else:
                logger.warning("NO competitors found - check API response above")
            
            if competitor_prices:
                logger.info(f"   ✅ {len(competitor_prices)} Wettbewerber gefunden:")
                for c in competitor_prices[:3]:
                    logger.info(f"      -  {c['source']}: €{c['price']:.2f}")
                if len(competitor_prices) > 3:
                    logger.info(f"      -  ... und {len(competitor_prices)-3} weitere")
            else:
                logger.warning(f"   ⚠️ Keine Wettbewerber-Preise gefunden")
        
        except Exception as e:
            logger.error(f"   ❌ Fehler beim Laden der Competitor-Daten: {e}")
            competitor_prices = []
        
        print("[ROUTING] ========== AFTER COMPETITOR FETCH ==========", flush=True)
        logger.critical("[ROUTING] ========== AFTER COMPETITOR FETCH ==========")
        
        # Nutze Competitive Strategy mit echten Daten (wenn verfügbar)
        # WICHTIG: Diese wird jetzt direkt in Pricing Engine integriert
        if competitor_prices:
            competitive_strategy = EnhancedCompetitiveStrategy()
            product_dict = {
                'id': product.id,
                'title': product.title,
                'price': product.price,
                'cost': product.cost,
                'inventory': product.inventory_quantity
            }
            competitive_rec = competitive_strategy.calculate(
                product=product_dict,
                competitor_prices=competitor_prices  # ← ECHTE DATEN von Serper API
            )
            logger.info(f"Competitive Strategy: €{competitive_rec['recommended_price']:.2f} (Confidence: {competitive_rec['confidence']:.2f})")
            
            # Speichere Competitor-Durchschnittspreis
            competitor_avg_price = competitive_rec.get('competitor_context', {}).get('avg_price')
            
            # Übergib Competitive Strategy an Pricing Engine
            # Die Engine wird sie automatisch mit dynamischer Gewichtung kombinieren
            base_engine.competitive_recommendation = competitive_rec
        else:
            logger.info("Competitive Strategy: Keine Daten verfügbar, überspringe")
            base_engine.competitive_recommendation = None
        
        # Berechne Base Recommendation (mit integrierter Competitive Strategy)
        # Die Engine nutzt jetzt automatisch dynamische Gewichtung bei extremer Differenz
        logger.info(f"🔍 DEBUG - Before calculate_price() - Competitor prices: {len(competitor_prices) if competitor_prices else 0}")
        base_recommendation = base_engine.calculate_price(product, sales_data=sales_data)
        logger.info(f"🔍 DEBUG - After calculate_price() - Recommended: {base_recommendation.get('price'):.2f}€, Strategy: {base_recommendation.get('strategy')}")
        
        # Speichere Competitor-Kontext in Response
        if competitor_prices and competitive_rec:
            if 'strategies' not in base_recommendation.get('reasoning', {}):
                base_recommendation.setdefault('reasoning', {})['strategies'] = {}
            base_recommendation['reasoning']['competitive'] = competitive_rec.get('competitor_context')
            base_recommendation['reasoning']['strategies']['competitive'] = competitive_rec
        
        # NEW: MARGIN VALIDATION
        margin_analysis = None
        if base_engine.margin_calculator:
            try:
                margin_analysis = base_engine._validate_margin(
                    product_id=str(product.id),
                    shop_id=str(shop_context.active_shop_id) if shop_context.active_shop_id else "demo",
                    recommended_price=base_recommendation.get('price', product.price),
                    current_price=product.price
                )
                
                # Check if recommendation is safe
                if margin_analysis and not margin_analysis.get('is_safe'):
                    # Add warning
                    if 'warnings' not in base_recommendation:
                        base_recommendation['warnings'] = []
                    
                    base_recommendation['warnings'].append({
                        'type': 'MARGIN_WARNING',
                        'severity': 'HIGH' if margin_analysis.get('warning') == 'BELOW_BREAK_EVEN' else 'MEDIUM',
                        'message': margin_analysis.get('message', 'Margin warning'),
                        'action_required': margin_analysis.get('warning') == 'BELOW_BREAK_EVEN'
                    })
                    
                    # If below break-even, override recommendation
                    if margin_analysis.get('warning') == 'BELOW_BREAK_EVEN':
                        break_even_price = margin_analysis.get('details', {}).get('break_even_price', product.price)
                        safe_price = break_even_price * 1.05  # Break-even + 5%
                        
                        logger.error(f"""
                        🚨 REJECTED RECOMMENDATION: Below Break-Even
                           Product: {product_id}
                           Recommended: €{base_recommendation['price']:.2f}
                           Break-Even: €{break_even_price:.2f}
                           
                           OVERRIDING to safe price: €{safe_price:.2f}
                        """)
                        
                        base_recommendation['price'] = round(safe_price, 2)
                        base_recommendation['confidence'] = min(base_recommendation.get('confidence', 0.5), 0.50)
                        base_recommendation['reasoning'] = (
                            f"⚠️ Ursprüngliche Empfehlung lag unter Break-Even. "
                            f"Preis wurde auf sicheres Minimum (Break-Even + 5%) angepasst."
                        )
                        
                        # Recalculate margin with safe price
                        margin_analysis = base_engine._validate_margin(
                            product_id=str(product.id),
                            shop_id=str(shop_context.active_shop_id) if shop_context.active_shop_id else "demo",
                            recommended_price=safe_price,
                            current_price=product.price
                        )
                
                # Add margin analysis to recommendation
                base_recommendation['margin_analysis'] = margin_analysis
                
            except Exception as e:
                logger.warning(f"Margin validation failed: {e}", exc_info=True)
                # Continue without margin validation
        
        # Feature Confidence Analysis
        # NOTE: Called AFTER competitor fetch to include competitor data in analysis
        logger.debug("[ANALYSIS] Running feature confidence analysis (with competitor data)...")
        confidence_data = None
        try:
            confidence_data = analyze_feature_availability(
                product_id, 
                db, 
                shop_context, 
                competitor_data=competitor_prices if competitor_prices else None
            )
            logger.info(f"[ANALYSIS] Confidence analysis complete. Overall: {confidence_data.get('overall_confidence', 0):.1f}%")
        except Exception as e:
            logger.warning(f"Feature confidence analysis failed: {e}")
            logger.warning(f"[ANALYSIS] Analysis failed: {e}")
        
        # 8. Erstelle ML-Enhanced Engine (mit Fallback zu Base)
        print("[ROUTING] ========== REACHED ML ENGINE SECTION ==========", flush=True)
        logger.critical("[ROUTING] ========== REACHED ML ENGINE SECTION ==========")
        # ═══════════════════════════════════════════════════════════════
        # ALWAYS use Orchestrator - it routes to OLD or NEW based on feature flags
        # ═══════════════════════════════════════════════════════════════
        use_orchestrator = True  # Always use orchestrator for consistent routing
        
        # Log routing decision (CRITICAL - must appear in logs)
        print(f"[ROUTING] USE_NEW_ML_ENGINE={settings.USE_NEW_ML_ENGINE} ROLLOUT_PCT={settings.ML_ENGINE_ROLLOUT_PCT}", flush=True)
        logger.critical(f"[ROUTING] USE_NEW_ML_ENGINE={settings.USE_NEW_ML_ENGINE} ROLLOUT_PCT={settings.ML_ENGINE_ROLLOUT_PCT}")
        print("[ROUTING] Starting orchestrator routing decision", flush=True)
        logger.critical("[ROUTING] Starting orchestrator routing decision")
        print(f"[ROUTING] USE_NEW_ML_ENGINE={settings.USE_NEW_ML_ENGINE} (type: {type(settings.USE_NEW_ML_ENGINE).__name__})", flush=True)
        logger.critical(f"[ROUTING] USE_NEW_ML_ENGINE={settings.USE_NEW_ML_ENGINE} (type: {type(settings.USE_NEW_ML_ENGINE).__name__})")
        print(f"[ROUTING] ML_ENGINE_ROLLOUT_PCT={settings.ML_ENGINE_ROLLOUT_PCT} (type: {type(settings.ML_ENGINE_ROLLOUT_PCT).__name__})", flush=True)
        logger.critical(f"[ROUTING] ML_ENGINE_ROLLOUT_PCT={settings.ML_ENGINE_ROLLOUT_PCT} (type: {type(settings.ML_ENGINE_ROLLOUT_PCT).__name__})")
        print(f"[ROUTING] force_new={force_new}, force_old={force_old}", flush=True)
        logger.critical(f"[ROUTING] force_new={force_new}, force_old={force_old}")
        print(f"[ROUTING] Using orchestrator: {use_orchestrator} (always enabled for routing)", flush=True)
        logger.critical(f"[ROUTING] Using orchestrator: {use_orchestrator} (always enabled for routing)")
        
        if use_orchestrator:
            print("[ORCHESTRATOR] Entering orchestrator code path", flush=True)
            logger.critical("[ORCHESTRATOR] Entering orchestrator code path")
            # ═══════════════════════════════════════════════════════════
            # NEW: Use PricingOrchestrator (routes OLD vs NEW)
            # ═══════════════════════════════════════════════════════════
            try:
                # ═══════════════════════════════════════════════════════════
                # STEP 1: Collecting input data
                # ═══════════════════════════════════════════════════════════
                logger.info("=" * 80)
                product_name = getattr(product, 'title', getattr(product, 'name', 'Unknown'))
                logger.info(f"ML PRICE RECOMMENDATION - Product: {product_name} (ID: {product.id})")
                logger.info("=" * 80)
                
                logger.info("STEP 1: Collecting input data")
                logger.info(f"  - Current price: €{product.price:.2f}" if product.price else "  - Current price: €0.00")
                logger.info(f"  - Original price: €{getattr(product, 'price_original', product.price or 0):.2f}" if hasattr(product, 'price_original') and product.price_original else f"  - Original price: €{product.price:.2f}" if product.price else "  - Original price: €0.00")
                logger.info(f"  - Product cost: €{product.cost:.2f}" if product.cost else "  - Product cost: €0.00")
                logger.info(f"  - Competitor data: {len(competitor_prices) if competitor_prices else 0} items")
                logger.info(f"  - Sales history: {len(sales_data) if not sales_data.empty else 0} records")
                
                # Prepare product_data for orchestrator
                product_data_dict = {
                    'id': str(product.id),
                    'current_price': float(product.price) if product.price else 0.0,
                    'cost': float(product.cost) if product.cost else 0.0,
                    'inventory_quantity': product.inventory_quantity or 0,
                    'breakeven_price': float(product.breakeven_price) if hasattr(product, 'breakeven_price') and product.breakeven_price else 0.0,
                    'competitor_avg_price': competitor_avg_price if competitor_avg_price else 0.0,
                    'competitor_data': competitor_prices if competitor_prices else None
                }
                
                # Get recommendation from orchestrator
                print("[ORCHESTRATOR] Calling pricing_orchestrator.get_price_recommendation()...", flush=True)
                logger.critical("[ORCHESTRATOR] Calling pricing_orchestrator.get_price_recommendation()...")
                orchestrator_result = await pricing_orchestrator.get_price_recommendation(
                    product_data=product_data_dict,
                    product=product,  # Pass product object for FeatureEngineeringService
                    competitor_data=competitor_prices,  # Pass competitor data for feature extraction
                    force_new=force_new,
                    force_old=force_old
                )
                print(f"[ORCHESTRATOR] Orchestrator returned: {orchestrator_result.get('_ml_engine', 'UNKNOWN')}", flush=True)
                logger.critical(f"[ORCHESTRATOR] Orchestrator returned: {orchestrator_result.get('_ml_engine', 'UNKNOWN')}")
                
                # Extract ML details for logging
                ml_details = orchestrator_result.get('ml_details', {})
                model_versions = orchestrator_result.get('model_versions', {})
                
                # Log STEP 2 and STEP 3 if available in orchestrator result
                if ml_details:
                    logger.info("STEP 2: Feature extraction")
                    if 'features_extracted' in ml_details:
                        logger.info(f"  - Total features extracted: {len(ml_details['features_extracted'])}")
                    else:
                        logger.info(f"  - Feature extraction: Completed (details in service logs)")
                    
                    logger.info("STEP 3: ML model prediction")
                    if 'xgboost_raw_prediction' in ml_details:
                        logger.info(f"  - XGBoost raw prediction: €{ml_details['xgboost_raw_prediction']:.2f}")
                    if 'meta_confidence' in ml_details:
                        logger.info(f"  - Meta Labeler confidence: {ml_details['meta_confidence']:.2%}")
                    if 'meta_class' in ml_details:
                        logger.info(f"  - Meta Labeler class: {ml_details['meta_class']}")
                    if model_versions:
                        logger.info(f"  - Model versions: {model_versions}")
                
                # ═══════════════════════════════════════════════════════════
                # STEP 5: Final price recommendation
                # ═══════════════════════════════════════════════════════════
                recommended_price = orchestrator_result.get('price', orchestrator_result.get('recommended_price', 0.0))
                confidence = orchestrator_result.get('confidence', 0.5)
                strategy = orchestrator_result.get('strategy', 'unknown')
                ml_engine = orchestrator_result.get('_ml_engine', 'UNKNOWN')
                
                logger.info("STEP 5: Final price recommendation")
                logger.info(f"  - Recommended price: €{recommended_price:.2f}")
                price_change = ((recommended_price - (product.price or 0)) / (product.price or 1)) * 100 if product.price else 0
                logger.info(f"  - Price change: {price_change:+.2f}% from current")
                logger.info(f"  - Confidence: {confidence:.1%}")
                confidence_label = orchestrator_result.get('confidence_label', orchestrator_result.get('mvp_confidence_label', 'Medium'))
                logger.info(f"  - Confidence label: {confidence_label}")
                
                # Log price calculation breakdown
                if ml_details and 'xgboost_raw_prediction' in ml_details:
                    base_price = product.price or 0
                    ml_price = ml_details['xgboost_raw_prediction']
                    if base_price > 0:
                        ml_adjustment = ((ml_price - base_price) / base_price) * 100
                        logger.info(f"  - Base price (current): €{base_price:.2f}")
                        logger.info(f"  - ML predicted price: €{ml_price:.2f}")
                        logger.info(f"  - ML adjustment: {ml_adjustment:+.1f}%")
                        if abs(recommended_price - ml_price) > 0.01:
                            constraint_adjustment = ((recommended_price - ml_price) / ml_price) * 100
                            logger.info(f"  - After constraints: €{recommended_price:.2f} ({constraint_adjustment:+.1f}% from ML)")
                
                # Log constraints applied
                constraints_applied = orchestrator_result.get('constraints_applied', [])
                if constraints_applied:
                    logger.info(f"  - Constraints applied: {constraints_applied}")
                else:
                    logger.info(f"  - Constraints applied: None")
                
                # Calculate expected margin
                if product.cost and recommended_price > 0:
                    expected_margin = ((recommended_price - product.cost) / recommended_price) * 100
                    logger.info(f"  - Expected margin: {expected_margin:.1f}%")
                
                logger.info(f"  - ML Engine: {ml_engine}")
                logger.info(f"  - Strategy: {strategy}")
                
                logger.info("=" * 80)
                logger.info("ML RECOMMENDATION COMPLETE")
                logger.info("=" * 80)
                
                # Convert orchestrator result to recommendation format
                recommendation = {
                    'price': recommended_price,
                    'recommended_price': recommended_price,
                    'confidence': confidence,
                    'strategy': strategy,
                    'reasoning': orchestrator_result.get('reasoning', ''),
                    'ml_confidence': orchestrator_result.get('ml_confidence', confidence),
                    'confidence_label': confidence_label,
                    'mvp_confidence': orchestrator_result.get('mvp_confidence', confidence),
                    'mvp_confidence_label': orchestrator_result.get('mvp_confidence_label', confidence_label),
                    'confidence_breakdown': orchestrator_result.get('confidence_breakdown', {}),
                    '_ml_engine': ml_engine,
                    '_routing_reason': orchestrator_result.get('_routing_reason', 'unknown')
                }
                
            except Exception as e:
                logger.critical("=" * 80)
                logger.critical("[ORCHESTRATOR] ========== EXCEPTION IN ORCHESTRATOR TRY BLOCK ==========")
                logger.critical(f"[ORCHESTRATOR] Exception Type: {type(e).__name__}")
                logger.critical(f"[ORCHESTRATOR] Exception Message: {str(e)[:500]}")
                import traceback
                logger.critical(f"[ORCHESTRATOR] Full traceback:\n{traceback.format_exc()}")
                logger.critical("=" * 80)
                # Fallback to OLD engine
                use_orchestrator = False
        
        if not use_orchestrator:
            logger.critical("[FALLBACK] Using OLD engine code path (orchestrator disabled or failed)")
            # ═══════════════════════════════════════════════════════════
            # OLD: Use MLPricingEngine directly (existing code)
            # ═══════════════════════════════════════════════════════════
            try:
                # ═══════════════════════════════════════════════════════════
                # STEP 1: Collecting input data
                # ═══════════════════════════════════════════════════════════
                logger.info("=" * 80)
                product_name = getattr(product, 'title', getattr(product, 'name', 'Unknown'))
                logger.info(f"ML PRICE RECOMMENDATION - Product: {product_name} (ID: {product.id})")
                logger.info("=" * 80)
                
                logger.info("STEP 1: Collecting input data")
                logger.info(f"  - Current price: €{product.price:.2f}" if product.price else "  - Current price: €0.00")
                logger.info(f"  - Original price: €{getattr(product, 'price_original', product.price or 0):.2f}" if hasattr(product, 'price_original') and product.price_original else f"  - Original price: €{product.price:.2f}" if product.price else "  - Original price: €0.00")
                logger.info(f"  - Product cost: €{product.cost:.2f}" if product.cost else "  - Product cost: €0.00")
                logger.info(f"  - Competitor data: {len(competitor_prices) if competitor_prices else 0} items")
                logger.info(f"  - Sales history: {len(sales_data) if not sales_data.empty else 0} records")
                
                logger.critical("[FALLBACK] Creating OLD MLPricingEngine directly (bypassing orchestrator)")
                ml_engine = MLPricingEngine(base_engine=base_engine)
                logger.critical(f"[FALLBACK] OLD MLPricingEngine created: {ml_engine is not None}")
                logger.critical(f"[FALLBACK] Models loaded: {ml_engine.models_loaded}")
                
                recommendation = ml_engine.generate_ml_enhanced_recommendation(
                    product=product, 
                    sales_data=sales_data,
                    competitor_data=competitor_prices if competitor_prices else None
                )
                
                # ═══════════════════════════════════════════════════════════
                # STEP 5: Final price recommendation
                # ═══════════════════════════════════════════════════════════
                recommended_price = recommendation.get('price', 0.0)
                confidence = recommendation.get('confidence', 0.5)
                strategy = recommendation.get('strategy', 'unknown')
                
                logger.info("STEP 5: Final price recommendation")
                logger.info(f"  - Recommended price: €{recommended_price:.2f}")
                price_change = ((recommended_price - (product.price or 0)) / (product.price or 1)) * 100 if product.price else 0
                logger.info(f"  - Price change: {price_change:+.2f}% from current")
                logger.info(f"  - Confidence: {confidence:.1%}")
                confidence_label = recommendation.get('confidence_label', 'Medium')
                logger.info(f"  - Confidence label: {confidence_label}")
                
                # Calculate expected margin
                if product.cost and recommended_price > 0:
                    expected_margin = ((recommended_price - product.cost) / recommended_price) * 100
                    logger.info(f"  - Expected margin: {expected_margin:.1f}%")
                
                logger.info(f"  - ML Engine: OLD_legacy")
                logger.info(f"  - Strategy: {strategy}")
                
                logger.info("=" * 80)
                logger.info("ML RECOMMENDATION COMPLETE")
                logger.info("=" * 80)
            except Exception as e:
                # === EXCEPTION LOGGING ===
                logger.debug("=" * 80)
                logger.error("EXCEPTION CAUGHT in generate_recommendation endpoint")
                logger.error(f"Exception Type: {type(e).__name__}")
                logger.error(f"Exception Message: {str(e)}")
                import traceback
                logger.error(f"Full Traceback:\n{traceback.format_exc()}")
                logger.debug("=" * 80)
                logger.critical("=" * 70)
                logger.critical("🔥🔥🔥 EXCEPTION CAUGHT in generate_recommendation endpoint 🔥🔥🔥")
                logger.critical(f"🔥 Exception Type: {type(e).__name__}")
                logger.critical(f"🔥 Exception Message: {str(e)}")
                logger.critical("🔥 Full Traceback:")
                import traceback
                logger.critical(traceback.format_exc())
                logger.critical("🔥 Falling back to base_engine.calculate_price()")
                logger.critical("=" * 70)
                # === END EXCEPTION LOGGING ===
                logger.warning(f"ML Engine Fehler, nutze Base Engine: {e}", exc_info=True)
                recommendation = base_engine.calculate_price(product, sales_data=sales_data)
        
        # 9. Berechne price_change_pct
        current_price = product.price
        recommended_price = recommendation["price"]
        price_change_pct = ((recommended_price - current_price) / current_price * 100) if current_price > 0 else 0
        
        # 10. Speichere Recommendation in DB mit Shop-Context
        new_rec = Recommendation(
            product_id=product_id,
            shop_id=shop_context.active_shop_id,
            is_demo=shop_context.is_demo_mode,
            current_price=current_price,
            recommended_price=recommended_price,
            price_change_pct=price_change_pct,
            confidence=recommendation.get("confidence", 0.5),
            strategy=recommendation.get("strategy", "unknown"),
            reasoning=json.dumps(recommendation.get("reasoning", {})) if isinstance(recommendation.get("reasoning"), dict) else str(recommendation.get("reasoning", {})),
            demand_growth=demand_growth,
            days_of_stock=days_of_stock,
            sales_7d=sales_7d,
            sales_30d=int(sales_30d) if sales_30d else None,  # WICHTIG: Für Dashboard
            competitor_avg_price=competitor_avg_price
        )
        db.add(new_rec)
        db.commit()
        db.refresh(new_rec)
        
        logger.info(f"Recommendation gespeichert: ID={new_rec.id}, Shop={shop_context.active_shop_id}, Demo={shop_context.is_demo_mode}")
        
        # 11. Erweitere Response
        # Extrahiere strategy_details aus reasoning für Frontend
        reasoning_data = recommendation.get("reasoning", {})
        strategy_details = []
        
        # Prüfe ob strategies in reasoning vorhanden sind
        if isinstance(reasoning_data, dict) and "strategies" in reasoning_data:
            strategies = reasoning_data.get("strategies", {})
            # Konvertiere strategies Dict zu strategy_details Array
            for strategy_name, strategy_data in strategies.items():
                if isinstance(strategy_data, dict):
                    strategy_details.append({
                        "strategy": strategy_name,
                        "recommended_price": strategy_data.get("price", strategy_data.get("recommended_price", recommended_price)),
                        "confidence": strategy_data.get("confidence", new_rec.confidence or 0.5),
                        "reasoning": strategy_data.get("reasoning", ""),
                        "competitor_context": strategy_data.get("competitor_context")
                    })
        
        # Confidence data already calculated above
        
        response = {
            "success": True,
            "recommendation": {
                "id": new_rec.id,
                "product_id": product_id,
                "product_name": product.title,
                "current_price": current_price,
                "recommended_price": recommended_price,
                "price_change_pct": price_change_pct,
                "confidence": new_rec.confidence,
                "strategy": new_rec.strategy,
                "demand_growth": demand_growth,
                "days_of_stock": days_of_stock,
                "sales_7d": sales_7d,
                "competitor_avg_price": competitor_avg_price,
                "strategy_details": strategy_details if strategy_details else None,  # WICHTIG: Für PriceReasoningStory
                "reasoning": reasoning_data  # Behalte auch original reasoning
            },
            "confidence": confidence_data,  # NEW: Feature confidence breakdown
            "details": reasoning_data,
            "shop_context": {
                "shop_id": shop_context.active_shop_id,
                "is_demo": shop_context.is_demo_mode
            }
        }
        
        # Add margin analysis if available
        if margin_analysis:
            response["recommendation"]["margin_analysis"] = margin_analysis
        
        # Füge ML-Daten hinzu, falls vorhanden
        if "ml_confidence" in recommendation:
            response["recommendation"]["base_confidence"] = recommendation.get("base_confidence")
            response["recommendation"]["ml_confidence"] = recommendation.get("ml_confidence")
            response["recommendation"]["ml_detector_confidence"] = recommendation.get("ml_detector_confidence")
            response["recommendation"]["meta_labeler_confidence"] = recommendation.get("meta_labeler_confidence")
            response["recommendation"]["meta_labeler_approved"] = recommendation.get("meta_labeler_approved", True)
        
        # 🚀 NEW: Add MVP Confidence v2.0 fields
        if "confidence_label" in recommendation:
            response["recommendation"]["confidence_label"] = recommendation.get("confidence_label")
        
        if "confidence_breakdown" in recommendation:
            response["recommendation"]["confidence_breakdown"] = recommendation.get("confidence_breakdown")
        
        if "mvp_confidence_breakdown" in recommendation:
            response["recommendation"]["mvp_confidence_breakdown"] = recommendation.get("mvp_confidence_breakdown")
        
        if "confidence_details" in recommendation:
            response["recommendation"]["confidence_details"] = recommendation.get("confidence_details")
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        full_traceback = traceback.format_exc()
        logger.error(f"[ENDPOINT ERROR] Product {product_id}: {str(e)}")
        logger.error(f"[FULL TRACEBACK]:\n{full_traceback}")
        raise HTTPException(
            status_code=500,
            detail=f"{str(e)}"
        )


# Request Models
from pydantic import BaseModel


class AcceptRecommendationRequest(BaseModel):
    """Request: Accept Recommendation"""
    pass  # Keine Parameter nötig


class RejectRecommendationRequest(BaseModel):
    """Request: Reject Recommendation"""
    reason: Optional[str] = None


class ApplyRecommendationRequest(BaseModel):
    """Request: Apply Recommendation"""
    applied_price: Optional[float] = None  # Falls User Preis anpasst


# Status Update Endpoints
@router.patch("/{recommendation_id}/accept")
async def accept_recommendation(
    recommendation_id: int,
    db: Session = Depends(get_db)
):
    """
    Accept Recommendation (User hat akzeptiert, aber noch nicht angewendet).
    Status: pending → accepted
    """
    from app.services.recommendation_service import RecommendationService
    
    try:
        service = RecommendationService(db)
        recommendation = service.mark_as_accepted(recommendation_id)
        
        return {
            "success": True,
            "recommendation_id": recommendation_id,
            "status": recommendation.status,
            "message": "Recommendation akzeptiert"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Fehler beim Akzeptieren: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")


@router.patch("/{recommendation_id}/reject")
async def reject_recommendation(
    recommendation_id: int,
    request: RejectRecommendationRequest,
    db: Session = Depends(get_db)
):
    """
    Reject Recommendation (User hat abgelehnt).
    Status: pending → rejected
    """
    from app.services.recommendation_service import RecommendationService
    
    try:
        service = RecommendationService(db)
        recommendation = service.mark_as_rejected(
            recommendation_id, 
            reason=request.reason
        )
        
        return {
            "success": True,
            "recommendation_id": recommendation_id,
            "status": recommendation.status,
            "reason": request.reason,
            "message": "Recommendation abgelehnt"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Fehler beim Ablehnen: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")


@router.patch("/{recommendation_id}/mark-applied")
async def mark_recommendation_applied(
    recommendation_id: int,
    request: ApplyRecommendationRequest,
    db: Session = Depends(get_db)
):
    """
    Mark Recommendation as Applied (Preis wurde auf Shopify angewendet).
    Status: accepted → applied
    
    WICHTIG: Diese Endpoint markiert nur die Recommendation.
    Der tatsächliche Apply-Prozess läuft über /api/shopify/apply-price
    """
    from app.services.recommendation_service import RecommendationService
    
    try:
        service = RecommendationService(db)
        recommendation = service.get_by_id(recommendation_id)
        
        if not recommendation:
            raise HTTPException(status_code=404, detail="Recommendation nicht gefunden")
        
        # Nutze applied_price falls angegeben, sonst recommended_price
        applied_price = request.applied_price or recommendation.recommended_price
        
        recommendation = service.mark_as_applied(
            recommendation_id,
            applied_price=applied_price
        )
        
        return {
            "success": True,
            "recommendation_id": recommendation_id,
            "status": recommendation.status,
            "applied_price": applied_price,
            "applied_at": recommendation.applied_at.isoformat(),
            "message": "Recommendation als angewendet markiert"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Fehler beim Markieren: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fehler: {str(e)}")


@router.get("/engine-status")
async def get_engine_status(
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Get ML Engine status (which engine is active, feature flags, etc.)
    
    🆕 Monitoring endpoint für admins
    """
    try:
        status_info = pricing_orchestrator.get_engine_status()
        
        return {
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            **status_info
        }
    except Exception as e:
        logger.error(f"Failed to get engine status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{recommendation_id}/status")
async def get_recommendation_status(
    recommendation_id: int,
    db: Session = Depends(get_db)
):
    """Get Recommendation Status"""
    from app.services.recommendation_service import RecommendationService
    
    service = RecommendationService(db)
    recommendation = service.get_by_id(recommendation_id)
    
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation nicht gefunden")
    
    return {
        "recommendation_id": recommendation_id,
        "status": recommendation.status,
        "created_at": recommendation.created_at.isoformat() if recommendation.created_at else None,
        "applied_at": recommendation.applied_at.isoformat() if recommendation.applied_at else None,
        "applied_price": recommendation.applied_price
    }


@router.get("/confidence/{product_id}")
async def get_feature_confidence(
    product_id: int,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Get detailed feature confidence breakdown for a product.
    
    Returns confidence analysis showing:
    - Overall confidence score
    - Category-wise breakdown (SALES, COMPETITOR, etc.)
    - Missing critical vs non-critical features
    - Legitimate zeros vs missing data
    - Warnings and recommendations
    """
    try:
        # ✅ CRITICAL: Load latest context from Redis/Memory
        shop_context.load()
        
        logger.info(
            f"[CONFIDENCE] Session {shop_context.session_id}: "
            f"shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}"
        )
        
        # Get competitor data if available
        competitor_data = None
        try:
            from app.services.competitor_price_service import CompetitorPriceService
            
            # Get product for title
            if shop_context.is_demo_mode:
                adapter = shop_context.get_adapter()
                demo_products = adapter.load_products()
                product_data = next(
                    (p for p in demo_products if p.get('id') == product_id or str(p.get('id')) == str(product_id)),
                    None
                )
                if product_data:
                    product_title = product_data.get('title', f'Product {product_id}')
                else:
                    product_title = None
            else:
                product = db.query(Product).filter(
                    Product.id == product_id,
                    Product.shop_id == shop_context.active_shop_id
                ).first()
                product_title = product.title if product else None
            
            if product_title:
                competitor_service = CompetitorPriceService(
                    db_session=db,
                    save_to_db=False,
                    product_id=product_id
                )
                competitor_data = competitor_service.find_competitor_prices(
                    product_title=product_title,
                    max_results=5,
                    use_cache=True
                )
        except Exception as e:
            logger.warning(f"Could not fetch competitor data for confidence analysis: {e}")
        
        # Get confidence analysis
        confidence_data = analyze_feature_availability(
            product_id,
            db,
            shop_context,
            competitor_data=competitor_data if competitor_data else None
        )
        
        return confidence_data
    
    except Exception as e:
        logger.error(f"Error getting feature confidence: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing feature confidence: {str(e)}"
        )

