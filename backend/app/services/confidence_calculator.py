"""
Confidence Calculator Service

Berechnet produkt-spezifische Confidence Scores basierend auf 4 gewichteten Komponenten:
1. Feature Availability (40%) - Nutzt FeatureConfidenceAnalyzer
2. Data Quality (30%) - Sales History, Velocity, Inventory
3. Competitor Coverage (15%) - Anzahl Competitors
4. Model Confidence (15%) - ML Prediction Uncertainty
"""

from typing import Dict, Optional, List
import logging
from datetime import datetime, timedelta
from app.services.confidence_analyzer import FeatureConfidenceAnalyzer

logger = logging.getLogger(__name__)

# Gewichtungen
WEIGHTS = {
    "feature_availability": 0.40,  # 40%
    "data_quality": 0.30,          # 30%
    "competitor_coverage": 0.15,    # 15%
    "model_confidence": 0.15        # 15%
}

# Data Quality Thresholds
SALES_HISTORY_THRESHOLDS = {
    90: 1.0,   # 90+ Tage = perfekt
    50: 0.83,  # 50-89 Tage = sehr gut
    20: 0.5,   # 20-49 Tage = okay
    10: 0.25,  # 10-19 Tage = niedrig
    0: 0.1     # <10 Tage = sehr niedrig
}

# Competitor Coverage Thresholds
COMPETITOR_THRESHOLDS = {
    5: 1.0,    # 5+ = perfekt
    3: 0.6,    # 3-4 = gut
    1: 0.3,    # 1-2 = niedrig
    0: 0.1     # 0 = minimum (nicht 0.0!)
}


