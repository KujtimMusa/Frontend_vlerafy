"""
Price Story Generator - Generiert menschenlesbare Stories aus ML-Entscheidungen
"""
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging
from app.utils.datetime_helpers import get_effective_now
from app.core.shop_context import ShopContext

logger = logging.getLogger(__name__)


class PriceStoryGenerator:
    """Generiert verständliche Stories aus Pricing-Empfehlungen"""
    
    def __init__(self, shop_context: Optional[ShopContext] = None):
        """Initialize with optional shop_context for demo mode support"""
        self.shop_context = shop_context
    
    def generate_story(
        self, 
        recommendation: Dict,
        product: Dict,
        competitors: Optional[List[Dict]],
        sales_data: Optional[pd.DataFrame]
    ) -> Dict:
        """
        Generiert eine Story mit 3-5 Schritten die erklären WARUM dieser Preis empfohlen wird.
        
        Args:
            recommendation: Die generierte Recommendation mit recommended_price, confidence, etc.
            product: Product-Dict mit id, title, price, inventory_quantity, cost
            competitors: List von Competitor-Dicts mit source, price, scraped_at
            sales_data: DataFrame mit date, quantity, revenue, price
            
        Returns:
            Dict mit:
            - steps: List[Dict] mit step, title, explanation, impact, confidence, data_points, reasoning
            - total_impact: float (Summe aller Impacts)
            - base_price: float
            - recommended_price: float
            - summary: str
        """
        story_steps = []
        
        # STEP 1: Competitor Analysis
        if competitors and len(competitors) > 0:
            competitor_step = self._generate_competitor_step(
                recommendation=recommendation,
                product=product,
                competitors=competitors
            )
            if competitor_step:
                story_steps.append(competitor_step)
        
        # STEP 2: Demand Growth Analysis
        if sales_data is not None and not sales_data.empty and len(sales_data) > 14:
            demand_step = self._generate_demand_step(
                product=product,
                sales_data=sales_data
            )
            if demand_step:
                story_steps.append(demand_step)
        
        # STEP 3: Inventory Level Strategy
        if product.get('inventory_quantity'):
            inventory_step = self._generate_inventory_step(
                product=product,
                sales_data=sales_data
            )
            if inventory_step:
                story_steps.append(inventory_step)
        
        # Calculate total impact
        total_impact = sum(step['impact'] for step in story_steps)
        
        # 🆕 GEÄNDERT: Calculate actual price change
        recommended_price = recommendation.get('price', recommendation.get('recommended_price', product['price']))
        price_change = recommended_price - product['price']
        
        return {
            "steps": story_steps,
            "total_impact": round(total_impact, 2),
            "total_impact_pct": round((total_impact / product['price'] * 100), 2) if product['price'] > 0 else 0,
            "base_price": product['price'],
            "recommended_price": recommended_price,
            "price_change": round(price_change, 2),  # 🆕 NEU
            "confidence": recommendation.get('confidence', 0.5),
            "summary": self._generate_summary(
                story_steps, 
                total_impact,
                product['price'],  # 🆕 NEU
                recommended_price  # 🆕 NEU
            )
        }
    
    def _generate_competitor_step(
        self, 
        recommendation: Dict, 
        product: Dict, 
        competitors: List[Dict]
    ) -> Optional[Dict]:
        """Generiert Step 1: Competitor Analysis"""
        try:
            prices = [c['price'] for c in competitors if c.get('price')]
            if not prices:
                return None
                
            avg_price = np.mean(prices)
            your_price = recommendation.get('price', recommendation.get('recommended_price', product['price']))
            current_price = product['price']
            
            # Berechne Impact: Wie viel der Competitor-Faktor beiträgt
            price_gap = avg_price - current_price
            max_impact = current_price * 0.10  # Cap bei ±10%
            competitor_impact = np.clip(price_gap * 0.5, -max_impact, max_impact)
            
            # Bestimme Position im Markt
            position_pct = ((your_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            
            return {
                "step": 1,
                "title": "Deine Konkurrenz ist teurer" if position_pct < 5 else "Du bist teurer als der Markt",
                "explanation": (
                    f"Wir haben **{len(competitors)} Wettbewerber** analysiert. "
                    f"Der durchschnittliche Preis liegt bei **{avg_price:.2f} €**. "
                    f"{'Du kannst noch **' + f'{abs(price_gap):.2f}' + ' € mehr** verlangen und bleibst trotzdem attraktiv.' if price_gap > 0 else 'Du solltest **' + f'{abs(price_gap):.2f}' + ' € senken** um wettbewerbsfähig zu bleiben.'}"
                ),
                "impact": round(competitor_impact, 2),
                "impact_pct": round((competitor_impact / current_price * 100), 2) if current_price > 0 else 0,
                "confidence": 85,
                "data_points": [
                    {
                        "source": c.get('source', 'Unknown'),
                        "price": round(c['price'], 2),
                        "scraped_at": c.get('scraped_at', datetime.now()).isoformat() if isinstance(c.get('scraped_at'), datetime) else str(c.get('scraped_at', ''))
                    }
                    for c in competitors if c.get('price')
                ],
                "reasoning": self._explain_competitor_positioning(your_price, avg_price, position_pct)
            }
        except Exception as e:
            logger.warning(f"Fehler bei Competitor Step: {e}")
            return None
    
    def _generate_demand_step(
        self, 
        product: Dict, 
        sales_data: pd.DataFrame
    ) -> Optional[Dict]:
        """Generiert Step 2: Demand Growth"""
        try:
            # Ensure date column is datetime
            sales_data = sales_data.copy()
            if 'date' in sales_data.columns:
                sales_data['date'] = pd.to_datetime(sales_data['date'])
            
            # Use effective_now for demo mode compatibility (demo CSV data may be historical)
            effective_now = get_effective_now(sales_data, self.shop_context) if self.shop_context else datetime.now()
            
            # Calculate 7-day windows relative to effective_now
            if len(sales_data) >= 7:
                last_7d = sales_data[sales_data['date'] >= (effective_now - timedelta(days=7))]
                prev_7d = sales_data[
                    (sales_data['date'] >= (effective_now - timedelta(days=14))) & 
                    (sales_data['date'] < (effective_now - timedelta(days=7)))
                ]
                
                sales_7d = int(last_7d['quantity'].sum()) if not last_7d.empty else 0
                sales_7d_prev = int(prev_7d['quantity'].sum()) if not prev_7d.empty else 0
            else:
                # Fallback if not enough data
                sales_7d = int(sales_data['quantity'].sum())
                sales_7d_prev = 0
            
            growth_pct = ((sales_7d - sales_7d_prev) / sales_7d_prev * 100) if sales_7d_prev > 0 else 0
            
            # 🆕 GEÄNDERT: Senke Schwelle von 10% auf 5%
            # UND: Zeige auch stabile Nachfrage (0-5%)
            if abs(growth_pct) < 5:
                # Zeige "Stabile Nachfrage" Step
                return {
                    "step": 2,
                    "title": "Die Nachfrage ist stabil",
                    "explanation": (
                        f"In den letzten 7 Tagen hast du **{sales_7d} Verkäufe** gemacht "
                        f"(vorher: {sales_7d_prev} Verkäufe). Das ist ein **stabiler Trend** ohne große Veränderungen. "
                        f"Du kannst den Preis anpassen ohne großes Risiko."
                    ),
                    "impact": 0.0,  # Kein Impact bei stabiler Nachfrage
                    "impact_pct": 0.0,
                    "confidence": 70,
                    "data_points": [
                        {"date": row['date'].isoformat() if isinstance(row['date'], datetime) else str(row['date']), 
                         "sales": int(row['quantity'])}
                        for _, row in sales_data.tail(14).iterrows()
                    ],
                    "reasoning": (
                        "➡️ **Stabile Nachfrage.** Keine signifikanten Veränderungen in den letzten Wochen. "
                        "Das ist ein gutes Zeichen - du kannst Preisanpassungen vornehmen ohne dass "
                        "sich die Nachfrage stark verändert."
                    )
                }
            
            # Berechne Impact basierend auf Demand Growth
            if growth_pct > 50:
                demand_impact = product['price'] * 0.05  # +5%
            elif growth_pct > 20:
                demand_impact = product['price'] * 0.02  # +2%
            elif growth_pct < -20:
                demand_impact = product['price'] * -0.03  # -3%
            else:
                demand_impact = product['price'] * 0.01  # +1%
            
            return {
                "step": 2,
                "title": "Die Nachfrage steigt stark" if growth_pct > 0 else "Die Nachfrage sinkt",
                "explanation": (
                    f"In den letzten 7 Tagen hast du **{sales_7d} Verkäufe** gemacht "
                    f"(vorher: {sales_7d_prev} Verkäufe). Das ist ein **{growth_pct:+.0f}% {'Wachstum' if growth_pct > 0 else 'Rückgang'}**! "
                    f"{'Wenn die Nachfrage steigt, kannst du höhere Preise durchsetzen.' if growth_pct > 0 else 'Bei sinkender Nachfrage solltest du vorsichtig sein mit Preiserhöhungen.'}"
                ),
                "impact": round(demand_impact, 2),
                "impact_pct": round((demand_impact / product['price'] * 100), 2) if product['price'] > 0 else 0,
                "confidence": 78,
                "data_points": [
                    {"date": row['date'].isoformat() if isinstance(row['date'], datetime) else str(row['date']), 
                     "sales": int(row['quantity'])}
                    for _, row in sales_data.tail(14).iterrows()
                ],
                "reasoning": self._explain_demand_trend(growth_pct, sales_7d)
            }
        except Exception as e:
            logger.warning(f"Fehler bei Demand Step: {e}")
            return None
    
    def _generate_inventory_step(
        self, 
        product: Dict, 
        sales_data: Optional[pd.DataFrame]
    ) -> Optional[Dict]:
        """Generiert Step 3: Inventory Strategy"""
        try:
            inventory_qty = product.get('inventory_quantity', 0)
            
            if inventory_qty <= 0:
                return None
            
            # Berechne Days of Stock
            if sales_data is not None and not sales_data.empty:
                sales_7d = sales_data.tail(7)['quantity'].sum()
                avg_daily_sales = sales_7d / 7 if sales_7d > 0 else 0.1
            else:
                avg_daily_sales = 1.0  # Fallback
            
            days_of_stock = inventory_qty / avg_daily_sales if avg_daily_sales > 0 else 999
            
            # Berechne Impact basierend auf Lagerbestand
            if days_of_stock > 60:
                inventory_impact = product['price'] * -0.03  # -3% (Überbestand)
            elif days_of_stock < 14:
                inventory_impact = product['price'] * 0.04   # +4% (Knappheit)
            else:
                inventory_impact = product['price'] * -0.01  # -1% (Normal)
            
            return {
                "step": 3,
                "title": "Du hast genug Lagerbestand" if days_of_stock > 20 else "Dein Lagerbestand ist niedrig",
                "explanation": (
                    f"Mit **{inventory_qty} Einheiten** auf Lager hast du bei aktuellem Tempo "
                    f"noch **{days_of_stock:.0f} Tage Vorrat**. "
                    + ("Das ist mehr als genug. Du kannst es dir leisten, etwas aggressiver zu verkaufen."
                       if days_of_stock > 20
                       else "Das ist knapp! Du solltest vorsichtig mit Preissenkungen sein.")
                ),
                "impact": round(inventory_impact, 2),
                "impact_pct": round((inventory_impact / product['price'] * 100), 2) if product['price'] > 0 else 0,
                "confidence": 82,
                "data_points": {
                    "current_inventory": inventory_qty,
                    "days_of_stock": round(days_of_stock, 1),
                    "daily_sales_avg": round(avg_daily_sales, 1)
                },
                "reasoning": self._explain_inventory_strategy(days_of_stock, inventory_qty)
            }
        except Exception as e:
            logger.warning(f"Fehler bei Inventory Step: {e}")
            return None
    
    def _explain_competitor_positioning(self, your_price: float, avg_price: float, position_pct: float) -> str:
        """Erklärt Wettbewerbsposition in Plain Language"""
        if position_pct > 10:
            return (
                f"Du bist **{position_pct:.0f}% teurer** als der Durchschnitt. "
                f"Das ist riskant - Kunden könnten zur Konkurrenz abwandern. "
                f"Wir empfehlen näher am Markt zu bleiben."
            )
        elif position_pct > 5:
            return (
                f"Du bist **{position_pct:.0f}% teurer** als der Durchschnitt. "
                f"Das ist ein Premium-Positioning - funktioniert wenn dein Service besser ist."
            )
        elif position_pct > -5:
            return (
                f"Du bist **genau im Markt-Durchschnitt**. "
                f"Gute Position - weder zu teuer noch zu billig."
            )
        else:
            return (
                f"Du bist **{abs(position_pct):.0f}% günstiger** als der Durchschnitt. "
                f"Du verschenkst Marge! Kunden würden auch mehr zahlen."
            )
    
    def _explain_demand_trend(self, growth_pct: float, sales_7d: int) -> str:
        """Erklärt Nachfrage-Trend"""
        if growth_pct > 50:
            return (
                f"📈 **Starkes Wachstum!** Die Nachfrage explodiert gerade. "
                f"Das ist der perfekte Moment für eine Preiserhöhung. "
                f"Kunden wollen dein Produkt - nutze die Situation!"
            )
        elif growth_pct > 20:
            return (
                f"📊 **Solides Wachstum.** Die Nachfrage steigt konstant. "
                f"Du kannst vorsichtig den Preis erhöhen ohne Verkäufe zu verlieren."
            )
        elif growth_pct < -20:
            return (
                f"📉 **Nachfrage sinkt.** Vorsicht - jetzt ist NICHT der Moment "
                f"für Preiserhöhungen. Besser Preis senken um Volumen zu halten."
            )
        else:
            return (
                f"➡️ **Stabile Nachfrage.** Keine großen Veränderungen. "
                f"Du kannst den Preis anpassen ohne großes Risiko."
            )
    
    def _explain_inventory_strategy(self, days_of_stock: float, inventory_qty: int) -> str:
        """Erklärt Lagerbestand-Strategie"""
        if days_of_stock > 60:
            return (
                f"🏭 **Überbestand!** {inventory_qty} Einheiten sind zu viel. "
                f"Bei {days_of_stock:.0f} Tagen Vorrat solltest du **aggressiv** verkaufen. "
                f"Senke den Preis um Volumen zu pushen."
            )
        elif days_of_stock > 30:
            return (
                f"✅ **Gesunder Bestand.** {inventory_qty} Einheiten sind ein gutes Polster. "
                f"Du kannst entspannt optimieren ohne Druck."
            )
        elif days_of_stock < 14:
            return (
                f"⚠️ **Knapper Bestand!** Nur noch {days_of_stock:.0f} Tage Vorrat. "
                f"Erhöhe den Preis um die Nachfrage zu drosseln bis Nachschub kommt."
            )
        else:
            return (
                f"📦 **Normaler Bestand.** {inventory_qty} Einheiten - alles im grünen Bereich."
            )
    
    def _generate_summary(
        self, 
        steps: List[Dict], 
        total_impact: float,
        base_price: float,  # 🆕 NEU
        recommended_price: float  # 🆕 NEU
    ) -> str:
        """Generiert Zusammenfassung basierend auf tatsächlicher Preisänderung"""
        
        # 🆕 GEÄNDERT: Nutze actual price change statt total_impact
        price_change = recommended_price - base_price
        
        if price_change > 1:  # Mehr als 1€ Erhöhung
            return (
                f"Alle Faktoren zusammen sprechen für eine **Preiserhöhung um {abs(price_change):.2f} €**. "
                f"Die Marktbedingungen sind günstig!"
            )
        elif price_change < -1:  # Mehr als 1€ Senkung
            return (
                f"Die Analyse zeigt, dass eine **Preissenkung um {abs(price_change):.2f} €** "
                f"sinnvoll wäre um wettbewerbsfähig zu bleiben."
            )
        else:  # Minimale Änderung (-1€ bis +1€)
            return (
                f"Der aktuelle Preis ist **nahezu optimal**. "
                f"Nur minimale Anpassung um {price_change:+.2f} € empfohlen."
            )

