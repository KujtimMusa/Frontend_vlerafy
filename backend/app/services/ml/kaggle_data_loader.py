"""
Kaggle Dataset Loader für E-Commerce Pricing Optimization
Lädt und verarbeitet Kaggle Dataset für ML-Training
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, Tuple, Optional
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class KaggleDataLoader:
    """Lädt und verarbeitet Kaggle E-Commerce Pricing Dataset"""
    
    def __init__(self, data_dir: str = "data/kaggle"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def download_dataset(self, dataset_name: str = "ecommerce-pricing-optimization") -> bool:
        """
        Lädt Dataset von Kaggle herunter (benötigt kaggle CLI)
        
        Args:
            dataset_name: Name des Kaggle Datasets
            
        Returns:
            True wenn erfolgreich
        """
        try:
            import kaggle
            from kaggle.api.kaggle_api_extended import KaggleApi
            
            api = KaggleApi()
            api.authenticate()
            
            # Download Dataset
            api.dataset_download_files(
                dataset_name,
                path=str(self.data_dir),
                unzip=True
            )
            
            logger.info(f"Dataset {dataset_name} erfolgreich heruntergeladen")
            return True
            
        except ImportError:
            logger.warning("Kaggle API nicht installiert. Nutze lokale Daten oder synthetische Daten.")
            return False
        except Exception as e:
            logger.error(f"Fehler beim Download: {e}")
            return False
    
    def load_dataset(self, filename: str = "pricing_data.csv") -> Optional[pd.DataFrame]:
        """
        Lädt Dataset aus CSV
        
        Args:
            filename: Name der CSV-Datei
            
        Returns:
            DataFrame mit Pricing-Daten
        """
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            logger.warning(f"Datei {filepath} nicht gefunden. Erstelle synthetische Daten.")
            return None
        
        try:
            df = pd.read_csv(filepath)
            logger.info(f"Dataset geladen: {len(df)} Zeilen")
            return df
        except Exception as e:
            logger.error(f"Fehler beim Laden: {e}")
            return None
    
    def preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocessing: Berechnet Features und Labels
        
        Erwartete Spalten:
        - product_id, price, cost, inventory, sales_7d, sales_30d, 
          price_change_pct, revenue_lift
        
        Args:
            df: Raw DataFrame
            
        Returns:
            Preprocessed DataFrame mit Features
        """
        df = df.copy()
        
        # Berechne demand_growth
        if 'sales_7d' in df.columns and 'sales_30d' in df.columns:
            sales_30d_avg = df['sales_30d'] / 30 * 7  # Normalisiert auf 7 Tage
            df['demand_growth'] = (df['sales_7d'] - sales_30d_avg) / (sales_30d_avg + 1e-6)
        else:
            df['demand_growth'] = 0.0
        
        # Berechne days_of_stock
        if 'inventory' in df.columns and 'sales_7d' in df.columns:
            avg_daily_sales = df['sales_7d'] / 7
            df['days_of_stock'] = df['inventory'] / (avg_daily_sales + 1e-6)
        else:
            df['days_of_stock'] = 30.0  # Default
        
        # Berechne current_margin
        if 'price' in df.columns and 'cost' in df.columns:
            df['current_margin'] = (df['price'] - df['cost']) / (df['price'] + 1e-6)
        else:
            df['current_margin'] = 0.3  # Default 30%
        
        # Normalisiere inventory_level (0-1)
        if 'inventory' in df.columns:
            max_inventory = df['inventory'].max() if df['inventory'].max() > 0 else 100
            df['inventory_level'] = df['inventory'] / max_inventory
        else:
            df['inventory_level'] = 0.5
        
        # Label: was_profitable
        if 'revenue_lift' in df.columns:
            df['was_profitable'] = (df['revenue_lift'] > 0).astype(int)
        elif 'price_change_pct' in df.columns:
            # Fallback: Wenn revenue_lift fehlt, nutze price_change als Proxy
            df['was_profitable'] = (df['price_change_pct'] > 0).astype(int)
        else:
            df['was_profitable'] = 1  # Default: profitable
        
        # Entferne NaN/Inf Werte
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna({
            'demand_growth': 0.0,
            'days_of_stock': 30.0,
            'current_margin': 0.3,
            'inventory_level': 0.5,
            'was_profitable': 1
        })
        
        logger.info(f"Preprocessing abgeschlossen: {len(df)} Zeilen")
        return df
    
    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extrahiert ML-Features aus preprocessed DataFrame
        
        Returns:
            DataFrame mit Feature-Spalten
        """
        feature_columns = [
            'price_change_pct',
            'demand_growth',
            'days_of_stock',
            'current_margin',
            'inventory_level'
        ]
        
        # Füge fehlende Spalten hinzu
        for col in feature_columns:
            if col not in df.columns:
                if col == 'price_change_pct':
                    df[col] = 0.0
                elif col == 'demand_growth':
                    df['demand_growth'] = 0.0
                elif col == 'days_of_stock':
                    df['days_of_stock'] = 30.0
                elif col == 'current_margin':
                    df['current_margin'] = 0.3
                elif col == 'inventory_level':
                    df['inventory_level'] = 0.5
        
        features = df[feature_columns].copy()
        
        # Clamp extreme values (Quick-Fix: Aligned with inference range -0.20 to +0.20)
        features['price_change_pct'] = features['price_change_pct'].clip(-0.20, 0.20)
        features['demand_growth'] = features['demand_growth'].clip(-1.0, 2.0)
        features['days_of_stock'] = features['days_of_stock'].clip(0, 365)
        features['current_margin'] = features['current_margin'].clip(0, 1)
        features['inventory_level'] = features['inventory_level'].clip(0, 1)
        
        return features
    
    def load_and_preprocess(self, filename: str = "pricing_data.csv") -> Optional[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Kompletter Workflow: Laden + Preprocessing + Feature Extraction
        
        Returns:
            Tuple (features_df, labels_series) oder None
        """
        df = self.load_dataset(filename)
        
        if df is None or len(df) == 0:
            logger.warning("Keine Daten geladen. Nutze synthetische Daten.")
            return None
        
        # Preprocessing
        df = self.preprocess_data(df)
        
        # Features extrahieren
        features = self.extract_features(df)
        
        # Labels
        labels = df['was_profitable']
        
        logger.info(f"Features: {features.shape}, Labels: {labels.shape}")
        
        return features, labels



















