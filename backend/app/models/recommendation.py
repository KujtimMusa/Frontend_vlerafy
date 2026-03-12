from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Recommendation(Base):
    """
    Recommendation Model - Speichert Preisempfehlungen mit Status-Tracking
    
    Status-Lifecycle:
    - pending: Neu erstellt, noch nicht angewendet
    - accepted: User hat akzeptiert (aber noch nicht angewendet)
    - rejected: User hat abgelehnt
    - applied: Preis wurde auf Shopify angewendet
    """
    __tablename__ = "recommendations"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Keys
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    is_demo = Column(Boolean, nullable=False, server_default='false', index=True)
    
    # Pricing Data
    current_price = Column(Float, nullable=True)
    recommended_price = Column(Float, nullable=False)
    price_change_pct = Column(Float, nullable=True)
    
    # Strategy & Confidence
    strategy = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    
    # Metrics
    demand_growth = Column(Float, nullable=True)
    days_of_stock = Column(Float, nullable=True)
    sales_7d = Column(Integer, nullable=True)
    sales_30d = Column(Integer, nullable=True)  # 30 Tage Sales (für Dashboard)
    competitor_avg_price = Column(Float, nullable=True)
    
    # ML Enhancement
    base_confidence = Column(Float, nullable=True)
    ml_confidence = Column(Float, nullable=True)
    ml_detector_confidence = Column(Float, nullable=True)
    meta_labeler_confidence = Column(Float, nullable=True)
    meta_labeler_approved = Column(Boolean, nullable=True, server_default='true')
    
    # Status Tracking (NEU!)
    status = Column(String(50), nullable=True, server_default='pending', index=True)
    applied_at = Column(DateTime(timezone=True), nullable=True, index=True)
    applied_price = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Metadata
    meta_data = Column(JSONB, nullable=True)
    
    # Relationships
    product = relationship("Product", backref="recommendations")
    shop = relationship("Shop", backref="recommendations")
    
    # Table Args
    __table_args__ = (
        Index('idx_recommendation_product_created', 'product_id', 'created_at'),
        Index('idx_recommendation_shop_status', 'shop_id', 'status'),
    )
    
    def to_dict(self) -> dict:
        """Konvertiert Recommendation zu Dictionary"""
        return {
            'id': self.id,
            'product_id': self.product_id,
            'shop_id': self.shop_id,
            'is_demo': self.is_demo,
            'current_price': self.current_price,
            'recommended_price': self.recommended_price,
            'price_change_pct': self.price_change_pct,
            'strategy': self.strategy,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'demand_growth': self.demand_growth,
            'days_of_stock': self.days_of_stock,
            'sales_7d': self.sales_7d,
            'sales_30d': self.sales_30d,
            'competitor_avg_price': self.competitor_avg_price,
            'status': self.status,
            'applied_at': self.applied_at.isoformat() if self.applied_at else None,
            'applied_price': self.applied_price,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
