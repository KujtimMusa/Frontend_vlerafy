from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from datetime import datetime, date
from typing import List, Dict, Optional
import logging
from app.models.recommendation import Recommendation

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Service für Recommendation CRUD und Status-Tracking
    
    Features:
    - Status Updates (accept/reject/apply)
    - Recommendation Queries (by product, shop, status)
    - Price History Integration
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def mark_as_accepted(self, recommendation_id: int) -> Recommendation:
        """
        Markiert Recommendation als accepted.
        User hat akzeptiert, aber noch nicht angewendet.
        """
        recommendation = self.db.query(Recommendation).filter(
            Recommendation.id == recommendation_id
        ).first()
        
        if not recommendation:
            raise ValueError(f"Recommendation {recommendation_id} nicht gefunden")
        
        recommendation.status = "accepted"
        recommendation.updated_at = datetime.now()
        self.db.commit()
        
        logger.info(f"✅ Recommendation {recommendation_id} als 'accepted' markiert")
        return recommendation
    
    def mark_as_rejected(self, recommendation_id: int, reason: Optional[str] = None) -> Recommendation:
        """
        Markiert Recommendation als rejected.
        User hat abgelehnt.
        """
        recommendation = self.db.query(Recommendation).filter(
            Recommendation.id == recommendation_id
        ).first()
        
        if not recommendation:
            raise ValueError(f"Recommendation {recommendation_id} nicht gefunden")
        
        recommendation.status = "rejected"
        recommendation.updated_at = datetime.now()
        
        # Speichere Grund in meta_data
        if reason:
            if not recommendation.meta_data:
                recommendation.meta_data = {}
            recommendation.meta_data['rejection_reason'] = reason
        
        self.db.commit()
        
        logger.info(f"❌ Recommendation {recommendation_id} als 'rejected' markiert")
        return recommendation
    
    def mark_as_applied(
        self, 
        recommendation_id: int, 
        applied_price: float,
        applied_at: Optional[datetime] = None
    ) -> Recommendation:
        """
        Markiert Recommendation als applied.
        Preis wurde auf Shopify angewendet.
        
        Args:
            recommendation_id: Recommendation ID
            applied_price: Tatsächlich angewendeter Preis (kann von recommended_price abweichen)
            applied_at: Zeitpunkt der Anwendung (default: jetzt)
        """
        recommendation = self.db.query(Recommendation).filter(
            Recommendation.id == recommendation_id
        ).first()
        
        if not recommendation:
            raise ValueError(f"Recommendation {recommendation_id} nicht gefunden")
        
        recommendation.status = "applied"
        recommendation.applied_price = applied_price
        recommendation.applied_at = applied_at or datetime.now()
        recommendation.updated_at = datetime.now()
        self.db.commit()
        
        logger.info(f"✅ Recommendation {recommendation_id} als 'applied' markiert (Preis: {applied_price})")
        
        # OPTIONAL: Track in Price History
        try:
            from app.services.price_history_service import PriceHistoryService
            price_service = PriceHistoryService(self.db)
            
            price_service.track_price_change(
                product_id=recommendation.product_id,
                shop_id=recommendation.shop_id,
                new_price=applied_price,
                previous_price=recommendation.current_price,
                triggered_by="recommendation_applied",
                meta_data={
                    'recommendation_id': recommendation_id,
                    'recommended_price': recommendation.recommended_price,
                    'applied_price': applied_price,
                    'strategy': recommendation.strategy
                }
            )
            logger.info(f"✅ Price Change getrackt für Recommendation {recommendation_id}")
        except Exception as e:
            logger.warning(f"⚠️ Konnte Price Change nicht tracken: {e}")
        
        return recommendation
    
    def get_by_id(self, recommendation_id: int) -> Optional[Recommendation]:
        """Lädt Recommendation by ID"""
        return self.db.query(Recommendation).filter(
            Recommendation.id == recommendation_id
        ).first()
    
    def get_by_product(
        self, 
        product_id: int, 
        shop_id: int,
        limit: int = 10
    ) -> List[Recommendation]:
        """Lädt Recommendations für ein Product"""
        return self.db.query(Recommendation).filter(
            Recommendation.product_id == product_id,
            Recommendation.shop_id == shop_id
        ).order_by(desc(Recommendation.created_at)).limit(limit).all()
    
    def get_by_status(
        self, 
        shop_id: int, 
        status: str,
        limit: int = 50
    ) -> List[Recommendation]:
        """Lädt Recommendations by Status"""
        return self.db.query(Recommendation).filter(
            Recommendation.shop_id == shop_id,
            Recommendation.status == status
        ).order_by(desc(Recommendation.created_at)).limit(limit).all()
    
    def get_pending_recommendations(self, shop_id: int, limit: int = 50) -> List[Recommendation]:
        """Lädt alle pending Recommendations"""
        return self.get_by_status(shop_id, "pending", limit)
    
    def get_accepted_recommendations(self, shop_id: int, limit: int = 50) -> List[Recommendation]:
        """Lädt alle accepted Recommendations (bereit für Apply)"""
        return self.get_by_status(shop_id, "accepted", limit)
