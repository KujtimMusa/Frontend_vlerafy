from celery import Celery
from celery.schedules import crontab
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Lazy Celery initialization - only create if Redis is available
def get_celery_app():
    """Lazy Celery app initialization - returns None if Redis not available"""
    try:
        # Check if Redis URL is configured and not default/localhost
        redis_url = getattr(settings, 'REDIS_URL', None)
        if not redis_url or redis_url.startswith('redis://redis:') or redis_url.startswith('redis://localhost:'):
            logger.info("⚠️ Celery disabled (Redis not configured)")
            return None
        
        celery_app = Celery(
            "pricing_optimizer",
            broker=redis_url,
            backend=redis_url,
            include=['app.tasks.pricing_tasks', 'app.tasks.ml_tasks', 'app.tasks.competitor_tasks']
        )
        return celery_app
    except Exception as e:
        logger.warning(f"⚠️ Celery initialization failed: {e}")
        return None

# Create celery_app only if Redis is available
celery_app = get_celery_app()

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        'retrain-ml-models-weekly': {
            'task': 'app.tasks.ml_tasks.retrain_ml_models',
            'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Sonntag 2:00 Uhr
        },
        'monitor-ml-performance-daily': {
            'task': 'app.tasks.ml_tasks.monitor_ml_performance',
            'schedule': crontab(hour=3, minute=0),  # Täglich 3:00 Uhr
        },
        'update-competitors-daily': {
            'task': 'app.tasks.competitor_tasks.update_competitor_prices',
            'schedule': crontab(hour=3, minute=0),  # Täglich 3:00 Uhr
        },
        'retry-failed-scrapes': {
            'task': 'app.tasks.competitor_tasks.retry_failed_scrapes',
            'schedule': crontab(hour=6, minute=0),  # Täglich 6:00 Uhr
        },
        'auto-discover-competitors-daily': {
            'task': 'app.tasks.competitor_tasks.auto_discover_competitors_daily',
            'schedule': crontab(hour=4, minute=0),  # Täglich 4:00 Uhr (nach Preis-Updates)
        },
    },
)

