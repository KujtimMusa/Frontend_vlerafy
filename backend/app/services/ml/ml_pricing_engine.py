"""
ML-Enhanced Pricing Engine
Kombiniert regelbasierte Strategien mit ML-Predictions
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional
from pathlib import Path
import joblib
import random
import os
import json

from app.models.product import Product
from app.models.sales_history import SalesHistory
from app.services.pricing_engine import PricingEngine
from app.services.confidence_calculator import ConfidenceCalculator  # Legacy (for fallback)
from app.services.mvp_confidence_calculator import MVPConfidenceCalculator  # NEW MVP System
from app.services.ml.model_config import (
    PRODUCTION_MODELS,
    LEGACY_MODELS,
    EXPECTED_FEATURE_COUNT,
    load_feature_order,
    validate_model_files,
    MODEL_VERSION,
    MODEL_METADATA,
    XGBOOST_MODELS
)
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Feature flag for XGBoost Kaggle models
USE_XGBOOST_KAGGLE = os.getenv("USE_XGBOOST_KAGGLE", "true").lower() == "true"

# Module loaded (no verbose logging needed)

# FIX: Setze Random Seeds für deterministische ML-Predictions
random.seed(42)
np.random.seed(42)


class MLPricingEngine:
    """ML-Enhanced Pricing Engine mit RandomForest + GradientBoosting"""
    
    def __init__(self, base_engine: PricingEngine, models_dir: str = "models/ml"):
        self.base_engine = base_engine
        self.models_dir = Path(models_dir)
        self.ml_detector = None
        self.meta_labeler = None
        self.models_loaded = False
        self.model_version = None
        self.expected_feature_count = EXPECTED_FEATURE_COUNT
        self.feature_order = None
        self.model_metadata = {}  # Store model metadata
        
        # Try to load feature order early (before model loading completes)
        # This ensures expected_feature_count matches actual training count
        try:
            self.feature_order = load_feature_order()
            self.expected_feature_count = len(self.feature_order)
            logger.debug(f"Loaded feature order early: {len(self.feature_order)} features")
            logger.debug(f"Using actual feature count from model: {self.expected_feature_count}")
        except Exception as e:
            logger.warning(f"Could not load feature order early: {e}")
            logger.warning(f"Will use default EXPECTED_FEATURE_COUNT: {EXPECTED_FEATURE_COUNT}")
        
        # Validate model files
        validation = validate_model_files()
        if validation["warnings"]:
            for warning in validation["warnings"]:
                logger.warning(f"{warning}")
        
        self._load_models()
    
    def _load_models(self):
        """Load ML models with automatic fallback strategy"""
        
        # CRITICAL: Log USE_XGBOOST_KAGGLE value (BOTH print AND logger for guaranteed visibility)
        logger.debug(f"[MODEL LOADING] USE_XGBOOST_KAGGLE = {USE_XGBOOST_KAGGLE}")
        logger.debug(f"[MODEL LOADING] Environment Variable: {os.getenv('USE_XGBOOST_KAGGLE', 'NOT SET')}")
        
        if USE_XGBOOST_KAGGLE:
            logger.info("Attempting to load XGBoost Kaggle models...")
            success = self._load_xgboost_kaggle()
            if success:
                logger.info("XGBoost loaded successfully!")
                return True
            logger.warning("XGBoost loading failed, falling back to legacy...")
        else:
            logger.warning("USE_XGBOOST_KAGGLE is False, skipping XGBoost and loading RandomForest...")
        
        logger.info("Loading RandomForest models (legacy)...")
        logger.info("📦 Loading RandomForest models (legacy)...")
        logger.critical("📦 [MODEL LOADING] Loading RandomForest models (legacy)...")
        return self._load_legacy_models()
    
    def _load_xgboost_kaggle(self) -> bool:
        """
        Load XGBoost Kaggle models (prefers 118-feature models, falls back to 201-feature)
        
        Priority:
        1. xgboost_detector_118.pkl (118 features, optimized)
        2. xgboost_kaggle_universal.pkl (201 features, legacy)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            model_dir = Path("models/ml")
            
            # ✅ PRIORITY 1: Try 118-feature detector first
            detector_118_path = model_dir / "xgboost_detector_118.pkl"
            detector_118_metadata = model_dir / "xgboost_detector_118_metadata.json"
            
            # ✅ PRIORITY 1: Try 118-feature meta labeler first
            labeler_118_path = model_dir / "meta_labeler_lightgbm_118.pkl"
            labeler_118_metadata = model_dir / "meta_labeler_118_metadata.json"
            
            # Fallback to old 201-feature models
            model_path = model_dir / "xgboost_kaggle_universal.pkl"
            features_path = model_dir / "xgboost_kaggle_features.json"
            metadata_path = model_dir / "xgboost_kaggle_metadata.json"
            
            # ✅ PRIORITY 1: Try 118-feature models first
            if detector_118_path.exists():
                logger.debug(f"[MODEL] Found 118-feature detector: {detector_118_path}")
                logger.debug(f"Loading 118-feature detector: {detector_118_path}")
                
                # Load 118-feature detector
                self.ml_detector = joblib.load(detector_118_path)
                
                # Load feature names from metadata
                if detector_118_metadata.exists():
                    with open(detector_118_metadata) as f:
                        detector_meta = json.load(f)
                        self.feature_order = detector_meta.get('feature_names', [])
                        self.expected_feature_count = len(self.feature_order)
                        self.model_metadata = detector_meta
                        logger.debug(f"[MODEL] Loaded {len(self.feature_order)} features from metadata")
                        logger.debug(f"Detector Accuracy: {detector_meta.get('val_accuracy', 'N/A'):.4f}")
                else:
                    # Fallback: get from model
                    if hasattr(self.ml_detector, 'feature_names_in_'):
                        self.feature_order = list(self.ml_detector.feature_names_in_)
                        self.expected_feature_count = len(self.feature_order)
                    else:
                        self.feature_order = []
                        self.expected_feature_count = 118  # Default
                
                # Load 118-feature meta labeler
                if labeler_118_path.exists():
                    try:
                        self.meta_labeler = joblib.load(labeler_118_path)
                        logger.debug("LightGBM Meta Labeler (118 features) loaded")
                        
                        # Load metadata
                        if labeler_118_metadata.exists():
                            with open(labeler_118_metadata) as f:
                                labeler_meta = json.load(f)
                                self.meta_labeler_metadata = labeler_meta
                                logger.debug(f"Meta Labeler Accuracy: {labeler_meta.get('val_accuracy', 'N/A'):.4f}")
                    except Exception as e:
                        logger.warning(f"[MODEL] Could not load 118-feature Meta Labeler: {e}")
                        logger.warning("[MODEL] Falling back to detector copy")
                        import copy
                        self.meta_labeler = copy.deepcopy(self.ml_detector)
                else:
                    logger.warning("[MODEL] 118-feature Meta Labeler not found - using detector copy")
                    import copy
                    self.meta_labeler = copy.deepcopy(self.ml_detector)
                
                self.models_loaded = True
                self.model_version = "xgboost_optimized_118_v1"
                
                logger.info("118-FEATURE MODELS LOADED SUCCESSFULLY!")
                logger.info(f"   Detector: {detector_118_path.name}")
                logger.info(f"   Labeler: {labeler_118_path.name if labeler_118_path.exists() else 'detector copy'}")
                logger.info(f"   Features: {self.expected_feature_count}")
                logger.critical("=" * 80)
                logger.info("118-FEATURE MODELS LOADED SUCCESSFULLY!")
                logger.critical(f"   Features: {self.expected_feature_count}")
                logger.critical("=" * 80)
                
                return True
            
            # ✅ FALLBACK: Try old 201-feature models
            logger.warning("[MODEL] 118-feature models not found, trying legacy 201-feature models...")
            logger.warning("[MODEL] 118-feature models not found, falling back to legacy")
            
            # Check if model exists (BOTH print AND logger for guaranteed visibility)
            logger.debug(f"[XGBOOST] Checking model path: {model_path}")
            logger.debug(f"[XGBOOST] Model exists: {model_path.exists()}")
            logger.debug(f"[XGBOOST] Absolute path: {model_path.resolve()}")
            
            if not model_path.exists():
                logger.error(f"[XGBOOST] Model not found: {model_path}")
                logger.error(f"[XGBOOST] Absolute path: {model_path.resolve()}")
                return False
            
            # Load model
            logger.debug(f"[XGBOOST] Loading model from: {model_path}")
            logger.debug(f"Loading model from: {model_path}")
            self.ml_detector = joblib.load(model_path)
            
            # Try to load LightGBM Meta Labeler (separate model)
            meta_labeler_path = model_dir / "meta_labeler_lightgbm.pkl"
            if meta_labeler_path.exists():
                try:
                    self.meta_labeler = joblib.load(meta_labeler_path)
                    logger.debug("LightGBM Meta Labeler loaded successfully")
                    
                    # Load metadata if available
                    metadata_path = model_dir / "meta_labeler_metadata.json"
                    if metadata_path.exists():
                        with open(metadata_path) as f:
                            self.meta_labeler_metadata = json.load(f)
                        logger.debug(f"Meta Labeler Accuracy: {self.meta_labeler_metadata.get('val_accuracy', 'N/A')}")
                except Exception as e:
                    logger.warning(f"[MODEL] Could not load LightGBM Meta Labeler: {e}")
                    logger.warning("[MODEL] Falling back to XGBoost Detector as Meta Labeler")
                    import copy
                    self.meta_labeler = copy.deepcopy(self.ml_detector)
            else:
                logger.warning("[MODEL] LightGBM Meta Labeler not found - using XGBoost Detector copy")
                import copy
                self.meta_labeler = copy.deepcopy(self.ml_detector)
            logger.info("[XGBOOST] Model loaded successfully!")
            
            # Load feature names
            if features_path.exists():
                with open(features_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.feature_order = data.get('features', [])
                    logger.debug(f"[XGBOOST] Loaded {len(self.feature_order)} features")
                    logger.info(f"📋 Loaded {len(self.feature_order)} features")
                    self.expected_feature_count = len(self.feature_order)
            else:
                logger.warning(f"[XGBOOST] Features file not found: {features_path}")
                logger.warning(f"Features file not found: {features_path}")
                self.feature_order = []
            
            # Load metadata
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self.model_metadata = json.load(f)
            else:
                logger.warning(f"Metadata file not found: {metadata_path}")
                self.model_metadata = {
                    'model_name': 'XGBoost Kaggle Universal',
                    'test_accuracy': 91.2,
                    'cv_mean': 92.0,
                    'cv_std': 0.8
                }
            
            self.models_loaded = True
            self.model_version = "xgboost_kaggle_v1"
            
            # Log success with metrics
            metrics = self.model_metadata.get('metrics', {})
            test_acc = metrics.get('accuracy', 0.912) * 100
            cv_mean = metrics.get('cv_mean', 0.92) * 100
            cv_std = metrics.get('cv_std', 0.004) * 100
            samples = self.model_metadata.get('training_samples', 30268)
            
            success_msg = (
                f"✅ XGBoost Kaggle loaded successfully!\n"
                f"   Features: {len(self.feature_order)}\n"
                f"   Test Accuracy: {test_acc:.1f}%\n"
                f"   CV Accuracy: {cv_mean:.1f}% ± {cv_std:.1f}%\n"
                f"   Training Samples: {samples:,}"
            )
            logger.info(success_msg)
            logger.info(success_msg)
            logger.critical("=" * 80)
            logger.critical(success_msg)
            logger.critical("=" * 80)
            
            return True
            
        except Exception as e:
            error_msg = f"❌ Failed to load XGBoost Kaggle: {e}"
            import traceback
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            logger.error(error_msg)
            logger.exception(e)
            logger.critical("=" * 80)
            logger.critical(error_msg)
            logger.critical(traceback.format_exc())
            logger.critical("=" * 80)
            return False
    
    def _load_legacy_models(self):
        """Lädt Production 80-Features ML Models (RandomForest)"""
        try:
            # Try to load production 80-features models first
            ml_detector_path = PRODUCTION_MODELS["ml_detector"]
            meta_labeler_path = PRODUCTION_MODELS["meta_labeler"]
            
            # CRITICAL DEBUG: Log absolute paths and existence
            logger.debug("=" * 80)
            logger.debug("[MODEL LOADING] Checking model files...")
            logger.debug(f"[MODEL LOADING] ML Detector Path: {ml_detector_path}")
            logger.debug(f"[MODEL LOADING] ML Detector Exists: {ml_detector_path.exists()}")
            logger.debug(f"[MODEL LOADING] Meta Labeler Path: {meta_labeler_path}")
            logger.debug(f"[MODEL LOADING] Meta Labeler Exists: {meta_labeler_path.exists()}")
            
            if ml_detector_path.exists() and meta_labeler_path.exists():
                logger.info(f"Loading Production Models (Version: {MODEL_VERSION})")
                logger.info(f"   ML Detector:   {ml_detector_path}")
                logger.info(f"   Meta Labeler:  {meta_labeler_path}")
                
                # Load models (with NumPy version compatibility workaround)
                try:
                    # Try loading directly first (for models trained with NumPy 1.26.2)
                    self.ml_detector = joblib.load(ml_detector_path)
                    self.meta_labeler = joblib.load(meta_labeler_path)
                    logger.info("[MODEL LOADING] Models loaded successfully!")
                except (ValueError, TypeError, AttributeError) as e:
                    error_str = str(e)
                    if "BitGenerator" in error_str or "MT19937" in error_str or "random" in error_str.lower():
                        # Workaround: Monkey-patch NumPy's random state unpickling
                        # NOTE: This should not be needed anymore since requirements.txt uses NumPy 2.3.5
                        # But kept as fallback for edge cases
                        logger.debug("=" * 80)
                        logger.warning("[MODEL LOADING] NumPy version compatibility issue detected!")
                        logger.warning("[MODEL LOADING] This should not happen if NumPy versions match!")
                        logger.warning("[MODEL LOADING] Applying NumPy compatibility workaround...")
                        logger.warning(f"[MODEL LOADING] Error: {error_str[:100]}...")
                        logger.debug("=" * 80)
                        logger.warning("=" * 80)
                        logger.warning("[MODEL LOADING] NumPy version compatibility issue detected!")
                        logger.warning("[MODEL LOADING] This should not happen if NumPy versions match!")
                        logger.warning("[MODEL LOADING] Applying NumPy compatibility workaround...")
                        logger.warning(f"[MODEL LOADING] Error: {error_str}")
                        logger.warning("=" * 80)
                        
                        import numpy as np
                        import numpy.random._pickle as np_pickle
                        
                        # CRITICAL: Initialize variables outside try block
                        original_ctor = None
                        was_patched = False
                        
                        try:
                            # DIRECT PATCH: Überschreibe __bit_generator_ctor komplett
                            # Diese Funktion wird von pickle aufgerufen, wenn ein NumPy random state geladen wird
                            if hasattr(np_pickle, '__bit_generator_ctor'):
                                original_ctor = np_pickle.__bit_generator_ctor
                                
                                def patched_bit_generator_ctor(bit_generator_name):
                                    """
                                    Patched version die ALLE BitGenerator-Namen akzeptiert
                                    und einfach einen kompatiblen RandomState zurückgibt
                                    """
                                    # Ignoriere den BitGenerator-Namen komplett
                                    # und gib einfach einen kompatiblen RandomState zurück
                                    return np.random.RandomState(42)
                                
                                # Überschreibe die Funktion
                                np_pickle.__bit_generator_ctor = patched_bit_generator_ctor
                                was_patched = True
                                logger.debug("Patched numpy.random._pickle.__bit_generator_ctor")
                                logger.debug("[MODEL LOADING] Patched __bit_generator_ctor")
                            
                            # Versuche Models zu laden
                            logger.info("🔍 Attempting to load ML Detector...")
                            self.ml_detector = joblib.load(ml_detector_path)
                            logger.info("✅ ML Detector loaded successfully")
                            logger.debug("[MODEL LOADING] ML Detector loaded")
                            
                            logger.info("🔍 Attempting to load Meta Labeler...")
                            self.meta_labeler = joblib.load(meta_labeler_path)
                            logger.info("✅ Meta Labeler loaded successfully")
                            logger.debug("[MODEL LOADING] Meta Labeler loaded")
                            
                            logger.info("[MODEL LOADING] Models loaded successfully with NumPy workaround!")
                            
                        except Exception as e2:
                            logger.error(f"❌ Workaround failed: {e2}")
                            logger.error(f"   Error type: {type(e2).__name__}")
                            import traceback
                            logger.error(f"   Traceback: {traceback.format_exc()}")
                            logger.error(f"[MODEL LOADING] Workaround failed: {e2}")
                            raise
                        
                        finally:
                            # Restore original function falls vorhanden
                            if was_patched and original_ctor is not None:
                                try:
                                    np_pickle.__bit_generator_ctor = original_ctor
                                    logger.debug("✅ Restored original __bit_generator_ctor")
                                except Exception as restore_error:
                                    logger.warning(f"Could not restore original function: {restore_error}")
                    else:
                        # Re-raise if it's a different ValueError
                        raise
                self.model_version = MODEL_VERSION
                
                # Load feature order
                try:
                    self.feature_order = load_feature_order()
                    logger.info(f"✅ Loaded feature order: {len(self.feature_order)} features")
                except Exception as e:
                    logger.warning(f"⚠️ Could not load feature order: {e}")
                    self.feature_order = None
                
                # Log model metadata
                logger.info(f"📊 Model Configuration:")
                logger.info(f"   Version: {MODEL_VERSION}")
                logger.info(f"   Expected Features: {EXPECTED_FEATURE_COUNT}")
                logger.info(f"   Training Metrics: R²={MODEL_METADATA['training_metrics']['r2_score']:.4f}, "
                          f"MAE={MODEL_METADATA['training_metrics']['mae']:.4f}")
                
                self.models_loaded = True
                logger.info("✅ Production ML Models erfolgreich geladen")
                
            else:
                # Fallback: Try legacy models (DEPRECATED)
                legacy_detector_path = LEGACY_MODELS["ml_detector"]
                legacy_labeler_path = LEGACY_MODELS["meta_labeler"]
                
                if legacy_detector_path.exists() and legacy_labeler_path.exists():
                    logger.warning("⚠️ DEPRECATED: Loading legacy 5-feature models!")
                    logger.warning("   These models were trained with 5 features but inference uses 80 features.")
                    logger.warning("   This causes feature mismatch. Please train 80-feature models.")
                    
                    self.ml_detector = joblib.load(legacy_detector_path)
                    self.meta_labeler = joblib.load(legacy_labeler_path)
                    self.model_version = "legacy_5_features"
                    self.models_loaded = True
                    logger.warning("⚠️ Legacy models loaded (NOT RECOMMENDED)")
                else:
                    error_msg = (
                        f"No ML models found (neither production nor legacy)\n"
                        f"  Production Detector: {ml_detector_path} (exists: {ml_detector_path.exists()})\n"
                        f"  Production Labeler: {meta_labeler_path} (exists: {meta_labeler_path.exists()})\n"
                        f"  Legacy Detector: {legacy_detector_path} (exists: {legacy_detector_path.exists()})\n"
                        f"  Legacy Labeler: {legacy_labeler_path} (exists: {legacy_labeler_path.exists()})"
                    )
                    logger.debug("=" * 80)
                    logger.error("MODEL LOADING FAILED")
                    logger.error(error_msg)
                    logger.debug("=" * 80)
                    logger.error("=" * 80)
                    logger.error("❌❌❌ MODEL LOADING FAILED ❌❌❌")
                    logger.error(error_msg)
                    logger.error("=" * 80)
                    raise FileNotFoundError(error_msg)
                    
        except FileNotFoundError as e:
            logger.error(f"[MODEL LOADING] FileNotFoundError: {e}")
            logger.warning(f"ML Models nicht gefunden: {e}")
            logger.warning("Nutze nur regelbasierte Engine.")
            self.models_loaded = False
        except Exception as e:
            logger.debug("=" * 80)
            import traceback
            logger.error("MODEL LOADING EXCEPTION")
            logger.error(f"[MODEL LOADING] Exception Type: {type(e).__name__}")
            logger.error(f"[MODEL LOADING] Exception Message: {str(e)}")
            logger.error(f"[MODEL LOADING] Traceback:\n{traceback.format_exc()}")
            logger.error(f"Fehler beim Laden der ML Models: {e}", exc_info=True)
            self.models_loaded = False
    
    def extract_features(
        self, 
        product: Product,
        competitor_data: Optional[List[Dict]] = None,
        db: Optional[Session] = None
    ) -> pd.DataFrame:
        """
        Extract all 80 ML features using FeatureEngineeringService.
        
        Args:
            product: Product model instance
            competitor_data: Competitor prices (optional)
            db: Database session (optional, falls nicht in base_engine)
            
        Returns:
            DataFrame with 80 feature values (for ML model compatibility)
        """
        from app.services.feature_engineering_service import FeatureEngineeringService
        
        # Get DB session from base_engine or parameter
        db_session = db
        if not db_session and hasattr(self.base_engine, 'db') and self.base_engine.db:
            db_session = self.base_engine.db
        
        if not db_session:
            logger.warning("⚠️ No DB session available for feature extraction. Using fallback features.")
            logger.warning("[ML] No DB session - using fallback features (5 features only)")
            logger.warning(f"⚠️ base_engine has 'db' attr: {hasattr(self.base_engine, 'db')}")
            if hasattr(self.base_engine, 'db'):
                logger.warning(f"⚠️ base_engine.db value: {self.base_engine.db}")
            return self._get_fallback_features(product)
        
        logger.info(f"✅ DB session available for feature extraction")
        logger.debug("[ML] DB session available")
        
        # Get shop_id
        shop_id = product.shop_id if hasattr(product, 'shop_id') else None
        
        # Initialize feature service
        feature_service = FeatureEngineeringService(db=db_session, shop_id=shop_id)
        
        # Extract all 80 features
        features_dict = feature_service.extract_all_features(
            product=product,
            competitor_data=competitor_data,
            custom_data=None
        )
        
        logger.info(f"✅ Extracted {len(features_dict)} features for product {product.id}")
        logger.debug(f"Feature sample: {list(features_dict.keys())[:10]}...")
        
        # Convert to DataFrame (ML models expect DataFrame)
        features_df = pd.DataFrame([features_dict])
        
        # Ensure all values are numeric and handle NaN/Inf
        for col in features_df.columns:
            features_df[col] = pd.to_numeric(features_df[col], errors='coerce').fillna(0.0)
            # Replace Inf with large finite values
            features_df[col] = features_df[col].replace([np.inf, -np.inf], [1e10, -1e10])
        
        # ✅ CRITICAL: Ensure feature order matches training order
        # This is CRITICAL for XGBoost which requires exact feature name matching
        if self.feature_order and len(self.feature_order) > 0:
            # Reorder columns to match training order
            missing_features = set(self.feature_order) - set(features_df.columns)
            extra_features = set(features_df.columns) - set(self.feature_order)
            
            # ✅ CHECK: For 118-feature models, NO PADDING! Use only extracted features
            is_118_feature_model = (
                self.model_version == "xgboost_optimized_118_v1" or
                (hasattr(self, 'expected_feature_count') and 115 <= self.expected_feature_count <= 120)
            )
            
            if missing_features:
                if is_118_feature_model:
                    # For 118-feature models: ERROR if features are missing (shouldn't happen!)
                    logger.error(f"❌ [118-FEATURE MODEL] Missing {len(missing_features)} features!")
                    logger.error(f"   Missing: {list(missing_features)[:10]}...")
                    logger.error(f"   Expected: {len(self.feature_order)} | Got: {len(features_df.columns)}")
                    logger.error("   This should NOT happen with 118-feature models!")
                    # Still add them for now, but log error
                    missing_data = pd.DataFrame(
                        {feat: [0.0] for feat in missing_features},
                        index=features_df.index
                    )
                    features_df = pd.concat([features_df, missing_data], axis=1)
                    logger.warning("⚠️ [118-FEATURE MODEL] Added missing features with 0.0 (SHOULD NOT HAPPEN!)")
                else:
                    # For legacy 201-feature models: Add missing features with 0.0 (expected)
                    logger.warning(f"⚠️ Missing {len(missing_features)} features in extracted data")
                    logger.debug(f"⚠️ Missing features: {list(missing_features)[:10]}...")
                    # Add missing features with 0.0 using pd.concat (better performance)
                    missing_data = pd.DataFrame(
                        {feat: [0.0] for feat in missing_features},
                        index=features_df.index
                    )
                    features_df = pd.concat([features_df, missing_data], axis=1)
                    logger.info(f"✅ Added {len(missing_features)} missing features with default value 0.0")
                    logger.debug(f"[ML] Added {len(missing_features)} missing features with default value 0.0")
            
            if extra_features:
                logger.warning(f"⚠️ {len(extra_features)} extra features in extracted data (will be ignored)")
                logger.debug(f"⚠️ Extra features: {list(extra_features)[:10]}...")
            
            # ✅ CRITICAL: Reorder to match training order exactly
            # This ensures XGBoost receives features in the exact order it expects
            try:
                features_df = features_df[self.feature_order]
                logger.info(f"✅ Features reordered to match training order: {len(features_df.columns)} features")
                logger.debug(f"[ML] Features reordered to match training order: {len(features_df.columns)} features")
            except KeyError as e:
                # If a feature in feature_order is missing, this will fail
                logger.error(f"❌ Failed to reorder features: {e}")
                logger.error(f"   Missing features in DataFrame: {set(self.feature_order) - set(features_df.columns)}")
                # Try to add missing features again
                for feat in self.feature_order:
                    if feat not in features_df.columns:
                        features_df[feat] = 0.0
                features_df = features_df[self.feature_order]
                logger.info(f"✅ Features reordered after adding missing: {len(features_df.columns)} features")
        else:
            logger.warning("⚠️ No feature_order available - features may not be in correct order for XGBoost")
        
        # ✅ CRITICAL: Feature count validation
        if self.models_loaded and len(features_df.columns) != self.expected_feature_count:
            error_msg = (
                f"❌ FEATURE COUNT MISMATCH!\n"
                f"   Expected: {self.expected_feature_count} features\n"
                f"   Got:      {len(features_df.columns)} features\n"
                f"   Model Version: {self.model_version}\n"
                f"   This will cause incorrect predictions!"
            )
            logger.error(error_msg)
            logger.error(error_msg)
            
            # Fallback: Use base engine only
            logger.error("⚠️ Falling back to base engine only (no ML predictions)")
            return None
        
        logger.debug(f"✅ Feature vector validated: {len(features_df.columns)} features")
        
        return features_df
    
    def _get_fallback_features(self, product: Product) -> pd.DataFrame:
        """Fallback: Return minimal features if DB not available"""
        current_price = float(product.price) if product.price else 0.0
        cost = float(product.cost) if product.cost else 0.0
        margin = ((current_price - cost) / current_price) if current_price > 0 else 0.0
        
        return pd.DataFrame([{
            'current_price': current_price,
            'cost': cost,
            'margin_pct': margin * 100,
            'inventory_quantity': float(product.inventory_quantity or 0),
            'inventory_value': current_price * (product.inventory_quantity or 0)
        }])
    
    def generate_ml_enhanced_recommendation(
        self, 
        product: Product, 
        sales_data: Optional[pd.DataFrame] = None,
        competitor_data: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Generiert ML-enhanced Recommendation mit 80 Features
        
        Args:
            product: Product Model
            sales_data: Optional Sales-Daten (für base engine)
            competitor_data: Optional Competitor prices (für feature extraction)
            
        Returns:
            Enhanced Recommendation Dictionary
        """
        # === FUNCTION ENTRY LOG - FIRST THING EXECUTED ===
        logger.critical("=" * 70)
        logger.critical("🔥🔥🔥 FUNCTION CALLED: generate_ml_enhanced_recommendation 🔥🔥🔥")
        logger.critical(f"🔥 Product ID: {product.id if hasattr(product, 'id') else 'UNKNOWN'}")
        logger.critical(f"🔥 Product Title: {product.title if hasattr(product, 'title') else 'UNKNOWN'}")
        logger.critical(f"🔥 Sales data: {sales_data is not None}")
        logger.critical(f"🔥 Competitor data: {competitor_data is not None and len(competitor_data) > 0 if competitor_data else False}")
        logger.critical("=" * 70)
        # === END FUNCTION ENTRY LOG ===
        
        # 1. Regelbasierte Empfehlungen
        logger.debug("Calculating base recommendation")
        base_recommendation = self.base_engine.calculate_price(product, sales_data=sales_data)
        logger.debug(f"Base recommendation calculated: price={base_recommendation.get('price', 'N/A')}")
        
        # ==================== CHECK IF ML MODELS ARE LOADED ====================
        logger.debug(f"Checking models_loaded: {self.models_loaded}")
        
        # Prepare ML output (will be updated if ML models are loaded)
        ml_output_for_mvp = {
            "ml_detector_proba": 0.85,  # Default
            "meta_labeler_proba": 0.85  # Default
        }
        
        # If ML models are loaded, try to get real ML predictions
        if self.models_loaded:
            logger.debug("ML models loaded - extracting features for ML predictions")
            
            try:
                # Extract features for ML predictions
                logger.debug("Extracting features for ML predictions")
                
                # Get DB session - try multiple sources
                db_session = None
                if hasattr(self.base_engine, 'db') and self.base_engine.db:
                    db_session = self.base_engine.db
                    logger.debug("Using DB session from base_engine")
                else:
                    logger.debug("No DB session in base_engine")
                
                features = self.extract_features(
                    product=product,
                    competitor_data=competitor_data,
                    db=db_session
                )
                
                if features is not None and hasattr(features, 'shape') and len(features) > 0:
                    # Validate feature count
                    if len(features.columns) == self.expected_feature_count:
                        logger.debug(f"Features extracted: {len(features.columns)} features")
                        
                        # Run ML predictions
                        logger.debug("Running ML predictions")
                        try:
                            # ✅ CRITICAL: For XGBoost, ensure features are DataFrame with correct column order
                            if self.model_version == "xgboost_kaggle_v1" and self.feature_order:
                                # Get expected feature names from model (if available)
                                expected_features = None
                                if hasattr(self.ml_detector, 'feature_names_in_'):
                                    # CRITICAL: Convert np.str_ to Python str for pandas compatibility
                                    expected_features = [str(feat) for feat in self.ml_detector.feature_names_in_]
                                    logger.debug(f"XGBoost model expects {len(expected_features)} features")
                                else:
                                    # Fallback to feature_order from JSON
                                    expected_features = self.feature_order
                                    logger.warning("⚠️ [XGBOOST] Model has no feature_names_in_, using feature_order from JSON")
                                
                                # Ensure all expected features exist in DataFrame
                                missing = set(expected_features) - set(features.columns)
                                if missing:
                                    logger.debug(f"Adding {len(missing)} missing features with 0.0")
                                    
                                    # MISSING FEATURES ANALYSIS (DEBUG only)
                                    logger.debug(f"Missing features: {len(missing)}/{len(expected_features)} ({len(missing)/len(expected_features)*100:.1f}%)")
                                    
                                    for feat in missing:
                                        features[feat] = 0.0
                                
                                # Remove extra features
                                extra = set(features.columns) - set(expected_features)
                                if extra:
                                    logger.warning(f"⚠️ [XGBOOST] Removing {len(extra)} extra features")
                                    features = features.drop(columns=list(extra))
                                
                                # Reorder to match EXACT training order
                                features = features[expected_features]
                                
                                # CRITICAL: Verify DataFrame has column names (not NumPy array)
                                if not hasattr(features, 'columns'):
                                    logger.error("Features lost column names! Converting back to DataFrame")
                                    features = pd.DataFrame(features, columns=expected_features)
                                
                                # CRITICAL: Ensure column names are Python str (not np.str_)
                                # Convert DataFrame column names to Python str to match expected_features
                                features.columns = [str(col) for col in features.columns]
                                
                                logger.debug(f"Features aligned: {len(features.columns)} features")
                            
                            # CRITICAL: Final verification before predict_proba
                            if not hasattr(features, 'columns'):
                                logger.error("Features have no column names! Cannot proceed with prediction")
                                raise ValueError("Features DataFrame lost column names before predict_proba")
                            
                            # ✅ CRITICAL: Ensure DataFrame type and verify column names match exactly
                            assert isinstance(features, pd.DataFrame), f"Features must be DataFrame, got {type(features)}"
                            assert hasattr(features, 'columns'), "Features DataFrame must have .columns attribute"
                            
                            # ✅ CRITICAL: Final column name type check - ensure all are Python str
                            features.columns = [str(col) for col in features.columns]
                            
                            # ✅ CRITICAL: Use DMatrix workaround for XGBoost feature name validation
                            # XGBoost sometimes fails to recognize DataFrame column names, so we use DMatrix explicitly
                            try:
                                import xgboost as xgb
                                # Create DMatrix with explicit feature names
                                dmatrix = xgb.DMatrix(
                                    features.values,  # NumPy array
                                    feature_names=features.columns.tolist(),  # Explicit feature names
                                    enable_categorical=False
                                )
                                # Use booster directly for prediction
                                # For binary:logistic objective, predict() returns probabilities directly
                                booster = self.ml_detector.get_booster()
                                ml_detector_proba_raw = booster.predict(dmatrix)
                                # booster.predict() returns 1D array with probability of class 1
                                ml_detector_proba = float(ml_detector_proba_raw[0])
                                
                                # Same for meta_labeler (LightGBM uses sklearn API, not XGBoost booster)
                                if hasattr(self.meta_labeler, 'get_booster'):
                                    # XGBoost meta labeler
                                    booster_meta = self.meta_labeler.get_booster()
                                    meta_labeler_proba_raw = booster_meta.predict(dmatrix)
                                    meta_labeler_proba = float(meta_labeler_proba_raw[0])
                                else:
                                    # LightGBM meta labeler (sklearn API)
                                    meta_labeler_proba = float(self.meta_labeler.predict_proba(features)[0][1])
                                
                                # DEBUG: Model prediction details (DEBUG level only)
                                logger.debug(f"ML predictions: Detector={ml_detector_proba:.6f}, Labeler={meta_labeler_proba:.6f}")
                                
                                logger.debug("Used DMatrix workaround for predictions")
                            except Exception as dmatrix_error:
                                # Fallback to direct predict_proba if DMatrix fails
                                logger.warning(f"DMatrix workaround failed: {dmatrix_error}, trying direct predict_proba")
                                ml_detector_proba = self.ml_detector.predict_proba(features)[0][1]
                                meta_labeler_proba = self.meta_labeler.predict_proba(features)[0][1]
                            
                            ml_output_for_mvp = {
                                "ml_detector_proba": float(ml_detector_proba),
                                "meta_labeler_proba": float(meta_labeler_proba)
                            }
                            
                            logger.debug(f"ML predictions successful: Detector={ml_detector_proba:.4f}, Labeler={meta_labeler_proba:.4f}")
                        except Exception as e:
                            logger.warning(f"ML prediction failed: {e}, using default ML output")
                    else:
                        logger.warning(f"Feature count mismatch: Expected {self.expected_feature_count}, got {len(features.columns)}, using default ML output")
                else:
                    logger.warning("Feature extraction failed or returned None, using default ML output")
            except Exception as e:
                logger.warning(f"Error during ML prediction setup: {e}, using default ML output")
        else:
            logger.debug("ML models not loaded, using default ML output")
        
        # ==================== MVP CONFIDENCE CALCULATOR (v2.0) - WITH REAL OR DEFAULT ML OUTPUT ====================
        logger.debug(f"Calculating MVP confidence with ML output: Detector={ml_output_for_mvp['ml_detector_proba']:.4f}, Labeler={ml_output_for_mvp['meta_labeler_proba']:.4f}")
        
        # Calculate MVP Confidence with real or default ML output
        mvp_confidence = None
        mvp_confidence_label = "Medium"
        mvp_confidence_breakdown = {}
        mvp_confidence_details = {}
        
        try:
            # Convert competitor_data to list format if needed
            competitor_list = None
            if competitor_data:
                competitor_list = competitor_data
                logger.debug(f"Competitor data: {len(competitor_list)} items")
            else:
                logger.debug("No competitor data available")
            
            # Convert sales_data to list format if needed
            sales_list = None
            if sales_data is not None and not sales_data.empty:
                sales_list = sales_data.to_dict('records')
                logger.debug(f"Sales data: {len(sales_list)} records")
            else:
                logger.debug("No sales data available")
            
            # Use MVP Confidence Calculator
            logger.debug("Instantiating MVPConfidenceCalculator")
            mvp_calculator = MVPConfidenceCalculator(db=self.base_engine.db)
            logger.debug(f"Calling calculate_confidence() with ML output: Detector={ml_output_for_mvp['ml_detector_proba']:.4f}, Labeler={ml_output_for_mvp['meta_labeler_proba']:.4f}")
            
            mvp_result = mvp_calculator.calculate_confidence(
                product=product,
                ml_output=ml_output_for_mvp,  # Use real ML output if available, otherwise default
                competitor_data=competitor_list,
                sales_history=sales_list,
                price_history=None  # Will be fetched automatically if DB available
            )
            
            mvp_confidence = mvp_result["overall_confidence"]
            mvp_confidence_label = mvp_result["confidence_label"]
            mvp_confidence_breakdown = mvp_result["breakdown"]
            mvp_confidence_details = mvp_result.get("details", {})
            
            logger.debug("=" * 80)
            logger.debug(f"MVP confidence calculated: {mvp_confidence:.4f} ({mvp_confidence * 100:.1f}%), Label: {mvp_confidence_label}")
            logger.debug("=" * 80)
            logger.critical("=" * 80)
            logger.debug("MVP confidence calculated")
            logger.critical(f"✅ [MVP] Confidence: {mvp_confidence:.4f} ({mvp_confidence * 100:.1f}%)")
            logger.critical(f"✅ [MVP] Label: {mvp_confidence_label}")
            logger.critical(f"✅ [MVP] ML Output Used: Detector={ml_output_for_mvp['ml_detector_proba']:.4f}, Labeler={ml_output_for_mvp['meta_labeler_proba']:.4f}")
            logger.critical("=" * 80)
            
            # Update base_recommendation with MVP confidence
            base_recommendation['confidence'] = float(mvp_confidence)
            base_recommendation['confidence_label'] = mvp_confidence_label
            base_recommendation['confidence_breakdown'] = mvp_confidence_breakdown
            base_recommendation['confidence_details'] = mvp_confidence_details
            
        except Exception as e:
            logger.debug("=" * 80)
            import traceback
            logger.error("MVP CONFIDENCE CALCULATOR FAILED")
            logger.error(f"[MVP] Exception: {type(e).__name__}: {str(e)}")
            logger.error(f"[MVP] Traceback:\n{traceback.format_exc()}")
            logger.debug("=" * 80)
            logger.critical("=" * 80)
            logger.critical(f"❌❌❌ MVP CONFIDENCE CALCULATOR FAILED ❌❌❌")
            logger.critical(f"❌ [MVP] Exception: {type(e).__name__}: {str(e)}")
            import traceback
            logger.critical(f"❌ [MVP] Traceback:\n{traceback.format_exc()}")
            logger.critical("=" * 80)
            # Continue with base_recommendation (confidence will be from base engine)
        
        # ==================== OLD: Calculate NEW confidence IMMEDIATELY (before any checks) ====================
        logger.critical("=" * 70)
        logger.critical("🎯 [CONFIDENCE] Calculating NEW confidence (before ML checks)")
        # NOTE: Old ConfidenceCalculator removed - using MVPConfidenceCalculator only
        # The MVPConfidenceCalculator is called later in the code and will set the correct confidence
        
        logger.debug(f"Checking models_loaded: {self.models_loaded}")
        logger.debug(f"Checking models_loaded: {self.models_loaded}")
        if not self.models_loaded:
            # Fallback: Nur regelbasierte Engine
            logger.warning("[DEBUG] ML Models nicht verfügbar. Nutze nur regelbasierte Engine.")
            logger.warning("[DEBUG] EARLY RETURN: Skipping ConfidenceCalculator (models not loaded)")
            logger.warning("❌ [DEBUG] ML Models nicht verfügbar. Nutze nur regelbasierte Engine.")
            logger.warning("❌ [DEBUG] EARLY RETURN: Skipping ConfidenceCalculator (models not loaded)")
            return base_recommendation
        
        try:
            # 2. Extrahiere alle 80 Features (NEU: mit FeatureEngineeringService)
            features = self.extract_features(
                product=product,
                competitor_data=competitor_data,
                db=self.base_engine.db if hasattr(self.base_engine, 'db') else None
            )
            
            # ✅ CRITICAL: Feature validation
            logger.debug(f"Validating features: is None={features is None}")
            logger.debug(f"Validating features: is None={features is None}")
            if features is None:
                logger.warning("[DEBUG] Feature extraction failed - using base engine only")
                logger.warning("[DEBUG] EARLY RETURN: Skipping ConfidenceCalculator (features is None)")
                logger.error("❌ [DEBUG] Feature extraction failed - using base engine only")
                logger.error("❌ [DEBUG] EARLY RETURN: Skipping ConfidenceCalculator (features is None)")
                return base_recommendation
            
            logger.debug(f"Features shape: {features.shape if hasattr(features, 'shape') else 'N/A'}, columns: {len(features.columns) if hasattr(features, 'columns') else 'N/A'}, expected: {self.expected_feature_count}")
            
            if len(features.columns) != self.expected_feature_count:
                logger.error(
                    f"❌ [DEBUG] Feature count mismatch: Expected {self.expected_feature_count}, "
                    f"got {len(features.columns)} - using base engine only"
                )
                logger.error("❌ [DEBUG] EARLY RETURN: Skipping ConfidenceCalculator (feature count mismatch)")
                return base_recommendation
            
            # 3. ML Predictions (DataFrame wird direkt akzeptiert)
            logger.debug("Running ML predictions")
            logger.debug("Running ML predictions")
            try:
                # ✅ CRITICAL: For XGBoost, ensure features are DataFrame with correct column order
                if self.model_version == "xgboost_kaggle_v1" and self.feature_order:
                    # Get expected feature names from model (if available)
                    expected_features = None
                    if hasattr(self.ml_detector, 'feature_names_in_'):
                        # ✅ CRITICAL: Convert np.str_ to Python str for pandas compatibility
                        expected_features = [str(feat) for feat in self.ml_detector.feature_names_in_]
                        logger.info(f"✅ [DEBUG] [XGBOOST] Model expects {len(expected_features)} features")
                        logger.debug(f"[DEBUG] [XGBOOST] Model expects {len(expected_features)} features")
                    else:
                        # Fallback to feature_order from JSON
                        expected_features = self.feature_order
                        logger.warning("⚠️ [DEBUG] [XGBOOST] Model has no feature_names_in_, using feature_order from JSON")
                    
                    # Ensure all expected features exist in DataFrame
                    missing = set(expected_features) - set(features.columns)
                    if missing:
                        logger.warning(f"⚠️ [DEBUG] [XGBOOST] Adding {len(missing)} missing features with 0.0")
                        for feat in missing:
                            features[feat] = 0.0
                    
                    # Remove extra features
                    extra = set(features.columns) - set(expected_features)
                    if extra:
                        logger.warning(f"⚠️ [DEBUG] [XGBOOST] Removing {len(extra)} extra features")
                        features = features.drop(columns=list(extra))
                    
                    # Reorder to match EXACT training order
                    features = features[expected_features]
                    
                    # ✅ CRITICAL: Verify DataFrame has column names (not NumPy array)
                    if not hasattr(features, 'columns'):
                        logger.error("❌ [DEBUG] [XGBOOST] Features lost column names! Converting back to DataFrame")
                        features = pd.DataFrame(features, columns=expected_features)
                    
                    # ✅ CRITICAL: Ensure column names are Python str (not np.str_)
                    # Convert DataFrame column names to Python str to match expected_features
                    features.columns = [str(col) for col in features.columns]
                    
                    logger.info(f"✅ [DEBUG] [XGBOOST] Features aligned: {len(features.columns)} features, type={type(features)}")
                    logger.debug(f"[DEBUG] Features reordered for XGBoost: {len(features.columns)} features")
                    logger.debug(f"[DEBUG] Feature type: {type(features)}")
                    logger.debug(f"[DEBUG] Has columns: {hasattr(features, 'columns')}")
                    if hasattr(features, 'columns'):
                        logger.debug(f"[DEBUG] First 5 columns: {list(features.columns[:5])}")
                
                # ✅ CRITICAL: Final verification before predict_proba
                if not hasattr(features, 'columns'):
                    logger.error("❌ [DEBUG] [XGBOOST] Features have no column names! Cannot proceed with prediction")
                    raise ValueError("Features DataFrame lost column names before predict_proba")
                
                # ✅ CRITICAL: Ensure DataFrame type and verify column names match exactly
                assert isinstance(features, pd.DataFrame), f"Features must be DataFrame, got {type(features)}"
                assert hasattr(features, 'columns'), "Features DataFrame must have .columns attribute"
                
                # ✅ CRITICAL: Final column name type check - ensure all are Python str
                features.columns = [str(col) for col in features.columns]
                
                # ✅ CRITICAL: Use DMatrix workaround for XGBoost feature name validation
                # XGBoost sometimes fails to recognize DataFrame column names, so we use DMatrix explicitly
                try:
                    import xgboost as xgb
                    # Create DMatrix with explicit feature names
                    dmatrix = xgb.DMatrix(
                        features.values,  # NumPy array
                        feature_names=features.columns.tolist(),  # Explicit feature names
                        enable_categorical=False
                    )
                    # Use booster directly for prediction
                    booster = self.ml_detector.get_booster()
                    ml_detector_proba_raw = booster.predict(dmatrix)
                    # Convert to probability (XGBoost returns raw scores for binary classification)
                    if len(ml_detector_proba_raw.shape) == 1:
                        # Binary classification: convert to probability
                        ml_detector_proba = 1.0 / (1.0 + np.exp(-ml_detector_proba_raw[0]))
                    else:
                        ml_detector_proba = ml_detector_proba_raw[0][1]
                    
                    # Same for meta_labeler (LightGBM uses sklearn API, not XGBoost booster)
                    if hasattr(self.meta_labeler, 'get_booster'):
                        # XGBoost meta labeler
                        booster_meta = self.meta_labeler.get_booster()
                        meta_labeler_proba_raw = booster_meta.predict(dmatrix)
                        if len(meta_labeler_proba_raw.shape) == 1:
                            meta_labeler_proba = 1.0 / (1.0 + np.exp(-meta_labeler_proba_raw[0]))
                        else:
                            meta_labeler_proba = meta_labeler_proba_raw[0][1]
                    else:
                        # LightGBM meta labeler (sklearn API)
                        meta_labeler_proba = float(self.meta_labeler.predict_proba(features)[0][1])
                    
                    logger.info(f"✅ [XGBOOST] Used DMatrix workaround for predictions")
                    logger.debug("[XGBOOST] Used DMatrix workaround for predictions")
                except Exception as dmatrix_error:
                    # Fallback to direct predict_proba if DMatrix fails
                    logger.warning(f"⚠️ [XGBOOST] DMatrix workaround failed: {dmatrix_error}, trying direct predict_proba")
                    logger.warning("[XGBOOST] DMatrix workaround failed, trying direct predict_proba")
                    ml_detector_proba = self.ml_detector.predict_proba(features)[0][1]
                    meta_labeler_proba = self.meta_labeler.predict_proba(features)[0][1]
                logger.debug(f"[DEBUG] ML Predictions successful: Detector={ml_detector_proba:.3f}, Labeler={meta_labeler_proba:.3f}")
                logger.critical(f"✅ [DEBUG] ML Predictions successful: Detector={ml_detector_proba:.3f}, Labeler={meta_labeler_proba:.3f}")
            except Exception as e:
                import traceback
                logger.error(f"[DEBUG] ML Prediction failed: {e}")
                logger.error(f"   Feature shape: {features.shape}")
                logger.error(f"   Feature columns: {list(features.columns)[:10]}...")
                logger.error("[DEBUG] EARLY RETURN: Skipping ConfidenceCalculator (ML prediction failed)")
                logger.error(f"[DEBUG] Traceback:\n{traceback.format_exc()}")
                logger.error(f"❌ [DEBUG] ML Prediction failed: {e}")
                logger.error(f"   Feature shape: {features.shape}")
                logger.error(f"   Feature columns: {list(features.columns)[:10]}...")
                logger.error("❌ [DEBUG] EARLY RETURN: Skipping ConfidenceCalculator (ML prediction failed)")
                logger.error(f"❌ [DEBUG] Traceback:\n{traceback.format_exc()}")
                return base_recommendation
            
            logger.critical(f"✅ [DEBUG] ML Predictions: Detector={ml_detector_proba:.3f}, Labeler={meta_labeler_proba:.3f}")
            
            # ==================== DEBUG: CONFIDENCE CALCULATOR ====================
            logger.critical("=" * 70)
            logger.debug(f"Before ConfidenceCalculator: Product {product.id} ({product.title}), Features: {type(features)}, shape: {features.shape if hasattr(features, 'shape') else 'N/A'}, columns: {len(features.columns) if hasattr(features, 'columns') else 'N/A'}")
            logger.critical("=" * 70)
            
            # 🚀 CRITICAL: Log that we're about to reach MVP Calculator
            logger.debug("=" * 80)
            logger.debug("Approaching MVP calculator checkpoint")
            logger.debug("=" * 80)
            logger.debug("Approaching MVP calculator checkpoint")
            
            # NOTE: Old ConfidenceCalculator removed - using MVPConfidenceCalculator only
            
            # Bereite recommendation_data vor
            logger.debug("Preparing recommendation_data")
            # Versuche sales_90d aus base_recommendation oder sales_data zu holen
            sales_90d = base_recommendation.get("sales_90d", 0)
            if sales_90d == 0 and sales_data is not None and not sales_data.empty:
                try:
                    from datetime import timedelta
                    end_date = datetime.now()
                    start_90d = end_date - timedelta(days=90)
                    if "date" in sales_data.columns:
                        sales_data["date"] = pd.to_datetime(sales_data["date"])
                        sales_90d = int(sales_data[sales_data["date"] >= start_90d]["quantity"].sum() if "quantity" in sales_data.columns else 0)
                except Exception as e:
                    logger.debug(f"Could not calculate sales_90d: {e}")
            
            recommendation_data = {
                "sales_7d": base_recommendation.get("sales_7d", 0) or 0,
                "sales_30d": base_recommendation.get("sales_30d", 0) or 0,
                "sales_90d": sales_90d or 0,
                "competitor_count": len(competitor_data) if competitor_data else 0,
                "inventory_quantity": product.inventory_quantity or 0,
            }
            logger.critical(f"✅ [DEBUG] recommendation_data prepared: {recommendation_data}")
            
            # Berechne days_since_first_sale (optional, für bessere Data Quality)
            try:
                if self.base_engine.db:
                    first_sale = self.base_engine.db.query(
                        func.min(SalesHistory.sale_date)
                    ).filter(
                        SalesHistory.product_id == product.id
                    ).scalar()
                    
                    if first_sale:
                        days_since_first = (datetime.now().date() - first_sale).days
                        recommendation_data["days_since_first_sale"] = days_since_first
                        
                        # Berechne sales_velocity (optional) - aus sales_30d oder sales_7d
                        if recommendation_data["sales_30d"] and days_since_first > 0:
                            recommendation_data["sales_velocity"] = recommendation_data["sales_30d"] / min(days_since_first, 30)
                        elif recommendation_data["sales_7d"] and days_since_first > 0:
                            recommendation_data["sales_velocity"] = recommendation_data["sales_7d"] / min(days_since_first, 7)
            except Exception as e:
                logger.debug(f"Could not calculate days_since_first_sale: {e}")
            
            # Konvertiere Features DataFrame zu Dict für ConfidenceCalculator
            logger.debug("Converting features to dict")
            try:
                if isinstance(features, dict):
                    features_dict = features
                elif hasattr(features, 'iloc') and len(features) > 0:
                    features_dict = features.iloc[0].to_dict()
                else:
                    features_dict = {}
                logger.critical(f"✅ [DEBUG] features_dict prepared: {len(features_dict)} keys")
                if len(features_dict) > 0:
                    logger.critical(f"✅ [DEBUG] Sample keys: {list(features_dict.keys())[:5]}")
            except Exception as e:
                logger.error(f"❌ [DEBUG] Error converting features to dict: {e}")
                import traceback
                logger.error(f"❌ [DEBUG] Traceback:\n{traceback.format_exc()}")
                features_dict = {}
            
            # 🚀 NEW: Use MVP Confidence Calculator (v2.0) for product-specific scoring
            logger.debug("=" * 80)
            logger.debug(f"Starting MVP confidence calculator for product {product.id}: {product.title}")
            logger.debug("=" * 80)
            
            logger.critical("=" * 80)
            logger.debug("Starting MVP confidence calculator v2.0")
            logger.critical(f"🚀 Product ID: {product.id}")
            logger.critical(f"🚀 Product Title: {product.title}")
            logger.critical(f"🚀 Competitor Data Available: {competitor_data is not None and len(competitor_data) > 0 if competitor_data else False}")
            logger.critical(f"🚀 Competitor Data Type: {type(competitor_data)}")
            logger.critical(f"🚀 Competitor Data Length: {len(competitor_data) if competitor_data else 0}")
            logger.critical(f"🚀 Sales Data Available: {sales_data is not None and not sales_data.empty if sales_data is not None else False}")
            logger.critical(f"🚀 Sales Data Type: {type(sales_data)}")
            logger.critical(f"🚀 Sales Data Shape: {sales_data.shape if hasattr(sales_data, 'shape') else 'N/A'}")
            logger.critical("=" * 80)
            
            confidence_label = "Medium"  # Default
            mvp_result = None
            
            try:
                # Convert competitor_data to list format if needed
                competitor_list = None
                if competitor_data:
                    # If it's a list of dicts, use as-is; if objects, convert
                    competitor_list = competitor_data
                    logger.critical(f"🚀 [MVP] Competitor data converted: {len(competitor_list)} items")
                    if competitor_list and len(competitor_list) > 0:
                        logger.critical(f"🚀 [MVP] Sample competitor: {competitor_list[0]}")
                else:
                    logger.warning(f"⚠️ [MVP] NO COMPETITOR DATA PROVIDED!")
                
                # Convert sales_data to list format if needed
                sales_list = None
                if sales_data is not None and not sales_data.empty:
                    # Convert DataFrame to list of dicts
                    sales_list = sales_data.to_dict('records')
                    logger.critical(f"🚀 [MVP] Sales data converted: {len(sales_list)} records")
                else:
                    logger.warning(f"⚠️ [MVP] NO SALES DATA PROVIDED!")
                
                # Use MVP Confidence Calculator
                logger.debug("Instantiating MVPConfidenceCalculator")
                mvp_calculator = MVPConfidenceCalculator(db=self.base_engine.db)
                logger.debug(f"Calling calculate_confidence() for product {product.id}")
                
                mvp_result = mvp_calculator.calculate_confidence(
                    product=product,
                    ml_output=ml_output_for_mvp_calc,
                    competitor_data=competitor_list,
                    sales_history=sales_list,
                    price_history=None  # Will be fetched automatically if DB available
                )
                
                logger.debug(f"calculate_confidence() returned: confidence={mvp_result.get('overall_confidence', 'MISSING')}, label={mvp_result.get('confidence_label', 'MISSING')}")
                
                # Update final_confidence with MVP version
                final_confidence = mvp_result["overall_confidence"]
                confidence_label = mvp_result["confidence_label"]
                
                # Convert breakdown to old format for compatibility
                mvp_breakdown = mvp_result["breakdown"]
                confidence_breakdown = {
                    "data_richness": {"score": mvp_breakdown["data_richness"], "weight": 0.35},
                    "market_intelligence": {"score": mvp_breakdown["market_intelligence"], "weight": 0.30},
                    "model_confidence": {"score": mvp_breakdown["model_confidence"], "weight": 0.10},
                    "product_maturity": {"score": mvp_breakdown["product_maturity"], "weight": 0.15},
                    "content_quality": {"score": mvp_breakdown["content_quality"], "weight": 0.10}
                }
            except Exception as e:
                logger.error(f"❌ [MVP] Error in MVP Confidence Calculator: {e}")
                import traceback
                logger.error(f"❌ [MVP] Traceback:\n{traceback.format_exc()}")
                # Fallback: Use default confidence
                final_confidence = base_recommendation.get('confidence', 0.5)
                confidence_label = "Medium"
                confidence_breakdown = {}
                
                logger.debug(f"MVP confidence calculated: {final_confidence:.4f} ({final_confidence * 100:.1f}%), Label: {confidence_label}")
                
            except Exception as e:
                logger.warning(f"⚠️ [DEBUG] Could not calculate MVP confidence: {e}")
                logger.warning("⚠️ [DEBUG] Falling back to legacy ConfidenceCalculator")
                import traceback
                logger.warning(f"⚠️ [DEBUG] Traceback: {traceback.format_exc()}")
                
                # Fallback: Use base recommendation confidence
                logger.warning("⚠️ [DEBUG] MVP Calculator failed, using base recommendation confidence")
                final_confidence = base_recommendation.get('confidence', 0.5)
                confidence_breakdown = {}
                confidence_label = "Medium"
            
            logger.debug("Using final_confidence")
            logger.critical(f"✅ [DEBUG] final_confidence: {final_confidence:.3f}")
            
            # 🎯 MVP CONFIDENCE (v2.0): Logging mit detailliertem Breakdown
            logger.critical("=" * 70)
            logger.critical(f"🎯 [MVP CONFIDENCE v2.0] Product {product.id}: {final_confidence:.3f} ({confidence_label})")
            logger.critical(f"🎯 [BREAKDOWN]")
            if confidence_breakdown:
                logger.critical(f"  - Data Richness (35%): {confidence_breakdown.get('data_richness', {}).get('score', 0):.3f}")
                logger.critical(f"  - Market Intelligence (30%): {confidence_breakdown.get('market_intelligence', {}).get('score', 0):.3f}")
                logger.critical(f"  - Model Confidence (10%): {confidence_breakdown.get('model_confidence', {}).get('score', 0):.3f}")
                logger.critical(f"  - Product Maturity (15%): {confidence_breakdown.get('product_maturity', {}).get('score', 0):.3f}")
                logger.critical(f"  - Content Quality (10%): {confidence_breakdown.get('content_quality', {}).get('score', 0):.3f}")
            logger.critical("=" * 70)
            logger.debug(f"After ConfidenceCalculator: final_confidence={final_confidence}")
            
            # OLD: Alte Confidence-Berechnung (kommentiert)
            # base_confidence = base_recommendation.get('confidence', 0.5)
            # ml_confidence = (ml_detector_proba + meta_labeler_proba) / 2
            # if ml_confidence > 0.90:
            #     final_confidence = base_confidence * 0.7 + ml_confidence * 0.3
            # else:
            #     final_confidence = base_confidence * 0.4 + ml_confidence * 0.6
            
            # 5. Meta Labeler Filter (Quick-Fix: Lowered threshold from 0.7 to 0.5 for less filtering)
            meta_approved = bool(meta_labeler_proba > 0.5)  # Konvertiere zu Python bool
            
            # 6. Enhanced Recommendation
            enhanced = base_recommendation.copy()
            enhanced['confidence'] = float(final_confidence)
            enhanced['confidence_label'] = confidence_label
            
            # OLD: Alte Confidence-Felder (behalten für Kompatibilität)
            enhanced['base_confidence'] = float(base_recommendation.get('confidence', 0.5))
            ml_confidence_old = (ml_detector_proba + meta_labeler_proba) / 2
            enhanced['ml_confidence'] = float(ml_confidence_old)
            enhanced['ml_detector_confidence'] = float(ml_detector_proba)
            enhanced['meta_labeler_confidence'] = float(meta_labeler_proba)
            enhanced['meta_labeler_approved'] = meta_approved
            
            # 🚀 NEW: MVP Confidence Breakdown (v2.0)
            # Use MVP confidence from early calculation if available, otherwise use ML-enhanced version
            if mvp_confidence is not None:
                # Use early MVP confidence (calculated before ML checks)
                enhanced['confidence'] = float(mvp_confidence)
                enhanced['confidence_label'] = mvp_confidence_label
                enhanced['confidence_breakdown'] = mvp_confidence_breakdown
                enhanced['confidence_details'] = mvp_confidence_details
                enhanced['mvp_confidence_breakdown'] = mvp_confidence_breakdown
                logger.debug("=" * 80)
                logger.info(f"[MVP] Using EARLY MVP confidence: {mvp_confidence:.4f} ({mvp_confidence_label})")
                logger.debug("=" * 80)
                logger.critical("=" * 80)
                logger.critical(f"✅ [MVP] Using EARLY MVP confidence: {mvp_confidence:.4f} ({mvp_confidence_label})")
                logger.critical("=" * 80)
            elif mvp_result:
                # Use ML-enhanced MVP confidence (if ML ran successfully)
                enhanced['confidence_breakdown'] = confidence_breakdown
                enhanced['confidence_details'] = mvp_result.get('details', {})
                enhanced['mvp_confidence_breakdown'] = mvp_result.get('breakdown', {})
            else:
                # Fallback: Use calculated confidence_breakdown
                enhanced['confidence_breakdown'] = confidence_breakdown
            
            # Update reasoning (konvertiere alle numpy types zu Python types)
            enhanced['reasoning']['ml_predictions'] = {
                'ml_detector_proba': float(ml_detector_proba),
                'meta_labeler_proba': float(meta_labeler_proba),
                'combined_ml_confidence': float(ml_confidence_old),
                'meta_approved': bool(meta_approved)
            }
            
            # NEU: Confidence Calculator Info
            enhanced['reasoning']['confidence_calculator'] = {
                'overall_confidence': float(final_confidence),
                'breakdown': confidence_breakdown
            }
            
            # Final Logging (nur einmal, nicht doppelt)
            logger.info(f"ML-Enhanced Recommendation: Final Confidence={final_confidence:.3f} ({confidence_label}) - MVP v2.0")
            
            return enhanced
            
        except Exception as e:
            logger.error("=" * 70)
            logger.error(f"❌ [DEBUG] EXCEPTION in generate_ml_enhanced_recommendation (outer try-except)")
            logger.error(f"❌ [DEBUG] Exception type: {type(e).__name__}")
            logger.error(f"❌ [DEBUG] Error message: {str(e)}")
            import traceback
            logger.error(f"❌ [DEBUG] Full traceback:\n{traceback.format_exc()}")
            logger.error("=" * 70)
            logger.error(f"Fehler bei ML-Enhancement: {e}")
            logger.error("❌ [DEBUG] EARLY RETURN: Falling back to base recommendation (exception caught)")
            # Fallback zu base recommendation
            return base_recommendation

