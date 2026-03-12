"""
Feature Schema for ML Model Versioning and Validation

Ensures training and inference use the same features in the same order.
This is critical for XGBoost models which require exact feature name matching.
"""

import joblib
from typing import List, Dict, Optional
from pathlib import Path
import json
import hashlib
import logging
import pandas as pd

logger = logging.getLogger(__name__)


class FeatureSchema:
    """
    Feature Schema for versioning and validation.
    Ensures training and inference use same features.
    """
    
    def __init__(self, feature_names: List[str], version: str = "v1.0.0"):
        self.version = version
        self.feature_names = feature_names
        self.n_features = len(feature_names)
        self.checksum = self._compute_checksum()
    
    def _compute_checksum(self) -> str:
        """Compute checksum for reproducibility"""
        schema_str = json.dumps(self.feature_names, sort_keys=True)
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]
    
    def save(self, model_dir: str = "models/ml"):
        """Save schema alongside model"""
        path = Path(model_dir) / f"feature_schema_{self.version}.pkl"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info(f"✅ Saved feature schema: {path}")
        logger.info(f"   - Features: {self.n_features}")
        logger.info(f"   - Checksum: {self.checksum}")
    
    @classmethod
    def load(cls, version: str = "v1.0.0", model_dir: str = "models/ml") -> Optional['FeatureSchema']:
        """Load schema"""
        path = Path(model_dir) / f"feature_schema_{version}.pkl"
        if not path.exists():
            logger.warning(f"⚠️ Feature schema not found: {path}")
            return None
        
        try:
            schema = joblib.load(path)
            logger.info(f"✅ Loaded feature schema: {version}")
            logger.info(f"   - Features: {schema.n_features}")
            logger.info(f"   - Checksum: {schema.checksum}")
            return schema
        except Exception as e:
            logger.error(f"❌ Failed to load feature schema: {e}")
            return None
    
    def validate(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        """
        Validate DataFrame against schema
        
        Returns:
            Dict with 'missing', 'extra', 'correct' features
        """
        expected = set(self.feature_names)
        actual = set(df.columns)
        
        validation = {
            'missing': sorted(list(expected - actual)),
            'extra': sorted(list(actual - expected)),
            'correct': sorted(list(expected & actual))
        }
        
        # Log validation results
        if validation['missing']:
            logger.error(f"❌ Missing {len(validation['missing'])} features: {validation['missing'][:5]}...")
        if validation['extra']:
            logger.warning(f"⚠️ Extra {len(validation['extra'])} features: {validation['extra'][:5]}...")
        if not validation['missing'] and not validation['extra']:
            logger.info(f"✅ All {self.n_features} features validated successfully")
        
        return validation
    
    def align_features(self, df: pd.DataFrame, fill_missing: bool = True) -> pd.DataFrame:
        """
        Align DataFrame columns to match schema
        
        Args:
            df: Input DataFrame
            fill_missing: If True, fill missing features with 0.0
        
        Returns:
            DataFrame with columns in correct order
        """
        validation = self.validate(df)
        
        if validation['missing']:
            if fill_missing:
                logger.warning(f"⚠️ Filling {len(validation['missing'])} missing features with 0.0")
                for feat in validation['missing']:
                    df[feat] = 0.0
            else:
                raise ValueError(f"Missing features: {validation['missing']}")
        
        # Drop extra features
        if validation['extra']:
            logger.warning(f"⚠️ Dropping {len(validation['extra'])} extra features")
            df = df.drop(columns=validation['extra'])
        
        # Reorder to match schema
        df = df[self.feature_names]
        
        logger.info(f"✅ Features aligned: {df.shape}")
        return df
