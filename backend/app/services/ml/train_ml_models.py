"""
ML Models Training Pipeline
Trainiert RandomForest (ML Detector) und GradientBoosting (Meta Labeler)
"""
import pandas as pd
import numpy as np
import pickle
import logging
from pathlib import Path
from typing import Tuple, Dict
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
import joblib

from app.services.ml.kaggle_data_loader import KaggleDataLoader
from app.services.ml.synthetic_data_generator import SyntheticDataGenerator
from app.services.ml.ecommerce_data_loader import EcommerceDataLoader

logger = logging.getLogger(__name__)


class MLModelTrainer:
    """Trainiert ML Models für Pricing Recommendations"""
    
    def __init__(self, models_dir: str = "models/ml"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Model Hyperparameter
        self.ml_detector_params = {
            'n_estimators': 100,
            'max_depth': 10,
            'min_samples_split': 20,
            'random_state': 42,
            'n_jobs': -1
        }
        
        self.meta_labeler_params = {
            'n_estimators': 50,
            'max_depth': 5,
            'learning_rate': 0.1,
            'random_state': 42
        }
    
    def load_training_data(self, use_kaggle: bool = False, use_ecommerce: bool = False) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Lädt Training-Daten (E-Commerce, Kaggle, Synthetic)
        
        Args:
            use_kaggle: Ob Kaggle-Daten verwendet werden sollen
            use_ecommerce: Ob E-Commerce-Daten verwendet werden sollen
            
        Returns:
            Tuple (features, labels)
        """
        all_features = []
        all_labels = []
        
        # 1. E-Commerce Data (carrie1/ecommerce-data) - PRIORITÄT
        if use_ecommerce:
            try:
                loader = EcommerceDataLoader()
                ecom_features = loader.load_and_preprocess()
                
                if not ecom_features.empty:
                    # Generate labels for E-Commerce data based on features
                    # Label = 1 if price_change_pct > 0 and demand_growth > 0 (good pricing decision)
                    ecom_labels = (
                        (ecom_features['price_change_pct'] > 0) & 
                        (ecom_features['demand_growth'] > 0)
                    ).astype(int)
                    
                    # Add more sophisticated labeling
                    # Good: positive demand growth OR high margin
                    ecom_labels = (
                        (ecom_features['demand_growth'] > 0.1) |
                        (ecom_features['current_margin'] > 0.25) |
                        (ecom_features['inventory_level'] < 0.3)  # Low inventory = good pricing
                    ).astype(int)
                    
                    all_features.append(ecom_features)
                    all_labels.append(pd.Series(ecom_labels))
                    logger.info(f"E-Commerce Daten geladen: {len(ecom_features)} Samples")
            except Exception as e:
                logger.warning(f"E-Commerce Daten konnten nicht geladen werden: {e}")
        
        # 2. Kaggle Data (optional)
        if use_kaggle:
            try:
                loader = KaggleDataLoader()
                kaggle_data = loader.load_and_preprocess()
                
                if kaggle_data:
                    kaggle_features, kaggle_labels = kaggle_data
                    all_features.append(kaggle_features)
                    all_labels.append(kaggle_labels)
                    logger.info(f"Kaggle Daten geladen: {len(kaggle_features)} Samples")
            except Exception as e:
                logger.warning(f"Kaggle Daten konnten nicht geladen werden: {e}")
        
        # 3. Synthetic Data (always included for baseline)
        generator = SyntheticDataGenerator(n_samples=1000)
        synth_features, synth_labels = generator.get_features_and_labels()
        all_features.append(synth_features)
        all_labels.append(synth_labels)
        logger.info(f"Synthetische Daten generiert: {len(synth_features)} Samples")
        
        # Kombiniere
        if all_features:
            features = pd.concat(all_features, ignore_index=True)
            labels = pd.concat(all_labels, ignore_index=True)
        else:
            # Fallback: Nur Synthetic
            features, labels = synth_features, synth_labels
        
        logger.info(f"Gesamt Training-Daten: {len(features)} Samples")
        
        return features, labels
    
    def train_ml_detector(self, X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestClassifier:
        """
        Trainiert ML Detector (RandomForest)
        
        Args:
            X_train: Training Features
            y_train: Training Labels
            
        Returns:
            Trainiertes RandomForest Model
        """
        logger.info("Trainiere ML Detector (RandomForest)...")
        
        model = RandomForestClassifier(**self.ml_detector_params)
        model.fit(X_train, y_train)
        
        logger.info("ML Detector Training abgeschlossen")
        
        return model
    
    def train_meta_labeler(self, X_train: pd.DataFrame, y_train: pd.Series) -> GradientBoostingClassifier:
        """
        Trainiert Meta Labeler (GradientBoosting)
        
        Args:
            X_train: Training Features
            y_train: Training Labels
            
        Returns:
            Trainiertes GradientBoosting Model
        """
        logger.info("Trainiere Meta Labeler (GradientBoosting)...")
        
        model = GradientBoostingClassifier(**self.meta_labeler_params)
        model.fit(X_train, y_train)
        
        logger.info("Meta Labeler Training abgeschlossen")
        
        return model
    
    def evaluate_model(self, model, X_test: pd.DataFrame, y_test: pd.Series, model_name: str) -> Dict:
        """
        Evaluates Model Performance
        
        Args:
            model: Trainiertes Model
            X_test: Test Features
            y_test: Test Labels
            model_name: Name des Models
            
        Returns:
            Dictionary mit Metriken
        """
        # Predictions
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        
        # Metriken
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        
        # Cross-Validation
        cv_scores = cross_val_score(model, X_test, y_test, cv=5, scoring='accuracy')
        
        metrics = {
            'model_name': model_name,
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'cv_mean': float(cv_scores.mean()),
            'cv_std': float(cv_scores.std())
        }
        
        logger.info(f"{model_name} - Accuracy: {accuracy:.3f}, Precision: {precision:.3f}, Recall: {recall:.3f}")
        
        return metrics
    
    def get_feature_importance(self, model, feature_names: list) -> Dict:
        """Gibt Feature Importance zurück"""
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
            importance_dict = dict(zip(feature_names, importances))
            return dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))
        return {}
    
    def train_all_models(self, use_kaggle: bool = False, use_ecommerce: bool = False) -> Dict:
        """
        Kompletter Training-Workflow
        
        Args:
            use_kaggle: Ob Kaggle-Daten verwendet werden sollen
            use_ecommerce: Ob E-Commerce-Daten verwendet werden sollen
            
        Returns:
            Dictionary mit Models und Metriken
        """
        logger.info("=== ML Models Training gestartet ===")
        
        # 1. Daten laden
        features, labels = self.load_training_data(use_kaggle=use_kaggle, use_ecommerce=use_ecommerce)
        
        # 2. Train/Test Split
        X_train, X_test, y_train, y_test = train_test_split(
            features, labels, test_size=0.3, random_state=42, stratify=labels
        )
        
        logger.info(f"Train: {len(X_train)}, Test: {len(X_test)}")
        
        # 3. Trainiere Models
        ml_detector = self.train_ml_detector(X_train, y_train)
        meta_labeler = self.train_meta_labeler(X_train, y_train)
        
        # 4. Evaluierung
        detector_metrics = self.evaluate_model(ml_detector, X_test, y_test, "ML Detector")
        labeler_metrics = self.evaluate_model(meta_labeler, X_test, y_test, "Meta Labeler")
        
        # 5. Feature Importance
        feature_names = features.columns.tolist()
        detector_importance = self.get_feature_importance(ml_detector, feature_names)
        labeler_importance = self.get_feature_importance(meta_labeler, feature_names)
        
        # 6. Models speichern
        self.save_models(ml_detector, meta_labeler)
        
        results = {
            'ml_detector': {
                'model': ml_detector,
                'metrics': detector_metrics,
                'feature_importance': detector_importance
            },
            'meta_labeler': {
                'model': meta_labeler,
                'metrics': labeler_metrics,
                'feature_importance': labeler_importance
            },
            'training_samples': len(X_train),
            'test_samples': len(X_test)
        }
        
        logger.info("=== ML Models Training abgeschlossen ===")
        
        return results
    
    def save_models(self, ml_detector: RandomForestClassifier, meta_labeler: GradientBoostingClassifier):
        """Speichert Models als Pickle"""
        ml_detector_path = self.models_dir / "ml_detector.pkl"
        meta_labeler_path = self.models_dir / "meta_labeler.pkl"
        
        joblib.dump(ml_detector, ml_detector_path)
        joblib.dump(meta_labeler, meta_labeler_path)
        
        logger.info(f"Models gespeichert: {ml_detector_path}, {meta_labeler_path}")
    
    def load_models(self) -> Tuple[RandomForestClassifier, GradientBoostingClassifier]:
        """Lädt Models aus Pickle"""
        ml_detector_path = self.models_dir / "ml_detector.pkl"
        meta_labeler_path = self.models_dir / "meta_labeler.pkl"
        
        if not ml_detector_path.exists() or not meta_labeler_path.exists():
            raise FileNotFoundError("Models nicht gefunden. Führe Training aus.")
        
        ml_detector = joblib.load(ml_detector_path)
        meta_labeler = joblib.load(meta_labeler_path)
        
        logger.info("Models geladen")
        
        return ml_detector, meta_labeler


if __name__ == "__main__":
    # Training ausführen
    trainer = MLModelTrainer()
    results = trainer.train_all_models(use_kaggle=False)  # Nur Synthetic für Test
    
    print("\n=== Training Results ===")
    print(f"ML Detector Accuracy: {results['ml_detector']['metrics']['accuracy']:.3f}")
    print(f"Meta Labeler Accuracy: {results['meta_labeler']['metrics']['accuracy']:.3f}")




















