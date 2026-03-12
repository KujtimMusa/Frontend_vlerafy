"""
DateTime Helper Functions
Provides utilities for handling dates in demo vs live mode
"""
from datetime import datetime
from typing import Optional
import pandas as pd
from app.core.shop_context import ShopContext


def get_effective_now(sales_data: Optional[pd.DataFrame], shop_context: ShopContext) -> datetime:
    """
    Gibt ein 'effektives heute' zurück.
    
    - Im Demo-Mode: Das maximale Datum aus sales_data wird als 'heute' interpretiert.
      Dies ermöglicht es, Demo-CSV-Daten zeitlos zu verwenden, auch wenn sie historisch sind.
    - Im Live-Mode: Das echte datetime.now().
    
    Args:
        sales_data: DataFrame mit Sales-Daten (muss 'date' Spalte haben)
        shop_context: ShopContext mit is_demo_mode Flag
        
    Returns:
        datetime: Effektives "heute" für die Berechnungen
    """
    if shop_context.is_demo_mode and sales_data is not None and not sales_data.empty:
        try:
            # Kopiere DataFrame um Seiteneffekte zu vermeiden
            df = sales_data.copy()
            
            # Konvertiere Datum-Spalte zu datetime falls nötig
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                max_date = df['date'].max()
                
                # Im Demo-Mode: Nutze das maximale Datum als "heute"
                return max_date
        except Exception as e:
            # Bei Fehler: Fallback zu echtem datetime.now()
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Fehler beim Ermitteln des effektiven Datums im Demo-Mode: {e}. Nutze datetime.now()")
    
    # Live-Mode oder Fehler: Nutze echtes datetime.now()
    return datetime.now()