class ConfidenceCalculator:
    """
    Berechnet produkt-spezifische Confidence Scores basierend auf:
    1. Feature Availability (40%) - Nutzt FeatureConfidenceAnalyzer
    2. Data Quality (30%) - Sales History, Velocity, Inventory
    3. Competitor Coverage (15%) - Anzahl Competitors
    4. Model Confidence (15%) - ML Prediction Uncertainty
    """
    
    def __init__(self):
        """Initialisiert ConfidenceCalculator mit FeatureConfidenceAnalyzer"""
        self.feature_analyzer = FeatureConfidenceAnalyzer()
    
    def calculate_overall_confidence(
        self,
        product,
        features: Dict[str, float],
        recommendation_data: Dict,
        ml_output: Dict
    ) -> Dict:
        """
        Berechnet Overall Confidence mit Breakdown.
        
        Args:
            product: Product Model
            features: Dictionary of feature_name -> feature_value (80 Features)
            recommendation_data: {
                "sales_7d": int,
                "sales_30d": int,
                "sales_90d": int (optional),
                "competitor_count": int,
                "inventory_quantity": int,
                "days_since_first_sale": int (optional),
                "sales_velocity": float (optional)
            }
            ml_output: {
                "ml_detector_proba": float (0-1),
                "meta_labeler_proba": float (0-1)
            }
        
        Returns:
            {
                "overall_confidence": 0.85,  # 0-1
                "breakdown": {
                    "feature_availability": {"score": 0.961, "weight": 0.40},
                    "data_quality": {"score": 0.75, "weight": 0.30},
                    "competitor_coverage": {"score": 1.0, "weight": 0.15},
                    "model_confidence": {"score": 0.92, "weight": 0.15}
                }
            }
        """
        try:
            logger.info(f"🔍 [ConfidenceCalculator] Starting calculation for Product {product.id}")
            logger.info(f"🔍 [ConfidenceCalculator] Features count: {len(features)}")
            logger.info(f"🔍 [ConfidenceCalculator] Recommendation data: {recommendation_data}")
            logger.info(f"🔍 [ConfidenceCalculator] ML output: {ml_output}")
            
            # 1. Feature Availability (40%)
            logger.debug(f"🔍 [ConfidenceCalculator] Calculating feature_confidence...")
            feature_conf = self._calculate_feature_confidence(product, features)
            logger.debug(f"✅ [ConfidenceCalculator] feature_confidence: {feature_conf:.3f}")
            
            # 2. Data Quality (30%)
            logger.debug(f"🔍 [ConfidenceCalculator] Calculating data_quality...")
            data_quality = self._calculate_data_quality(product, recommendation_data)
            logger.debug(f"✅ [ConfidenceCalculator] data_quality: {data_quality:.3f}")
            
            # 3. Competitor Coverage (15%)
            logger.debug(f"🔍 [ConfidenceCalculator] Calculating competitor_coverage...")
            competitor_conf = self._calculate_competitor_coverage(recommendation_data)
            logger.debug(f"✅ [ConfidenceCalculator] competitor_coverage: {competitor_conf:.3f}")
            
            # 4. Model Confidence (15%)
            logger.debug(f"🔍 [ConfidenceCalculator] Calculating model_confidence...")
            model_conf = self._calculate_model_confidence(ml_output)
            logger.debug(f"✅ [ConfidenceCalculator] model_confidence: {model_conf:.3f}")
            
            # Weighted Average
            overall = (
                feature_conf * WEIGHTS["feature_availability"] +
                data_quality * WEIGHTS["data_quality"] +
                competitor_conf * WEIGHTS["competitor_coverage"] +
                model_conf * WEIGHTS["model_confidence"]
            )
            
            # Clamp to 0-1
            overall = max(0.0, min(1.0, overall))
            
            breakdown = {
                "feature_availability": {
                    "score": round(feature_conf, 3),
                    "weight": WEIGHTS["feature_availability"]
                },
                "data_quality": {
                    "score": round(data_quality, 3),
                    "weight": WEIGHTS["data_quality"]
                },
                "competitor_coverage": {
                    "score": round(competitor_conf, 3),
                    "weight": WEIGHTS["competitor_coverage"]
                },
                "model_confidence": {
                    "score": round(model_conf, 3),
                    "weight": WEIGHTS["model_confidence"]
                }
            }
            
            # Debug Logging
            logger.debug(f"[ConfidenceCalculator] Product {product.id}:")
            logger.debug(f"  Feature Availability: {feature_conf:.3f} (weight: {WEIGHTS['feature_availability']})")
            logger.debug(f"  Data Quality: {data_quality:.3f} (weight: {WEIGHTS['data_quality']})")
            logger.debug(f"  Competitor Coverage: {competitor_conf:.3f} (weight: {WEIGHTS['competitor_coverage']})")
            logger.debug(f"  Model Confidence: {model_conf:.3f} (weight: {WEIGHTS['model_confidence']})")
            logger.debug(f"  Overall: {overall:.3f}")
            
            return {
                "overall_confidence": round(overall, 3),
                "breakdown": breakdown
            }
            
        except Exception as e:
            logger.error("=" * 70)
            logger.error(f"❌ [ConfidenceCalculator] ERROR calculating confidence for product {product.id}")
            logger.error(f"❌ [ConfidenceCalculator] Exception type: {type(e).__name__}")
            logger.error(f"❌ [ConfidenceCalculator] Error message: {str(e)}")
            import traceback
            logger.error(f"❌ [ConfidenceCalculator] Full traceback:\n{traceback.format_exc()}")
            logger.error("=" * 70)
            # Fallback: Return default confidence
            return {
                "overall_confidence": 0.5,
                "breakdown": {
                    "feature_availability": {"score": 0.5, "weight": WEIGHTS["feature_availability"]},
                    "data_quality": {"score": 0.5, "weight": WEIGHTS["data_quality"]},
                    "competitor_coverage": {"score": 0.5, "weight": WEIGHTS["competitor_coverage"]},
                    "model_confidence": {"score": 0.5, "weight": WEIGHTS["model_confidence"]}
                }
            }
    
    def _calculate_feature_confidence(
        self,
        product,
        features: Dict[str, float]
    ) -> float:
        """
        Nutzt bestehenden FeatureConfidenceAnalyzer.
        
        Args:
            product: Product Model
            features: Dictionary of feature_name -> feature_value
        
        Returns:
            0-1 (z.B. 0.961 = 96.1%)
        """
        try:
            # Nutze FeatureConfidenceAnalyzer
            analysis = self.feature_analyzer.analyze_confidence(
                features=features,
                include_explanations=False  # Schneller ohne Explanations
            )
            
            # overall_confidence ist 0-100, konvertiere zu 0-1
            overall_percentage = analysis.get("overall_confidence", 50.0)
            confidence = overall_percentage / 100.0
            
            return max(0.0, min(1.0, confidence))
            
        except Exception as e:
            logger.warning(f"Error calculating feature confidence: {e}")
            return 0.5  # Fallback
    
    def _calculate_data_quality(
        self,
        product,
        recommendation_data: Dict
    ) -> float:
        """
        Berechnet Data Quality basierend auf:
        - Sales History Depth (90d=1.0, 50d=0.83, 20d=0.5, 10d=0.25, <10d=0.1)
        - Sales Velocity (high=bonus, low=penalty)
        - Inventory Availability (in stock vs out of stock)
        
        Args:
            product: Product Model
            recommendation_data: {
                "sales_7d": int,
                "sales_30d": int,
                "sales_90d": int (optional),
                "days_since_first_sale": int (optional),
                "sales_velocity": float (optional),
                "inventory_quantity": int
            }
        
        Returns:
            0-1
        """
        try:
            # 1. Sales History Depth Score
            sales_history_score = self._calculate_sales_history_score(recommendation_data)
            
            # 2. Sales Velocity Score (bonus/penalty)
            velocity_score = self._calculate_velocity_score(recommendation_data)
            
            # 3. Inventory Availability Score
            inventory_score = self._calculate_inventory_score(product, recommendation_data)
            
            # Weighted combination
            # Sales History: 60% (most important)
            # Velocity: 25% (bonus/penalty)
            # Inventory: 15% (availability)
            data_quality = (
                sales_history_score * 0.60 +
                velocity_score * 0.25 +
                inventory_score * 0.15
            )
            
            return max(0.0, min(1.0, data_quality))
            
        except Exception as e:
            logger.warning(f"Error calculating data quality: {e}")
            return 0.5  # Fallback
    
    def _calculate_sales_history_score(self, recommendation_data: Dict) -> float:
        """
        Berechnet Sales History Depth Score basierend auf verfügbaren Tagen.
        
        Returns:
            0.1-1.0
        """
        # Versuche days_since_first_sale zu nutzen
        days_since_first = recommendation_data.get("days_since_first_sale")
        
        if days_since_first is not None and days_since_first > 0:
            # Nutze days_since_first_sale
            if days_since_first >= 90:
                return SALES_HISTORY_THRESHOLDS[90]
            elif days_since_first >= 50:
                return SALES_HISTORY_THRESHOLDS[50]
            elif days_since_first >= 20:
                return SALES_HISTORY_THRESHOLDS[20]
            elif days_since_first >= 10:
                return SALES_HISTORY_THRESHOLDS[10]
            else:
                return SALES_HISTORY_THRESHOLDS[0]
        
        # Fallback: Nutze sales_90d, sales_30d, sales_7d
        sales_90d = recommendation_data.get("sales_90d", 0)
        sales_30d = recommendation_data.get("sales_30d", 0)
        sales_7d = recommendation_data.get("sales_7d", 0)
        
        # Wenn sales_90d vorhanden → 90+ Tage
        if sales_90d is not None and sales_90d > 0:
            return SALES_HISTORY_THRESHOLDS[90]
        
        # Wenn sales_30d vorhanden → 30-49 Tage (schätze 30)
        if sales_30d is not None and sales_30d > 0:
            return SALES_HISTORY_THRESHOLDS[20]  # Zwischen 20-49
        
        # Wenn sales_7d vorhanden → 7-19 Tage
        if sales_7d is not None and sales_7d > 0:
            return SALES_HISTORY_THRESHOLDS[10]  # Zwischen 10-19
        
        # Keine Sales-Daten
        return SALES_HISTORY_THRESHOLDS[0]
    
    def _calculate_velocity_score(self, recommendation_data: Dict) -> float:
        """
        Berechnet Sales Velocity Score (bonus/penalty).
        
        High velocity = bonus (1.0-1.1)
        Low velocity = penalty (0.5-1.0)
        No velocity = 0.8 (neutral)
        
        Returns:
            0.5-1.1
        """
        sales_velocity = recommendation_data.get("sales_velocity")
        
        if sales_velocity is None:
            # Versuche aus sales_7d zu berechnen
            sales_7d = recommendation_data.get("sales_7d", 0)
            if sales_7d is not None and sales_7d > 0:
                sales_velocity = sales_7d / 7.0  # Sales pro Tag
            else:
                return 0.8  # Neutral wenn keine Daten
        
        # High velocity (>5 sales/day) = bonus
        if sales_velocity >= 5.0:
            return 1.1  # Bonus
        elif sales_velocity >= 2.0:
            return 1.0  # Gut
        elif sales_velocity >= 0.5:
            return 0.9  # Okay
        elif sales_velocity > 0:
            return 0.7  # Niedrig
        else:
            return 0.5  # Sehr niedrig
    
    def _calculate_inventory_score(
        self,
        product,
        recommendation_data: Dict
    ) -> float:
        """
        Berechnet Inventory Availability Score.
        
        In stock (>0) = 1.0
        Out of stock (0) = 0.5
        
        Returns:
            0.5-1.0
        """
        inventory = recommendation_data.get("inventory_quantity")
        
        if inventory is None:
            # Versuche aus product zu holen
            inventory = getattr(product, "inventory_quantity", 0)
        
        if inventory is None:
            inventory = 0
        
        # In stock = 1.0, Out of stock = 0.5
        return 1.0 if inventory > 0 else 0.5
    
    def _calculate_competitor_coverage(self, recommendation_data: Dict) -> float:
        """
        Berechnet Competitor Coverage basierend auf Anzahl.
        
        Args:
            recommendation_data: {
                "competitor_count": int
            }
        
        Returns:
            0.1-1.0
        """
        competitor_count = recommendation_data.get("competitor_count", 0)
        
        if competitor_count is None:
            competitor_count = 0
        
        # Mapping basierend auf Thresholds
        if competitor_count >= 5:
            return COMPETITOR_THRESHOLDS[5]
        elif competitor_count >= 3:
            return COMPETITOR_THRESHOLDS[3]
        elif competitor_count >= 1:
            return COMPETITOR_THRESHOLDS[1]
        else:
            return COMPETITOR_THRESHOLDS[0]  # Minimum 0.1 (nicht 0.0!)
    
    def _calculate_model_confidence(self, ml_output: Dict) -> float:
        """
        Berechnet Model Confidence basierend auf:
        - ml_detector_proba (average)
        - meta_labeler_proba (average)
        - Penalty für niedrige Probabilities
        
        Args:
            ml_output: {
                "ml_detector_proba": float (0-1),
                "meta_labeler_proba": float (0-1)
            }
        
        Returns:
            0-1
        """
        try:
            ml_detector_proba = ml_output.get("ml_detector_proba", 0.5)
            meta_labeler_proba = ml_output.get("meta_labeler_proba", 0.5)
            
            # Default falls None
            if ml_detector_proba is None:
                ml_detector_proba = 0.5
            if meta_labeler_proba is None:
                meta_labeler_proba = 0.5
            
            # Average der beiden Probabilities
            avg_proba = (ml_detector_proba + meta_labeler_proba) / 2.0
            
            # Clamp to 0-1
            return max(0.0, min(1.0, avg_proba))
            
        except Exception as e:
            logger.warning(f"Error calculating model confidence: {e}")
            return 0.5  # Fallback
