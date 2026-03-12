from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class PriceHistory(Base):
    """
    Price History Table - Trackt historische Preisänderungen
    
    Features:
    - Automatisches Tracking via PostgreSQL Trigger
    - Manuelle Tracking via PriceHistoryService
    - Trend-Analyse und Volatilitäts-Berechnung
    - ML Feature Engineering (10 neue Features!)
    
    Unterstützt:
    - Demo-Shop (shop_id=999): Recommendations generieren neue Preise
    - Live-Shop (Shopify): Echte Preisänderungen
    """
    __tablename__ = "price_history"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Keys
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Price Data
    price_date = Column(Date, nullable=False, index=True)
    price = Column(Numeric(10, 2), nullable=False)
    previous_price = Column(Numeric(10, 2), nullable=True)
    price_change_pct = Column(Numeric(5, 2), nullable=True)  # In Prozent (z.B. 5.50 = +5.5%)
    
    # Tracking Info
    triggered_by = Column(String(100), nullable=True)  # 'pricing_engine', 'manual', 'shopify_sync', 'recommendation', 'product_update'
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Metadata (JSON) - WICHTIG: meta_data statt metadata!
    meta_data = Column(JSONB, nullable=True)
    
    # Relationships
    product = relationship("Product", backref="price_history")
    shop = relationship("Shop", backref="price_history")
    
    # Table Args (Constraints & Indexes)
    __table_args__ = (
        UniqueConstraint('product_id', 'shop_id', 'price_date', name='uq_price_history_unique'),
        CheckConstraint('price > 0', name='ck_price_positive'),
        Index('idx_price_product_date', 'product_id', 'price_date'),
        Index('idx_price_shop_date', 'shop_id', 'price_date'),
    )
