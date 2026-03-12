"""
E-Commerce Data Loader für ML Training
Preprocesses carrie1/ecommerce-data für ML Training
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class EcommerceDataLoader:
    """
    Preprocesses carrie1/ecommerce-data für ML Training
    Features: price_change_pct, demand_growth, days_of_stock, current_margin
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Args:
            data_dir: Optional path to kaggle data directory
        """
        if data_dir is None:
            self.data_dir = Path(__file__).parent.parent.parent.parent / "data" / "kaggle"
        else:
            self.data_dir = Path(data_dir)
        
        # Try to find the CSV file (could be data.csv, ecommerce-data.csv, etc.)
        self.input_path = self._find_csv_file()
        self.output_path = Path(__file__).parent.parent.parent.parent / "data" / "ml_training_ecommerce.csv"
        
        # Create output directory if needed
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _find_csv_file(self) -> Optional[Path]:
        """Find the CSV file in the data directory"""
        if not self.data_dir.exists():
            logger.warning(f"Data directory does not exist: {self.data_dir}")
            return None
        
        # Common filenames
        possible_names = ["data.csv", "ecommerce-data.csv", "ecommerce_data.csv", "online_retail.csv"]
        
        for name in possible_names:
            path = self.data_dir / name
            if path.exists():
                logger.info(f"Found CSV file: {path}")
                return path
        
        # Try to find any CSV file
        csv_files = list(self.data_dir.glob("*.csv"))
        if csv_files:
            logger.info(f"Found CSV file: {csv_files[0]}")
            return csv_files[0]
        
        logger.error(f"No CSV file found in {self.data_dir}")
        return None
    
    def load_and_preprocess(self) -> pd.DataFrame:
        """
        Lädt CSV → extrahiert ML Features → speichert Training Data
        
        Returns:
            DataFrame mit ML Features
        """
        if self.input_path is None or not self.input_path.exists():
            raise FileNotFoundError(f"CSV file not found. Expected in: {self.data_dir}")
        
        logger.info(f"Loading {self.input_path}...")
        df = pd.read_csv(self.input_path, encoding='latin-1')  # E-commerce data often uses latin-1
        
        # SCHRITT 1: Inspect Columns
        logger.info(f"Columns: {df.columns.tolist()}")
        logger.info(f"Shape: {df.shape}")
        logger.info(f"Sample data:")
        logger.info(f"{df.head()}")
        
        # SCHRITT 2: Feature Engineering
        features = self._extract_features(df)
        
        # SCHRITT 3: Save
        features.to_csv(self.output_path, index=False)
        logger.info(f"[OK] {len(features)} samples → {self.output_path}")
        
        return features
    
    def _extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        E-Commerce CSV → ML Features
        
        Expected columns (carrie1/ecommerce-data):
        - InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country
        
        Returns:
            DataFrame mit ML Features
        """
        logger.info("Extracting ML features...")
        
        # Clean data
        df = df.copy()
        
        # Remove cancelled invoices (usually start with 'C')
        if 'InvoiceNo' in df.columns:
            df = df[~df['InvoiceNo'].astype(str).str.startswith('C')]
        
        # Remove negative quantities
        if 'Quantity' in df.columns:
            df = df[df['Quantity'] > 0]
        
        # Remove negative prices
        if 'UnitPrice' in df.columns:
            df = df[df['UnitPrice'] > 0]
        
        # Convert InvoiceDate to datetime
        if 'InvoiceDate' in df.columns:
            df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'], errors='coerce')
            df = df.dropna(subset=['InvoiceDate'])
        
        # Group by StockCode and InvoiceDate
        if 'StockCode' not in df.columns:
            logger.warning("StockCode column not found. Using first column as product ID.")
            df['StockCode'] = df.iloc[:, 0]
        
        # Sort by StockCode and InvoiceDate
        df_sorted = df.sort_values(['StockCode', 'InvoiceDate']).copy()
        
        # Calculate price_change_pct (price change over time per product)
        df_sorted['price_lag'] = df_sorted.groupby('StockCode')['UnitPrice'].shift(1)
        df_sorted['price_change_pct'] = (
            (df_sorted['UnitPrice'] - df_sorted['price_lag']) / df_sorted['price_lag']
        ).clip(-0.50, 0.30)
        
        # Calculate demand_growth (quantity change over time per product)
        # Aggregate by StockCode and InvoiceDate (daily sales per product)
        daily_sales = df_sorted.groupby(['StockCode', df_sorted['InvoiceDate'].dt.date])['Quantity'].sum().reset_index()
        daily_sales.columns = ['StockCode', 'Date', 'DailyQuantity']
        daily_sales = daily_sales.sort_values(['StockCode', 'Date'])
        
        daily_sales['quantity_lag'] = daily_sales.groupby('StockCode')['DailyQuantity'].shift(1)
        daily_sales['demand_growth'] = (
            (daily_sales['DailyQuantity'] - daily_sales['quantity_lag']) / 
            daily_sales['quantity_lag'].replace(0, np.nan)
        ).clip(-0.50, 1.0)
        
        # Merge back to original dataframe
        df_sorted['Date'] = df_sorted['InvoiceDate'].dt.date
        df_sorted = df_sorted.merge(
            daily_sales[['StockCode', 'Date', 'demand_growth']],
            on=['StockCode', 'Date'],
            how='left'
        )
        
        # Fill missing demand_growth with 0 (no change)
        df_sorted['demand_growth'] = df_sorted['demand_growth'].fillna(0.0)
        
        # Calculate days_of_stock (simplified: based on average daily sales)
        avg_daily_sales = daily_sales.groupby('StockCode')['DailyQuantity'].mean()
        df_sorted['avg_daily_sales'] = df_sorted['StockCode'].map(avg_daily_sales)
        df_sorted['days_of_stock'] = (30 / (df_sorted['avg_daily_sales'] + 1)).clip(0, 365)
        
        # Calculate current_margin (simplified: assume 30% margin)
        df_sorted['current_margin'] = 0.3
        
        # Calculate inventory_level (normalized: 0-1)
        max_quantity = df_sorted.groupby('StockCode')['Quantity'].max()
        df_sorted['max_quantity'] = df_sorted['StockCode'].map(max_quantity)
        df_sorted['inventory_level'] = (df_sorted['Quantity'] / (df_sorted['max_quantity'] + 1)).clip(0, 1)
        
        # Select and filter features
        feature_cols = [
            'price_change_pct', 'demand_growth', 'days_of_stock', 
            'current_margin', 'inventory_level'
        ]
        
        # Check which columns exist
        available_cols = [col for col in feature_cols if col in df_sorted.columns]
        missing_cols = [col for col in feature_cols if col not in df_sorted.columns]
        
        if missing_cols:
            logger.warning(f"Missing columns: {missing_cols}. Using available: {available_cols}")
        
        features = df_sorted[available_cols].copy()
        
        # Drop rows with NaN
        features = features.dropna()
        
        logger.info(f"Extracted {len(features)} feature samples")
        logger.info(f"Feature statistics:")
        logger.info(f"{features.describe()}")
        
        return features


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Add backend to path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    
    logging.basicConfig(level=logging.INFO)
    
    loader = EcommerceDataLoader()
    try:
        features = loader.load_and_preprocess()
        print(f"\n[SUCCESS] Preprocessed {len(features)} samples")
        print(f"Output: {loader.output_path}")
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)













