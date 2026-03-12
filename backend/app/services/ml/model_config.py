"""
ML Model Configuration - Centralized Model Versioning and Paths

This module defines the production model configuration to ensure
consistency between training and inference.
"""

from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# ==================== MODEL VERSION CONFIGURATION ====================

MODEL_VERSION = "80_features_v1"
MODEL_VERSION_DESCRIPTION = "Vlerafy 80-Features Model v1 - Production Ready"

# ==================== MODEL PATHS ====================

# Base directory for models
MODELS_BASE_DIR = Path(__file__).parent.parent.parent.parent / "models" / "ml"

# Production 80-Features Models (CURRENT)
PRODUCTION_MODELS = {
    "ml_detector": MODELS_BASE_DIR / "ml_detector_80f.pkl",
    "meta_labeler": MODELS_BASE_DIR / "meta_labeler_80f.pkl",
    "feature_list": MODELS_BASE_DIR / "ml_detector_80f_features.txt",
    "model_metadata": MODELS_BASE_DIR / "ml_detector_80f_metadata.json"
}

# Legacy 5-Features Models (DEPRECATED)
LEGACY_MODELS = {
    "ml_detector": MODELS_BASE_DIR / "ml_detector.pkl",
    "meta_labeler": MODELS_BASE_DIR / "meta_labeler.pkl"
}

# Regression Model (from train_with_80_features.py) - DEPRECATED for classification
REGRESSION_MODEL = {
    "pricing_model": MODELS_BASE_DIR / "pricing_model_80features.pkl",
    "feature_list": MODELS_BASE_DIR / "pricing_model_80features_features.txt"
}

# ==================== FEATURE CONFIGURATION ====================

# Expected number of features for production models
# NOTE: Models were actually trained with 104 features (see ml_detector_80f_metadata.json)
EXPECTED_FEATURE_COUNT = 104

# Feature order must match training order exactly
# This list is generated during training and saved to feature_list file
FEATURE_ORDER: Optional[List[str]] = None

def load_feature_order() -> List[str]:
    """
    Load feature order from saved file.
    This ensures inference uses the same feature order as training.
    """
    global FEATURE_ORDER, EXPECTED_FEATURE_COUNT
    
    if FEATURE_ORDER is not None:
        return FEATURE_ORDER
    
    feature_list_path = PRODUCTION_MODELS["feature_list"]
    
    if not feature_list_path.exists():
        # Fallback: Try legacy regression model feature list
        legacy_path = REGRESSION_MODEL["feature_list"]
        if legacy_path.exists():
            feature_list_path = legacy_path
        else:
            raise FileNotFoundError(
                f"Feature list not found at {feature_list_path}. "
                "Please train models first using train_with_80_features.py"
            )
    
    with open(feature_list_path, 'r') as f:
        FEATURE_ORDER = [line.strip() for line in f if line.strip()]
    
    # Allow feature count to match what was actually trained (104, not 80)
    if len(FEATURE_ORDER) != EXPECTED_FEATURE_COUNT:
        logger.warning(
            f"Feature count in file ({len(FEATURE_ORDER)}) doesn't match "
            f"EXPECTED_FEATURE_COUNT ({EXPECTED_FEATURE_COUNT}). "
            f"Using actual count from file: {len(FEATURE_ORDER)}"
        )
        # Update EXPECTED_FEATURE_COUNT to match actual training
        EXPECTED_FEATURE_COUNT = len(FEATURE_ORDER)
    
    return FEATURE_ORDER

# ==================== MODEL METADATA ====================

MODEL_METADATA = {
    "version": MODEL_VERSION,
    "description": MODEL_VERSION_DESCRIPTION,
    "feature_count": EXPECTED_FEATURE_COUNT,
    "training_script": "scripts/train_with_80_features.py",
    "training_metrics": {
        "r2_score": 0.1653,
        "mae": 0.3401,
        "cv_mae": 0.3350,
        "cv_mae_std": 0.0138
    },
    "status": "production",
    "deprecated_models": [
        "ml_detector.pkl (5 features)",
        "meta_labeler.pkl (5 features)",
        "pricing_model_80features.pkl (regression, not used for classification)"
    ]
}

# ==================== VALIDATION ====================

def validate_model_files() -> dict:
    """
    Validate that all required model files exist.
    
    Returns:
        dict with validation results
    """
    results = {
        "production_models_exist": False,
        "legacy_models_exist": False,
        "feature_list_exists": False,
        "warnings": []
    }
    
    # Check production models
    prod_detector = PRODUCTION_MODELS["ml_detector"].exists()
    prod_labeler = PRODUCTION_MODELS["meta_labeler"].exists()
    results["production_models_exist"] = prod_detector and prod_labeler
    
    if not prod_detector:
        results["warnings"].append("Production ML Detector not found. Training required.")
    if not prod_labeler:
        results["warnings"].append("Production Meta Labeler not found. Training required.")
    
    # Check feature list
    results["feature_list_exists"] = PRODUCTION_MODELS["feature_list"].exists()
    if not results["feature_list_exists"]:
        results["warnings"].append("Feature list not found. Training required.")
    
    # Check legacy models (for deprecation warning)
    legacy_detector = LEGACY_MODELS["ml_detector"].exists()
    legacy_labeler = LEGACY_MODELS["meta_labeler"].exists()
    results["legacy_models_exist"] = legacy_detector or legacy_labeler
    
    if results["legacy_models_exist"]:
        results["warnings"].append(
            "Legacy 5-feature models detected. These are DEPRECATED. "
            "Please use 80-feature models for production."
        )
    
    return results

# NEW: XGBoost Kaggle models
XGBOOST_MODELS = {
    "universal": Path("models/ml/xgboost_kaggle_universal.pkl"),
    "features": Path("models/ml/xgboost_kaggle_features.json"),
    "metadata": Path("models/ml/xgboost_kaggle_metadata.json")
}
