from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    shopify_product_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    cost = Column(Float, nullable=True)
    inventory_quantity = Column(Integer, default=0)
    meta_data = Column(Text, nullable=True)  # JSON als String
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    shop = relationship("Shop", backref="products")
































