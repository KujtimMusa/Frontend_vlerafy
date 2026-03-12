"""
CSV-basierter Demo-Shop-Adapter
Verhält sich identisch wie ShopifyDataAdapter für Testing und ML-Training
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import csv
import pandas as pd
import os
import logging
from pathlib import Path
from app.utils.datetime_helpers import get_effective_now
from app.core.shop_context import ShopContext

logger = logging.getLogger(__name__)


class CSVDemoShopAdapter:
    """
    CSV-basierter Demo-Shop der sich identisch wie ShopifyDataAdapter verhält.
    Liest Daten aus CSV-Dateien und cached sie im Speicher.
    """
    
    def __init__(
        self, 
        products_csv: str = None,
        sales_history_csv: str = None,
        competitors_csv: Optional[str] = None,
        shop_context: Optional[ShopContext] = None
    ):
        """
        Initialisiere Adapter mit CSV-Dateien.
        Demo-Shop arbeitet nur in-memory mit CSV-Daten, KEINE DB-Speicherung!
        
        Args:
            products_csv: Pfad zu products CSV (optional, default: /app/data/demo_products.csv)
            sales_history_csv: Pfad zu sales history CSV (optional, default: /app/data/demo_sales_history.csv)
            competitors_csv: Pfad zu competitors CSV (optional, default: /app/data/demo_competitors.csv)
        """
        # Resolve paths relative to project root
        project_root = Path(__file__).parent.parent.parent
        
        # Default paths
        if products_csv is None:
            products_csv = project_root / 'data' / 'demo_products.csv'
        if sales_history_csv is None:
            sales_history_csv = project_root / 'data' / 'demo_sales_history.csv'
        if competitors_csv is None:
            competitors_csv = project_root / 'data' / 'demo_competitors.csv'
        
        self.products_csv = Path(products_csv) if not os.path.isabs(products_csv) else Path(products_csv)
        self.sales_history_csv = Path(sales_history_csv) if not os.path.isabs(sales_history_csv) else Path(sales_history_csv)
        self.competitors_csv = Path(competitors_csv) if competitors_csv and not os.path.isabs(competitors_csv) else (Path(competitors_csv) if competitors_csv else None)
        
        # In-Memory Cache (wird bei jedem Request neu geladen)
        self._products_cache = None
        self._sales_cache = None
        self._competitors_cache = None
        self.shop_context = shop_context
        
        # Initial load
        self._load_data()
    
    def _load_data(self) -> None:
        """Load all CSV files into memory cache"""
        try:
            # Load products
            if not self.products_csv.exists():
                raise FileNotFoundError(f"Products CSV nicht gefunden: {self.products_csv}")
            
            self._products_cache = pd.read_csv(self.products_csv)
            logger.info(f"✅ Geladen: {len(self._products_cache)} Demo-Produkte aus CSV")
            
            # Load sales history
            if not self.sales_history_csv.exists():
                logger.warning(f"Sales History CSV nicht gefunden: {self.sales_history_csv}")
                self._sales_cache = pd.DataFrame()
            else:
                self._sales_cache = pd.read_csv(self.sales_history_csv)
                self._sales_cache['date'] = pd.to_datetime(self._sales_cache['date'])
                logger.info(f"✅ Geladen: {len(self._sales_cache)} Sales-Einträge aus CSV")
                
                # DEBUG: Log Product 1 details
                p1_rows = self._sales_cache[self._sales_cache['product_id'] == 1]
                logger.info(f"✅ CSV DEBUG - Product 1: {len(p1_rows)} rows, {p1_rows['quantity_sold'].sum()} total sales")
                logger.info(f"✅ CSV DEBUG - Date range: {self._sales_cache['date'].min()} to {self._sales_cache['date'].max()}")
            
            # Load competitors (optional)
            if self.competitors_csv and self.competitors_csv.exists():
                self._competitors_cache = pd.read_csv(self.competitors_csv)
                if 'scraped_at' in self._competitors_cache.columns:
                    self._competitors_cache['scraped_at'] = pd.to_datetime(self._competitors_cache['scraped_at'])
                logger.info(f"✅ Geladen: {len(self._competitors_cache)} Competitor-Einträge aus CSV")
            else:
                self._competitors_cache = pd.DataFrame()
                logger.info("Keine Competitor-Daten gefunden (optional)")
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der CSV-Daten: {e}", exc_info=True)
            raise
    
    def load_products(self) -> List[Dict]:
        """
        Gibt alle Produkte zurück (wie Shopify API).
        
        Returns:
            List[Dict] mit Struktur:
            {
                'id': int,
                'shopify_product_id': str,
                'title': str,
                'sku': str,
                'category': str,
                'brand': str,
                'price': float,
                'cost': float,
                'inventory': int,
                'avg_daily_sales': float,
                'tags': List[str]
            }
        """
        if self._products_cache is None:
            self._load_data()
        
        products = []
        for _, row in self._products_cache.iterrows():
            # Parse tags
            tags = []
            if pd.notna(row.get('tags')):
                tags = [t.strip() for t in str(row['tags']).split(',')]
            
            # Kompatibel mit Shopify-Adapter Format
            # WICHTIG: id als Integer für Frontend-Kompatibilität
            product_id = int(row.get('id', row.get('product_id', 0)))
            products.append({
                'id': product_id,  # Integer statt String für Frontend-Kompatibilität
                'shopify_product_id': str(product_id),  # String für Shopify-Kompatibilität
                'title': str(row['title']),
                'price': float(row['price']),
                'inventory_quantity': int(row.get('inventory', 0)),
                'cost': float(row.get('cost', 0)) if pd.notna(row.get('cost')) else None,
                # Zusätzliche Demo-Daten (optional)
                'sku': str(row.get('sku', '')),
                'category': str(row.get('category', '')),
                'brand': str(row.get('brand', '')),
                'avg_daily_sales': float(row.get('avg_daily_sales', 0)),
                'tags': tags
            })
        
        return products
    
    def load_product_sales_history(
        self, 
        product_id: str,  # String wie Shopify-Adapter
        days_back: int = 90
    ) -> pd.DataFrame:
        """
        Gibt Sales-Historie für ein Produkt zurück.
        
        Args:
            product_id: Product ID (String)
            days_back: Anzahl Tage zurück (default 90, für vollständige Sales-Historie)
        
        Returns:
            DataFrame mit Spalten:
            - date: datetime
            - quantity: int (quantity_sold)
            - revenue: float
            - price: float
        """
        logger.debug("")
        logger.debug(f"📂 CSV ADAPTER: Loading sales for product {product_id}")
        logger.debug(f"   Days back requested: {days_back}")
        
        if self._sales_cache is None or self._sales_cache.empty:
            logger.warning(f"   ⚠️ No sales cache available")
            return pd.DataFrame()
        
        # Convert product_id to int (CSV uses int, but API accepts string)
        try:
            # Entferne "demo_" Präfix falls vorhanden
            product_id_clean = str(product_id).replace('demo_', '')
            product_id_int = int(product_id_clean)
        except (ValueError, TypeError):
            logger.warning(f"   ❌ Could not convert product_id: {product_id}")
            return pd.DataFrame()
        
        # Filter by product_id
        df_all = self._sales_cache.copy()
        logger.debug(f"   CSV file total rows: {len(df_all)}")
        
        product_sales = df_all[
            df_all['product_id'] == product_id_int
        ].copy()
        
        logger.debug(f"   After product filter: {len(product_sales)}")
        
        if product_sales.empty:
            logger.debug(f"   ❌ No data found for product {product_id}")
            logger.debug("")
            return pd.DataFrame()
        
        # Filter by date range
        # Use effective_now for demo mode compatibility (demo CSV data may be historical)
        product_sales['date'] = pd.to_datetime(product_sales['date'])
        
        # Create a demo ShopContext if not provided (CSVDemoShopAdapter is always demo)
        if self.shop_context is None:
            from app.core.shop_context import ShopContext
            demo_context = ShopContext("demo_session")
            demo_context.is_demo_mode = True
            effective_now = get_effective_now(product_sales, demo_context)
        else:
            effective_now = get_effective_now(product_sales, self.shop_context)
        
        start_date = effective_now - timedelta(days=days_back)
        
        product_sales = product_sales[
            product_sales['date'] >= start_date
        ].copy()
        
        logger.debug(f"   After date filter ({days_back}d): {len(product_sales)}")
        
        # Sort by date (newest first)
        product_sales = product_sales.sort_values('date', ascending=False)
        
        # Rename columns for compatibility
        if 'quantity_sold' in product_sales.columns:
            product_sales['quantity'] = product_sales['quantity_sold']
        
        # Ensure required columns exist
        required_cols = ['date', 'quantity']
        for col in required_cols:
            if col not in product_sales.columns:
                product_sales[col] = 0
        
        # Select only needed columns
        available_cols = ['date', 'quantity']
        if 'revenue' in product_sales.columns:
            available_cols.append('revenue')
        if 'price' in product_sales.columns:
            available_cols.append('price')
        
        result = product_sales[available_cols].copy()
        
        # Result summary
        if not result.empty:
            days_span = (result['date'].max() - result['date'].min()).days
            total_units = result['quantity'].sum() if 'quantity' in result.columns else 0
            logger.debug(f"   ✅ Result: {len(result)} rows | {days_span} days | {total_units} units sold")
        else:
            logger.debug(f"   ❌ No data found for product {product_id}")
        
        logger.debug("")
        return result
    
    def sync_sales_history_to_db(
        self, 
        db, 
        product_id: int, 
        days_back: int = 90,
        shop_id: int = 999
    ) -> int:
        """
        Synchronisiert Sales-Historie aus CSV zu DB (OPTIONAL für Demo-Shop).
        
        WICHTIG: 
        - Demo-Shop arbeitet normalerweise in-memory
        - DB-Speicherung ermöglicht ML-Training und historische Analyse
        - CSV-Daten haben keine Order IDs → aggregate_daily=True
        
        Workflow:
        1. Finde Product in DB (shop_id=999 für Demo-Shop)
        2. Lade Sales-Daten aus CSV via load_product_sales_history()
        3. WICHTIG: get_effective_now() wird bereits in load_product_sales_history() genutzt!
        4. Speichere in DB via SalesHistoryService.bulk_save_sales() mit aggregate_daily=True
        
        Args:
            db: SQLAlchemy Session
            product_id: Product ID (Integer!)
            days_back: Anzahl Tage zurück (default 90)
            shop_id: Shop ID (default 999 = Demo-Shop)
        
        Returns:
            Anzahl gespeicherter Records
        """
        from app.services.sales_history_service import SalesHistoryService
        from app.models.product import Product
        
        # Finde Product in DB (Demo-Shop hat shop_id=999)
        product = db.query(Product).filter(
            Product.shopify_product_id == str(product_id),
            Product.shop_id == shop_id
        ).first()
        
        if not product:
            logger.warning(f"Product {product_id} nicht in DB gefunden (Demo-Shop {shop_id})")
            return 0
        
        # Lade Sales-Daten aus CSV
        # WICHTIG: load_product_sales_history() nutzt bereits get_effective_now()
        # Das bedeutet: Daten werden relativ zu max_date aus CSV gefiltert
        sales_data = self.load_product_sales_history(str(product_id), days_back=days_back)
        
        if sales_data.empty:
            logger.warning(f"Keine Sales-Daten in CSV für Product {product_id}")
            return 0
        
        # Konvertiere zu erwartetem Format
        sales_records = []
        for _, row in sales_data.iterrows():
            sales_records.append({
                'date': row['date'],  # Bereits gefiltert relativ zu effective_now
                'quantity': int(row.get('quantity', row.get('quantity_sold', 0))),
                'revenue': float(row.get('revenue', 0)),
                'price': float(row.get('price', 0)),
                'order_id': None,  # CSV hat keine Order IDs
                'variant_id': None,
                'meta_data': {'source': 'csv_demo'}
            })
        
        # Speichere in DB
        service = SalesHistoryService(db)
        saved_count = service.bulk_save_sales(
            sales_records,
            product_id=product.id,
            shop_id=shop_id,
            aggregate_daily=True  # WICHTIG: CSV-Daten aggregieren (keine Order IDs!)
        )
        
        logger.info(f"✅ {saved_count} Sales-Records aus CSV für Product {product_id} (Demo-Shop {shop_id}) gespeichert")
        return saved_count
    
    def get_inventory_level(self, product_id: str) -> int:
        """
        Aktueller Lagerbestand
        
        Args:
            product_id: Product ID (String)
        
        Returns:
            Inventory quantity
        """
        if self._products_cache is None:
            self._load_data()
        
        # Convert product_id to int
        try:
            product_id_int = int(product_id)
        except (ValueError, TypeError):
            if isinstance(product_id, str) and product_id.startswith('demo_'):
                product_id_int = int(product_id.replace('demo_', ''))
            else:
                return 0
        
        product = self._products_cache[
            self._products_cache['product_id'] == product_id_int
        ]
        
        if product.empty:
            return 0
        
        return int(product.iloc[0]['inventory'])
    
    def get_product_cost(self, product_id: str) -> Optional[float]:
        """
        EK-Preis des Produkts
        
        Args:
            product_id: Product ID
        
        Returns:
            Cost price or None
        """
        if self._products_cache is None:
            self._load_data()
        
        # Convert product_id to int
        try:
            product_id_int = int(product_id)
        except (ValueError, TypeError):
            if isinstance(product_id, str) and product_id.startswith('demo_'):
                product_id_int = int(product_id.replace('demo_', ''))
            else:
                return None
        
        product = self._products_cache[
            self._products_cache['product_id'] == product_id_int
        ]
        
        if product.empty:
            return None
        
        cost = product.iloc[0].get('cost')
        if pd.isna(cost):
            return None
        
        return float(cost)
    
    def load_competitors(self, product_id: str) -> List[Dict]:
        """
        Lädt Competitor-Daten für ein Produkt aus CSV
        
        Args:
            product_id: Product ID (String)
        
        Returns:
            List[Dict] mit Competitor-Daten
        """
        if self._competitors_cache is None or self._competitors_cache.empty:
            return []
        
        # Convert product_id to int
        try:
            product_id_clean = str(product_id).replace('demo_', '')
            product_id_int = int(product_id_clean)
        except (ValueError, TypeError):
            return []
        
        competitors = self._competitors_cache[
            self._competitors_cache['product_id'] == product_id_int
        ]
        
        result = []
        for _, row in competitors.iterrows():
            result.append({
                'competitor_name': str(row['competitor_name']),
                'competitor_url': str(row['competitor_url']),
                'price': float(row['price']) if pd.notna(row['price']) else None,
                'scraped_at': row['scraped_at'] if pd.notna(row.get('scraped_at')) else datetime.now()
            })
        
        logger.info(f"✅ Geladen: {len(result)} Competitor-Einträge für Produkt {product_id}")
        return result
    
    def calculate_metrics(self, product_id: str) -> Dict:
        """
        Berechnet Metriken aus Sales-Historie
        
        Args:
            product_id: Product ID (String)
        
        Returns:
            {
                'sales_7d': int,
                'sales_30d': int,
                'avg_daily_sales': float,
                'days_of_stock': float,
                'demand_growth': float
            }
        """
        sales_df = self.load_product_sales_history(product_id, days_back=90)
        
        if sales_df.empty:
            products = self.load_products()
            product = next((p for p in products if str(p['id']) == str(product_id)), None)
            inventory = product['inventory_quantity'] if product else 0
            
            return {
                "sales_7d": 0,
                "sales_30d": 0,
                "avg_daily_sales": 0.0,
                "days_of_stock": float('inf') if inventory > 0 else 0.0,
                "demand_growth": 0.0
            }
        
        sales_df['date'] = pd.to_datetime(sales_df['date'])
        
        # Use effective_now for demo mode compatibility
        if self.shop_context is None:
            from app.core.shop_context import ShopContext
            demo_context = ShopContext("demo_session")
            demo_context.is_demo_mode = True
            effective_now = get_effective_now(sales_df, demo_context)
        else:
            effective_now = get_effective_now(sales_df, self.shop_context)
        
        # Sales letzte 7 Tage
        sales_7d = sales_df[sales_df['date'] >= (effective_now - timedelta(days=7))]['quantity'].sum()
        
        # Sales letzte 30 Tage
        sales_30d = sales_df[sales_df['date'] >= (effective_now - timedelta(days=30))]['quantity'].sum()
        
        # Durchschnittliche tägliche Sales
        avg_daily_sales = sales_30d / 30 if sales_30d > 0 else 0
        
        # Days of Stock (einfache Schätzung)
        products = self.load_products()
        product = next((p for p in products if str(p['id']) == str(product_id)), None)
        inventory = product['inventory_quantity'] if product else 0
        days_of_stock = inventory / avg_daily_sales if avg_daily_sales > 0 else 999
        
        # Demand Growth (Vergleich letzte 7 vs vorherige 7 Tage)
        prev_7d = sales_df[(sales_df['date'] >= (effective_now - timedelta(days=14))) & 
                           (sales_df['date'] < (effective_now - timedelta(days=7)))]['quantity'].sum()
        demand_growth = ((sales_7d - prev_7d) / prev_7d * 100) if prev_7d > 0 else 0
        
        return {
            "sales_7d": int(sales_7d),
            "sales_30d": int(sales_30d),
            "avg_daily_sales": float(avg_daily_sales),
            "days_of_stock": float(days_of_stock),
            "demand_growth": float(demand_growth)
        }
    
    def refresh_cache(self) -> None:
        """
        Reload CSV files (z.B. nach manuellen Änderungen).
        In echtem Shopify würde das ein API-Call sein.
        """
        logger.info("Aktualisiere CSV-Cache...")
        self._load_data()
        logger.info("Cache aktualisiert")

