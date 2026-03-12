"""
Price Trend Features für ML Feature Engineering
Nutzt PriceHistoryService für 10 neue ML-Features
"""
from sqlalchemy.orm import Session
from typing import Dict
import pandas as pd
import numpy as np
import logging
from app.services.price_history_service import PriceHistoryService

logger = logging.getLogger(__name__)


def calculate_price_trend_features(
    db: Session,
    product_id: int,
    shop_id: int
) -> Dict:
    """
    Berechnet Price Trend Features aus Price History.
    
    Returns:
        Dict mit 10 Features:
        - price_volatility_7d / 30d
        - price_trend_slope
        - price_change_frequency
        - price_max_change_30d / min / avg
        - price_stability_score
        - price_momentum
        - price_acceleration
    """
    features = {}
    
    if not product_id:
        # Fallback: Keine Features wenn Product nicht in DB
        return _get_default_price_features()
    
    try:
        service = PriceHistoryService(db)
        
        # Lade Price History
        trend_7d = service.get_price_trend(product_id, shop_id, days_back=7)
        trend_30d = service.get_price_trend(product_id, shop_id, days_back=30)
        
        # Feature 1-2: Price Volatility
        features['price_volatility_7d'] = service.calculate_volatility(product_id, shop_id, days_back=7)
        features['price_volatility_30d'] = service.calculate_volatility(product_id, shop_id, days_back=30)
        
        # Feature 3: Price Trend Slope (Regression)
        if not trend_30d.empty and len(trend_30d) >= 2:
            try:
                from scipy import stats
                x = np.arange(len(trend_30d))
                y = trend_30d['price'].values
                slope, _, _, _, _ = stats.linregress(x, y)
                features['price_trend_slope'] = float(slope)
            except ImportError:
                # Fallback wenn scipy nicht verfügbar
                features['price_trend_slope'] = 0.0
            except Exception as e:
                logger.warning(f"Fehler bei Trend Slope: {e}")
                features['price_trend_slope'] = 0.0
        else:
            features['price_trend_slope'] = 0.0
        
        # Feature 4: Price Change Frequency
        stats_30d = service.get_price_statistics(product_id, shop_id, days_back=30)
        features['price_change_frequency'] = stats_30d['price_changes'] / 30.0 if stats_30d['price_changes'] else 0.0
        
        # Feature 5-7: Price Change Statistics
        if not trend_30d.empty and 'price_change_pct' in trend_30d.columns:
            price_changes = trend_30d['price_change_pct'].dropna()
            if len(price_changes) > 0:
                features['price_max_change_30d'] = float(price_changes.max())
                features['price_min_change_30d'] = float(price_changes.min())
                features['price_avg_change_30d'] = float(price_changes.mean())
            else:
                features['price_max_change_30d'] = 0.0
                features['price_min_change_30d'] = 0.0
                features['price_avg_change_30d'] = 0.0
        else:
            features['price_max_change_30d'] = 0.0
            features['price_min_change_30d'] = 0.0
            features['price_avg_change_30d'] = 0.0
        
        # Feature 8: Price Stability Score (invers zu Volatilität)
        features['price_stability_score'] = 1.0 / (1.0 + features['price_volatility_30d']) if features['price_volatility_30d'] > 0 else 1.0
        
        # Feature 9: Price Momentum (Rate of Change)
        if not trend_7d.empty and len(trend_7d) >= 2:
            recent_changes = trend_7d['price_change_pct'].dropna()
            if len(recent_changes) > 0:
                features['price_momentum'] = float(recent_changes.mean())
            else:
                features['price_momentum'] = 0.0
        else:
            features['price_momentum'] = 0.0
        
        # Feature 10: Price Acceleration (Change in Momentum)
        if not trend_30d.empty and len(trend_30d) >= 3:
            midpoint = len(trend_30d) // 2
            first_half = trend_30d.iloc[:midpoint]['price_change_pct'].dropna().mean()
            second_half = trend_30d.iloc[midpoint:]['price_change_pct'].dropna().mean()
            features['price_acceleration'] = float(second_half - first_half) if not pd.isna(second_half) and not pd.isna(first_half) else 0.0
        else:
            features['price_acceleration'] = 0.0
        
    except Exception as e:
        logger.warning(f"Fehler bei Price Features: {e}")
        return _get_default_price_features()
    
    # Clamp values
    for key in features:
        if 'volatility' in key or 'frequency' in key:
            features[key] = np.clip(features[key], 0.0, 10.0)
        elif 'slope' in key or 'momentum' in key or 'acceleration' in key:
            features[key] = np.clip(features[key], -1.0, 1.0)
        elif 'stability' in key:
            features[key] = np.clip(features[key], 0.0, 1.0)
    
    return features


def _get_default_price_features() -> Dict:
    """Fallback: Default-Werte wenn keine Price History verfügbar"""
    return {
        'price_volatility_7d': 0.0,
        'price_volatility_30d': 0.0,
        'price_trend_slope': 0.0,
        'price_change_frequency': 0.0,
        'price_max_change_30d': 0.0,
        'price_min_change_30d': 0.0,
        'price_avg_change_30d': 0.0,
        'price_stability_score': 0.5,
        'price_momentum': 0.0,
        'price_acceleration': 0.0
    }
