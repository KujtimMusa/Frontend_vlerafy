"""
Kaggle Data Loader mit ECHTER History-Berechnung
Aggregiert Transaktionen pro Produkt über Zeit
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class KaggleHistoryLoader:
    """
    Lädt Kaggle E-Commerce Daten und berechnet ECHTE History-Features
    """
    
    def __init__(self, csv_path: str = None):
        """
        Args:
            csv_path: Pfad zur Kaggle CSV (default: auto-detect)
        """
        if not csv_path:
            # Auto-detect: Suche in data/kaggle/
            possible_paths = [
                Path(__file__).parent.parent.parent.parent / 'data' / 'kaggle' / 'data.csv',
                Path(__file__).parent.parent.parent.parent / 'data' / 'kaggle' / 'ecommerce-data.csv',
                Path(__file__).parent.parent.parent.parent / 'data' / 'ml_training_ecommerce.csv',
            ]
            
            for path in possible_paths:
                if path.exists():
                    csv_path = str(path)
                    break
            
            if not csv_path:
                raise FileNotFoundError("Kaggle CSV not found! Check data/kaggle/")
        
        self.csv_path = csv_path
        logger.info(f"Kaggle CSV: {csv_path}")
    
    
    def load_and_preprocess(self) -> pd.DataFrame:
        """
        Lädt Kaggle-Daten und bereitet sie vor
        
        Returns:
            DataFrame mit: InvoiceDate, StockCode, Quantity, UnitPrice
        """
        logger.info("📊 Loading Kaggle data...")
        
        # Load CSV
        df = pd.read_csv(self.csv_path, encoding='ISO-8859-1', low_memory=False)
        
        logger.info(f"   Loaded {len(df):,} transactions")
        
        # Clean
        df = df.dropna(subset=['InvoiceDate', 'StockCode', 'Quantity', 'UnitPrice'])
        df = df[df['Quantity'] > 0]  # Nur positive Quantities
        df = df[df['UnitPrice'] > 0]  # Nur positive Preise
        
        # Parse Date
        df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'], errors='coerce')
        df = df.dropna(subset=['InvoiceDate'])
        df['Date'] = df['InvoiceDate'].dt.date
        
        # Sort by Date
        df = df.sort_values('InvoiceDate')
        
        logger.info(f"   After cleaning: {len(df):,} transactions")
        logger.info(f"   Date range: {df['InvoiceDate'].min()} to {df['InvoiceDate'].max()}")
        logger.info(f"   Unique products: {df['StockCode'].nunique():,}")
        
        return df
    
    
    def compute_history_features(
        self,
        df: pd.DataFrame,
        n_samples: int = 10000,
        min_transactions: int = 10
    ) -> pd.DataFrame:
        """
        Berechnet ECHTE History-Features pro Produkt
        
        Args:
            df: Kaggle DataFrame (von load_and_preprocess)
            n_samples: Max Anzahl Training-Examples
            min_transactions: Min Transaktionen pro Produkt (für valide History)
        
        Returns:
            DataFrame mit 80 Features + Target
        """
        logger.info(f"\n🔄 Computing history features for {n_samples} samples...")
        
        # 1. Filtere Produkte mit genug Transaktionen
        product_counts = df['StockCode'].value_counts()
        valid_products = product_counts[product_counts >= min_transactions].index.tolist()
        
        logger.info(f"   Products with >={min_transactions} transactions: {len(valid_products)}")
        
        if len(valid_products) == 0:
            logger.warning("⚠️ No products with enough transactions!")
            return pd.DataFrame()
        
        df_valid = df[df['StockCode'].isin(valid_products)].copy()
        
        # 2. Sample Random Produkte
        n_to_sample = min(n_samples, len(valid_products))
        sampled_products = np.random.choice(
            valid_products,
            size=n_to_sample,
            replace=False
        )
        
        logger.info(f"   Sampling {len(sampled_products)} products...")
        
        # 3. Für jedes Produkt: Berechne Features an random Zeitpunkt
        training_examples = []
        
        for idx, product_code in enumerate(sampled_products):
            try:
                product_data = df_valid[df_valid['StockCode'] == product_code].copy()
                
                # Wähle random Zeitpunkt (nicht zu früh, nicht zu spät)
                # Min: Nach 30 Tagen (für History)
                # Max: 30 Tage vor Ende (für Target)
                min_date = product_data['InvoiceDate'].min() + timedelta(days=30)
                max_date = product_data['InvoiceDate'].max() - timedelta(days=30)
                
                if min_date >= max_date:
                    continue  # Nicht genug Daten
                
                # Random Cutoff-Zeitpunkt
                time_range = (max_date - min_date).total_seconds()
                random_offset = np.random.random() * time_range
                cutoff_date = min_date + timedelta(seconds=random_offset)
                
                # Compute Features
                features = self._compute_features_at_cutoff(
                    product_data,
                    cutoff_date
                )
                
                if features is None:
                    continue
                
                # Compute Target (Sales Ratio)
                target = self._compute_target(
                    product_data,
                    cutoff_date
                )
                
                if target is None:
                    continue
                
                features['target'] = target
                features['source'] = 'kaggle_history'
                features['stock_code'] = product_code
                
                training_examples.append(features)
                
                if (idx + 1) % 1000 == 0:
                    logger.info(f"   Processed {len(training_examples)} examples...")
                
            except Exception as e:
                logger.warning(f"Failed to process {product_code}: {e}")
                continue
        
        if not training_examples:
            logger.warning("⚠️ No training examples generated!")
            return pd.DataFrame()
        
        result_df = pd.DataFrame(training_examples)
        
        logger.info(f"✅ Computed history features for {len(result_df)} examples")
        
        return result_df
    
    
    def _compute_features_at_cutoff(
        self,
        product_data: pd.DataFrame,
        cutoff_date: datetime
    ) -> Optional[Dict]:
        """
        Berechnet Features AN einem bestimmten Zeitpunkt (mit History DAVOR)
        
        Args:
            product_data: Alle Transaktionen für ein Produkt
            cutoff_date: Zeitpunkt (Features nur VOR diesem Datum!)
        
        Returns:
            Dict mit 80 Features (ECHT berechnet!)
        """
        features = {}
        
        # History: Alles VOR cutoff_date
        history = product_data[product_data['InvoiceDate'] < cutoff_date].copy()
        
        if len(history) == 0:
            return None
        
        # === TIER 1: Basic (5) ===
        # Aktueller Preis = letzter Preis vor Cutoff
        features['current_price'] = float(history.iloc[-1]['UnitPrice'])
        features['cost'] = float(features['current_price'] * 0.70)  # Annahme: 30% Marge
        features['margin_pct'] = 30.0
        features['inventory_quantity'] = 50.0  # Default
        features['inventory_value'] = float(features['current_price'] * 50)
        
        # === TIER 2: Sales Features (19) - ECHT! ===
        # 7-Tage-Window
        start_7d = cutoff_date - timedelta(days=7)
        sales_7d = history[history['InvoiceDate'] >= start_7d]
        features['sales_velocity_7d'] = float(sales_7d['Quantity'].sum() / 7) if len(sales_7d) > 0 else 0.0
        
        # 30-Tage-Window
        start_30d = cutoff_date - timedelta(days=30)
        sales_30d = history[history['InvoiceDate'] >= start_30d]
        features['sales_velocity_30d'] = float(sales_30d['Quantity'].sum() / 30) if len(sales_30d) > 0 else 0.0
        
        # 90-Tage-Window
        start_90d = cutoff_date - timedelta(days=90)
        sales_90d = history[history['InvoiceDate'] >= start_90d]
        features['sales_velocity_90d'] = float(sales_90d['Quantity'].sum() / 90) if len(sales_90d) > 0 else 0.0
        
        # Demand Growth (ECHT!)
        if features['sales_velocity_30d'] > 0:
            features['demand_growth_7d_vs_30d'] = float(
                (features['sales_velocity_7d'] - features['sales_velocity_30d']) / 
                features['sales_velocity_30d'] * 100
            )
        else:
            features['demand_growth_7d_vs_30d'] = 0.0
        
        if features['sales_velocity_90d'] > 0:
            features['demand_growth_30d_vs_90d'] = float(
                (features['sales_velocity_30d'] - features['sales_velocity_90d']) / 
                features['sales_velocity_90d'] * 100
            )
        else:
            features['demand_growth_30d_vs_90d'] = 0.0
        
        # Demand Trend
        features['demand_trend'] = 1.0 if features['demand_growth_7d_vs_30d'] > 0 else (-1.0 if features['demand_growth_7d_vs_30d'] < 0 else 0.0)
        
        # Sales Volatility
        if len(sales_30d) > 1:
            features['sales_volatility_7d'] = float(sales_7d['Quantity'].std()) if len(sales_7d) > 1 else 0.0
            features['sales_volatility_30d'] = float(sales_30d['Quantity'].std())
        else:
            features['sales_volatility_7d'] = 0.0
            features['sales_volatility_30d'] = 0.0
        
        # Sales Consistency
        if features['sales_velocity_30d'] > 0:
            features['sales_consistency'] = float(max(0.0, min(1.0, 1.0 - (features['sales_volatility_30d'] / features['sales_velocity_30d']))))
        else:
            features['sales_consistency'] = 0.0
        
        # Revenue
        features['revenue_7d'] = float((sales_7d['Quantity'] * sales_7d['UnitPrice']).sum()) if len(sales_7d) > 0 else 0.0
        features['revenue_30d'] = float((sales_30d['Quantity'] * sales_30d['UnitPrice']).sum()) if len(sales_30d) > 0 else 0.0
        features['revenue_90d'] = float((sales_90d['Quantity'] * sales_90d['UnitPrice']).sum()) if len(sales_90d) > 0 else 0.0
        
        # Avg Order Value
        if len(sales_7d) > 0:
            features['avg_order_value_7d'] = float(features['revenue_7d'] / len(sales_7d.groupby('InvoiceDate'))) if len(sales_7d.groupby('InvoiceDate')) > 0 else 0.0
        else:
            features['avg_order_value_7d'] = 0.0
        
        if len(sales_30d) > 0:
            features['avg_order_value_30d'] = float(features['revenue_30d'] / len(sales_30d.groupby('InvoiceDate'))) if len(sales_30d.groupby('InvoiceDate')) > 0 else 0.0
        else:
            features['avg_order_value_30d'] = 0.0
        
        # Days since last sale
        if len(history) > 0:
            last_sale_date = history['InvoiceDate'].max()
            days_since = (cutoff_date - last_sale_date).days
            features['days_since_last_sale'] = float(max(0, days_since))
        else:
            features['days_since_last_sale'] = 0.0
        
        # Sales Frequency
        if len(sales_30d) > 0:
            unique_dates = sales_30d['Date'].nunique()
            features['sales_frequency'] = float(unique_dates / 30.0)
        else:
            features['sales_frequency'] = 0.0
        
        # Peak Sales Day (Wochentag mit meisten Sales)
        if len(sales_30d) > 0:
            sales_30d_copy = sales_30d.copy()
            sales_30d_copy['Weekday'] = pd.to_datetime(sales_30d_copy['Date']).dt.dayofweek
            weekday_sales = sales_30d_copy.groupby('Weekday')['Quantity'].sum()
            features['peak_sales_day'] = float(weekday_sales.idxmax()) if len(weekday_sales) > 0 else 0.0
        else:
            features['peak_sales_day'] = 0.0
        
        # Weekend Sales Ratio
        if len(sales_30d) > 0:
            sales_30d_copy = sales_30d.copy()
            sales_30d_copy['Weekday'] = pd.to_datetime(sales_30d_copy['Date']).dt.dayofweek
            weekend_sales = sales_30d_copy[sales_30d_copy['Weekday'].isin([5, 6])]['Quantity'].sum()
            total_sales = sales_30d_copy['Quantity'].sum()
            features['weekend_sales_ratio'] = float(weekend_sales / total_sales) if total_sales > 0 else 0.0
        else:
            features['weekend_sales_ratio'] = 0.0
        
        # Sales Acceleration (ECHT!)
        if len(sales_30d) >= 3:
            # Linear Regression: Trend in letzten 30 Tagen
            sales_30d_daily = sales_30d.groupby('Date')['Quantity'].sum().reset_index()
            if len(sales_30d_daily) >= 3:
                x = np.arange(len(sales_30d_daily))
                y = sales_30d_daily['Quantity'].values
                slope = np.polyfit(x, y, 1)[0]
                features['sales_acceleration'] = float(slope)
            else:
                features['sales_acceleration'] = 0.0
        else:
            features['sales_acceleration'] = 0.0
        
        # === TIER 3: Price Features (10) - ECHT! ===
        if len(sales_30d) > 0:
            features['price_min_30d'] = float(sales_30d['UnitPrice'].min())  # ✅ ECHT!
            features['price_max_30d'] = float(sales_30d['UnitPrice'].max())  # ✅ ECHT!
            features['price_avg_30d'] = float(sales_30d['UnitPrice'].mean())
            features['price_std_30d'] = float(sales_30d['UnitPrice'].std()) if len(sales_30d) > 1 else 0.0
            
            # Price Trend (ECHT!)
            if len(sales_30d) >= 3:
                sales_30d_sorted = sales_30d.sort_values('InvoiceDate')
                x = np.arange(len(sales_30d_sorted))
                y = sales_30d_sorted['UnitPrice'].values
                slope = np.polyfit(x, y, 1)[0]
                features['price_trend_slope'] = float(slope)  # ✅ ECHT!
            else:
                features['price_trend_slope'] = 0.0
            
            # Price vs Avg
            if features['price_avg_30d'] > 0:
                features['price_vs_avg_30d_pct'] = float(
                    (features['current_price'] - features['price_avg_30d']) / 
                    features['price_avg_30d'] * 100
                )
            else:
                features['price_vs_avg_30d_pct'] = 0.0
        else:
            # Fallback
            features['price_min_30d'] = features['current_price']
            features['price_max_30d'] = features['current_price']
            features['price_avg_30d'] = features['current_price']
            features['price_std_30d'] = 0.0
            features['price_trend_slope'] = 0.0
            features['price_vs_avg_30d_pct'] = 0.0
        
        # Rest Price Features
        features['price_volatility_7d'] = features['price_std_30d']
        features['price_volatility_30d'] = features['price_std_30d']
        features['price_stability_score'] = float(max(0.0, min(1.0, 1.0 - (features['price_std_30d'] / features['current_price']) if features['current_price'] > 0 else 1.0)))
        features['price_change_frequency'] = 1.0 if features['price_std_30d'] > 0.01 else 0.0
        features['price_momentum'] = 1.0 if features['price_trend_slope'] > 0 else (-1.0 if features['price_trend_slope'] < 0 else 0.0)
        features['price_zscore'] = 0.0  # Not easily computable without full distribution
        
        # === TIER 4: Inventory Features (15) ===
        # Estimate from sales velocity
        if features['sales_velocity_30d'] > 0:
            estimated_stock = features['sales_velocity_30d'] * 30  # 30 days of stock
            features['inventory_quantity'] = float(estimated_stock)
            features['inventory_value'] = float(estimated_stock * features['current_price'])
            features['days_of_stock_7d'] = float(estimated_stock / features['sales_velocity_7d']) if features['sales_velocity_7d'] > 0 else 30.0
            features['days_of_stock_30d'] = float(estimated_stock / features['sales_velocity_30d']) if features['sales_velocity_30d'] > 0 else 30.0
            features['days_of_stock_90d'] = float(estimated_stock / features['sales_velocity_90d']) if features['sales_velocity_90d'] > 0 else 30.0
            features['inventory_turnover_30d'] = float(features['sales_velocity_30d'] / estimated_stock) if estimated_stock > 0 else 0.0
            features['inventory_turnover_90d'] = float(features['sales_velocity_90d'] / estimated_stock) if estimated_stock > 0 else 0.0
        else:
            features['inventory_quantity'] = 50.0
            features['inventory_value'] = float(50.0 * features['current_price'])
            features['days_of_stock_7d'] = 30.0
            features['days_of_stock_30d'] = 30.0
            features['days_of_stock_90d'] = 30.0
            features['inventory_turnover_30d'] = 0.0
            features['inventory_turnover_90d'] = 0.0
        
        # Stock Health
        if features['days_of_stock_30d'] < 7:
            features['stockout_risk'] = 1.0
            features['understock_risk'] = 1.0
            features['overstock_risk'] = 0.0
        elif features['days_of_stock_30d'] > 90:
            features['stockout_risk'] = 0.0
            features['understock_risk'] = 0.0
            features['overstock_risk'] = 1.0
        else:
            features['stockout_risk'] = 0.0
            features['understock_risk'] = 0.0
            features['overstock_risk'] = 0.0
        
        features['stock_health_score'] = float(max(0.0, min(1.0, 1.0 - abs(features['days_of_stock_30d'] - 30) / 30)))
        features['stock_velocity_ratio'] = 1.0
        features['inventory_trend'] = 0.0
        features['reorder_point'] = float(features['sales_velocity_30d'] * 7) if features['sales_velocity_30d'] > 0 else 0.0
        features['safety_stock'] = float(features['sales_velocity_30d'] * 3) if features['sales_velocity_30d'] > 0 else 0.0
        
        # === TIER 5: Competitive Features (8) ===
        # Not available from Kaggle
        features['competitor_count'] = np.nan
        features['competitor_avg_price'] = np.nan
        features['competitor_min_price'] = np.nan
        features['competitor_max_price'] = np.nan
        features['price_rank'] = np.nan
        features['price_vs_competitor_avg_pct'] = np.nan
        features['price_vs_competitor_min_pct'] = np.nan
        features['market_share_estimate'] = np.nan
        
        # === TIER 6: Advanced Features (23) ===
        # Product Age (estimate from first transaction)
        if len(history) > 0:
            first_transaction = history['InvoiceDate'].min()
            product_age_days = (cutoff_date - first_transaction).days
            features['product_age_days'] = float(product_age_days)
        else:
            features['product_age_days'] = 0.0
        
        # Rest: Defaults
        for i in range(22):
            features[f'advanced_feature_{i}'] = np.nan
        
        return features
    
    
    def _compute_target(
        self,
        product_data: pd.DataFrame,
        cutoff_date: datetime
    ) -> Optional[float]:
        """
        Berechnet Target (Sales Ratio) NACH cutoff_date
        
        Args:
            product_data: Alle Transaktionen
            cutoff_date: Zeitpunkt (Target aus Daten NACH diesem Datum)
        
        Returns:
            Sales Ratio (sales_after / sales_before) oder None
        """
        # Sales 30d VOR Cutoff
        start_before = cutoff_date - timedelta(days=30)
        sales_before = product_data[
            (product_data['InvoiceDate'] >= start_before) &
            (product_data['InvoiceDate'] < cutoff_date)
        ]['Quantity'].sum()
        
        # Sales 30d NACH Cutoff
        end_after = cutoff_date + timedelta(days=30)
        sales_after = product_data[
            (product_data['InvoiceDate'] >= cutoff_date) &
            (product_data['InvoiceDate'] < end_after)
        ]['Quantity'].sum()
        
        if sales_before == 0:
            return None  # Kein valides Target
        
        sales_ratio = sales_after / sales_before
        
        # Plausibilitäts-Check
        if not (0.2 <= sales_ratio <= 5.0):
            return None  # Outlier
        
        return float(sales_ratio)


# === HELPER FUNCTION FÜR TRAINING ===

def load_kaggle_with_history(n_samples: int = 10000) -> pd.DataFrame:
    """
    Convenience Function: Lädt Kaggle mit ECHTER History
    
    Usage:
        kaggle_data = load_kaggle_with_history(n_samples=10000)
    """
    loader = KaggleHistoryLoader()
    df = loader.load_and_preprocess()
    return loader.compute_history_features(df, n_samples=n_samples)
