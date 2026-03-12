"""
ML Monitoring Service für Production Predictions
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class MLMonitoringService:
    """
    Monitoring für ML Predictions in Production
    """
    
    def __init__(self, log_dir: str = 'ml_logs'):
        """
        Initialisiere Monitoring Service
        
        Args:
            log_dir: Verzeichnis für Log-Dateien
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True, parents=True)
        self.predictions_log = self.log_dir / 'predictions.jsonl'
        self.performance_log = self.log_dir / 'performance.jsonl'
        self.feature_drift_log = self.log_dir / 'feature_drift.jsonl'
    
    def log_prediction(
        self,
        product_id: Optional[str],
        prediction: Dict[str, Any],
        features: Dict[str, Any],
        latency_ms: Optional[float] = None
    ):
        """
        Logge einzelne Prediction für Monitoring
        
        Args:
            product_id: Product-ID
            prediction: Prediction-Result
            features: Verwendete Features
            latency_ms: Prediction-Latenz in Millisekunden
        """
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'product_id': str(product_id) if product_id else None,
                'predicted_price': float(prediction.get('price', 0)),
                'confidence': float(prediction.get('confidence', 0)),
                'strategy': prediction.get('strategy', 'UNKNOWN'),
                'revenue_class': prediction.get('revenue_class'),
                'model_versions': prediction.get('model_versions', {}),
                'latency_ms': latency_ms,
                'feature_count': len(features),
                'features': {k: float(v) if isinstance(v, (int, float, np.number)) else str(v) 
                            for k, v in list(features.items())[:10]}  # Nur erste 10 Features
            }
            
            # Append to JSONL file
            with open(self.predictions_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        except Exception as e:
            logger.error(f"Failed to log prediction: {e}", exc_info=True)
    
    def log_performance(
        self,
        metric_name: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Logge Performance-Metrik
        
        Args:
            metric_name: Name der Metrik (z.B. 'prediction_latency', 'model_accuracy')
            value: Wert der Metrik
            metadata: Zusätzliche Metadaten
        """
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'metric_name': metric_name,
                'value': float(value),
                'metadata': metadata or {}
            }
            
            with open(self.performance_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        except Exception as e:
            logger.error(f"Failed to log performance: {e}", exc_info=True)
    
    def log_feature_drift(
        self,
        feature_name: str,
        current_mean: float,
        training_mean: float,
        drift_score: float
    ):
        """
        Logge Feature Drift
        
        Args:
            feature_name: Name des Features
            current_mean: Aktueller Mittelwert
            training_mean: Mittelwert aus Training
            drift_score: Drift-Score (0-1, höher = mehr Drift)
        """
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'feature_name': feature_name,
                'current_mean': float(current_mean),
                'training_mean': float(training_mean),
                'drift_score': float(drift_score),
                'drift_pct': float((current_mean - training_mean) / training_mean * 100) if training_mean != 0 else 0
            }
            
            with open(self.feature_drift_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        except Exception as e:
            logger.error(f"Failed to log feature drift: {e}", exc_info=True)
    
    def get_prediction_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Analyse der letzten Predictions
        
        Args:
            hours: Zeitfenster in Stunden
        
        Returns:
            Dict mit Statistiken
        """
        try:
            if not self.predictions_log.exists():
                return {'error': 'No predictions logged yet'}
            
            # Lade Predictions
            predictions = []
            with open(self.predictions_log, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        predictions.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            
            if not predictions:
                return {'error': 'No valid predictions found'}
            
            df = pd.DataFrame(predictions)
            
            # Filter nach Zeitfenster
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            cutoff = datetime.now() - timedelta(hours=hours)
            df_recent = df[df['timestamp'] >= cutoff]
            
            if len(df_recent) == 0:
                return {'error': f'No predictions in last {hours} hours'}
            
            # Statistiken
            stats = {
                'total_predictions': len(df_recent),
                'timeframe_hours': hours,
                'average_confidence': float(df_recent['confidence'].mean()),
                'median_confidence': float(df_recent['confidence'].median()),
                'min_confidence': float(df_recent['confidence'].min()),
                'max_confidence': float(df_recent['confidence'].max()),
                'strategy_distribution': df_recent['strategy'].value_counts().to_dict(),
                'revenue_class_distribution': df_recent['revenue_class'].value_counts().to_dict() if 'revenue_class' in df_recent.columns else {},
                'price_statistics': {
                    'mean': float(df_recent['predicted_price'].mean()),
                    'median': float(df_recent['predicted_price'].median()),
                    'min': float(df_recent['predicted_price'].min()),
                    'max': float(df_recent['predicted_price'].max()),
                    'std': float(df_recent['predicted_price'].std())
                },
                'latency_statistics': {
                    'mean': float(df_recent['latency_ms'].mean()) if 'latency_ms' in df_recent.columns else None,
                    'median': float(df_recent['latency_ms'].median()) if 'latency_ms' in df_recent.columns else None,
                    'p95': float(df_recent['latency_ms'].quantile(0.95)) if 'latency_ms' in df_recent.columns else None,
                    'p99': float(df_recent['latency_ms'].quantile(0.99)) if 'latency_ms' in df_recent.columns else None
                } if 'latency_ms' in df_recent.columns else None
            }
            
            return stats
        
        except Exception as e:
            logger.error(f"Failed to get prediction statistics: {e}", exc_info=True)
            return {'error': str(e)}
    
    def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Hole Performance-Metriken
        
        Args:
            hours: Zeitfenster in Stunden
        
        Returns:
            Dict mit Performance-Metriken
        """
        try:
            if not self.performance_log.exists():
                return {'error': 'No performance metrics logged yet'}
            
            # Lade Performance-Logs
            metrics = []
            with open(self.performance_log, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        metrics.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            
            if not metrics:
                return {'error': 'No valid performance metrics found'}
            
            df = pd.DataFrame(metrics)
            
            # Filter nach Zeitfenster
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            cutoff = datetime.now() - timedelta(hours=hours)
            df_recent = df[df['timestamp'] >= cutoff]
            
            if len(df_recent) == 0:
                return {'error': f'No performance metrics in last {hours} hours'}
            
            # Gruppiere nach Metrik-Name
            result = {}
            for metric_name in df_recent['metric_name'].unique():
                metric_data = df_recent[df_recent['metric_name'] == metric_name]
                result[metric_name] = {
                    'count': len(metric_data),
                    'mean': float(metric_data['value'].mean()),
                    'median': float(metric_data['value'].median()),
                    'min': float(metric_data['value'].min()),
                    'max': float(metric_data['value'].max()),
                    'std': float(metric_data['value'].std())
                }
            
            return {
                'timeframe_hours': hours,
                'metrics': result
            }
        
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}", exc_info=True)
            return {'error': str(e)}
    
    def detect_feature_drift(
        self,
        current_features: Dict[str, float],
        training_features: Dict[str, float],
        threshold: float = 0.2
    ) -> List[Dict[str, Any]]:
        """
        Erkenne Feature Drift
        
        Args:
            current_features: Aktuelle Feature-Werte
            training_features: Training Feature-Werte (Referenz)
            threshold: Drift-Threshold (0-1)
        
        Returns:
            Liste von Features mit Drift
        """
        drift_detected = []
        
        for feature_name in current_features:
            if feature_name not in training_features:
                continue
            
            current_val = current_features[feature_name]
            training_val = training_features[feature_name]
            
            # Berechne Drift-Score
            if training_val == 0:
                drift_score = 1.0 if current_val != 0 else 0.0
            else:
                drift_score = abs((current_val - training_val) / training_val)
            
            if drift_score > threshold:
                drift_detected.append({
                    'feature_name': feature_name,
                    'current_value': float(current_val),
                    'training_value': float(training_val),
                    'drift_score': float(drift_score),
                    'drift_pct': float((current_val - training_val) / training_val * 100) if training_val != 0 else 0
                })
                
                # Logge Drift
                self.log_feature_drift(
                    feature_name=feature_name,
                    current_mean=current_val,
                    training_mean=training_val,
                    drift_score=drift_score
                )
        
        return drift_detected


# Singleton Instance
ml_monitoring = MLMonitoringService()
