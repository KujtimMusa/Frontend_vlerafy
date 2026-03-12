"""
Margin Calculator Models
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base


class ProductCost(Base):
    """Stores cost data for products"""
    __tablename__ = "product_costs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(255), nullable=False, index=True)
    shop_id = Column(String(255), nullable=False, index=True)
    
    # Cost Components
    purchase_cost = Column(Numeric(10, 2), nullable=False, comment='Einkaufspreis netto in €')
    shipping_cost = Column(Numeric(10, 2), default=0.00, comment='Versandkosten pro Einheit')
    packaging_cost = Column(Numeric(10, 2), default=0.00, comment='Verpackungskosten pro Einheit')
    
    # Payment Provider Settings
    payment_provider = Column(String(50), default='stripe', comment='stripe, paypal, klarna, custom')
    payment_fee_percentage = Column(Numeric(5, 3), default=2.900, comment='z.B. 2.9 für 2.9%')
    payment_fee_fixed = Column(Numeric(10, 2), default=0.30, comment='Fixe Fee in € z.B. 0.30')
    
    # VAT Settings
    vat_rate = Column(Numeric(5, 3), default=0.190, comment='MwSt-Satz z.B. 0.19 für 19%')
    country_code = Column(String(2), default='DE', comment='DE, AT, CH, US, GB')
    
    # Metadata
    category = Column(String(100), nullable=True, comment='fashion, electronics, beauty, etc.')
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('product_id', 'shop_id', name='uq_product_costs_product_shop'),
        CheckConstraint('purchase_cost >= 0', name='ck_purchase_cost_positive'),
        CheckConstraint('shipping_cost >= 0', name='ck_shipping_cost_positive'),
        CheckConstraint('packaging_cost >= 0', name='ck_packaging_cost_positive'),
        Index('ix_product_costs_shop_category', 'shop_id', 'category'),
    )


class MarginCalculation(Base):
    """Historical margin calculations for audit trail"""
    __tablename__ = "margin_calculations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(255), nullable=False, index=True)
    shop_id = Column(String(255), nullable=False, index=True)
    calculation_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Pricing Data
    selling_price = Column(Numeric(10, 2), nullable=False, comment='Verkaufspreis brutto')
    net_revenue = Column(Numeric(10, 2), nullable=False, comment='Nettoerlös nach MwSt')
    
    # Cost Breakdown
    purchase_cost = Column(Numeric(10, 2), nullable=False)
    shipping_cost = Column(Numeric(10, 2), nullable=False)
    packaging_cost = Column(Numeric(10, 2), nullable=False)
    payment_fee = Column(Numeric(10, 2), nullable=False)
    total_variable_costs = Column(Numeric(10, 2), nullable=False)
    
    # Margin Results
    contribution_margin_euro = Column(Numeric(10, 2), nullable=False, comment='DB I in €')
    contribution_margin_percent = Column(Numeric(5, 2), nullable=False, comment='DB I in %')
    
    # Reference Data
    break_even_price = Column(Numeric(10, 2), nullable=False)
    recommended_min_price = Column(Numeric(10, 2), nullable=False, comment='Bei 20% Mindestmarge')
    
    # Context
    triggered_by = Column(String(100), comment='pricing_engine, manual, autopilot')
    calculation_metadata = Column(JSONB, comment='Additional context')
    
    __table_args__ = (
        Index('ix_margin_calc_product_date', 'product_id', 'calculation_date'),
    )






























