from typing import Dict, Optional
from app.models.product import Product
from app.models.shop import Shop
from app.services.shopify_adapter import ShopifyDataAdapter
from app.utils.encryption import decrypt_token
from app.services.margin_calculator_service import MarginCalculatorService
from sqlalchemy.orm import Session
import logging
import math
import pandas as pd
from datetime import datetime, timedelta
import random
import numpy as np

logger = logging.getLogger(__name__)

# FIX: Setze globale Random Seeds für deterministische Berechnungen
# Verhindert unterschiedliche Ergebnisse bei gleichen Inputs
random.seed(42)
np.random.seed(42)


class PricingEngine:
    """Erweiterte Pricing Engine mit datenbasierten Strategien"""
    
    def __init__(
        self, 
        shop: Optional[Shop] = None, 
        adapter: Optional[ShopifyDataAdapter] = None, 
        competitor_analysis: Optional[Dict] = None,
        db: Optional[Session] = None,
        use_competitor_data: bool = True
    ):
        self.shop = shop
        self.adapter = adapter
        self.competitor_analysis = competitor_analysis
        self.db = db
        self.use_competitor_data = use_competitor_data
        self.competitive_recommendation = None  # Initialize to avoid AttributeError
        
        # Initialize Margin Calculator if DB available
        if self.db:
            self.margin_calculator = MarginCalculatorService(db=self.db)
        else:
            self.margin_calculator = None
    
    def _detect_and_handle_anomalies(self, sales_data: pd.DataFrame) -> pd.DataFrame:
        """
        Intelligente Anomalie-Behandlung:
        - Erkennt statistische Ausreißer (> 2 Standardabweichungen über dem Mittelwert)
        - Prüft, ob Ausreißer an bekannten Sale-Event-Daten liegen
        - Ersetzt Event-Spikes durch Median (robust gegen Ausreißer)
        - Behält alle Datenpunkte, löscht nichts
        """
        if sales_data is None or sales_data.empty or len(sales_data) < 14:
            return sales_data
        
        df = sales_data.copy()
        if 'date' not in df.columns or 'quantity' not in df.columns:
            return df
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        mean = df['quantity'].mean()
        std = df['quantity'].std()
        median = df['quantity'].median()
        
        if std == 0 or pd.isna(std):
            return df
        
        # Spikes definieren
        threshold = mean + (2 * std)
        df['is_spike'] = df['quantity'] > threshold
        
        def is_sale_event(date: datetime) -> bool:
            """Bekannte Sale-Event-Zeiträume (erweiterbar)"""
            # Black Friday / Cyber Week (25.-30. November)
            if date.month == 11 and 25 <= date.day <= 30:
                return True
            # Weihnachts-Shopping (15.-24. Dezember)
            if date.month == 12 and 15 <= date.day <= 24:
                return True
            return False
        
        df['needs_correction'] = df.apply(
            lambda row: bool(row['is_spike']) and is_sale_event(row['date']),
            axis=1
        )
        
        corrected_count = int(df['needs_correction'].sum())
        if corrected_count > 0:
            percentile_75 = df['quantity'].quantile(0.75)
            df.loc[df['needs_correction'], 'quantity'] = percentile_75
            logger.info(f"   🔧 {corrected_count} Event-Spikes gedämpft (→P75: {percentile_75:.1f})")
        
        # Nur relevante Spalten zurückgeben
        cols = [c for c in ['date', 'quantity', 'revenue', 'price'] if c in df.columns]
        return df[cols]
    
    def calculate_price(self, product: Product, sales_data: Optional[pd.DataFrame] = None) -> Dict:
        """
        Berechnet eine Preisempfehlung mit erweiterten Strategien:
        1. Demand Trend Factor (7 vs 30 Tage) mit Anomalie-Erkennung
        2. Days of Stock (inkl. Fallback bei fehlenden Sales)
        3. Gewichtete Kombination
        4. Optionale Rundung (aktuell: einfache 2-Nachkommastellen)
        
        FIX: Deterministisch - keine Random-Komponenten mehr!
        """
        # FIX: Setze Random Seed für deterministische Berechnungen (falls irgendwo verwendet)
        import random
        import numpy as np
        random.seed(42)  # Fixer Seed für Reproduzierbarkeit
        np.random.seed(42)  # NumPy Seed
        
        # === DETAILLIERTES DEBUG LOGGING ===
        logger.info("\n" + "=" * 80)
        logger.info(f"🔍 PRICING CALCULATION START - Product: {getattr(product, 'title', 'Unknown')}")
        logger.info(f"   Product ID: {product.id}")
        logger.info(f"   Current Price: {product.price}€")
        logger.info(f"   Timestamp: {datetime.now().isoformat()}")
        logger.info(f"   Sales Data Rows: {len(sales_data) if sales_data is not None and not sales_data.empty else 0}")
        
        # Prüfe Random Seeds
        logger.info(f"   Random Seed Test: random.random() = {random.random()}")
        logger.info(f"   NumPy Seed Test: np.random.random() = {np.random.random()}")
        logger.info(f"   Competitive Recommendation: {'Yes' if hasattr(self, 'competitive_recommendation') and self.competitive_recommendation else 'No'}")
        if hasattr(self, 'competitive_recommendation') and self.competitive_recommendation:
            comp_rec = self.competitive_recommendation
            logger.info(f"     → Price: {comp_rec.get('recommended_price')}€")
            logger.info(f"     → Confidence: {comp_rec.get('confidence')}")
            if comp_rec.get('competitor_context'):
                ctx = comp_rec['competitor_context']
                logger.info(f"     → Competitor Avg: {ctx.get('avg_price', 0):.2f}€")
        logger.info("=" * 80)
        logger.info("📊 Input-Daten:")
        try:
            logger.info(f"  • Aktueller Preis: €{float(product.price):.2f}")
        except Exception:
            logger.info("  • Aktueller Preis: n/a")
        if getattr(product, 'cost', None) is not None:
            logger.info(f"  • Cost: €{float(product.cost):.2f}")
        else:
            logger.info("  • Cost: Nicht verfügbar")
        logger.info(f"  • Inventory: {getattr(product, 'inventory_quantity', 'n/a')}")
        logger.info(f"  • Sales-Daten: {len(sales_data) if isinstance(sales_data, pd.DataFrame) and not sales_data.empty else 0} Zeilen")
        logger.info("=" * 70 + "\n")
        
        # 3-stufige Logik: DB → Adapter → Optional DB-Speicherung
        if sales_data is None:
            # Stufe 1: Versuche zuerst aus DB zu laden (funktioniert für Live UND Demo-Shop)
            if self.db and product.id:
                from app.services.sales_history_service import SalesHistoryService
                service = SalesHistoryService(self.db)
                sales_data = service.get_sales_history(
                    product_id=product.id,
                    shop_id=product.shop_id,  # WICHTIG: shop_id=999 für Demo-Shop
                    days_back=60
                )
                logger.info(f"✅ Sales-Daten aus DB geladen: {len(sales_data)} Einträge (Shop {product.shop_id})")
            
            # Stufe 2: Fallback - Lade von Adapter (Shopify API oder CSV)
            if (sales_data is None or sales_data.empty) and self.adapter and getattr(product, 'shopify_product_id', None):
                try:
                    sales_data = self.adapter.load_product_sales_history(
                        product.shopify_product_id,
                        days_back=60
                    )
                    logger.info(f"✅ Sales-Daten von Adapter geladen: {len(sales_data)} Einträge")
                    
                    # Stufe 3: OPTIONAL - Speichere Adapter-Daten in DB für zukünftige Verwendung
                    # WICHTIG: Funktioniert auch für Demo-Shop (shop_id=999)
                    if self.db and product.id and not sales_data.empty:
                        from app.services.sales_history_service import SalesHistoryService
                        service = SalesHistoryService(self.db)
                        
                        # Konvertiere DataFrame zu Records-Format
                        records = []
                        for _, row in sales_data.iterrows():
                            records.append({
                                'date': row['date'],
                                'quantity': int(row.get('quantity', row.get('quantity_sold', 0))),
                                'revenue': float(row.get('revenue', 0)),
                                'price': float(row.get('price', 0)),
                                'order_id': row.get('order_id'),
                                'variant_id': row.get('variant_id'),
                                'meta_data': {'source': 'adapter_sync'}
                            })
                        
                        # WICHTIG: Für Demo-Shop (shop_id=999) aggregiere tägliche Sales
                        # Für Live-Shop: Ein Record pro Order
                        is_demo = product.shop_id == 999
                        service.bulk_save_sales(
                            records,
                            product_id=product.id,
                            shop_id=product.shop_id,  # 999 für Demo, echte ID für Live
                            aggregate_daily=is_demo  # CSV-Daten aggregieren
                        )
                        logger.info(f"✅ Sales-Daten in DB gespeichert (Shop {product.shop_id})")
                except Exception as e:
                    logger.warning(f"⚠️ Konnte Sales-Daten nicht laden: {e}")
                    sales_data = pd.DataFrame()
        
        if sales_data is None:
            sales_data = pd.DataFrame()
        
        strategies: Dict[str, Dict] = {}
        
        # STRATEGIE 1: Demand Trend
        demand_recommendation = self._calculate_demand_trend(product, sales_data)
        if demand_recommendation:
            strategies['demand'] = demand_recommendation
            change_pct = ((demand_recommendation['price'] / product.price) - 1) * 100 if product.price else 0.0
            logger.info("✅ DEMAND STRATEGY:")
            logger.info(f"   → Preis: €{demand_recommendation['price']:.2f} ({change_pct:+.1f}%)")
            logger.info(f"   → Confidence: {demand_recommendation['confidence']:.0%}")
            logger.info(f"   → Reasoning: {demand_recommendation['reasoning']}")
        else:
            logger.warning("❌ DEMAND: Keine Empfehlung (zu wenig oder keine Daten)")
        
        # STRATEGIE 2: Inventory (Days of Stock)
        inventory_recommendation = self._calculate_days_of_stock(product, sales_data)
        if inventory_recommendation:
            strategies['inventory'] = inventory_recommendation
            change_pct = ((inventory_recommendation['price'] / product.price) - 1) * 100 if product.price else 0.0
            logger.info("\n✅ INVENTORY STRATEGY:")
            logger.info(f"   → Preis: €{inventory_recommendation['price']:.2f} ({change_pct:+.1f}%)")
            logger.info(f"   → Confidence: {inventory_recommendation['confidence']:.0%}")
            logger.info(f"   → Reasoning: {inventory_recommendation['reasoning']}")
        else:
            logger.warning("❌ INVENTORY: Keine Empfehlung")
        
        # STRATEGIE 3: Cost-based
        cost_recommendation = self._calculate_cost_based(product)
        if cost_recommendation:
            strategies['cost'] = cost_recommendation
            change_pct = ((cost_recommendation['price'] / product.price) - 1) * 100 if product.price else 0.0
            logger.info("\n✅ COST STRATEGY:")
            logger.info(f"   → Preis: €{cost_recommendation['price']:.2f} ({change_pct:+.1f}%)")
            logger.info(f"   → Confidence: {cost_recommendation['confidence']:.0%}")
            logger.info(f"   → Reasoning: {cost_recommendation['reasoning']}")
        else:
            logger.warning("❌ COST: Keine Empfehlung (Cost fehlt)")
        
        # STRATEGIE 4: Competitive (wenn verfügbar)
        if hasattr(self, 'competitive_recommendation') and self.competitive_recommendation:
            competitive_rec = self.competitive_recommendation
            # Konvertiere zu Pricing Engine Format
            strategies['competitive'] = {
                'price': competitive_rec.get('recommended_price', product.price),
                'confidence': competitive_rec.get('confidence', 0.5),
                'strategy': 'competitive',
                'reasoning': competitive_rec.get('reasoning', ''),
                'competitor_context': competitive_rec.get('competitor_context')
            }
            change_pct = ((competitive_rec['recommended_price'] / product.price) - 1) * 100 if product.price else 0.0
            logger.info("\n✅ COMPETITIVE STRATEGY:")
            logger.info(f"   → Preis: €{competitive_rec['recommended_price']:.2f} ({change_pct:+.1f}%)")
            logger.info(f"   → Confidence: {competitive_rec['confidence']:.0%}")
            logger.info(f"   → Reasoning: {competitive_rec['reasoning']}")
            if competitive_rec.get('competitor_context'):
                ctx = competitive_rec['competitor_context']
                logger.info(f"   → Position: {ctx.get('position', 'unknown')}")
                logger.info(f"   → Markt-Ø: €{ctx.get('avg_price', 0):.2f}")
                logger.info(f"   → Differenz: {ctx.get('price_diff_pct', 0):.1f}%")
        
        # Fallback wenn keine Strategien
        if not strategies:
            logger.warning("\n⚠️ FALLBACK: Keine Strategien → +2% Value-based")
            strategies['value'] = {
                'price': product.price * 1.02,
                'confidence': 0.50,
                'strategy': 'value',
                'reasoning': 'Fallback: Leichte Wertsteigerung (+2%)'
            }
        
        # Gewichtete Kombination mit dynamischer Gewichtung basierend auf Competitor-Differenz
        final_price_raw = self._weighted_average(strategies, float(product.price))
        
        # Dynamische Constraints basierend auf Competitor-Differenz
        final_price_raw = self._apply_dynamic_constraints(
            final_price_raw, 
            float(product.price), 
            strategies
        )
        
        final_price = self._psychological_rounding(final_price_raw)
        
        logger.info("\n" + "=" * 80)
        logger.info("🎯 FINALER PREIS:")
        logger.info(f"  Von €{float(product.price):.2f} → €{final_price:.2f}")
        change_pct_final = ((final_price / float(product.price)) - 1) * 100 if product.price else 0.0
        logger.info(f"  Änderung: {change_pct_final:+.1f}%")
        logger.info("=" * 80 + "\n")
        
        # Confidence & beste Strategie
        confidence = self._calculate_confidence(product, sales_data, strategies)
        logger.warning(f"🔍 DEBUG CONFIDENCE CALCULATED: {confidence:.2%}")  # Debug-Log
        
        # FIX: Deterministische Strategy Selection (wenn mehrere gleiche Confidence haben)
        if strategies:
            # Sortiere nach Confidence (absteigend), dann nach Strategy-Name (deterministisch)
            sorted_strategies = sorted(
                strategies.items(),
                key=lambda x: (x[1].get('confidence', 0), x[0]),  # Zuerst Confidence, dann Name
                reverse=True
            )
            best_strategy = sorted_strategies[0][1] if sorted_strategies else None
            logger.info(f"🔍 DEBUG - Selected Strategy: {sorted_strategies[0][0] if sorted_strategies else 'none'} (confidence: {best_strategy.get('confidence', 0) if best_strategy else 0:.2f})")
        else:
            best_strategy = None
            logger.info(f"🔍 DEBUG - No strategies available")
        
        # === FINAL DEBUG OUTPUT ===
        logger.info("─" * 80)
        logger.info(f"🎯 PRICING CALCULATION RESULT:")
        logger.info(f"   Recommended Price: {final_price:.2f}€")
        logger.info(f"   Strategy: {best_strategy.get('strategy', 'unknown') if best_strategy else 'none'}")
        logger.info(f"   Confidence: {confidence:.3f}")
        if hasattr(self, 'competitive_recommendation') and self.competitive_recommendation and self.competitive_recommendation.get('competitor_context'):
            ctx = self.competitive_recommendation['competitor_context']
            logger.info(f"   Competitor Avg: {ctx.get('avg_price', 0):.2f}€")
        logger.info("=" * 80)
        
        # Track Price Change (funktioniert für Demo UND Live-Shop)
        if self.db and product.id:
            from app.services.price_history_service import PriceHistoryService
            service = PriceHistoryService(self.db)
            
            # WICHTIG: Track auch für Demo-Shop (shop_id=999)
            # Demo-Shop Preise ändern sich zwar nicht in Shopify, 
            # aber Recommendations generieren neue Preise
            try:
                service.track_price_change(
                    product_id=product.id,
                    shop_id=product.shop_id,  # 999 für Demo, echte ID für Live
                    new_price=final_price,
                    previous_price=float(product.price) if product.price else None,
                    triggered_by="pricing_engine",
                    meta_data={
                        'recommendation_id': None,  # Wird später gesetzt wenn Recommendation gespeichert
                        'strategy': best_strategy.get('strategy', 'weighted_average') if best_strategy else 'fallback',
                        'confidence': confidence,
                        'is_demo': product.shop_id == 999  # Flag für Demo-Shop
                    }
                )
                logger.info(f"✅ Price Change getrackt: {product.price} → {final_price} (Shop {product.shop_id})")
            except Exception as e:
                logger.warning(f"⚠️ Fehler beim Tracken der Preisänderung: {e}")
        
        return {
            'price': float(final_price),
            'confidence': confidence,
            'strategy': best_strategy.get('strategy', 'weighted_average') if best_strategy else 'fallback',
            'reasoning': {
                'current_price': float(product.price),
                'recommended_price': float(final_price),
                'price_change_pct': change_pct_final if product.price > 0 else 0,
                'strategies': strategies,
            }
        }
    
    def _calculate_demand_trend(self, product: Product, sales_data: pd.DataFrame) -> Optional[Dict]:
        """
        Berechnet Demand Trend (7-Tage vs. 30-Tage-Durchschnitt)
        mit intelligenter Anomalie-Behandlung und granularen Preisstufen.
        """
        if sales_data is None or sales_data.empty or len(sales_data) < 7:
            logger.info(f"   ⚠️ Demand: Nur {len(sales_data) if isinstance(sales_data, pd.DataFrame) else 0} Datenpunkte")
            
            # Intelligenter Fallback: Nutze Inventory- und Margin-Signale
            inv = getattr(product, 'inventory_quantity', None)
            cost = getattr(product, 'cost', None)
            price = float(getattr(product, 'price', 0.0))
            
            if inv is not None and inv < 10:
                logger.info(f"   → Niedriger Bestand erkannt → +3% Test")
                return {
                    'price': price * 1.03,
                    'confidence': 0.50,
                    'strategy': 'demand_inventory_signal',
                    'reasoning': f'Wenig Daten, aber kritischer Bestand ({inv}) → +3%'
                }
            elif cost and cost > 0 and price > 0 and (price / cost) < 1.5:
                margin_pct = (price / cost - 1) * 100
                logger.info(f"   → Niedrige Marge erkannt ({margin_pct:.0f}%) → +5% Test")
                return {
                    'price': price * 1.05,
                    'confidence': 0.55,
                    'strategy': 'demand_margin_signal',
                    'reasoning': f'Niedrige Marge ({margin_pct:.0f}%) → +5%'
                }
            else:
                logger.info(f"   → Keine starken Signale → Preis beibehalten")
                return {
                    'price': price,
                    'confidence': 0.40,
                    'strategy': 'demand_insufficient_data',
                    'reasoning': f'Zu wenig Daten ({len(sales_data) if isinstance(sales_data, pd.DataFrame) else 0} Zeilen)'
                }
        
        try:
            df = sales_data.copy()
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Anomalien glätten
            df = self._detect_and_handle_anomalies(df)
            if df is None or df.empty or len(df) < 7:
                logger.warning("   ⚠️ Demand: Zu wenig Daten nach Anomalie-Behandlung")
                return {
                    'price': float(product.price),
                    'confidence': 0.40,
                    'strategy': 'demand_post_correction',
                    'reasoning': 'Zu wenig Daten nach Event-Korrektur'
                }
            
            end_date = datetime.now()
            start_7d = end_date - timedelta(days=7)
            start_30d = end_date - timedelta(days=30)
            
            sales_7d = df[df['date'] >= start_7d]['quantity'].sum()
            sales_30d = df[df['date'] >= start_30d]['quantity'].sum()
            
            sales_30d_avg = (sales_30d / 30.0) * 7.0 if sales_30d > 0 else 0.0
            if sales_30d_avg == 0:
                logger.info("   ⚠️ Demand: 0 Verkäufe in 30 Tagen → -5%")
                return {
                    'price': float(product.price) * 0.95,
                    'confidence': 0.65,
                    'strategy': 'demand_zero_sales',
                    'reasoning': 'Keine Verkäufe in 30 Tagen → -5%'
                }
            
            demand_growth = (sales_7d - sales_30d_avg) / sales_30d_avg
            
            logger.info(f"   📈 Sales 7d: {sales_7d:.0f}, 30d-avg: {sales_30d_avg:.1f}")
            logger.info(f"   📊 Demand Growth: {demand_growth*100:+.1f}%")
            
            # Granulare Preisstufen
            if demand_growth > 0.5:      # 50%+ Wachstum
                price_change = 0.15
                strategy_name = "demand_very_high"
                reasoning = f"Sehr starkes Wachstum ({demand_growth*100:.0f}%) → +15%"
            elif demand_growth > 0.3:    # 30%+ Wachstum
                price_change = 0.10
                strategy_name = "demand_high"
                reasoning = f"Starkes Wachstum ({demand_growth*100:.0f}%) → +10%"
            elif demand_growth > 0.1:    # 10%+ Wachstum
                price_change = 0.05
                strategy_name = "demand_growing"
                reasoning = f"Wachstum ({demand_growth*100:.0f}%) → +5%"
            elif demand_growth > -0.05:  # -5% bis +10% (stabil)
                price_change = 0.00
                strategy_name = "demand_stable"
                reasoning = f"Stabil ({demand_growth*100:.0f}%) → unverändert"
            elif demand_growth > -0.15:  # -5% bis -15%
                price_change = -0.03
                strategy_name = "demand_slow"
                reasoning = f"Leichter Rückgang ({demand_growth*100:.0f}%) → -3%"
            elif demand_growth > -0.30:  # -15% bis -30%
                price_change = -0.07
                strategy_name = "demand_declining"
                reasoning = f"Rückgang ({demand_growth*100:.0f}%) → -7%"
            else:                        # < -30%
                price_change = -0.12
                strategy_name = "demand_critical"
                reasoning = f"Starker Rückgang ({demand_growth*100:.0f}%) → -12%"
            
            recommended_price = float(product.price) * (1 + price_change)
            
            return {
                'price': recommended_price,
                'confidence': 0.75,
                'strategy': strategy_name,
                'reasoning': reasoning
            }
        
        except Exception as e:
            logger.warning(f"Fehler bei Demand Trend: {e}")
            return None
    
    def _calculate_days_of_stock(self, product: Product, sales_data: pd.DataFrame) -> Optional[Dict]:
        """
        Berechnet Days of Stock mit Fallback bei fehlenden Sales-Daten
        und granularen Preisstufen.
        """
        inventory = getattr(product, 'inventory_quantity', None)
        if inventory is None or inventory == 0:
            return None
        
        # Fallback ohne Sales-Daten: reine Inventory-Heuristik
        if sales_data is None or sales_data.empty:
            logger.info("   ⚠️ Inventory: Keine Sales-Daten → reine Inventory-Heuristik")
            iq = inventory
            if iq < 5:
                return {
                    'price': float(product.price) * 1.08,
                    'confidence': 0.65,
                    'strategy': 'inventory_critical_no_sales',
                    'reasoning': f'Kritisch niedriger Bestand ({iq}) → +8%'
                }
            elif iq < 10:
                return {
                    'price': float(product.price) * 1.03,
                    'confidence': 0.60,
                    'strategy': 'inventory_low_no_sales',
                    'reasoning': f'Niedriger Bestand ({iq}) → +3%'
                }
            elif iq > 100:
                return {
                    'price': float(product.price) * 0.95,
                    'confidence': 0.65,
                    'strategy': 'inventory_high_no_sales',
                    'reasoning': f'Hoher Bestand ({iq}) → -5%'
                }
            else:
                return {
                    'price': float(product.price),
                    'confidence': 0.55,
                    'strategy': 'inventory_normal_no_sales',
                    'reasoning': f'Normaler Bestand ({iq}) → unverändert'
                }
        
        # Mit Sales-Daten: echte Days-of-Stock-Berechnung
        try:
            df = sales_data.copy()
            df['date'] = pd.to_datetime(df['date'])
            
            # Anomalien glätten
            df = self._detect_and_handle_anomalies(df)
            if df is None or df.empty:
                logger.info("   ⚠️ Inventory: Keine gültigen Sales-Daten nach Korrektur")
                return {
                    'price': float(product.price),
                    'confidence': 0.50,
                    'strategy': 'stock_no_data_after_correction',
                    'reasoning': 'Keine belastbaren Sales-Daten nach Anomalie-Korrektur'
                }
            
            end_date = datetime.now()
            start_30d = end_date - timedelta(days=30)
            
            recent_sales = df[df['date'] >= start_30d]
            total_quantity = recent_sales['quantity'].sum()
            if len(recent_sales) > 0:
                days_in_period = min(30, (end_date - recent_sales['date'].min()).days + 1)
            else:
                days_in_period = 30
            avg_daily_sales = total_quantity / days_in_period if days_in_period > 0 else 0
            
            if avg_daily_sales == 0:
                logger.info("   ⚠️ Inventory: Keine Verkäufe, Bestand vorhanden")
                if inventory > 50:
                    return {
                        'price': float(product.price) * 0.92,
                        'confidence': 0.70,
                        'strategy': 'stock_dead',
                        'reasoning': f'Kein Verkauf + Überbestand ({inventory}) → -8%'
                    }
                else:
                    return {
                        'price': float(product.price) * 0.98,
                        'confidence': 0.60,
                        'strategy': 'stock_no_movement',
                        'reasoning': f'Kein Verkauf ({inventory} auf Lager) → -2%'
                    }
            
            days_of_stock = inventory / avg_daily_sales
            
            logger.info(f"   📦 Days of Stock: {days_of_stock:.1f} Tage")
            logger.info(f"   📊 Durchschnitt: {avg_daily_sales:.1f} Verkäufe/Tag")
            
            # Granulare Preisstufen basierend auf Days of Stock
            if days_of_stock < 7:       # Knappheit
                price_change = 0.10
                strategy_name = "stock_critical"
                reasoning = f"Kritisch ({days_of_stock:.0f} Tage) → +10%"
            elif days_of_stock < 14:    # Niedrig
                price_change = 0.05
                strategy_name = "stock_low"
                reasoning = f"Niedrig ({days_of_stock:.0f} Tage) → +5%"
            elif days_of_stock < 21:    # Optimal
                price_change = 0.00
                strategy_name = "stock_optimal"
                reasoning = f"Optimal ({days_of_stock:.0f} Tage) → unverändert"
            elif days_of_stock < 45:    # Etwas hoch
                price_change = -0.03
                strategy_name = "stock_adequate"
                reasoning = f"Erhöht ({days_of_stock:.0f} Tage) → -3%"
            elif days_of_stock < 90:    # Überbestand
                price_change = -0.08
                strategy_name = "stock_high"
                reasoning = f"Überbestand ({days_of_stock:.0f} Tage) → -8%"
            else:                       # Kritischer Überbestand
                price_change = -0.12
                strategy_name = "stock_critical_high"
                reasoning = f"Kritischer Überbestand ({days_of_stock:.0f} Tage) → -12%"
            
            recommended_price = float(product.price) * (1 + price_change)
            
            return {
                'price': recommended_price,
                'confidence': 0.80,
                'strategy': strategy_name,
                'reasoning': reasoning
            }
        
        except Exception as e:
            logger.warning(f"Fehler bei Days of Stock: {e}")
            return None
    
    def _calculate_cost_based(self, product: Product) -> Optional[Dict]:
        """
        Cost-based Pricing mit dynamischer Confidence.
        Ziel: 30% Zielmarge, aber Vertrauen sinkt, wenn Änderung sehr groß ist.
        """
        cost = getattr(product, 'cost', None)
        price = float(getattr(product, 'price', 0.0))
        if not cost or cost <= 0 or price <= 0:
            return None
        
        target_margin = 0.30  # 30% Ziel-Gewinn
        recommended_price = cost / (1 - target_margin)
        
        # Relative Preisänderung
        price_change_pct = abs((recommended_price / price) - 1)
        
        if price_change_pct > 0.25:  # >25% Änderung
            confidence = 0.50
            note = "(extreme Änderung)"
        elif price_change_pct > 0.15:  # >15% Änderung
            confidence = 0.65
            note = "(große Änderung)"
        else:
            confidence = 0.85
            note = ""
        
        return {
            'price': recommended_price,
            'confidence': confidence,
            'strategy': 'cost_based',
            'reasoning': f'Target margin {target_margin:.0%} {note}'.strip()
        }
    
    def _weighted_average(self, strategies: Dict, current_price: float) -> float:
        """Gewichtete Kombination aller Strategien mit dynamischer Gewichtung"""
        if not strategies:
            return current_price
        
        # Hole Competitor-Kontext für dynamische Gewichtung
        competitive_strategy = strategies.get("competitive", {})
        competitor_context = competitive_strategy.get("competitor_context") if isinstance(competitive_strategy, dict) else None
        
        # NEU: Dynamische Gewichtung basierend auf Competitor-Differenz
        if competitor_context and competitor_context.get("avg_price"):
            avg_competitor = competitor_context["avg_price"]
            price_diff_pct = abs((current_price / avg_competitor) - 1)
            
            if price_diff_pct > 0.50:  # >50% Differenz
                # OVERRIDE: Competitive Strategy dominiert!
                weights = {
                    "demand": 0.10,      # Reduziert von 0.40
                    "inventory": 0.10,   # Reduziert von 0.25
                    "cost": 0.10,        # Reduziert von 0.25
                    "competitive": 0.70  # Erhöht von 0.35
                }
                logger.warning(f"""
                🚨 CRITICAL PRICE MISMATCH ({price_diff_pct*100:.1f}%)
                Switching to Competitive-Dominant mode (70% weight)
                Market avg: €{avg_competitor:.2f}, Your price: €{current_price:.2f}
                """)
            elif price_diff_pct > 0.30:  # 30-50% Differenz
                weights = {
                    "demand": 0.25,
                    "inventory": 0.20,
                    "cost": 0.15,
                    "competitive": 0.40  # Erhöht
                }
                logger.info(f"ℹ️ Moderate price difference ({price_diff_pct*100:.1f}%) - increased competitive weight to 40%")
            else:
                # Standard-Gewichtung
                weights = {
                    "demand": 0.40,
                    "inventory": 0.25,
                    "cost": 0.25,
                    "competitive": 0.35
                }
        else:
            # Fallback: Standard-Gewichtung (ohne Competitive)
            weights = {
                "demand": 0.40,
                "inventory": 0.35,
                "cost": 0.25
            }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for strategy_name, strategy_data in strategies.items():
            weight = weights.get(strategy_name, 0.10)  # Default 10%
            price = strategy_data.get("price", current_price)
            confidence = strategy_data.get("confidence", 0.5)
            
            # Gewicht mit Confidence multiplizieren
            effective_weight = weight * confidence
            weighted_sum += price * effective_weight
            total_weight += effective_weight
            
            logger.debug(f"   {strategy_name.upper()}: €{price:.2f} × {weight:.0%} × {confidence:.2f} = Einfluss {((price * effective_weight) / (current_price * effective_weight) - 1) * 100:+.1f}%")
        
        if total_weight > 0:
            return weighted_sum / total_weight
        else:
            return current_price
    
    def _apply_dynamic_constraints(
        self, 
        recommended_price: float, 
        current_price: float, 
        strategies: Dict
    ) -> float:
        """
        Wendet dynamische Constraints basierend auf Competitor-Differenz an
        """
        competitive_strategy = strategies.get("competitive", {})
        competitor_context = competitive_strategy.get("competitor_context") if isinstance(competitive_strategy, dict) else None
        
        # Dynamischer Max-Change basierend auf Competitor-Differenz
        if competitor_context and competitor_context.get("avg_price"):
            avg_competitor_price = competitor_context["avg_price"]
            price_diff_pct = abs((current_price / avg_competitor_price) - 1)
            
            # Dynamischer Max-Change:
            # Normal: ±15%
            # Bei >30% Differenz: ±30%
            # Bei >50% Differenz: ±50%
            # Bei >80% Differenz: Unlimitiert (folge Wettbewerb!)
            
            if price_diff_pct > 0.80:  # >80% Differenz
                max_change = 1.0  # Unlimitiert
                logger.warning(f"⚠️ EXTREME PRICE DIFFERENCE: {price_diff_pct*100:.1f}% - removing constraint!")
            elif price_diff_pct > 0.50:  # >50% Differenz
                max_change = 0.50  # Max ±50%
                logger.warning(f"⚠️ HIGH PRICE DIFFERENCE: {price_diff_pct*100:.1f}% - increased constraint to ±50%")
            elif price_diff_pct > 0.30:  # >30% Differenz
                max_change = 0.30  # Max ±30%
                logger.info(f"ℹ️ Moderate price difference: {price_diff_pct*100:.1f}% - increased constraint to ±30%")
            else:
                max_change = 0.15  # Standard ±15%
        else:
            max_change = 0.15  # Fallback
        
        # Wende Constraint an
        min_allowed = current_price * (1 - max_change)
        max_allowed = current_price * (1 + max_change)
        
        if recommended_price < min_allowed:
            logger.info(f"   ⚠️ Constraint: Max -{max_change*100:.0f}% → €{recommended_price:.2f} → €{min_allowed:.2f}")
            recommended_price = min_allowed
        elif recommended_price > max_allowed:
            logger.info(f"   ⚠️ Constraint: Max +{max_change*100:.0f}% → €{recommended_price:.2f} → €{max_allowed:.2f}")
            recommended_price = max_allowed
        
        return recommended_price
    
    def _psychological_rounding(self, price: float) -> float:
        """
        Aktuell: neutrale Rundung auf 2 Nachkommastellen.
        Kein .99-Hack, kein künstliches Kappen – nur saubere Darstellung.
        """
        return max(0.01, round(float(price), 2))
    
    def _calculate_confidence(self, product: Product, sales_data: pd.DataFrame, strategies: Dict) -> float:
        """
        ✅ FIX: Dynamic Confidence Calculation mit mehr Varianz
        
        Confidence basiert auf:
        - Feature Quality (Datenqualität)
        - Sales History (wie viel Daten vorhanden)
        - Prediction Reasonableness (ist Prediction plausibel?)
        """
        confidence = 0.3  # Base confidence (nicht 0.0!)
        
        # 1. Feature Quality (40% weight)
        feature_quality = 0.0
        
        # Cost-Daten vorhanden?
        if product.cost and product.cost > 0:
            feature_quality += 0.15
        
        # Sales-Historie vorhanden?
        if not sales_data.empty and len(sales_data) > 0:
            try:
                sales_history_days = (datetime.now() - pd.to_datetime(sales_data["date"]).min()).days
                # Mehr Daten = höhere Quality
                history_score = min(1.0, sales_history_days / 90)  # 90 Tage = 100%
                feature_quality += 0.15 * history_score
                
                # Zusätzlich: Sales-Volumen (mehr Sales = höhere Confidence)
                total_sales = sales_data["quantity"].sum() if "quantity" in sales_data.columns else 0
                if total_sales > 100:
                    feature_quality += 0.10  # Viele Sales = gute Daten
                elif total_sales > 10:
                    feature_quality += 0.05  # Einige Sales = OK
            except:
                pass
        
        # Inventory-Daten vorhanden?
        if product.inventory_quantity is not None:
            feature_quality += 0.10
        
        confidence += 0.4 * feature_quality
        
        # 2. Strategie-Vielfalt (30% weight)
        strategy_quality = 0.0
        strategy_count = len(strategies)
        if strategy_count >= 3:
            strategy_quality = 1.0  # Viele Strategien = hohe Confidence
        elif strategy_count == 2:
            strategy_quality = 0.7  # Zwei Strategien = moderate Confidence
        elif strategy_count == 1:
            strategy_name = list(strategies.keys())[0] if strategies else "value"
            if strategy_name != "value":
                strategy_quality = 0.5  # Eine echte Strategie = OK
            else:
                strategy_quality = 0.2  # Fallback = niedrig
        
        confidence += 0.3 * strategy_quality
        
        # 3. Prediction Reasonableness (30% weight)
        # Prüfe ob recommended_price plausibel ist
        prediction_quality = 0.5  # Default: neutral
        
        if strategies:
            # Check ob Preis-Änderung zu extrem ist
            current_price = float(product.price) if product.price else 0.0
            if current_price > 0:
                # Finde recommended_price aus strategies
                recommended_price = current_price
                for strategy_name, strategy_data in strategies.items():
                    if isinstance(strategy_data, dict) and 'price' in strategy_data:
                        recommended_price = strategy_data['price']
                        break
                
                price_change_pct = abs((recommended_price - current_price) / current_price) if current_price > 0 else 0.0
                
                # Moderate Änderungen (5-20%) = hohe Confidence
                if 0.05 <= price_change_pct <= 0.20:
                    prediction_quality = 1.0
                # Kleine Änderungen (<5%) = moderate Confidence
                elif price_change_pct < 0.05:
                    prediction_quality = 0.7
                # Große Änderungen (>20%) = niedrige Confidence
                elif price_change_pct > 0.50:
                    prediction_quality = 0.2
                else:
                    prediction_quality = 0.5
        
        confidence += 0.3 * prediction_quality
        
        # 4. Penalties (reduzieren Confidence)
        
        # Penalty: Sehr neues Produkt (wenig Daten)
        if product.created_at:
            try:
                product_age_days = (datetime.now() - product.created_at.replace(tzinfo=None) if hasattr(product.created_at, 'tzinfo') and product.created_at.tzinfo else product.created_at).days
                if product_age_days < 7:
                    confidence -= 0.15  # Sehr neu = weniger Confidence
                elif product_age_days < 30:
                    confidence -= 0.10  # Neu = etwas weniger Confidence
            except:
                pass
        
        # Penalty: Keine Sales-Daten
        if sales_data.empty or len(sales_data) == 0:
            confidence -= 0.20  # Keine Sales = weniger Confidence
        
        # 5. Clamp to reasonable range (30-95%)
        confidence = max(0.30, min(0.95, confidence))
        
        logger.warning(f"🔍 DEBUG FINAL CONFIDENCE: {confidence:.2%}")  # Debug-Log
        return confidence
