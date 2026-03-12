"""
Celery Tasks für ML Model Retraining
"""
from celery import shared_task
from app.services.ml.train_ml_models import MLModelTrainer
from app.database import SessionLocal
from app.models.recommendation import Recommendation
from app.models.product import Product
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@shared_task
def retrain_ml_models():
    """
    Wöchentliches Retraining der ML Models mit neuen Daten
    
    Lädt:
    1. Neue Preisänderungen aus DB (letzte 7 Tage)
    2. Kombiniert mit bestehenden Training-Daten
    3. Retrain beide Models
    4. Speichere neue Models
    """
    logger.info("=== ML Models Retraining gestartet ===")
    
    try:
        db = SessionLocal()
        
        # 1. Hole neue Recommendations aus DB (letzte 7 Tage)
        cutoff_date = datetime.now() - timedelta(days=7)
        recent_recommendations = db.query(Recommendation).filter(
            Recommendation.created_at >= cutoff_date
        ).all()
        
        logger.info(f"Gefunden: {len(recent_recommendations)} neue Recommendations")
        
        # 2. Konvertiere zu Training-Daten (wenn genug Daten vorhanden)
        # TODO: Implementiere Conversion von Recommendations zu Training-Features
        # Für jetzt: Nutze nur Synthetic + Kaggle
        
        # 3. Trainiere Models
        trainer = MLModelTrainer()
        results = trainer.train_all_models(use_kaggle=False)  # Nur Synthetic für jetzt
        
        # 4. Log Metrics
        detector_acc = results['ml_detector']['metrics']['accuracy']
        labeler_acc = results['meta_labeler']['metrics']['accuracy']
        
        logger.info(f"Retraining abgeschlossen:")
        logger.info(f"  ML Detector Accuracy: {detector_acc:.3f}")
        logger.info(f"  Meta Labeler Accuracy: {labeler_acc:.3f}")
        
        db.close()
        
        return {
            "success": True,
            "ml_detector_accuracy": detector_acc,
            "meta_labeler_accuracy": labeler_acc,
            "training_samples": results['training_samples'],
            "test_samples": results['test_samples']
        }
        
    except Exception as e:
        logger.error(f"Fehler beim Retraining: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@shared_task
def monitor_ml_performance():
    """
    Tägliches Monitoring der ML Performance
    
    Trackt:
    - Durchschnittliche ML Confidence
    - Wie viele Empfehlungen wurden durch Meta Labeler gefiltert?
    - Model Accuracy auf neuen Daten (wenn verfügbar)
    """
    logger.info("=== ML Performance Monitoring ===")
    
    try:
        db = SessionLocal()
        
        # Hole Recommendations der letzten 24 Stunden
        cutoff_date = datetime.now() - timedelta(days=1)
        recent_recommendations = db.query(Recommendation).filter(
            Recommendation.created_at >= cutoff_date
        ).all()
        
        if not recent_recommendations:
            logger.info("Keine Recommendations in den letzten 24 Stunden")
            db.close()
            return {"success": True, "message": "No data"}
        
        # Analysiere ML-Daten (aus reasoning field)
        ml_confidences = []
        meta_approved_count = 0
        total_count = len(recent_recommendations)
        
        for rec in recent_recommendations:
            # Parse reasoning (JSON string)
            try:
                import json
                reasoning = json.loads(rec.reasoning) if isinstance(rec.reasoning, str) else rec.reasoning
                
                if 'ml_predictions' in reasoning:
                    ml_pred = reasoning['ml_predictions']
                    ml_confidences.append(ml_pred.get('combined_ml_confidence', 0))
                    if ml_pred.get('meta_approved', False):
                        meta_approved_count += 1
            except:
                pass
        
        avg_ml_confidence = sum(ml_confidences) / len(ml_confidences) if ml_confidences else 0
        meta_approval_rate = meta_approved_count / total_count if total_count > 0 else 0
        
        metrics = {
            "success": True,
            "total_recommendations": total_count,
            "avg_ml_confidence": float(avg_ml_confidence),
            "meta_approval_rate": float(meta_approval_rate),
            "meta_approved_count": meta_approved_count
        }
        
        logger.info(f"ML Performance:")
        logger.info(f"  Avg ML Confidence: {avg_ml_confidence:.3f}")
        logger.info(f"  Meta Approval Rate: {meta_approval_rate:.3f}")
        
        db.close()
        
        return metrics
        
    except Exception as e:
        logger.error(f"Fehler beim Monitoring: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
































