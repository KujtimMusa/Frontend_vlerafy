from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
import logging
from app.models.price_history import PriceHistory
from app.models.product import Product

logger = logging.getLogger(__name__)


class PriceHistoryService:
    """
    Service für Price History Tracking und Analytics
    
    Features:
    - Manuelles Price-Tracking (zusätzlich zum PostgreSQL Trigger)
    - Preis-Trend Analyse (DataFrame)
    - Volatilitäts-Berechnung
    - Preis-Statistiken (Min/Max/Avg/Current)
    
    Unterstützt:
    - Demo-Shop (shop_id=999): Tracking von Recommendation-Preisen
    - Live-Shop: Tracking von echten Preisänderungen
    """
    
    def __init__(self, db: Session):
        self.db = db

    def track_price_change(
        self,
        product_id: int,
        shop_id: int,
        new_price: float,
        previous_price: Optional[float] = None,
        triggered_by: str = "pricing_engine",
        meta_data: Optional[Dict] = None
    ) -> PriceHistory:
        """
        Trackt eine Preisänderung (manuell, zusätzlich zum PostgreSQL Trigger).
        
        Args:
            product_id: Product ID (DB ID)
            shop_id: Shop ID (999 für Demo, echte ID für Live)
            new_price: Neuer Preis
            previous_price: Vorheriger Preis (optional, wird automatisch geladen)
            triggered_by: Quelle ('pricing_engine', 'manual', 'shopify_sync', 'recommendation')
            meta_data: Zusätzliche Daten (z.B. recommendation_id)
        
        Returns:
            PriceHistory Record
        """
        price_date = date.today()
        
        # Prüfe ob heute bereits ein Eintrag existiert
        existing = self.db.query(PriceHistory).filter(
            PriceHistory.product_id == product_id,
            PriceHistory.shop_id == shop_id,
            PriceHistory.price_date == price_date
        ).first()
        
        if existing:
            # Update existing record
            if previous_price is None:
                previous_price = existing.previous_price or existing.price
            existing.price = new_price
            existing.previous_price = previous_price
            existing.price_change_pct = ((new_price - previous_price) / previous_price * 100) if previous_price and previous_price > 0 else None
            existing.triggered_by = triggered_by
            existing.meta_data = meta_data
            return existing
        
        # Get previous price if not provided
        if previous_price is None:
            last_price = self.db.query(PriceHistory).filter(
                PriceHistory.product_id == product_id,
                PriceHistory.shop_id == shop_id
            ).order_by(PriceHistory.price_date.desc()).first()
            previous_price = last_price.price if last_price else None
        
        # Create new record
        price_change_pct = ((new_price - previous_price) / previous_price * 100) if previous_price and previous_price > 0 else None
        
        new_record = PriceHistory(
            product_id=product_id,
            shop_id=shop_id,
            price_date=price_date,
            price=new_price,
            previous_price=previous_price,
            price_change_pct=price_change_pct,
            triggered_by=triggered_by,
            meta_data=meta_data
        )
        self.db.add(new_record)
        self.db.commit()
        return new_record
    
    def get_price_trend(
        self,
        product_id: int,
        shop_id: int,
        days_back: int = 90
    ) -> pd.DataFrame:
        """
        Lädt Preis-Trend als DataFrame.
        
        Returns:
            DataFrame mit Spalten: ['date', 'price', 'price_change_pct']
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        records = self.db.query(PriceHistory).filter(
            PriceHistory.product_id == product_id,
            PriceHistory.shop_id == shop_id,
            PriceHistory.price_date >= start_date
        ).order_by(PriceHistory.price_date.asc()).all()
        
        if not records:
            return pd.DataFrame(columns=['date', 'price', 'price_change_pct'])
        
        data = []
        for record in records:
            data.append({
                'date': record.price_date,
                'price': float(record.price),
                'price_change_pct': float(record.price_change_pct) if record.price_change_pct else None
            })
        
        return pd.DataFrame(data)
    
    def calculate_volatility(
        self,
        product_id: int,
        shop_id: int,
        days_back: int = 30
    ) -> float:
        """
        Berechnet Preis-Volatilität (Standardabweichung der Preisänderungen).
        
        Returns:
            Volatilität als Float (0.0 = stabil, höher = volatil)
        """
        trend = self.get_price_trend(product_id, shop_id, days_back)
        
        if trend.empty or len(trend) < 2:
            return 0.0
        
        # Berechne tägliche Preisänderungen (Percent Change)
        trend['price_change'] = trend['price'].pct_change()
        
        # Volatilität = Standardabweichung der Preisänderungen
        volatility = trend['price_change'].std()
        
        return float(volatility) if not pd.isna(volatility) else 0.0
    
    def get_price_statistics(
        self,
        product_id: int,
        shop_id: int,
        days_back: int = 90
    ) -> Dict:
        """
        Berechnet Preis-Statistiken.
        
        Returns:
            Dict mit: min_price, max_price, avg_price, current_price, volatility, price_changes
        """
        trend = self.get_price_trend(product_id, shop_id, days_back)
        
        if trend.empty:
            return {
                'min_price': None,
                'max_price': None,
                'avg_price': None,
                'current_price': None,
                'volatility': 0.0,
                'price_changes': 0
            }
        
        return {
            'min_price': float(trend['price'].min()),
            'max_price': float(trend['price'].max()),
            'avg_price': float(trend['price'].mean()),
            'current_price': float(trend['price'].iloc[-1]),
            'volatility': self.calculate_volatility(product_id, shop_id, days_back),
            'price_changes': len(trend[trend['price_change_pct'].notna()])
        }
