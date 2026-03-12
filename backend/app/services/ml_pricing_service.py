"""
Production ML Service für Pricing Predictions
"""

import joblib
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime
from sqlalchemy.orm import Session
import math

from app.services.feature_engineering_service import FeatureEngineeringService
from app.models.product import Product
import time
import logging

logger = logging.getLogger(__name__)

# Optional: ML Monitoring (falls verfügbar)
try:
    from app.services.ml_monitoring_service import ml_monitoring
    ML_MONITORING_AVAILABLE = True
except ImportError:
    ML_MONITORING_AVAILABLE = False
    logger.warning("[ML_PRICING_SERVICE] ML monitoring service not available - monitoring disabled")

logger = logging.getLogger(__name__)

class MLPricingService:
    """
    Production ML Service für Pricing Predictions
    """
    
    def __init__(self, db: Optional[Session] = None):
        """
        Lade trainierte Models
        
        Args:
            db: Optional database session for feature extraction
        """
        # Try multiple model directories (NEW first, then OLD as fallback)
        base_dir = Path(__file__).parent.parent.parent
        self.models_dir = base_dir / 'ml_models'
        self.models_dir_fallback = base_dir / 'models' / 'ml'
        
        self.db = db
        self.feature_service = FeatureEngineeringService(db) if db else None
        
        try:
            logger.critical(f"[ML_PRICING_SERVICE] Initializing - models_dir: {self.models_dir}")
            logger.critical(f"[ML_PRICING_SERVICE] models_dir exists: {self.models_dir.exists()}")
            logger.critical(f"[ML_PRICING_SERVICE] Fallback models_dir: {self.models_dir_fallback}")
            logger.critical(f"[ML_PRICING_SERVICE] Fallback exists: {self.models_dir_fallback.exists()}")
            
            # Helper function to find model in primary or fallback directory
            def find_model(filename):
                primary = self.models_dir / filename
                if primary.exists():
                    return primary
                fallback = self.models_dir_fallback / filename
                if fallback.exists():
                    logger.critical(f"[ML_PRICING_SERVICE] Using fallback path for {filename}: {fallback}")
                    return fallback
                return None
            
            # Lade XGBoost (NUR neue Modelle v1.2 oder v1.0, KEINE Legacy-Modelle!)
            xgb_path = find_model('xgboost_v1.2_tuned.pkl')
            if xgb_path is None:
                xgb_path = find_model('xgboost_v1.0_production.pkl')
                logger.critical(f"[ML_PRICING_SERVICE] Checking XGBoost v1.0: {xgb_path is not None}")
            
            if xgb_path is None:
                # Check both directories for available files
                available_new = list(self.models_dir.glob('*.pkl')) if self.models_dir.exists() else []
                available_old = list(self.models_dir_fallback.glob('*.pkl')) if self.models_dir_fallback.exists() else []
                all_available = available_new + available_old
                logger.critical(f"[ML_PRICING_SERVICE] NEW XGBoost model (v1.2 or v1.0) not found! Available files: {[f.name for f in all_available[:10]]}")
                raise FileNotFoundError(f"NEW XGBoost model (xgboost_v1.2_tuned.pkl or xgboost_v1.0_production.pkl) not found in {self.models_dir} or {self.models_dir_fallback}. Available files: {[f.name for f in all_available[:10]]}. Legacy models (201 features) are NOT supported!")
            
            self.xgb_model_path = xgb_path
            logger.critical(f"[ML_PRICING_SERVICE] Loading XGBoost from: {xgb_path}")
            xgb_data = joblib.load(xgb_path)
            logger.critical(f"[ML_PRICING_SERVICE] XGBoost loaded successfully")
            
            if isinstance(xgb_data, dict):
                self.xgb_model = xgb_data['model']
                self.xgb_features = xgb_data.get('feature_names', [])
                self.xgb_version = xgb_data.get('version', 'unknown')
                self.xgb_metrics = xgb_data.get('metrics', {})
                logger.info(f"[OK] XGBoost v{self.xgb_version} loaded ({len(self.xgb_features)} features)")
            else:
                self.xgb_model = xgb_data
                self.xgb_version = 'legacy'
                self.xgb_metrics = {}
                
                # Try to extract feature names from legacy model
                self.xgb_features = []
                
                # Option 1: Check if model has feature_names_in_ (newer XGBoost versions)
                if hasattr(self.xgb_model, 'feature_names_in_'):
                    self.xgb_features = [str(feat) for feat in self.xgb_model.feature_names_in_]
                    logger.critical(f"[ML_PRICING_SERVICE] Extracted {len(self.xgb_features)} features from model.feature_names_in_")
                
                # Option 2: Try to load from JSON file (same directory as model)
                if not self.xgb_features:
                    import json
                    json_paths = [
                        xgb_path.parent / 'xgboost_kaggle_features_latest.json',
                        xgb_path.parent / 'xgboost_kaggle_features.json',
                        self.models_dir / 'xgboost_kaggle_features_latest.json',
                        self.models_dir / 'xgboost_kaggle_features.json',
                        self.models_dir_fallback / 'xgboost_kaggle_features_latest.json',
                        self.models_dir_fallback / 'xgboost_kaggle_features.json'
                    ]
                    for json_path in json_paths:
                        if json_path.exists():
                            try:
                                with open(json_path, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    self.xgb_features = data.get('features', [])
                                    if self.xgb_features:
                                        logger.critical(f"[ML_PRICING_SERVICE] Loaded {len(self.xgb_features)} features from {json_path.name}")
                                        break
                            except Exception as e:
                                logger.warning(f"[ML_PRICING_SERVICE] Failed to load features from {json_path}: {e}")
                
                # Option 3: Try to extract from booster (last resort)
                if not self.xgb_features:
                    try:
                        import xgboost as xgb
                        if hasattr(self.xgb_model, 'get_booster'):
                            booster = self.xgb_model.get_booster()
                            if hasattr(booster, 'feature_names'):
                                self.xgb_features = list(booster.feature_names)
                                logger.critical(f"[ML_PRICING_SERVICE] Extracted {len(self.xgb_features)} features from booster.feature_names")
                    except Exception as e:
                        logger.warning(f"[ML_PRICING_SERVICE] Failed to extract features from booster: {e}")
                
                if not self.xgb_features:
                    logger.warning("[WARNING] XGBoost: Legacy format (no metadata, no feature names found)")
                else:
                    logger.info(f"[OK] XGBoost legacy loaded ({len(self.xgb_features)} features extracted)")
            
            # Lade Meta-Labeler (NUR neues Modell v1.0, KEINE Legacy-Modelle!)
            meta_path = find_model('meta_labeler_v1.0_production.pkl')
            if meta_path is None:
                # Fallback auf alternatives neues Modell (falls vorhanden)
                meta_path = find_model('meta_labeler_direct_new_features.pkl')
                logger.critical(f"[ML_PRICING_SERVICE] Checking Meta Labeler direct_new_features: {meta_path is not None}")
            
            if meta_path is None:
                # Check both directories for available files
                available_new = list(self.models_dir.glob('*.pkl')) if self.models_dir.exists() else []
                available_old = list(self.models_dir_fallback.glob('*.pkl')) if self.models_dir_fallback.exists() else []
                all_available = available_new + available_old
                logger.critical(f"[ML_PRICING_SERVICE] NEW Meta Labeler model (v1.0) not found! Available files: {[f.name for f in all_available[:10]]}")
                raise FileNotFoundError(f"NEW Meta Labeler model (meta_labeler_v1.0_production.pkl) not found in {self.models_dir} or {self.models_dir_fallback}. Available files: {[f.name for f in all_available[:10]]}. Legacy models are NOT supported!")
            
            self.meta_model_path = meta_path
            logger.critical(f"[ML_PRICING_SERVICE] Loading Meta Labeler from: {meta_path}")
            meta_data = joblib.load(meta_path)
            logger.critical(f"[ML_PRICING_SERVICE] Meta Labeler loaded successfully")
            
            if isinstance(meta_data, dict):
                self.meta_model = meta_data['model']
                self.meta_features = meta_data.get('feature_names', [])
                self.meta_version = meta_data.get('version', 'unknown')
                self.meta_metrics = meta_data.get('metrics', {})
                logger.info(f"[OK] Meta-Labeler v{self.meta_version} loaded ({len(self.meta_features)} features)")
            else:
                self.meta_model = meta_data
                self.meta_version = 'legacy'
                self.meta_metrics = {}
                
                # Try to extract feature names from legacy model
                self.meta_features = []
                
                # Option 1: Check if model has feature_names_in_ (scikit-learn models)
                if hasattr(self.meta_model, 'feature_names_in_'):
                    self.meta_features = [str(feat) for feat in self.meta_model.feature_names_in_]
                    logger.critical(f"[ML_PRICING_SERVICE] Extracted {len(self.meta_features)} features from meta_model.feature_names_in_")
                
                # Option 2: Try to load from JSON file (same directory as model)
                if not self.meta_features:
                    import json
                    json_paths = [
                        meta_path.parent / 'meta_labeler_features_latest.json',
                        meta_path.parent / 'meta_labeler_features.json',
                        self.models_dir / 'meta_labeler_features_latest.json',
                        self.models_dir / 'meta_labeler_features.json',
                        self.models_dir_fallback / 'meta_labeler_features_latest.json',
                        self.models_dir_fallback / 'meta_labeler_features.json'
                    ]
                    for json_path in json_paths:
                        if json_path.exists():
                            try:
                                with open(json_path, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    self.meta_features = data.get('features', [])
                                    if self.meta_features:
                                        logger.critical(f"[ML_PRICING_SERVICE] Loaded {len(self.meta_features)} features from {json_path.name}")
                                        break
                            except Exception as e:
                                logger.warning(f"[ML_PRICING_SERVICE] Failed to load features from {json_path}: {e}")
                
                if not self.meta_features:
                    logger.warning("[WARNING] Meta-Labeler: Legacy format (no metadata, no feature names found)")
                else:
                    logger.info(f"[OK] Meta-Labeler legacy loaded ({len(self.meta_features)} features extracted)")
            
        except Exception as e:
            logger.error(f"[ERROR] Model loading failed: {e}")
            raise
    
    def extract_features_xgboost(
        self, 
        product: Optional[Product] = None,
        product_data: Optional[Dict[str, Any]] = None,
        competitor_data: Optional[List[Dict]] = None
    ) -> pd.DataFrame:
        """
        Extrahiere Features für XGBoost aus Product-Daten
        
        Args:
            product: Product model instance (wenn db verfügbar)
            product_data: Dict mit Product-Informationen (Fallback)
            competitor_data: Optional competitor data
        
        Returns:
            DataFrame mit Features in korrekter Reihenfolge
        """
        features = {}
        
        # Option 1: Verwende FeatureEngineeringService (wenn Product und DB verfügbar)
        if product and self.feature_service:
            try:
                print(f"[FEATURE EXTRACTION] Using FeatureEngineeringService for product {product.id}", flush=True)
                logger.critical(f"[FEATURE EXTRACTION] Using FeatureEngineeringService for product {product.id}")
                all_features = self.feature_service.extract_all_features(
                    product=product,
                    competitor_data=competitor_data,
                    cutoff_date=None  # Für Inference = jetzt
                )
                features = all_features
                print(f"[FEATURE EXTRACTION] Extracted {len(features)} features from FeatureEngineeringService", flush=True)
                logger.critical(f"[FEATURE EXTRACTION] Extracted {len(features)} features from FeatureEngineeringService")
                # Log sample of extracted features
                sample_features = {k: v for k, v in list(features.items())[:5]}
                print(f"[FEATURE EXTRACTION] Sample features: {sample_features}", flush=True)
                logger.critical(f"[FEATURE EXTRACTION] Sample features: {sample_features}")
            except Exception as e:
                print(f"[FEATURE EXTRACTION] ⚠️ FeatureEngineeringService failed: {e}", flush=True)
                logger.warning(f"Feature extraction from Product failed: {e}, using product_data")
                features = product_data or {}
        
        # Option 2: Verwende product_data Dict (Fallback)
        elif product_data:
            print(f"[FEATURE EXTRACTION] Using product_data dict (fallback)", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] Using product_data dict (fallback)")
            features = product_data.copy()
            print(f"[FEATURE EXTRACTION] Extracted {len(features)} features from product_data", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] Extracted {len(features)} features from product_data")
        else:
            print(f"[FEATURE EXTRACTION] ⚠️ No features extracted (no product, no product_data)", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] ⚠️ No features extracted (no product, no product_data)")
            features = {}
        
        # Erstelle DataFrame in korrekter Feature-Reihenfolge
        if self.xgb_features:
            # Fülle fehlende Features mit 0
            for feat in self.xgb_features:
                if feat not in features:
                    features[feat] = 0.0
            
            # Erstelle DataFrame in korrekter Reihenfolge
            # WICHTIG: Nur Features verwenden, die im Modell erwartet werden
            df = pd.DataFrame([features])
            # Stelle sicher, dass alle erwarteten Features vorhanden sind
            missing_features = set(self.xgb_features) - set(df.columns)
            if missing_features:
                logger.warning(f"[ML_PRICING_SERVICE] Adding {len(missing_features)} missing features with 0.0")
                for feat in missing_features:
                    df[feat] = 0.0
            # Entferne extra Features, die nicht erwartet werden
            extra_features = set(df.columns) - set(self.xgb_features)
            if extra_features:
                logger.warning(f"[ML_PRICING_SERVICE] Removing {len(extra_features)} extra features")
                df = df.drop(columns=list(extra_features))
            # Reorder to match EXACT training order
            df = df[self.xgb_features]
        else:
            df = pd.DataFrame([features])
        
        # Clean data
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna(0)
        
        return df
    
    def extract_features_meta(
        self,
        product: Optional[Product] = None,
        product_data: Optional[Dict[str, Any]] = None,
        competitor_data: Optional[List[Dict]] = None
    ) -> pd.DataFrame:
        """
        Extrahiere Features für Meta-Labeler aus Product-Daten
        """
        features = {}
        
        # Option 1: Verwende FeatureEngineeringService (wenn Product und DB verfügbar)
        if product and self.feature_service:
            try:
                all_features = self.feature_service.extract_all_features(
                    product=product,
                    competitor_data=competitor_data,
                    cutoff_date=None
                )
                features = all_features
            except Exception as e:
                logger.warning(f"Feature extraction from Product failed: {e}, using product_data")
                features = product_data or {}
        
        # Option 2: Verwende product_data Dict (Fallback)
        elif product_data:
            features = product_data.copy()
        else:
            features = {}
        
        # Erstelle DataFrame in korrekter Feature-Reihenfolge
        if self.meta_features:
            # Fülle fehlende Features mit 0
            for feat in self.meta_features:
                if feat not in features:
                    features[feat] = 0.0
            
            # Erstelle DataFrame in korrekter Reihenfolge
            # WICHTIG: Nur Features verwenden, die im Modell erwartet werden
            df = pd.DataFrame([features])
            # Stelle sicher, dass alle erwarteten Features vorhanden sind
            missing_features = set(self.meta_features) - set(df.columns)
            if missing_features:
                logger.warning(f"[ML_PRICING_SERVICE] Adding {len(missing_features)} missing meta features with 0.0")
                for feat in missing_features:
                    df[feat] = 0.0
            # Entferne extra Features, die nicht erwartet werden
            extra_features = set(df.columns) - set(self.meta_features)
            if extra_features:
                logger.warning(f"[ML_PRICING_SERVICE] Removing {len(extra_features)} extra meta features")
                df = df.drop(columns=list(extra_features))
            # Reorder to match EXACT training order
            df = df[self.meta_features]
        else:
            df = pd.DataFrame([features])
        
        # Clean data
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna(0)
        
        return df
    
    def predict_optimal_price(
        self,
        product: Optional[Product] = None,
        product_data: Optional[Dict[str, Any]] = None,
        competitor_data: Optional[List[Dict]] = None,
        confidence_threshold: float = 0.6,
        business_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Vorhersage optimaler Preis mit Confidence-Filtering
        
        Args:
            product: Product model instance (wenn db verfügbar)
            product_data: Dict mit Product-Informationen (Fallback)
            competitor_data: Optional competitor data
            confidence_threshold: Minimum Confidence für ML-Prediction
        
        Returns:
            Dict mit price, confidence, strategy
        """
        start_time = time.time()
        
        try:
            # 1. Feature Engineering
            xgb_features = self.extract_features_xgboost(
                product=product,
                product_data=product_data,
                competitor_data=competitor_data
            )
            meta_features = self.extract_features_meta(
                product=product,
                product_data=product_data,
                competitor_data=competitor_data
            )
            
            # ======================================================================
            # FEATURE EXTRACTION ANALYSIS
            # ======================================================================
            print("=" * 80, flush=True)
            print("[FEATURE EXTRACTION] Feature Analysis", flush=True)
            print("=" * 80, flush=True)
            logger.critical("=" * 80)
            logger.critical("[FEATURE EXTRACTION] Feature Analysis")
            logger.critical("=" * 80)
            
            # XGBoost Features
            xgb_missing_features = set(self.xgb_features) - set(xgb_features.columns)
            xgb_zero_features = [feat for feat in xgb_features.columns if abs(xgb_features.iloc[0][feat]) < 1e-10]
            xgb_available_features = [(feat, float(xgb_features.iloc[0][feat])) for feat in xgb_features.columns if abs(xgb_features.iloc[0][feat]) >= 1e-10]
            
            print(f"[XGBOOST] Expected: {len(self.xgb_features)} features | Extracted: {len(xgb_features.columns)} features", flush=True)
            logger.critical(f"[XGBOOST] Expected: {len(self.xgb_features)} features | Extracted: {len(xgb_features.columns)} features")
            
            if xgb_missing_features:
                print(f"[XGBOOST] Missing features ({len(xgb_missing_features)}): {', '.join(list(xgb_missing_features)[:10])}{'...' if len(xgb_missing_features) > 10 else ''}", flush=True)
                logger.critical(f"[XGBOOST] Missing features ({len(xgb_missing_features)}): {', '.join(list(xgb_missing_features)[:10])}{'...' if len(xgb_missing_features) > 10 else ''}")
            
            print(f"[XGBOOST] Available (non-zero): {len(xgb_available_features)}/{len(xgb_features.columns)} ({len(xgb_available_features)/len(xgb_features.columns)*100:.1f}%)", flush=True)
            logger.critical(f"[XGBOOST] Available (non-zero): {len(xgb_available_features)}/{len(xgb_features.columns)} ({len(xgb_available_features)/len(xgb_features.columns)*100:.1f}%)")
            
            if xgb_available_features:
                print(f"[XGBOOST] Features WITH values ({len(xgb_available_features)}): {', '.join([f'{feat}={val:.2f}' for feat, val in xgb_available_features[:10]])}{'...' if len(xgb_available_features) > 10 else ''}", flush=True)
                logger.critical(f"[XGBOOST] Features WITH values ({len(xgb_available_features)}): {', '.join([f'{feat}={val:.2f}' for feat, val in xgb_available_features[:10]])}{'...' if len(xgb_available_features) > 10 else ''}")
            
            if xgb_zero_features:
                print(f"[XGBOOST] Zero-value features ({len(xgb_zero_features)}): {', '.join(xgb_zero_features[:10])}{'...' if len(xgb_zero_features) > 10 else ''}", flush=True)
                logger.critical(f"[XGBOOST] Zero-value features ({len(xgb_zero_features)}): {', '.join(xgb_zero_features[:10])}{'...' if len(xgb_zero_features) > 10 else ''}")
            
            # Warnung wenn zu viele Features fehlen
            xgb_coverage = len(xgb_available_features) / len(self.xgb_features) * 100
            if xgb_coverage < 20:
                print(f"[XGBOOST] ⚠️ WARNING: Only {xgb_coverage:.1f}% features have values! Prediction may be unreliable!", flush=True)
                logger.critical(f"[XGBOOST] ⚠️ WARNING: Only {xgb_coverage:.1f}% features have values! Prediction may be unreliable!")
            
            # Meta Labeler Features
            meta_missing_features = set(self.meta_features) - set(meta_features.columns)
            meta_zero_features = [feat for feat in meta_features.columns if abs(meta_features.iloc[0][feat]) < 1e-10]
            meta_available_features = [(feat, float(meta_features.iloc[0][feat])) for feat in meta_features.columns if abs(meta_features.iloc[0][feat]) >= 1e-10]
            
            print(f"[META LABELER] Expected: {len(self.meta_features)} features | Extracted: {len(meta_features.columns)} features", flush=True)
            logger.critical(f"[META LABELER] Expected: {len(self.meta_features)} features | Extracted: {len(meta_features.columns)} features")
            
            if meta_missing_features:
                print(f"[META LABELER] Missing features ({len(meta_missing_features)}): {', '.join(list(meta_missing_features)[:10])}{'...' if len(meta_missing_features) > 10 else ''}", flush=True)
                logger.critical(f"[META LABELER] Missing features ({len(meta_missing_features)}): {', '.join(list(meta_missing_features)[:10])}{'...' if len(meta_missing_features) > 10 else ''}")
            
            print(f"[META LABELER] Available (non-zero): {len(meta_available_features)}/{len(meta_features.columns)} ({len(meta_available_features)/len(meta_features.columns)*100:.1f}%)", flush=True)
            logger.critical(f"[META LABELER] Available (non-zero): {len(meta_available_features)}/{len(meta_features.columns)} ({len(meta_available_features)/len(meta_features.columns)*100:.1f}%)")
            
            if meta_available_features:
                print(f"[META LABELER] Features WITH values ({len(meta_available_features)}): {', '.join([f'{feat}={val:.2f}' for feat, val in meta_available_features[:10]])}{'...' if len(meta_available_features) > 10 else ''}", flush=True)
                logger.critical(f"[META LABELER] Features WITH values ({len(meta_available_features)}): {', '.join([f'{feat}={val:.2f}' for feat, val in meta_available_features[:10]])}{'...' if len(meta_available_features) > 10 else ''}")
            
            if meta_zero_features:
                print(f"[META LABELER] Zero-value features ({len(meta_zero_features)}): {', '.join(meta_zero_features[:10])}{'...' if len(meta_zero_features) > 10 else ''}", flush=True)
                logger.critical(f"[META LABELER] Zero-value features ({len(meta_zero_features)}): {', '.join(meta_zero_features[:10])}{'...' if len(meta_zero_features) > 10 else ''}")
            
            # Warnung wenn zu viele Features fehlen
            meta_coverage = len(meta_available_features) / len(self.meta_features) * 100
            if meta_coverage < 20:
                print(f"[META LABELER] ⚠️ WARNING: Only {meta_coverage:.1f}% features have values! Confidence may be unreliable!", flush=True)
                logger.critical(f"[META LABELER] ⚠️ WARNING: Only {meta_coverage:.1f}% features have values! Confidence may be unreliable!")
            
            print("=" * 80, flush=True)
            logger.critical("=" * 80)
            
            # Get current price for comparison (needed for STEP 3 logging)
            if product:
                current_price = float(product.price) if product.price else 0.0
            elif product_data:
                current_price = float(product_data.get('current_price', 0))
            else:
                current_price = 0.0
            
            # ======================================================================
            # ML MODEL PREDICTIONS
            # ======================================================================
            print("=" * 80, flush=True)
            print("[ML PREDICTIONS] Running Model Predictions", flush=True)
            print("=" * 80, flush=True)
            logger.critical("=" * 80)
            logger.critical("[ML PREDICTIONS] Running Model Predictions")
            logger.critical("=" * 80)
            
            print(f"[MODEL INFO] XGBoost v{self.xgb_version} ({len(self.xgb_features)} features) | Meta Labeler v{self.meta_version} ({len(self.meta_features)} features)", flush=True)
            logger.critical(f"[MODEL INFO] XGBoost v{self.xgb_version} ({len(self.xgb_features)} features) | Meta Labeler v{self.meta_version} ({len(self.meta_features)} features)")
            
            # Model Performance Metrics
            if self.xgb_metrics:
                r2 = self.xgb_metrics.get('r2_score', 'N/A')
                mse = self.xgb_metrics.get('mse', 'N/A')
                r2_str = f"{r2:.4f}" if isinstance(r2, (int, float)) else str(r2)
                mse_str = f"{mse:.2f}" if isinstance(mse, (int, float)) else str(mse)
                print(f"[XGBOOST METRICS] R²={r2_str} | MSE={mse_str}", flush=True)
                logger.critical(f"[XGBOOST METRICS] R²={r2_str} | MSE={mse_str}")
            
            if self.meta_metrics:
                accuracy = self.meta_metrics.get('accuracy', 'N/A')
                accuracy_str = f"{accuracy:.4f}" if isinstance(accuracy, (int, float)) else str(accuracy)
                print(f"[META LABELER METRICS] Accuracy={accuracy_str}", flush=True)
                logger.critical(f"[META LABELER METRICS] Accuracy={accuracy_str}")
            
            # 2. XGBoost Prediction
            print("[XGBOOST] Making price prediction...", flush=True)
            logger.critical("[XGBOOST] Making price prediction...")
            
            try:
                import xgboost as xgb
                # Create DMatrix with explicit feature names
                dmatrix = xgb.DMatrix(
                    xgb_features.values,  # NumPy array
                    feature_names=xgb_features.columns.tolist(),  # Explicit feature names
                    enable_categorical=False
                )
                # Use booster directly for prediction
                if hasattr(self.xgb_model, 'get_booster'):
                    booster = self.xgb_model.get_booster()
                    price_pred = float(booster.predict(dmatrix)[0])
                else:
                    # Fallback to direct predict if no booster
                    price_pred = float(self.xgb_model.predict(xgb_features)[0])
                print(f"[XGBOOST] Prediction successful: €{price_pred:.2f}", flush=True)
                logger.critical(f"[XGBOOST] Prediction successful: €{price_pred:.2f}")
            except Exception as dmatrix_error:
                # Fallback to direct predict if DMatrix fails
                logger.warning(f"[ML_PRICING_SERVICE] DMatrix workaround failed: {dmatrix_error}, trying direct predict")
                price_pred = float(self.xgb_model.predict(xgb_features)[0])
                print(f"[XGBOOST] Prediction (fallback): €{price_pred:.2f}", flush=True)
                logger.critical(f"[XGBOOST] Prediction (fallback): €{price_pred:.2f}")
            
            # 3. Meta-Labeler Confidence
            print("[META LABELER] Calculating confidence score...", flush=True)
            logger.critical("[META LABELER] Calculating confidence score...")
            
            confidence_proba = self.meta_model.predict_proba(meta_features)[0]
            confidence = float(max(confidence_proba))
            predicted_class = int(self.meta_model.predict(meta_features)[0])
            
            print(f"[META LABELER] Confidence probabilities: {[f'{p:.3f}' for p in confidence_proba]}", flush=True)
            logger.critical(f"[META LABELER] Confidence probabilities: {[f'{p:.3f}' for p in confidence_proba]}")
            print(f"[META LABELER] Max confidence: {confidence:.4f} | Predicted class: {predicted_class}", flush=True)
            logger.critical(f"[META LABELER] Max confidence: {confidence:.4f} | Predicted class: {predicted_class}")
            
            # ======================================================================
            # PRICE CALCULATION
            # ======================================================================
            print("=" * 80, flush=True)
            print("[PRICE CALCULATION] Calculating Final Price", flush=True)
            print("=" * 80, flush=True)
            logger.critical("=" * 80)
            logger.critical("[PRICE CALCULATION] Calculating Final Price")
            logger.critical("=" * 80)
            
            print(f"[CURRENT PRICE] €{current_price:.2f}", flush=True)
            logger.critical(f"[CURRENT PRICE] €{current_price:.2f}")
            print(f"[XGBOOST PREDICTION] €{price_pred:.2f}", flush=True)
            logger.critical(f"[XGBOOST PREDICTION] €{price_pred:.2f}")
            
            if current_price > 0:
                pred_direction = "INCREASE" if price_pred > current_price else "DECREASE"
                pred_change_pct = ((price_pred - current_price) / current_price) * 100
                print(f"[PRICE CHANGE] {pred_direction}: {pred_change_pct:+.1f}% ({abs(price_pred - current_price):.2f}€)", flush=True)
                logger.critical(f"[PRICE CHANGE] {pred_direction}: {pred_change_pct:+.1f}% ({abs(price_pred - current_price):.2f}€)")
            else:
                print(f"[PRICE CHANGE] New product (no current price)", flush=True)
                logger.critical(f"[PRICE CHANGE] New product (no current price)")
            
            # ======================================================================
            # CONFIDENCE SCORE CALCULATION
            # ======================================================================
            print("=" * 80, flush=True)
            print("[CONFIDENCE SCORE] Score Calculation", flush=True)
            print("=" * 80, flush=True)
            logger.critical("=" * 80)
            logger.critical("[CONFIDENCE SCORE] Score Calculation")
            logger.critical("=" * 80)
            
            print(f"[META LABELER CONFIDENCE] {confidence:.4f} ({confidence*100:.1f}%)", flush=True)
            logger.critical(f"[META LABELER CONFIDENCE] {confidence:.4f} ({confidence*100:.1f}%)")
            print(f"[CONFIDENCE THRESHOLD] {confidence_threshold:.4f} ({confidence_threshold*100:.1f}%)", flush=True)
            logger.critical(f"[CONFIDENCE THRESHOLD] {confidence_threshold:.4f} ({confidence_threshold*100:.1f}%)")
            
            if confidence >= confidence_threshold:
                print(f"[CONFIDENCE STATUS] ✅ ABOVE THRESHOLD - ML prediction will be used", flush=True)
                logger.critical(f"[CONFIDENCE STATUS] ✅ ABOVE THRESHOLD - ML prediction will be used")
            else:
                print(f"[CONFIDENCE STATUS] ⚠️ BELOW THRESHOLD - Fallback strategy will be used", flush=True)
                logger.critical(f"[CONFIDENCE STATUS] ⚠️ BELOW THRESHOLD - Fallback strategy will be used")
            
            print("=" * 80, flush=True)
            logger.critical("=" * 80)
            
            # Meta Labeler details
            class_names = ['Low Revenue', 'Med-Low Revenue', 'Med-High Revenue', 'High Revenue']
            if len(confidence_proba) == len(class_names):
                class_probs = dict(zip(class_names, confidence_proba))
            else:
                class_probs = {f'Class_{i}': prob for i, prob in enumerate(confidence_proba)}
            
            print(f"[META LABELER CLASS] Predicted: {predicted_class} ({class_names[predicted_class] if predicted_class < len(class_names) else 'Unknown'})", flush=True)
            logger.critical(f"[META LABELER CLASS] Predicted: {predicted_class} ({class_names[predicted_class] if predicted_class < len(class_names) else 'Unknown'})")
            print(f"[META LABELER PROBABILITIES] {class_probs}", flush=True)
            logger.critical(f"[META LABELER PROBABILITIES] {class_probs}")
            
            # Berechne Latenz
            latency_ms = (time.time() - start_time) * 1000
            
            # ======================================================================
            # FINAL PRICE DECISION
            # ======================================================================
            print("=" * 80, flush=True)
            print("[FINAL PRICE DECISION] Decision Logic", flush=True)
            print("=" * 80, flush=True)
            logger.critical("=" * 80)
            logger.critical("[FINAL PRICE DECISION] Decision Logic")
            logger.critical("=" * 80)
            
            # 4. Decision Logic
            if confidence >= confidence_threshold:
                # HIGH CONFIDENCE: Use ML Prediction
                final_price = float(price_pred)
                strategy = "ML_OPTIMIZED"
                print(f"[DECISION] ✅ Using ML prediction (confidence {confidence:.2%} >= {confidence_threshold:.2%})", flush=True)
                logger.critical(f"[DECISION] ✅ Using ML prediction (confidence {confidence:.2%} >= {confidence_threshold:.2%})")
                print(f"[FINAL PRICE] €{final_price:.2f} (from XGBoost prediction)", flush=True)
                logger.critical(f"[FINAL PRICE] €{final_price:.2f} (from XGBoost prediction)")
            else:
                # LOW CONFIDENCE: Use Fallback
                if product and hasattr(product, 'breakeven_price') and product.breakeven_price:
                    breakeven = float(product.breakeven_price)
                    fallback_price = breakeven * 1.20
                elif product_data:
                    breakeven = product_data.get('breakeven_price', 0)
                    fallback_price = breakeven * 1.20
                else:
                    breakeven = 0.0
                    fallback_price = 0.0
                final_price = max(fallback_price, 1.0)  # Min 1.00€
                strategy = "FALLBACK_SAFE"
                print(f"[DECISION] ⚠️ Using fallback (confidence {confidence:.2%} < {confidence_threshold:.2%})", flush=True)
                logger.critical(f"[DECISION] ⚠️ Using fallback (confidence {confidence:.2%} < {confidence_threshold:.2%})")
                print(f"[FALLBACK CALCULATION] Breakeven: €{breakeven:.2f} → Fallback: €{fallback_price:.2f} (breakeven * 1.20)", flush=True)
                logger.critical(f"[FALLBACK CALCULATION] Breakeven: €{breakeven:.2f} → Fallback: €{fallback_price:.2f} (breakeven * 1.20)")
                print(f"[FINAL PRICE] €{final_price:.2f} (from fallback strategy)", flush=True)
                logger.critical(f"[FINAL PRICE] €{final_price:.2f} (from fallback strategy)")
            
            print("=" * 80, flush=True)
            logger.critical("=" * 80)
            
            # Get breakeven price for constraints (current_price already defined above)
            if product:
                breakeven_price = float(product.breakeven_price) if hasattr(product, 'breakeven_price') and product.breakeven_price else 0.0
            elif product_data:
                breakeven_price = float(product_data.get('breakeven_price', 0))
            else:
                breakeven_price = 0.0
            
            # Calculate competitor avg price
            competitor_avg = 0.0
            if competitor_data and len(competitor_data) > 0:
                competitor_prices = [float(c.get('price', 0)) for c in competitor_data if c.get('price', 0) > 0]
                if competitor_prices:
                    competitor_avg = sum(competitor_prices) / len(competitor_prices)
            
            # 5. Apply Business Constraints
            if business_constraints is None:
                from app.config.settings import settings
                business_constraints = {
                    'min_margin_pct': settings.ML_MIN_MARGIN_PCT,
                    'max_price_change_pct': settings.ML_MAX_PRICE_CHANGE_PCT,
                    'competitor_ceiling_pct': settings.ML_COMPETITOR_CEILING_PCT,
                    'psychological_pricing': settings.ML_PSYCHOLOGICAL_PRICING
                }
            
            # Prepare product_data dict for constraints
            constraint_product_data = {
                'current_price': current_price,
                'breakeven_price': breakeven_price,
                'competitor_avg_price': competitor_avg
            }
            
            final_price_constrained, constraints_applied = self._apply_business_constraints(
                price=final_price,
                product_data=constraint_product_data,
                constraints=business_constraints
            )
            
            # STEP 5: Price recommendation - Log calculation breakdown
            logger.info("STEP 5: Price recommendation")
            logger.info(f"  - Price calculation breakdown:")
            logger.info(f"    1. Base price (current): €{current_price:.2f}")
            
            # Show intermediate calculations
            logger.info(f"    2. XGBoost raw prediction: €{price_pred:.2f}")
            if current_price > 0:
                ml_change_abs = price_pred - current_price
                ml_change_pct = (ml_change_abs / current_price) * 100
                logger.info(f"       → ML change from base: {ml_change_abs:+.2f} ({ml_change_pct:+.1f}%)")
            
            # Show confidence-based decision
            if confidence >= confidence_threshold:
                logger.info(f"    3. Confidence check: {confidence:.1%} >= {confidence_threshold:.1%} → Using ML prediction")
                logger.info(f"       → Final ML price: €{final_price:.2f}")
            else:
                logger.info(f"    3. Confidence check: {confidence:.1%} < {confidence_threshold:.1%} → Using FALLBACK")
                logger.info(f"       → Fallback price: €{final_price:.2f} (breakeven + 20%)")
            
            logger.info(f"    4. After business constraints: €{final_price_constrained:.2f}")
            constraint_adjustment_pct = ((final_price_constrained - final_price) / final_price * 100) if final_price > 0 else 0
            if abs(constraint_adjustment_pct) > 0.01:
                constraint_adjustment_abs = final_price_constrained - final_price
                logger.info(f"       → Constraint adjustment: {constraint_adjustment_abs:+.2f} ({constraint_adjustment_pct:+.1f}%)")
            else:
                logger.info(f"       → No constraint adjustment needed")
            
            # Final summary
            total_change = final_price_constrained - current_price if current_price > 0 else 0
            total_change_pct = (total_change / current_price * 100) if current_price > 0 else 0
            logger.info(f"    5. FINAL RECOMMENDED PRICE: €{final_price_constrained:.2f}")
            logger.info(f"       → Total change from base: {total_change:+.2f} ({total_change_pct:+.1f}%)")
            
            # Constraint Application Details (Priority 3 - Extended)
            if constraints_applied:
                strategy += "_CONSTRAINED"
                constraint_change_pct = ((final_price_constrained - final_price) / final_price) * 100 if final_price > 0 else 0.0
                logger.info(f"  - Constraints applied: {constraints_applied}")
                if abs(constraint_change_pct) > 0.01:  # Only log if significant change
                    logger.info(f"  - Price change from ML: {constraint_change_pct:+.1f}%")
                
                # Detailed constraint reasoning (Priority 3)
                if 'min_margin' in str(constraints_applied):
                    min_margin_pct = business_constraints.get('min_margin_pct', 0) * 100
                    actual_margin = ((final_price_constrained - breakeven_price) / final_price_constrained) * 100 if final_price_constrained > 0 else 0
                    logger.info(f"    - Min margin constraint: {min_margin_pct:.0f}% required, actual: {actual_margin:.1f}%")
                
                if 'max_increase' in str(constraints_applied) or 'max_decrease' in str(constraints_applied):
                    max_change_pct = business_constraints.get('max_price_change_pct', 0) * 100
                    actual_change = ((final_price_constrained - current_price) / current_price) * 100 if current_price > 0 else 0
                    logger.info(f"    - Max change constraint: ±{max_change_pct:.0f}% allowed, actual: {actual_change:+.1f}%")
                
                if 'competitor_ceiling' in str(constraints_applied):
                    ceiling_pct = business_constraints.get('competitor_ceiling_pct', 0) * 100
                    vs_competitor = ((final_price_constrained / competitor_avg) - 1) * 100 if competitor_avg > 0 else 0
                    logger.info(f"    - Competitor ceiling: {ceiling_pct:.0f}% above competitor, actual: {vs_competitor:+.1f}%")
                
                if 'psychological_pricing' in str(constraints_applied):
                    logger.info(f"    - Psychological pricing: Rounded to .99 ending")
            else:
                logger.info(f"  - Constraints applied: None")
            
            # Log base price and adjustment if available
            if current_price > 0:
                base_adjustment = ((final_price - current_price) / current_price) * 100
                logger.info(f"  - Base price (current): €{current_price:.2f}")
                logger.info(f"  - ML adjustment: {base_adjustment:+.1f}%")
            
            # 6. Build Response (Frontend-Compatible)
            price_change = final_price_constrained - current_price
            price_change_pct = (price_change / current_price) if current_price > 0 else 0.0
            margin = ((final_price_constrained - breakeven_price) / final_price_constrained) if final_price_constrained > 0 else 0.0
            vs_competitor = ((final_price_constrained / competitor_avg) - 1) if competitor_avg > 0 else 0.0
            
            # Get confidence label
            confidence_label = self._get_confidence_label(confidence)
            
            # Get reasoning
            reasoning = self._generate_reasoning({
                'strategy': strategy,
                'confidence': confidence,
                'revenue_class': predicted_class
            })
            
            result = {
                # Core fields
                'price': round(final_price_constrained, 2),
                'confidence': round(confidence, 4),
                'strategy': strategy,
                'revenue_class': predicted_class,
                
                # Frontend-compatible fields
                'recommended_price': round(final_price_constrained, 2),
                'confidence_label': confidence_label,
                'reasoning': reasoning,
                'ml_confidence': round(confidence, 4),
                'mvp_confidence': round(confidence, 4),  # Compatibility
                'mvp_confidence_label': confidence_label,  # Compatibility
                
                # Recommendation details
                'recommendation': {
                    'recommended_price': round(final_price_constrained, 2),
                    'current_price': round(current_price, 2),
                    'price_change': round(price_change, 2),
                    'price_change_pct': round(price_change_pct, 4)
                },
                
                # Analysis
                'analysis': {
                    'margin': round(margin, 4),
                    'margin_pct': round(margin * 100, 2),
                    'breakeven_price': round(breakeven_price, 2),
                    'vs_competitor_avg_pct': round(vs_competitor * 100, 2) if competitor_avg > 0 else None,
                    'competitor_avg_price': round(competitor_avg, 2) if competitor_avg > 0 else None,
                },
                
                # Model info
                'model_versions': {
                    'xgboost': self.xgb_version,
                    'meta_labeler': self.meta_version
                },
                
                # ML details
                'ml_details': {
                    'xgboost_raw_prediction': round(float(price_pred), 2),
                    'meta_confidence': round(confidence, 4),
                    'meta_class_probabilities': {
                        f'class_{i}': round(float(confidence_proba[i]), 4) for i in range(len(confidence_proba))
                    },
                    'features_count': {
                        'xgboost': len(xgb_features.columns),
                        'meta_labeler': len(meta_features.columns)
                    }
                },
                
                # Constraints info
                'constraints_applied': constraints_applied,
                'constraints_config': business_constraints,
                
                # Confidence breakdown (compatibility)
                'confidence_breakdown': {
                    'model_confidence': round(confidence, 4),
                    'revenue_class': predicted_class,
                    'strategy': strategy
                }
            }
            
            # 7. Log Prediction für Monitoring (optional)
            if ML_MONITORING_AVAILABLE:
                try:
                    product_id = None
                    if product:
                        product_id = str(product.id)
                    elif product_data:
                        product_id = str(product_data.get('id', product_data.get('product_id', 'unknown')))
                    
                    features_dict = xgb_features.iloc[0].to_dict()
                    ml_monitoring.log_prediction(
                        product_id=product_id,
                        prediction=result,
                        features=features_dict,
                        latency_ms=latency_ms
                    )
                    
                    # Log Performance
                    ml_monitoring.log_performance(
                        metric_name='prediction_latency',
                        value=latency_ms,
                        metadata={'strategy': result['strategy']}
                    )
                except Exception as e:
                    logger.warning(f"Failed to log prediction for monitoring: {e}")
            
            return result
        
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            
            # Error Fallback
            if product and hasattr(product, 'breakeven_price') and product.breakeven_price:
                error_fallback = float(product.breakeven_price) * 1.20
            elif product_data:
                error_fallback = product_data.get('breakeven_price', 0) * 1.20
            else:
                error_fallback = 0.0
            
            return {
                'price': float(error_fallback),
                'confidence': 0.0,
                'strategy': 'ERROR_FALLBACK',
                'error': str(e)
            }
    
    def _apply_business_constraints(
        self,
        price: float,
        product_data: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """
        Apply Business Constraints to predicted price
        
        Args:
            price: ML predicted price (or fallback price)
            product_data: Product data with current_price, breakeven_price, competitor_avg_price
            constraints: Dict with constraint parameters
        
        Returns:
            (constrained_price, list_of_applied_constraints)
        """
        constrained_price = price
        applied_constraints = []
        
        # CONSTRAINT 1: Minimum Margin
        min_margin_pct = constraints.get('min_margin_pct', 0.15)
        breakeven_price = product_data.get('breakeven_price', 0.0)
        
        if breakeven_price > 0:
            min_price_for_margin = breakeven_price / (1 - min_margin_pct)
            if constrained_price < min_price_for_margin:
                logger.info(f"Applying min_margin constraint: {constrained_price:.2f} → {min_price_for_margin:.2f}")
                constrained_price = min_price_for_margin
                applied_constraints.append(f'min_margin_{int(min_margin_pct*100)}pct')
        
        # CONSTRAINT 2: Max Price Change (±X% vom current_price)
        max_change_pct = constraints.get('max_price_change_pct', 0.20)
        current_price = product_data.get('current_price', 0.0)
        
        if current_price > 0:
            max_allowed_price = current_price * (1 + max_change_pct)
            min_allowed_price = current_price * (1 - max_change_pct)
            
            if constrained_price > max_allowed_price:
                logger.info(f"Applying max_change constraint (upper): {constrained_price:.2f} → {max_allowed_price:.2f}")
                constrained_price = max_allowed_price
                applied_constraints.append(f'max_increase_{int(max_change_pct*100)}pct')
            elif constrained_price < min_allowed_price:
                logger.info(f"Applying max_change constraint (lower): {constrained_price:.2f} → {min_allowed_price:.2f}")
                constrained_price = min_allowed_price
                applied_constraints.append(f'max_decrease_{int(max_change_pct*100)}pct')
        
        # CONSTRAINT 3: Competitor Ceiling (Max X% über Competitor Avg)
        competitor_ceiling_pct = constraints.get('competitor_ceiling_pct', 1.20)
        competitor_avg = product_data.get('competitor_avg_price', 0.0)
        
        if competitor_avg > 0:
            max_vs_competitor = competitor_avg * competitor_ceiling_pct
            if constrained_price > max_vs_competitor:
                logger.info(f"Applying competitor_ceiling constraint: {constrained_price:.2f} → {max_vs_competitor:.2f}")
                constrained_price = max_vs_competitor
                applied_constraints.append(f'competitor_ceiling_{int(competitor_ceiling_pct*100)}pct')
        
        # CONSTRAINT 4: Psychological Pricing (.99 ending)
        if constraints.get('psychological_pricing', True):
            original_price = constrained_price
            constrained_price = math.floor(constrained_price) + 0.99
            if abs(original_price - constrained_price) > 0.01:
                applied_constraints.append('psychological_pricing_99')
        
        return constrained_price, applied_constraints
    
    def _get_confidence_label(self, confidence: float) -> str:
        """Konvertiere Confidence (0-1) zu Label"""
        if confidence >= 0.75:
            return "High"
        elif confidence >= 0.50:
            return "Medium"
        else:
            return "Low"
    
    def _generate_reasoning(self, result: Dict) -> str:
        """Generiere Text-Beschreibung für Reasoning"""
        strategy = result['strategy']
        confidence = result['confidence']
        revenue_class = result.get('revenue_class', 0)
        
        revenue_labels = {
            0: "Low Revenue Potential",
            1: "Medium-Low Revenue Potential",
            2: "Medium-High Revenue Potential",
            3: "High Revenue Potential"
        }
        
        if 'ML_OPTIMIZED' in strategy:
            return f"ML-optimized price with {confidence:.0%} confidence. {revenue_labels.get(revenue_class, 'Unknown')}."
        elif 'FALLBACK' in strategy:
            return f"Fallback strategy used due to low confidence ({confidence:.1%}). Using breakeven price + 20% margin."
        else:
            return f"Error fallback: {result.get('reason', 'Unknown error')}"
    
    def get_model_info(self) -> Dict[str, Any]:
        """Returniere Model-Informationen für Health-Check"""
        return {
            'xgboost': {
                'version': self.xgb_version,
                'features_count': len(self.xgb_features),
                'features': self.xgb_features[:10] + ['...'] if len(self.xgb_features) > 10 else self.xgb_features,
                'metrics': self.xgb_metrics
            },
            'meta_labeler': {
                'version': self.meta_version,
                'features_count': len(self.meta_features),
                'features': self.meta_features[:10] + ['...'] if len(self.meta_features) > 10 else self.meta_features,
                'metrics': self.meta_metrics
            }
        }


# Singleton Instance (wird mit DB Session initialisiert wenn nötig)
ml_pricing_service = None

def get_ml_pricing_service(db: Optional[Session] = None) -> MLPricingService:
    """Factory function für ML Pricing Service"""
    global ml_pricing_service
    if ml_pricing_service is None or db is not None:
        ml_pricing_service = MLPricingService(db=db)
    return ml_pricing_service
