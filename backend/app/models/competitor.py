"""
Competitor Price Tracking Model
Speichert Wettbewerberpreise für Produkte
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class CompetitorPrice(Base):
    __tablename__ = 'competitor_prices'
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False, index=True)
    competitor_name = Column(String(255), nullable=False)
    competitor_url = Column(String(512), nullable=False)
    price = Column(Float, nullable=True)
    in_stock = Column(Boolean, default=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    scrape_success = Column(Boolean, default=False)
    last_error = Column(String(512), nullable=True)
    
    # Relationship
    product = relationship("Product", backref="competitor_prices")
    
    # Indexes für Performance
    __table_args__ = (
        Index('idx_product_scraped', 'product_id', 'scraped_at'),
    )
    
    def __repr__(self):
        return f"<CompetitorPrice {self.competitor_name}: €{self.price}>"
































