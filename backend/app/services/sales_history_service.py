from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
import pandas as pd
import logging
from app.models.sales_history import SalesHistory
from app.models.product import Product

logger = logging.getLogger(__name__)


class SalesHistoryService:
    """
    Service für Sales History CRUD und Analytics
    
    Features:
    - Speichert Sales-Records (Duplikat-Check)
    - Bulk-Insert für Sync (mit/ohne Aggregation)
    - Lädt Sales-Historie als DataFrame (kompatibel mit bestehendem Code)
    - Berechnet aggregierte Metriken
    
    Unterstützt:
    - Demo-Shop (shop_id=999): aggregate_daily=True (CSV ohne Order IDs)
    - Live-Shop (Shopify): aggregate_daily=False (mit Order IDs)
    """
    
    def __init__(self, db: Session):
        self.db = db

    def save_sales_record(
        self,
        product_id: int,
        shop_id: int,
        sale_date: date,
        quantity_sold: int,
        revenue: float,
        unit_price: Optional[float] = None,
        order_id: Optional[str] = None,
        variant_id: Optional[str] = None,
        meta_data: Optional[Dict] = None
    ) -> SalesHistory:
        """
        Speichert einen einzelnen Sales-Record mit Duplikat-Check.
        Update bei existierendem Record, Insert bei neuem Record.
        """
        # Prüfe auf Duplikat
        existing = self.db.query(SalesHistory).filter(
            SalesHistory.product_id == product_id,
            SalesHistory.shop_id == shop_id,
            SalesHistory.sale_date == sale_date,
            SalesHistory.order_id == order_id
        ).first()
        
        if existing:
            # Update existing record
            existing.quantity_sold = quantity_sold
            existing.revenue = revenue
            existing.unit_price = unit_price or (revenue / quantity_sold if quantity_sold > 0 else None)
            existing.variant_id = variant_id
            existing.meta_data = meta_data
            existing.updated_at = datetime.now()
            return existing
        
        # Create new record
        new_record = SalesHistory(
            product_id=product_id,
            shop_id=shop_id,
            sale_date=sale_date,
            quantity_sold=quantity_sold,
            revenue=revenue,
            unit_price=unit_price or (revenue / quantity_sold if quantity_sold > 0 else None),
            order_id=order_id,
            variant_id=variant_id,
            meta_data=meta_data
        )
        self.db.add(new_record)
        return new_record

    def bulk_save_sales(
        self,
        sales_data: List[Dict],
        product_id: int,
        shop_id: int,
        aggregate_daily: bool = False
    ) -> int:
        """
        Bulk-Insert von Sales-Daten für Sync.
        
        Args:
            sales_data: Liste von Sales-Records (Format: [{'date': ..., 'quantity': ..., 'revenue': ..., ...}])
            product_id: Product ID (DB ID, nicht Shopify ID!)
            shop_id: Shop ID (999 für Demo-Shop, echte ID für Live-Shop)
            aggregate_daily: 
                - True: Aggregiere Sales pro Tag (für CSV ohne Order IDs)
                - False: Ein Record pro Sale (für Shopify mit Order IDs)
        
        Returns:
            Anzahl gespeicherter Records
        """
        saved_count = 0
        
        if aggregate_daily:
            # Aggregiere Sales pro Tag (für CSV-Daten ohne Order IDs)
            daily_sales = {}
            for sale in sales_data:
                try:
                    sale_date = pd.to_datetime(sale['date']).date() if isinstance(sale['date'], str) else sale['date']
                    if hasattr(sale_date, 'date'):
                        sale_date = sale_date.date()
                    date_key = str(sale_date)
                    
                    if date_key not in daily_sales:
                        daily_sales[date_key] = {
                            'date': sale_date,
                            'quantity': 0,
                            'revenue': 0.0,
                            'price': sale.get('price', 0),
                            'order_id': None,  # CSV hat keine Order IDs
                            'variant_id': sale.get('variant_id'),
                            'meta_data': sale.get('meta_data', sale.get('metadata', {}))
                        }
                    
                    daily_sales[date_key]['quantity'] += sale.get('quantity', sale.get('quantity_sold', 0))
                    daily_sales[date_key]['revenue'] += sale.get('revenue', 0)
                except Exception as e:
                    logger.warning(f"Fehler beim Aggregieren von Sales-Record: {e}")
                    continue
            
            # Speichere aggregierte tägliche Sales
            for date_key, aggregated in daily_sales.items():
                try:
                    self.save_sales_record(
                        product_id=product_id,
                        shop_id=shop_id,
                        sale_date=aggregated['date'],
                        quantity_sold=aggregated['quantity'],
                        revenue=aggregated['revenue'],
                        unit_price=aggregated['price'],
                        order_id=None,  # CSV: Keine Order IDs
                        variant_id=aggregated['variant_id'],
                        meta_data=aggregated.get('meta_data', aggregated.get('metadata', {}))
                    )
                    saved_count += 1
                except Exception as e:
                    logger.warning(f"Fehler beim Speichern von aggregiertem Sales-Record: {e}")
                    continue
        else:
            # Normale Speicherung (ein Record pro Sale, für Shopify mit Order IDs)
            for sale in sales_data:
                try:
                    sale_date = pd.to_datetime(sale['date']).date() if isinstance(sale['date'], str) else sale['date']
                    if hasattr(sale_date, 'date'):
                        sale_date = sale_date.date()
                    
                    self.save_sales_record(
                        product_id=product_id,
                        shop_id=shop_id,
                        sale_date=sale_date,
                        quantity_sold=sale.get('quantity', sale.get('quantity_sold', 0)),
                        revenue=sale.get('revenue', 0),
                        unit_price=sale.get('price'),
                        order_id=sale.get('order_id'),
                        variant_id=sale.get('variant_id'),
                        meta_data=sale.get('meta_data', sale.get('metadata'))
                    )
                    saved_count += 1
                except Exception as e:
                    logger.warning(f"Fehler beim Speichern von Sales-Record: {e}")
                    continue
        
        self.db.commit()
        return saved_count

    def get_sales_history(
        self,
        product_id: int,
        shop_id: int,
        days_back: int = 90,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        Lädt Sales-Historie als DataFrame (kompatibel mit bestehendem Code).
        
        Returns:
            DataFrame mit Spalten: ['date', 'quantity', 'revenue', 'price']
        """
        query = self.db.query(SalesHistory).filter(
            SalesHistory.product_id == product_id,
            SalesHistory.shop_id == shop_id
        )
        
        if start_date:
            query = query.filter(SalesHistory.sale_date >= start_date)
        if end_date:
            query = query.filter(SalesHistory.sale_date <= end_date)
        elif days_back:
            end_date = date.today()
            start_date = end_date - timedelta(days=days_back)
            query = query.filter(SalesHistory.sale_date >= start_date)
        
        records = query.order_by(SalesHistory.sale_date.asc()).all()
        
        if not records:
            return pd.DataFrame(columns=['date', 'quantity', 'revenue', 'price'])
        
        # Konvertiere zu DataFrame (kompatibel mit bestehendem Format)
        data = []
        for record in records:
            data.append({
                'date': record.sale_date,
                'quantity': record.quantity_sold,
                'revenue': float(record.revenue),
                'price': float(record.unit_price) if record.unit_price else (float(record.revenue) / record.quantity_sold if record.quantity_sold > 0 else 0)
            })
        
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        return df
    
    def get_aggregated_sales(
        self,
        product_id: int,
        shop_id: int,
        days_back: int = 30
    ) -> Dict:
        """Berechnet aggregierte Sales-Metriken"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        result = self.db.query(
            func.sum(SalesHistory.quantity_sold).label('total_quantity'),
            func.sum(SalesHistory.revenue).label('total_revenue'),
            func.avg(SalesHistory.unit_price).label('avg_price')
        ).filter(
            SalesHistory.product_id == product_id,
            SalesHistory.shop_id == shop_id,
            SalesHistory.sale_date >= start_date
        ).first()
        
        return {
            'total_quantity': int(result.total_quantity or 0),
            'total_revenue': float(result.total_revenue or 0),
            'avg_price': float(result.avg_price or 0),
            'days_back': days_back
        }
