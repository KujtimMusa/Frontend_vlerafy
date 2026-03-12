import shopify
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)


class ShopifyDataAdapter:
    """Lädt Daten aus Shopify für Pricing-Analyse"""
    
    def __init__(self, shop_id: int, shop_url: str, access_token: str, api_version: str = "2025-10"):
        self.shop_id = shop_id  # WICHTIG: Jeder Shop hat eigene ID
        self.shop_url = shop_url
        self.access_token = access_token
        self.api_version = api_version
        
        try:
            # Workaround für API Version
            if api_version not in shopify.ApiVersion.versions:
                class TempApiVersion:
                    def __init__(self, name):
                        self.name = name
                    def api_path(self, url):
                        if url.startswith('http://') or url.startswith('https://'):
                            from urllib.parse import urlparse
                            parsed = urlparse(url)
                            path = parsed.path
                            api_path = f"/admin/api/{self.name}{path}"
                            return f"{parsed.scheme}://{parsed.netloc}{api_path}"
                        else:
                            return f"/admin/api/{self.name}{url}"
                temp_version = TempApiVersion(api_version)
                shopify.ApiVersion.versions[api_version] = temp_version
            
            # Session erstellen und aktivieren
            session = shopify.Session(shop_url, api_version, access_token)
            shopify.ShopifyResource.activate_session(session)
            
            # Test ob Session funktioniert
            try:
                shop_info = shopify.Shop.current()
                if shop_info and hasattr(shop_info, 'name'):
                    logger.info(f"✅ Shopify Session aktiviert: {shop_info.name}")
                else:
                    logger.info(f"✅ Shopify Session aktiviert für {shop_url}")
            except (AttributeError, Exception) as e:
                logger.info(f"✅ Shopify Session aktiviert für {shop_url} (Shop.current() nicht verfügbar)")
                
        except Exception as e:
            logger.error(f"Fehler beim Aktivieren der Shopify Session: {e}")
            raise
    
    def load_products(self) -> List[Dict]:
        """Lädt alle Produkte (in-memory, NICHT in DB gespeichert)"""
        try:
            products = shopify.Product.find(limit=250)
            return [self._product_to_dict(p) for p in products]
        except Exception as e:
            logger.error(f"Fehler beim Laden der Produkte: {e}")
            raise
    
    def sync_products_to_db(self, db):
        """Synchronisiert Produkte von Shopify zu DB (mit shop_id)"""
        from app.models.product import Product
        
        try:
            shopify_products = self.load_products()
            synced = 0
            updated = 0
            
            for sp in shopify_products:
                existing = db.query(Product).filter(
                    Product.shop_id == self.shop_id,  # WICHTIG!
                    Product.shopify_product_id == sp['shopify_product_id']
                ).first()
                
                if existing:
                    # Update
                    existing.title = sp['title']
                    existing.price = sp['price']
                    existing.inventory_quantity = sp['inventory_quantity']
                    updated += 1
                else:
                    # Insert
                    new_product = Product(
                        shop_id=self.shop_id,  # WICHTIG!
                        shopify_product_id=sp['shopify_product_id'],
                        title=sp['title'],
                        price=sp['price'],
                        inventory_quantity=sp['inventory_quantity']
                    )
                    db.add(new_product)
                    synced += 1
            
            db.commit()
            logger.info(f"✅ Produktsync: {synced} neu, {updated} aktualisiert (Shop {self.shop_id})")
            return {"synced": synced, "updated": updated}
            
        except Exception as e:
            logger.error(f"Fehler beim Sync: {e}")
            db.rollback()
            raise
    
    def load_product_sales_history(self, product_id: str, days_back: int = 90) -> pd.DataFrame:
        """Lädt Sales-Historie für ein Produkt (letzte 90 Tage)"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            orders = shopify.Order.find(
                status="any",
                created_at_min=start_date.isoformat(),
                limit=250
            )
            
            # Filtere Orders mit diesem Produkt
            sales_data = []
            for order in orders:
                for line_item in order.line_items:
                    if str(line_item.product_id) == str(product_id):
                        sales_data.append({
                            "date": order.created_at,
                            "quantity": line_item.quantity,
                            "price": float(line_item.price),
                            "revenue": float(line_item.price) * line_item.quantity,
                            "order_id": str(order.id) if hasattr(order, 'id') else None,
                            "variant_id": str(line_item.variant_id) if hasattr(line_item, 'variant_id') else None
                        })
            
            return pd.DataFrame(sales_data)
        except Exception as e:
            logger.error(f"Fehler beim Laden der Sales-Historie: {e}")
            raise
    
    def sync_sales_history_to_db(self, db, product_id: int, days_back: int = 90) -> int:
        """
        Synchronisiert Sales-Historie von Shopify API zu DB.
        
        Workflow:
        1. Finde Product in DB via shopify_product_id
        2. Lade Sales-Daten von Shopify API via load_product_sales_history()
        3. Speichere in DB via SalesHistoryService.bulk_save_sales()
        
        Args:
            db: SQLAlchemy Session
            product_id: Shopify Product ID (String!)
            days_back: Anzahl Tage zurück (default 90)
        
        Returns:
            Anzahl gespeicherter Records
        """
        from app.services.sales_history_service import SalesHistoryService
        from app.models.product import Product
        
        # Finde Product in DB
        product = db.query(Product).filter(
            Product.shopify_product_id == str(product_id),
            Product.shop_id == self.shop_id
        ).first()
        
        if not product:
            logger.warning(f"Product {product_id} nicht in DB gefunden")
            return 0
        
        # Lade Sales-Daten von Shopify
        sales_data = self.load_product_sales_history(str(product_id), days_back=days_back)
        
        if sales_data.empty:
            logger.info(f"Keine Sales-Daten für Product {product_id}")
            return 0
        
        # Konvertiere zu Records-Format (mit Order IDs)
        records = []
        for _, row in sales_data.iterrows():
            # Extrahiere order_id aus metadata falls vorhanden
            order_id = row.get('order_id', None)
            records.append({
                'date': row['date'],
                'quantity': int(row.get('quantity', row.get('quantity_sold', 0))),
                'revenue': float(row.get('revenue', 0)),
                'price': float(row.get('price', 0)),
                'order_id': order_id,
                'variant_id': row.get('variant_id'),
                'meta_data': {'source': 'shopify_api'}
            })
        
        # Speichere in DB
        service = SalesHistoryService(db)
        saved_count = service.bulk_save_sales(
            records,
            product_id=product.id,
            shop_id=self.shop_id,
            aggregate_daily=False  # Live-Shop: Ein Record pro Order (mit Order IDs)
        )
        
        logger.info(f"✅ {saved_count} Sales-Records für Product {product_id} gespeichert")
        return saved_count
    
    def load_product_sales_history_extended(self, product_id: str, days_back: int = 730) -> pd.DataFrame:
        """Lädt erweiterte Sales-Historie (bis zu 2 Jahre) - benötigt read_all_orders"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Nutze read_all_orders für ältere Orders
            orders = shopify.Order.find(
                status="any",
                created_at_min=start_date.isoformat(),
                limit=250
            )
            
            sales_data = []
            for order in orders:
                for line_item in order.line_items:
                    if str(line_item.product_id) == str(product_id):
                        sales_data.append({
                            "date": order.created_at,
                            "quantity": line_item.quantity,
                            "price": float(line_item.price),
                            "revenue": float(line_item.price) * line_item.quantity
                        })
            
            return pd.DataFrame(sales_data)
        except Exception as e:
            logger.error(f"Fehler beim Laden der erweiterten Sales-Historie: {e}")
            raise
    
    def load_multiple_products_history(self, product_ids: List[str], days_back: int = 730) -> Dict[str, pd.DataFrame]:
        """Lädt Sales-Historie für mehrere Produkte (Batch-Loading)"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            orders = shopify.Order.find(
                status="any",
                created_at_min=start_date.isoformat(),
                limit=250
            )
            
            # Gruppiere nach Produkt-ID
            product_data = {pid: [] for pid in product_ids}
            
            for order in orders:
                for line_item in order.line_items:
                    product_id_str = str(line_item.product_id)
                    if product_id_str in product_data:
                        product_data[product_id_str].append({
                            "date": order.created_at,
                            "quantity": line_item.quantity,
                            "price": float(line_item.price),
                            "revenue": float(line_item.price) * line_item.quantity
                        })
            
            # Konvertiere zu DataFrames
            return {
                pid: pd.DataFrame(data) if data else pd.DataFrame()
                for pid, data in product_data.items()
            }
        except Exception as e:
            logger.error(f"Fehler beim Batch-Loading: {e}")
            raise
    
    def get_shop_sales_stats(self, days_back: int = 365) -> Dict:
        """Shop-weite Statistiken (Revenue, AOV, Top Products)"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            orders = shopify.Order.find(
                status="any",
                created_at_min=start_date.isoformat(),
                limit=250
            )
            
            total_revenue = 0.0
            total_orders = 0
            product_revenue = {}
            
            for order in orders:
                order_total = float(order.total_price or 0)
                total_revenue += order_total
                total_orders += 1
                
                for line_item in order.line_items:
                    product_id = str(line_item.product_id)
                    revenue = float(line_item.price) * line_item.quantity
                    if product_id not in product_revenue:
                        product_revenue[product_id] = 0.0
                    product_revenue[product_id] += revenue
            
            # Top Products
            top_products = sorted(
                product_revenue.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0.0
            
            return {
                "total_revenue": total_revenue,
                "total_orders": total_orders,
                "avg_order_value": avg_order_value,
                "top_products": [
                    {"product_id": pid, "revenue": rev}
                    for pid, rev in top_products
                ]
            }
        except Exception as e:
            logger.error(f"Fehler bei Shop-Stats: {e}")
            raise
    
    def _product_to_dict(self, product) -> Dict:
        """Konvertiert Shopify Product zu Dict"""
        shopify_id = str(product.id)
        
        return {
            "id": shopify_id,                    # Für API-Kompatibilität
            "shopify_product_id": shopify_id,    # Shopify Product ID
            "title": product.title,
            "price": float(product.variants[0].price) if product.variants and len(product.variants) > 0 else 0.0,
            "inventory_quantity": sum(v.inventory_quantity for v in product.variants) if product.variants else 0,
            "cost": None  # Cost wird später aus Shopify geladen
        }

