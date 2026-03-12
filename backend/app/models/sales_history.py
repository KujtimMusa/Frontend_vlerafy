from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class SalesHistory(Base):
    """
    Sales History Table - Persistiert historische Verkaufsdaten
    
    Unterstützt:
    - Demo-Shop (shop_id=999): CSV-Daten, aggregiert täglich, keine Order IDs
    - Live-Shop (Shopify): API-Daten, ein Record pro Order, mit Order IDs
    
    Verwendet für:
    - ML Feature Engineering (19 neue Features!)
    - Performance-Optimierung (DB statt API-Calls)
    - Historische Analyse (90+ Tage)
    """
    __tablename__ = "sales_history"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Keys
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Sales Data
    sale_date = Column(Date, nullable=False, index=True)
    quantity_sold = Column(Integer, nullable=False, server_default='0')
    revenue = Column(Numeric(10, 2), nullable=False, server_default='0')
    unit_price = Column(Numeric(10, 2), nullable=True)
    
    # Shopify-specific (nullable für CSV!)
    order_id = Column(String(255), nullable=True, index=True)  # NULL für CSV Demo-Daten
    variant_id = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Metadata (JSON) - WICHTIG: "metadata" ist reserviert, nutze "meta_data"
    meta_data = Column(JSONB, nullable=True)
    
    # Relationships
    product = relationship("Product", backref="sales_history")
    shop = relationship("Shop", backref="sales_history")
    
    # Table Args (Constraints & Indexes)
    __table_args__ = (
        CheckConstraint('quantity_sold >= 0', name='ck_quantity_positive'),
        CheckConstraint('revenue >= 0', name='ck_revenue_positive'),
        Index('idx_sales_product_date', 'product_id', 'sale_date'),
        Index('idx_sales_shop_date', 'shop_id', 'sale_date'),
    )
