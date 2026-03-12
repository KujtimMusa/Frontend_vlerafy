"""
MVP Confidence Calculator - Optimized for Demo/MVP Stage
Version: 2.0
Expected Variance: 40-50%

Tier Weights:
1. Data Richness: 35%
2. Market Intelligence: 30% (KEY for variance!)
3. Model Confidence: 10%
4. Product Maturity: 15%
5. Content Quality: 10%

Historical Performance: SKIPPED (MVP has no recommendation history)
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import numpy as np
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


class MVPConfidenceCalculator:
    """
    MVP-optimized Confidence Scoring System
    
    Tier Weights:
    1. Data Richness: 35%
    2. Market Intelligence: 30%
    3. Model Confidence: 10%
    4. Product Maturity: 15%
    5. Content Quality: 10%
    
    Expected Variance: 40-50% (vs. current 0.2%)
    """
    
    def __init__(self, db: Optional[Session] = None):
        """
        Initialize MVP Confidence Calculator
        
        Args:
            db: SQLAlchemy Session (optional, will fetch data if provided)
        """
        self.db = db
    
    def calculate_confidence(
        self,
        product,
        ml_output: Dict,
        competitor_data: Optional[List] = None,
        sales_history: Optional[List] = None,
        price_history: Optional[List] = None
    ) -> Dict:
        """
        Calculate product-specific confidence score with extensive debug logging
        """
        import traceback
        
        # Structured logging for MVP Confidence Calculator
        logger.info("STEP 4: Confidence score calculation")
        logger.info("  MVP Confidence Calculator v2.0")
        
        # Extract ML outputs
        ml_detector = ml_output.get('detector', 0.5)
        ml_labeler = ml_output.get('labeler', 0.5)
        logger.info(f"  Input: Detector={ml_detector:.4f}, Labeler={ml_labeler:.4f}")
        
        # Fetch data if not provided and DB available
        if self.db:
            if competitor_data is None:
                competitor_data = self._fetch_competitor_data(product.id)
            
            if sales_history is None:
                sales_history = self._fetch_sales_history(product.id)
            
            if price_history is None:
                price_history = self._fetch_price_history(product.id)
        
        # Convert competitor_data to list of prices if needed
        competitor_prices = self._extract_competitor_prices(competitor_data)
        
        # Initialize tier scores dict
        tier_scores = {}
        
        # === TIER 1: DATA RICHNESS (35%) ===
        try:
            data_richness_score, data_richness_details = self._calculate_data_richness(
                product, sales_history or [], price_history or []
            )
            tier_scores['data_richness'] = data_richness_score
            logger.info(f"  Tier 1 - Data Richness (35%): {data_richness_score:.4f}")
            sales_richness = data_richness_details.get('sales_richness', 0.0)
            comp_richness = data_richness_details.get('competitor_richness', 0.0)
            price_richness = data_richness_details.get('price_history_richness', 0.0)
            logger.info(f"    - Sales history richness: {sales_richness:.4f}")
            logger.info(f"    - Competitor data richness: {comp_richness:.4f}")
            logger.info(f"    - Price history richness: {price_richness:.4f}")
            
            # Missing Data Warnings (Priority 2)
            if data_richness_score < 0.5:
                logger.warning(f"  WARNING: Low data richness ({data_richness_score:.1%}) - Reasons:")
                sales_count = len(sales_history) if sales_history else 0
                if sales_richness < 0.3:
                    logger.warning(f"     - Insufficient sales data: {sales_count} sales (need 30+)")
                if comp_richness < 0.5:
                    comp_count = len(competitor_prices) if competitor_prices else 0
                    logger.warning(f"     - Limited competitor data: {comp_count} competitors (need 5+)")
                if price_richness < 0.3:
                    price_count = len(price_history) if price_history else 0
                    logger.warning(f"     - Limited price history: {price_count} records (need 10+)")
        except Exception as e:
            logger.error(f"  Tier 1 FAILED: {e}", exc_info=True)
            data_richness_score = 0.52
            data_richness_details = {}
            tier_scores['data_richness'] = 0.52
            logger.info(f"    Using default: {data_richness_score:.4f}")
        
        # === TIER 2: MARKET INTELLIGENCE (30%) ===
        try:
            market_intelligence_score, market_intelligence_details = self._calculate_market_intelligence(
                product, competitor_prices, competitor_data
            )
            tier_scores['market_intelligence'] = market_intelligence_score
            logger.info(f"  Tier 2 - Market Intelligence (30%): {market_intelligence_score:.4f}")
            position = market_intelligence_details.get('position_score', 0.0)
            coverage = market_intelligence_details.get('coverage_score', 0.0)
            logger.info(f"    - Position: {position:.4f}, Coverage: {coverage:.4f}")
        except Exception as e:
            logger.error(f"  Tier 2 FAILED: {e}", exc_info=True)
            market_intelligence_score = 0.52
            market_intelligence_details = {}
            tier_scores['market_intelligence'] = 0.52
            logger.info(f"    Using default: {market_intelligence_score:.4f}")
        
        # === TIER 3: MODEL CONFIDENCE (10%) ===
        try:
            model_confidence_score, model_details = self._calculate_model_confidence(ml_output)
            tier_scores['model_confidence'] = model_confidence_score
            logger.info(f"  Tier 3 - Model Confidence (10%): {model_confidence_score:.4f}")
            
            # ML Model Agreement Analysis (Priority 2)
            if model_confidence_score < 0.6:
                logger.warning(f"  WARNING: Low model confidence ({model_confidence_score:.1%}) - Reasons:")
                detector = ml_output.get('detector', 0.5)
                labeler = ml_output.get('labeler', 0.5)
                agreement = abs(detector - labeler)
                if agreement > 0.3:
                    logger.warning(f"     - ML models disagree: detector={detector:.2f}, labeler={labeler:.2f} (diff={agreement:.2f})")
                if detector < 0.4 or detector > 0.6:
                    logger.warning(f"     - Detector uncertain: {detector:.2f} (close to 0.5 = uncertain)")
                if labeler < 0.4:
                    logger.warning(f"     - Labeler low confidence: {labeler:.2f} (all classes have low probability)")
        except Exception as e:
            logger.error(f"  Tier 3 FAILED: {e}", exc_info=True)
            model_confidence_score = 0.52
            model_details = {}
            tier_scores['model_confidence'] = 0.52
            logger.info(f"    Using default: {model_confidence_score:.4f}")
        
        # === TIER 4: PRODUCT MATURITY (15%) ===
        try:
            product_maturity_score, maturity_details = self._calculate_product_maturity(
                product, sales_history or [], price_history or []
            )
            tier_scores['product_maturity'] = product_maturity_score
            logger.info(f"  Tier 4 - Product Maturity (15%): {product_maturity_score:.4f}")
        except Exception as e:
            logger.error(f"  Tier 4 FAILED: {e}", exc_info=True)
            product_maturity_score = 0.52
            maturity_details = {}
            tier_scores['product_maturity'] = 0.52
            logger.info(f"    Using default: {product_maturity_score:.4f}")
        
        # === TIER 5: CONTENT QUALITY (10%) ===
        try:
            content_quality_score, content_details = self._calculate_content_quality(product)
            tier_scores['content_quality'] = content_quality_score
            logger.info(f"  Tier 5 - Content Quality (10%): {content_quality_score:.4f}")
        except Exception as e:
            logger.error(f"  Tier 5 FAILED: {e}", exc_info=True)
            content_quality_score = 0.52
            content_details = {}
            tier_scores['content_quality'] = 0.52
            logger.info(f"    Using default: {content_quality_score:.4f}")
        
        # === CALCULATE WEIGHTED FINAL SCORE ===
        # ML-CENTRIC WEIGHTS (January 2026)
        # XGBoost Kaggle: 91.2% test, 92.0% ± 0.8% CV
        # Model is PRIMARY intelligence source
        weights = {
            'model_confidence': 0.50,        # ML is the boss! (50%)
            'data_richness': 0.25,           # Data quality supports ML (25%)
            'market_intelligence': 0.25       # Market provides validation (25%)
        }
        
        logger.info("  Weighted calculation:")
        model_weight = weights['model_confidence']
        data_weight = weights['data_richness']
        market_weight = weights['market_intelligence']
        maturity_weight = 0.15  # Tier 4
        content_weight = 0.10  # Tier 5
        
        model_confidence = tier_scores.get('model_confidence', 0.52)
        data_richness = tier_scores.get('data_richness', 0.52)
        market_score = tier_scores.get('market_intelligence', 0.52)
        maturity_score = tier_scores.get('product_maturity', 0.52)
        content_score = tier_scores.get('content_quality', 0.52)
        
        logger.info(f"    Model (50%): {model_weight * model_confidence:.4f}")
        logger.info(f"    Data (25%): {data_weight * data_richness:.4f}")
        logger.info(f"    Market (25%): {market_weight * market_score:.4f}")
        logger.info(f"    Maturity (15%): {maturity_weight * maturity_score:.4f}")
        logger.info(f"    Content (10%): {content_weight * content_score:.4f}")
        
        final_score = (model_weight * model_confidence + 
                      data_weight * data_richness + 
                      market_weight * market_score +
                      maturity_weight * maturity_score +
                      content_weight * content_score)
        
        # Clamp to realistic range (30%-98%)
        overall_confidence = max(0.30, min(0.98, final_score))
        
        # Low Confidence Reasoning (Priority 2)
        if overall_confidence < 0.5:
            logger.warning(f"  WARNING: LOW CONFIDENCE ({overall_confidence:.1%}) - Recommendation may be unreliable")
            logger.warning(f"     - Consider manual review or fallback pricing")
            if data_richness < 0.5:
                logger.warning(f"     - Primary issue: Insufficient data (Tier 1: {data_richness:.1%})")
            if market_score < 0.5:
                logger.warning(f"     - Primary issue: Limited market intelligence (Tier 2: {market_score:.1%})")
            if model_confidence < 0.6:
                logger.warning(f"     - Primary issue: ML models uncertain (Tier 3: {model_confidence:.1%})")
        
        # Confidence label
        if overall_confidence >= 0.80:
            confidence_label = 'High'
        elif overall_confidence >= 0.65:
            confidence_label = 'Medium'
        elif overall_confidence >= 0.50:
            confidence_label = 'Low'
        else:
            confidence_label = 'Very Low'
        
        logger.info(f"  WEIGHTED FINAL SCORE: {overall_confidence:.4f} ({overall_confidence*100:.1f}%) - {confidence_label}")
        
        return {
            'overall_confidence': round(overall_confidence, 4),
            'confidence_label': confidence_label,
            'breakdown': {
                'data_richness': round(data_richness_score, 4),
                'market_intelligence': round(market_intelligence_score, 4),
                'model_confidence': round(model_confidence_score, 4),
                'product_maturity': round(product_maturity_score, 4),
                'content_quality': round(content_quality_score, 4)
            },
            'details': {
                'data_richness': data_richness_details,
                'market_intelligence': market_intelligence_details,
                'model_confidence': model_details,
                'product_maturity': maturity_details,
                'content_quality': content_details
            }
        }
    
    # ========================================================================
    # DATA FETCHING HELPERS
    # ========================================================================
    
    def _fetch_competitor_data(self, product_id: int) -> List:
        """Fetch competitor prices for product"""
        if not self.db:
            return []
        
        from app.models.competitor import CompetitorPrice
        
        return self.db.query(CompetitorPrice).filter(
            CompetitorPrice.product_id == product_id
        ).order_by(CompetitorPrice.scraped_at.desc()).limit(10).all()
    
    def _fetch_sales_history(self, product_id: int) -> List:
        """Fetch sales history (last 90 days)"""
        if not self.db:
            return []
        
        from app.models.sales_history import SalesHistory
        
        cutoff_date = datetime.now().date() - timedelta(days=90)
        return self.db.query(SalesHistory).filter(
            SalesHistory.product_id == product_id,
            SalesHistory.sale_date >= cutoff_date
        ).order_by(SalesHistory.sale_date.desc()).all()
    
    def _fetch_price_history(self, product_id: int) -> List:
        """Fetch price history (last 90 days)"""
        if not self.db:
            return []
        
        from app.models.price_history import PriceHistory
        
        cutoff_date = datetime.now().date() - timedelta(days=90)
        return self.db.query(PriceHistory).filter(
            PriceHistory.product_id == product_id,
            PriceHistory.price_date >= cutoff_date
        ).order_by(PriceHistory.price_date.desc()).all()
    
    def _extract_competitor_prices(self, competitor_data: Optional[List]) -> List[float]:
        """Extract prices from competitor data (handles both objects and dicts)"""
        if not competitor_data:
            return []
        
        prices = []
        for item in competitor_data:
            if isinstance(item, dict):
                price = item.get('price', 0)
            else:
                price = getattr(item, 'price', 0)
            
            if price and price > 0:
                prices.append(float(price))
        
        return prices
    
    # ========================================================================
    # TIER 1: DATA RICHNESS (35%)
    # ========================================================================
    
    def _calculate_data_richness(
        self,
        product,
        sales_history: Optional[List],
        price_history: Optional[List]
    ) -> Tuple[float, Dict]:
        """
        Data Richness Score (35% weight)
        
        Components:
        - Sales History Richness (40%)
        - Price History Richness (30%)
        - Inventory Richness (30%)
        """
        
        sales_richness = self._calculate_sales_history_richness(product, sales_history or [])
        price_richness = self._calculate_price_history_richness(product, price_history or [])
        inventory_richness = self._calculate_inventory_richness(product, sales_history or [])
        
        data_richness_score = (
            sales_richness['score'] * 0.40 +
            price_richness['score'] * 0.30 +
            inventory_richness['score'] * 0.30
        )
        
        details = {
            'sales_richness': sales_richness,
            'price_richness': price_richness,
            'inventory_richness': inventory_richness
        }
        
        return data_richness_score, details
    
    def _calculate_sales_history_richness(
        self,
        product,
        sales_history: List
    ) -> Dict:
        """
        Sales History Richness
        
        Components:
        - Temporal Depth (25%): Days since created_at
        - Sales Volume (35%): Number of sales in 90d
        - Sales Consistency (20%): Volatility of daily sales
        - Recency (20%): Days since last sale
        """
        
        today = datetime.now()
        
        # 1. Temporal Depth
        if hasattr(product, 'created_at') and product.created_at:
            if isinstance(product.created_at, datetime):
                days_active = (today - product.created_at).days
            else:
                days_active = (today.date() - product.created_at).days
        else:
            days_active = 0
        
        depth_score = min(1.0, days_active / 180)
        
        # 2. Sales Volume (last 90 days)
        sales_90d = len(sales_history)
        
        if sales_90d >= 200:
            volume_score = 1.0
        elif sales_90d >= 100:
            volume_score = 0.9
        elif sales_90d >= 50:
            volume_score = 0.8
        elif sales_90d >= 20:
            volume_score = 0.6
        elif sales_90d >= 10:
            volume_score = 0.4
        else:
            volume_score = 0.2
        
        # 3. Sales Consistency
        if len(sales_history) > 7:
            # Extract quantities
            quantities = []
            for s in sales_history:
                if isinstance(s, dict):
                    qty = s.get('quantity_sold', s.get('quantity', 0))
                else:
                    qty = getattr(s, 'quantity_sold', 0)
                quantities.append(qty)
            
            if quantities:
                mean_sales = np.mean(quantities)
                if mean_sales > 0:
                    volatility = np.std(quantities) / mean_sales
                    consistency_score = max(0.0, 1.0 - min(1.0, volatility / 2.0))
                else:
                    consistency_score = 0.5
            else:
                consistency_score = 0.5
        else:
            consistency_score = 0.5
        
        # 4. Recency
        if sales_history:
            # Get last sale date
            last_sale_dates = []
            for s in sales_history:
                if isinstance(s, dict):
                    date = s.get('sale_date', s.get('date'))
                else:
                    date = getattr(s, 'sale_date', None)
                
                if date:
                    if isinstance(date, datetime):
                        last_sale_dates.append(date)
                    else:
                        last_sale_dates.append(datetime.combine(date, datetime.min.time()))
            
            if last_sale_dates:
                last_sale_date = max(last_sale_dates)
                days_since_last_sale = (today - last_sale_date).days
                
                if days_since_last_sale <= 7:
                    recency_score = 1.0
                elif days_since_last_sale <= 14:
                    recency_score = 0.9
                elif days_since_last_sale <= 30:
                    recency_score = 0.7
                elif days_since_last_sale <= 60:
                    recency_score = 0.5
                else:
                    recency_score = 0.2
            else:
                days_since_last_sale = None
                recency_score = 0.2
        else:
            days_since_last_sale = None
            recency_score = 0.2
        
        final_score = (
            depth_score * 0.25 +
            volume_score * 0.35 +
            consistency_score * 0.20 +
            recency_score * 0.20
        )
        
        return {
            'score': final_score,
            'depth_score': depth_score,
            'volume_score': volume_score,
            'consistency_score': consistency_score,
            'recency_score': recency_score,
            'days_active': days_active,
            'sales_90d': sales_90d,
            'days_since_last_sale': days_since_last_sale
        }
    
    def _calculate_price_history_richness(
        self,
        product,
        price_history: List
    ) -> Dict:
        """
        Price History Richness
        
        Components:
        - Price Changes Count (40%)
        - Price Range Tested (30%)
        - Price Stability (30%)
        """
        
        today = datetime.now()
        
        # 1. Price Changes Count
        price_changes = 0
        for p in price_history:
            if isinstance(p, dict):
                change_pct = p.get('price_change_pct', 0)
            else:
                change_pct = getattr(p, 'price_change_pct', None) or 0
            
            if change_pct and abs(change_pct) > 0.01:
                price_changes += 1
        
        changes_score = min(1.0, price_changes / 10)
        
        # 2. Price Range Tested
        if len(price_history) > 1:
            prices = []
            for p in price_history:
                if isinstance(p, dict):
                    price = p.get('price', 0)
                else:
                    price = getattr(p, 'price', 0)
                if price:
                    prices.append(float(price))
            
            if prices:
                current_price = float(product.price) if hasattr(product, 'price') and product.price else 1
                price_range_pct = (max(prices) - min(prices)) / current_price if current_price > 0 else 0
                range_score = min(1.0, price_range_pct / 0.3)
            else:
                price_range_pct = 0
                range_score = 0.3
        else:
            price_range_pct = 0
            range_score = 0.3
        
        # 3. Price Stability (recent 30 days)
        recent_prices = []
        for p in price_history:
            if isinstance(p, dict):
                price_date = p.get('price_date', p.get('date'))
                price = p.get('price', 0)
            else:
                price_date = getattr(p, 'price_date', None)
                price = getattr(p, 'price', 0)
            
            if price_date and price:
                if isinstance(price_date, datetime):
                    days_ago = (today - price_date).days
                else:
                    days_ago = (today.date() - price_date).days
                
                if days_ago <= 30:
                    recent_prices.append(float(price))
        
        if len(recent_prices) > 1:
            mean_price = np.mean(recent_prices)
            if mean_price > 0:
                volatility = np.std(recent_prices) / mean_price
                stability_score = max(0.0, 1.0 - min(1.0, volatility))
            else:
                stability_score = 0.7
        else:
            stability_score = 0.7
        
        final_score = (
            changes_score * 0.40 +
            range_score * 0.30 +
            stability_score * 0.30
        )
        
        return {
            'score': final_score,
            'changes_score': changes_score,
            'range_score': range_score,
            'stability_score': stability_score,
            'price_changes': price_changes,
            'price_range_pct': round(price_range_pct, 4)
        }
    
    def _calculate_inventory_richness(
        self,
        product,
        sales_history: List
    ) -> Dict:
        """
        Inventory Richness
        
        Components:
        - Turnover Rate (60%)
        - Days of Stock Adequacy (40%)
        """
        
        today = datetime.now()
        
        # Sales in last 30 days
        sales_30d = 0
        for s in sales_history:
            if isinstance(s, dict):
                sale_date = s.get('sale_date', s.get('date'))
            else:
                sale_date = getattr(s, 'sale_date', None)
            
            if sale_date:
                if isinstance(sale_date, datetime):
                    days_ago = (today - sale_date).days
                else:
                    days_ago = (today.date() - sale_date).days
                
                if days_ago <= 30:
                    sales_30d += 1
        
        # 1. Turnover Rate
        inventory = getattr(product, 'inventory_quantity', 0) or 1
        turnover_rate = sales_30d / inventory if inventory > 0 else 0
        
        if turnover_rate >= 5.0:
            turnover_score = 1.0
        elif turnover_rate >= 2.0:
            turnover_score = 0.9
        elif turnover_rate >= 1.0:
            turnover_score = 0.8
        elif turnover_rate >= 0.5:
            turnover_score = 0.6
        else:
            turnover_score = 0.4
        
        # 2. Days of Stock
        daily_sales = sales_30d / 30 if sales_30d > 0 else 0.01
        days_of_stock = inventory / daily_sales if daily_sales > 0 else 999
        
        if 30 <= days_of_stock <= 60:
            adequacy_score = 1.0
        elif 20 <= days_of_stock <= 90:
            adequacy_score = 0.9
        elif 10 <= days_of_stock <= 120:
            adequacy_score = 0.7
        else:
            adequacy_score = 0.5
        
        final_score = (
            turnover_score * 0.60 +
            adequacy_score * 0.40
        )
        
        return {
            'score': final_score,
            'turnover_score': turnover_score,
            'adequacy_score': adequacy_score,
            'turnover_rate': round(turnover_rate, 2),
            'days_of_stock': round(days_of_stock, 1),
            'sales_30d': sales_30d
        }
    
    # ========================================================================
    # TIER 2: MARKET INTELLIGENCE (30%) - KEY FOR VARIANCE!
    # ========================================================================
    
    def _calculate_market_intelligence(
        self,
        product,
        competitor_prices: List[float],
        competitor_data: Optional[List] = None
    ) -> Tuple[float, Dict]:
        """
        Market Intelligence Score (30% weight)
        
        Components:
        - Price Position Score (50%): Our price vs. competitor avg
        - Market Consistency Score (30%): How tight is competitor range
        - Data Quality Score (20%): Freshness & completeness
        """
        
        if not competitor_prices or len(competitor_prices) == 0:
            return 0.3, {
                'price_position': {'score': 0.3, 'reason': 'no_competitors'},
                'market_consistency': {'score': 0.5, 'reason': 'no_data'},
                'data_quality': {'score': 0.1, 'reason': 'no_data'}
            }
        
        # A) Price Position Score (50%)
        price_position = self._calculate_price_position_score(product, competitor_prices)
        
        # B) Market Consistency Score (30%)
        market_consistency = self._calculate_market_consistency_score(competitor_prices)
        
        # C) Data Quality Score (20%)
        data_quality = self._calculate_competitor_data_quality(competitor_data or [])
        
        market_intelligence_score = (
            price_position['score'] * 0.50 +
            market_consistency['score'] * 0.30 +
            data_quality['score'] * 0.20
        )
        
        details = {
            'price_position': price_position,
            'market_consistency': market_consistency,
            'data_quality': data_quality
        }
        
        return market_intelligence_score, details
    
    def _calculate_price_position_score(
        self,
        product,
        competitor_prices: List[float]
    ) -> Dict:
        """
        Price Position Score - How well priced vs. competitors
        
        Optimal: -5% to +5% of competitor average
        """
        
        current_price = float(getattr(product, 'price', 0)) if hasattr(product, 'price') else 0
        comp_avg = np.mean(competitor_prices)
        comp_min = min(competitor_prices)
        comp_max = max(competitor_prices)
        
        if comp_avg == 0:
            return {'score': 0.5, 'reason': 'invalid_competitor_avg'}
        
        # Price difference percentage
        price_diff_pct = ((current_price - comp_avg) / comp_avg) * 100
        
        # Position score based on difference
        if -5 <= price_diff_pct <= 5:
            position_score = 1.0  # Perfect!
        elif -10 <= price_diff_pct < -5:
            position_score = 0.9  # Slightly cheaper = good
        elif 5 < price_diff_pct <= 10:
            position_score = 0.85  # Slightly more expensive = OK
        elif -15 <= price_diff_pct < -10:
            position_score = 0.75  # Too cheap
        elif 10 < price_diff_pct <= 15:
            position_score = 0.70  # Too expensive
        elif -20 <= price_diff_pct < -15:
            position_score = 0.60  # Way too cheap
        elif 15 < price_diff_pct <= 20:
            position_score = 0.55  # Way too expensive
        elif price_diff_pct < -20:
            position_score = 0.40  # Massive underpricing
        else:  # > +20%
            position_score = 0.30  # Massive overpricing
        
        # Position in range (percentile)
        price_range = comp_max - comp_min
        if price_range > 0:
            position_in_range = (current_price - comp_min) / price_range
            
            if 0.25 <= position_in_range <= 0.75:
                range_position_score = 1.0  # Middle 50%
            elif 0.10 <= position_in_range < 0.25:
                range_position_score = 0.8  # Lower quartile
            elif 0.75 < position_in_range <= 0.90:
                range_position_score = 0.8  # Upper quartile
            else:
                range_position_score = 0.5  # Extreme
        else:
            position_in_range = 0.5
            range_position_score = 0.7
        
        final_score = position_score * 0.70 + range_position_score * 0.30
        
        return {
            'score': final_score,
            'position_score': position_score,
            'range_position_score': range_position_score,
            'current_price': current_price,
            'competitor_avg': round(comp_avg, 2),
            'price_diff_pct': round(price_diff_pct, 2),
            'position_in_range': round(position_in_range, 2),
            'competitor_min': round(comp_min, 2),
            'competitor_max': round(comp_max, 2)
        }
    
    def _calculate_market_consistency_score(
        self,
        competitor_prices: List[float]
    ) -> Dict:
        """
        Market Consistency Score - How tight is the market
        
        Low CV = tight market = higher confidence
        """
        
        comp_avg = np.mean(competitor_prices)
        comp_std = np.std(competitor_prices)
        comp_min = min(competitor_prices)
        comp_max = max(competitor_prices)
        
        # Coefficient of Variation (CV)
        cv = comp_std / comp_avg if comp_avg > 0 else 0
        
        if cv <= 0.10:
            consistency_score = 1.0  # Very tight (±10%)
        elif cv <= 0.20:
            consistency_score = 0.9  # Tight (±20%)
        elif cv <= 0.30:
            consistency_score = 0.7  # Normal
        elif cv <= 0.40:
            consistency_score = 0.5  # Wide
        else:
            consistency_score = 0.3  # Chaotic
        
        # Absolute price range
        price_range_pct = ((comp_max - comp_min) / comp_avg) * 100 if comp_avg > 0 else 0
        
        if price_range_pct <= 20:
            range_score = 1.0  # Very narrow
        elif price_range_pct <= 40:
            range_score = 0.9  # Narrow
        elif price_range_pct <= 60:
            range_score = 0.7  # Normal
        elif price_range_pct <= 80:
            range_score = 0.5  # Wide
        else:
            range_score = 0.3  # Very wide
        
        final_score = consistency_score * 0.60 + range_score * 0.40
        
        return {
            'score': final_score,
            'consistency_score': consistency_score,
            'range_score': range_score,
            'cv': round(cv, 4),
            'price_range_pct': round(price_range_pct, 2),
            'competitor_count': len(competitor_prices)
        }
    
    def _calculate_competitor_data_quality(
        self,
        competitor_data: List
    ) -> Dict:
        """
        Competitor Data Quality Score
        
        Components:
        - Competitor Count (40%)
        - Data Freshness (40%)
        - Data Completeness (20%)
        """
        
        today = datetime.now()
        
        # 1. Competitor Count
        competitor_count = len(competitor_data)
        
        if competitor_count >= 5:
            count_score = 1.0
        elif competitor_count >= 3:
            count_score = 0.8
        elif competitor_count >= 1:
            count_score = 0.5
        else:
            count_score = 0.1
        
        # 2. Data Freshness
        if competitor_data:
            last_scrape_dates = []
            for c in competitor_data:
                if isinstance(c, dict):
                    scraped_at = c.get('scraped_at', c.get('date'))
                else:
                    scraped_at = getattr(c, 'scraped_at', None)
                
                if scraped_at:
                    # Convert string to datetime if needed
                    if isinstance(scraped_at, str):
                        try:
                            from dateutil import parser
                            scraped_at = parser.parse(scraped_at)
                        except:
                            try:
                                scraped_at = datetime.fromisoformat(scraped_at.replace('Z', '+00:00'))
                            except:
                                continue
                    
                    # Convert datetime to date if needed
                    if isinstance(scraped_at, datetime):
                        last_scrape_dates.append(scraped_at)
                    elif isinstance(scraped_at, datetime.date):
                        last_scrape_dates.append(datetime.combine(scraped_at, datetime.min.time()))
            
            if last_scrape_dates:
                last_scrape = max(last_scrape_dates)
                days_since_scrape = (today - last_scrape).days
                
                if days_since_scrape <= 1:
                    freshness_score = 1.0
                elif days_since_scrape <= 3:
                    freshness_score = 0.9
                elif days_since_scrape <= 7:
                    freshness_score = 0.7
                elif days_since_scrape <= 14:
                    freshness_score = 0.5
                else:
                    freshness_score = 0.2
            else:
                days_since_scrape = None
                freshness_score = 0.5  # Default if we can't parse dates
        else:
            days_since_scrape = None
            freshness_score = 0.1
        
        # 3. Data Completeness
        complete_count = 0
        for c in competitor_data:
            if isinstance(c, dict):
                price = c.get('price', 0)
            else:
                price = getattr(c, 'price', None) or 0
            
            if price and price > 0:
                complete_count += 1
        
        completeness_score = complete_count / len(competitor_data) if competitor_data else 0
        
        final_score = (
            count_score * 0.40 +
            freshness_score * 0.40 +
            completeness_score * 0.20
        )
        
        return {
            'score': final_score,
            'count_score': count_score,
            'freshness_score': freshness_score,
            'completeness_score': completeness_score,
            'competitor_count': competitor_count,
            'days_since_scrape': days_since_scrape,
            'complete_count': complete_count
        }
    
    # ========================================================================
    # TIER 4: MODEL CONFIDENCE (10%)
    # ========================================================================
    
    def _calculate_model_confidence(
        self,
        ml_output: Dict
    ) -> Tuple[float, Dict]:
        """
        Model confidence based on XGBoost Kaggle predictions
        
        XGBoost models (91.2% test, 92.0% ± 0.8% CV) provide strong signals.
        Confidence scores are well-calibrated due to cross-validation.
        
        Confidence calculation:
        - If both ml_detector and meta_labeler agree (>0.6 or <0.4): HIGH confidence
        - If they disagree (one >0.6, one <0.4): LOW confidence
        - Distance from 0.5 indicates prediction strength
        """
        
        ml_detector_proba = ml_output.get('ml_detector_proba', 0.5)
        meta_labeler_proba = ml_output.get('meta_labeler_proba', 0.5)
        
        # Default if None
        if ml_detector_proba is None:
            ml_detector_proba = 0.5
        if meta_labeler_proba is None:
            meta_labeler_proba = 0.5
        
        # Since both use same XGBoost model now, they should agree
        # But keep logic for potential future ensemble
        
        # Check agreement
        both_high = ml_detector_proba > 0.6 and meta_labeler_proba > 0.6
        both_low = ml_detector_proba < 0.4 and meta_labeler_proba < 0.4
        disagree = (ml_detector_proba > 0.6 and meta_labeler_proba < 0.4) or (ml_detector_proba < 0.4 and meta_labeler_proba > 0.6)
        
        if both_high or both_low:
            # Strong agreement - high confidence
            avg_proba = (ml_detector_proba + meta_labeler_proba) / 2
            distance_from_middle = abs(avg_proba - 0.5)
            base_confidence = 0.7 + (distance_from_middle * 0.6)  # 0.7-1.0
        elif disagree:
            # Disagreement - low confidence
            base_confidence = 0.3
        else:
            # Mild signals - medium confidence
            avg_proba = (ml_detector_proba + meta_labeler_proba) / 2
            distance_from_middle = abs(avg_proba - 0.5)
            base_confidence = 0.5 + (distance_from_middle * 0.4)  # 0.5-0.7
        
        # Normalize to 0-1
        model_confidence = min(max(base_confidence, 0.0), 1.0)
        
        details = {
            'avg_proba': round((ml_detector_proba + meta_labeler_proba) / 2, 4),
            'agreement': round(1.0 - abs(ml_detector_proba - meta_labeler_proba), 4),
            'ml_detector_proba': ml_detector_proba,
            'meta_labeler_proba': meta_labeler_proba,
            'confidence_level': 'high' if model_confidence >= 0.7 else 'medium' if model_confidence >= 0.5 else 'low'
        }
        
        return model_confidence, details
    
    # ========================================================================
    # TIER 5: PRODUCT MATURITY (15%)
    # ========================================================================
    
    def _calculate_product_maturity(
        self,
        product,
        sales_history: List,
        price_history: List
    ) -> Tuple[float, Dict]:
        """
        Product Maturity Score (15% weight)
        
        Components:
        - Product Age (60%)
        - Data Maturity (40%): How many data points collected
        """
        
        today = datetime.now()
        
        # 1. Product Age
        if hasattr(product, 'created_at') and product.created_at:
            if isinstance(product.created_at, datetime):
                days_active = (today - product.created_at).days
            else:
                days_active = (today.date() - product.created_at).days
        else:
            days_active = 0
        
        if days_active >= 180:
            age_score = 1.0
        elif days_active >= 90:
            age_score = 0.9
        elif days_active >= 30:
            age_score = 0.7
        elif days_active >= 7:
            age_score = 0.5
        else:
            age_score = 0.3
        
        # 2. Data Maturity (data points collected)
        sales_count = len(sales_history)
        price_changes = len(price_history)
        data_points = sales_count + price_changes
        
        data_maturity = min(1.0, data_points / 100)  # 100+ = 1.0
        
        # Final score
        final_score = age_score * 0.60 + data_maturity * 0.40
        
        details = {
            'age_score': age_score,
            'data_maturity': data_maturity,
            'days_active': days_active,
            'sales_count': sales_count,
            'price_changes': price_changes,
            'total_data_points': data_points
        }
        
        return final_score, details
    
    # ========================================================================
    # TIER 6: PRODUCT CONTENT QUALITY (10%) - NEW
    # ========================================================================
    
    def _calculate_content_quality(
        self,
        product
    ) -> Tuple[float, Dict]:
        """
        Product Content Quality Score (10% weight)
        
        Components:
        - Title Quality (30%)
        - Description Quality (30%)
        - Image Count (25%)
        - Tags Count (15%)
        
        Note: If Shopify metadata not available, use basic fields only
        """
        
        # 1. Title Quality
        title = getattr(product, 'title', '') or ''
        title_length = len(title)
        
        if title_length >= 50:
            title_score = 1.0
        elif title_length >= 30:
            title_score = 0.8
        elif title_length >= 15:
            title_score = 0.6
        else:
            title_score = 0.3
        
        # 2. Description Quality (from meta_data if available)
        description = ""
        if hasattr(product, 'meta_data') and product.meta_data:
            import json
            try:
                meta = json.loads(product.meta_data) if isinstance(product.meta_data, str) else product.meta_data
                if isinstance(meta, dict):
                    description = meta.get('description', '') or ''
            except:
                description = ""
        
        desc_length = len(description)
        
        if desc_length >= 500:
            desc_score = 1.0
        elif desc_length >= 200:
            desc_score = 0.8
        elif desc_length >= 50:
            desc_score = 0.6
        else:
            desc_score = 0.3
        
        # 3. Image Count (from meta_data if available)
        image_count = 0
        if hasattr(product, 'meta_data') and product.meta_data:
            try:
                import json
                meta = json.loads(product.meta_data) if isinstance(product.meta_data, str) else product.meta_data
                if isinstance(meta, dict):
                    images = meta.get('images', [])
                    image_count = len(images) if isinstance(images, list) else 0
            except:
                image_count = 0
        
        if image_count >= 5:
            image_score = 1.0
        elif image_count >= 3:
            image_score = 0.8
        elif image_count >= 1:
            image_score = 0.6
        else:
            image_score = 0.2
        
        # 4. Tags Count (from meta_data if available)
        tags_count = 0
        if hasattr(product, 'meta_data') and product.meta_data:
            try:
                import json
                meta = json.loads(product.meta_data) if isinstance(product.meta_data, str) else product.meta_data
                if isinstance(meta, dict):
                    tags = meta.get('tags', [])
                    tags_count = len(tags) if isinstance(tags, list) else 0
            except:
                tags_count = 0
        
        if tags_count >= 5:
            tags_score = 1.0
        elif tags_count >= 3:
            tags_score = 0.8
        elif tags_count >= 1:
            tags_score = 0.6
        else:
            tags_score = 0.3
        
        # Final score
        final_score = (
            title_score * 0.30 +
            desc_score * 0.30 +
            image_score * 0.25 +
            tags_score * 0.15
        )
        
        details = {
            'title_score': title_score,
            'desc_score': desc_score,
            'image_score': image_score,
            'tags_score': tags_score,
            'title_length': title_length,
            'desc_length': desc_length,
            'image_count': image_count,
            'tags_count': tags_count
        }
        
        return final_score, details
