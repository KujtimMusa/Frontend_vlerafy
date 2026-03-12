"""
Enhanced Competitive Pricing Strategy
Nutzt ECHTE Competitor-Daten vom CompetitorPriceService (Serper API)
"""
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class EnhancedCompetitiveStrategy:
    """
    Competitive Pricing mit echten Wettbewerber-Daten
    """
    
    def __init__(self, weight: float = 0.35):
        self.weight = weight
        self.name = "competitive"
    
    def calculate(
        self, 
        product: Dict, 
        competitor_prices: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Berechnet Preis-Empfehlung basierend auf Wettbewerbern
        
        Args:
            product: {
                'id': str,
                'title': str,
                'price': float,
                'cost': float,
                'inventory': int,
                ...
            }
            competitor_prices: Liste von CompetitorPriceService.find_competitor_prices()
                [
                    {
                        'source': 'Zalando',
                        'title': 'Nike Air Max 90...',
                        'price': 89.99,
                        'url': 'https://...',
                        'scraped_at': '2025-12-18T13:00:00'
                    },
                    ...
                ]
        
        Returns:
            {
                'recommended_price': float,
                'confidence': float (0.0-1.0),
                'strategy': 'competitive',
                'reasoning': str,
                'competitor_context': {
                    'position': str,
                    'avg_price': float,
                    'min_price': float,
                    'max_price': float,
                    'competitor_count': int,
                    'sources': List[str]
                } or None
            }
        """
        current_price = product.get('price', 0.0)
        
        # Fallback wenn keine Competitor-Daten
        if not competitor_prices or len(competitor_prices) == 0:
            logger.warning(f"⚠️ Keine Competitor-Daten für '{product.get('title')}' - nutze Fallback")
            return self._fallback_strategy(current_price)
        
        # Extrahiere Preise
        prices = [c['price'] for c in competitor_prices if c.get('price', 0) > 0]
        
        if not prices:
            logger.warning(f"⚠️ Keine validen Competitor-Preise - nutze Fallback")
            return self._fallback_strategy(current_price)
        
        # Statistiken berechnen
        comp_avg = sum(prices) / len(prices)
        comp_min = min(prices)
        comp_max = max(prices)
        
        # Deine Position ermitteln
        position = self._calculate_position(current_price, prices)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 COMPETITIVE ANALYSIS: {product.get('title')}")
        logger.info(f"{'='*60}")
        logger.info(f"   Wettbewerber gefunden: {len(prices)}")
        logger.info(f"   Preis-Range: €{comp_min:.2f} - €{comp_max:.2f}")
        logger.info(f"   Durchschnitt: €{comp_avg:.2f}")
        logger.info(f"   Dein Preis: €{current_price:.2f}")
        logger.info(f"   Deine Position: {position.upper()}")
        logger.info(f"{'='*60}\n")
        
        # Berechne Differenz-Magnitude
        price_diff_pct = abs((current_price / comp_avg) - 1)
        
        # 🆕 FORMEL-BASIERTE CONFIDENCE (nicht mehr hart-codiert!)
        competitor_count = len(prices)
        confidence = self._calculate_competitive_confidence(
            position=position,
            price_diff_pct=price_diff_pct,
            competitor_count=competitor_count,
            price_range=(comp_min, comp_max)
        )
        
        logger.info(f"📊 Calculated Confidence: {confidence:.0%}")
        
        # Strategie basierend auf Position UND Differenz
        if position == "cheapest":
            # Bei extremem Preisunterschied nach OBEN → keine Erhöhung
            if price_diff_pct > 0.30:
                recommended_price = current_price * 1.01  # Nur +1%
                reasoning = (
                    f"Du bist günstigster, ABER Markt ist sehr viel teurer (+{price_diff_pct*100:.0f}%). "
                    f"Vorsichtige Erhöhung empfohlen (+1%)"
                )
            else:
                # Standard cheapest logic
                recommended_price = current_price * 1.03  # +3%
                reasoning = (
                    f"Du bist der günstigste Anbieter (Wettbewerber ab €{comp_min:.2f}). "
                    f"Empfehle moderate Erhöhung um 3% auf €{recommended_price:.2f}"
                )
        
        elif position == "most_expensive":
            # NEUE LOGIK: Aggressiver bei großer Differenz
            if price_diff_pct > 0.50:  # >50% teurer
                # EXTREM teuer → Aggressiv anpassen
                target_price = comp_avg * 1.05  # 5% ÜBER Durchschnitt (nicht drunter)
                recommended_price = target_price  # Kein Max-Limit!
                reasoning = (
                    f"❌ KRITISCH: Du bist {price_diff_pct*100:.0f}% teurer als Marktdurchschnitt (€{comp_avg:.2f})! "
                    f"Empfehle dringende Anpassung auf €{recommended_price:.2f}. "
                    f"Ohne Anpassung: Hohe Wahrscheinlichkeit für Umsatzverlust."
                )
            elif price_diff_pct > 0.30:  # 30-50% teurer
                target_price = comp_avg * 1.00  # Auf Durchschnitt
                recommended_price = max(target_price, current_price * 0.80)  # Max -20%
                reasoning = (
                    f"⚠️ Du bist deutlich teurer (+{price_diff_pct*100:.0f}% über Ø €{comp_avg:.2f}). "
                    f"Empfehle starke Senkung auf €{recommended_price:.2f}"
                )
            else:  # Standard "most_expensive"
                target_price = comp_avg * 0.95  # 5% unter Durchschnitt
                recommended_price = max(target_price, current_price * 0.90)  # Max -10%
                diff_pct = ((current_price / comp_avg) - 1) * 100
                reasoning = (
                    f"Du bist teuerster Anbieter (+{diff_pct:.1f}%). "
                    f"Empfehle Senkung auf €{recommended_price:.2f} für bessere Wettbewerbsfähigkeit"
                )
        
        elif position == "above_average":
            # Über Durchschnitt → Moderate Senkung
            target_price = comp_avg * 0.98  # 2% unter Durchschnitt
            recommended_price = max(target_price, current_price * 0.95)  # Max -5%
            diff_pct = ((current_price / comp_avg) - 1) * 100
            reasoning = (
                f"Über Marktdurchschnitt (+{diff_pct:.1f}%). "
                f"Empfehle Anpassung auf €{recommended_price:.2f} (näher an Ø €{comp_avg:.2f})"
            )
        
        elif position == "below_average":
            # Unter Durchschnitt → Preiserhöhung möglich
            target_price = comp_avg * 0.99  # 1% unter Durchschnitt
            recommended_price = min(target_price, current_price * 1.05)  # Max +5%
            diff_pct = ((current_price / comp_avg) - 1) * 100
            reasoning = (
                f"Unter Marktdurchschnitt ({diff_pct:.1f}%). "
                f"Empfehle Erhöhung auf €{recommended_price:.2f} (näher an Ø €{comp_avg:.2f})"
            )
        
        else:  # "average"
            # Am Durchschnitt → Minimal anpassen
            recommended_price = current_price * 1.01  # +1%
            reasoning = (
                f"Am Marktdurchschnitt (Ø €{comp_avg:.2f}). "
                f"Empfehle kleine Erhöhung um 1% auf €{recommended_price:.2f}"
            )
        
        # Constraint: Mindestmarge (aber nur wenn nicht extrem über Markt)
        cost = product.get('cost', 0)
        if cost and cost > 0:
            min_price = cost * 1.20
            
            # Nur wenn empfohlener Preis noch über Markt-Max liegt
            if recommended_price > comp_max:
                if recommended_price < min_price:
                    old_price = recommended_price
                    recommended_price = min_price
                    reasoning += f" (Marge-Constraint: €{old_price:.2f} → €{recommended_price:.2f})"
                    logger.warning(f"⚠️ Marge-Constraint: Preis von €{old_price:.2f} → €{recommended_price:.2f}")
            # Sonst: Folge dem Markt, auch wenn Marge < 20%
            else:
                if recommended_price < min_price:
                    logger.warning(f"""
                    ⚠️ TRADE-OFF ALERT:
                    Recommended price (€{recommended_price:.2f}) is below min margin (€{min_price:.2f})
                    BUT: Following market is more important than margin here
                    Consider: Is this product profitable at all?
                    """)
                    reasoning += f" (⚠️ Marge <20%, aber Markt-Anpassung wichtiger)"
        
        return {
            'recommended_price': round(recommended_price, 2),
            'confidence': confidence,
            'strategy': self.name,
            'reasoning': reasoning,
            'competitor_context': {
                'position': position,
                'avg_price': round(comp_avg, 2),
                'min_price': round(comp_min, 2),
                'max_price': round(comp_max, 2),
                'price_diff_pct': round(price_diff_pct * 100, 1),  # NEU!
                'competitor_count': len(prices),
                'sources': [c['source'] for c in competitor_prices[:5]]  # Top 5
            }
        }
    
    def _calculate_position(self, current_price: float, competitor_prices: List[float]) -> str:
        """
        Ermittelt Position im Markt
        
        Returns: 'cheapest' | 'below_average' | 'average' | 'above_average' | 'most_expensive'
        """
        if not competitor_prices:
            return "unknown"
        
        avg = sum(competitor_prices) / len(competitor_prices)
        min_price = min(competitor_prices)
        max_price = max(competitor_prices)
        
        # Position bestimmen
        if current_price <= min_price:
            return "cheapest"
        elif current_price < avg * 0.95:  # Mehr als 5% unter Durchschnitt
            return "below_average"
        elif current_price <= avg * 1.05:  # ±5% um Durchschnitt
            return "average"
        elif current_price < max_price:
            return "above_average"
        else:
            return "most_expensive"
    
    def _fallback_strategy(self, current_price: float) -> Dict:
        """
        Fallback-Strategie wenn keine Competitor-Daten verfügbar
        FIX: Keine Random-Variation mehr - deterministisch!
        """
        # FIX: Keine Random-Variation mehr - Preis bleibt unverändert wenn keine Competitor-Daten
        # Statt zufälliger ±2% Variation, empfehlen wir den aktuellen Preis
        recommended_price = current_price
        
        return {
            'recommended_price': round(recommended_price, 2),
            'confidence': 0.30,  # Sehr niedrige Confidence (keine Daten)
            'strategy': self.name,
            'reasoning': (
                "Keine Wettbewerber-Daten verfügbar. "
                "Empfehle aktuellen Preis beizubehalten bis Competitor-Daten verfügbar sind."
            ),
            'competitor_context': None
        }
    
    def _calculate_competitive_confidence(
        self,
        position: str,
        price_diff_pct: float,
        competitor_count: int,
        price_range: tuple
    ) -> float:
        """
        Formel-basierte Confidence für Competitive Strategy
        
        FAKTOREN (Rating: 9/10):
        1. Position Baseline (50-60%)
           - most_expensive/cheapest: 60% (klares Signal)
           - average: 50% (unklar)
        
        2. Price Difference Magnitude (0-30%)
           - 50%+ Differenz = sehr klares Signal = +30%
           - 10% Differenz = schwaches Signal = +6%
        
        3. Competitor Count (0-20%)
           - 5+ Competitors = robuste Daten = +20%
           - 1-2 Competitors = schwach = +4-8%
           - 🆕 PENALTY: <3 Competitors → -15% vom Total
        
        4. Price Range Consistency (0-10%)
           - Enger Range (<30% spread) = konsistenter Markt = +10%
           - Breiter Range (>50% spread) = fragmentiert = +2%
        
        Returns: 0.35 - 0.98
        """
        
        # FAKTOR 1: Position Baseline (50-60%)
        # -------------------------------------
        position_baseline = {
            'most_expensive': 0.60,   # Höchste (Markt sagt eindeutig "zu teuer")
            'cheapest': 0.60,          # Höchste (Markt sagt eindeutig "zu günstig")
            'above_average': 0.55,
            'below_average': 0.55,
            'average': 0.50,           # Niedrigste (Markt ist neutral/unklar)
        }.get(position, 0.50)
        
        logger.info(f"📊 Position Baseline ({position}): {position_baseline:.0%}")
        
        # FAKTOR 2: Price Difference Bonus (0-30%)
        # ------------------------------------------
        # Linear scaling: 0% diff = 0%, 50%+ diff = 30%
        diff_bonus = min(0.30, price_diff_pct * 0.6)
        logger.info(f"📊 Price Diff Bonus ({price_diff_pct:.0%} diff): +{diff_bonus:.0%}")
        
        # FAKTOR 3: Competitor Count Bonus (0-20%)
        # ------------------------------------------
        if competitor_count >= 5:
            comp_bonus = 0.20  # Excellent sample size
        elif competitor_count >= 3:
            comp_bonus = 0.12 + ((competitor_count - 3) * 0.04)  # 3→12%, 4→16%, 5→20%
        elif competitor_count >= 1:
            comp_bonus = competitor_count * 0.04  # 1→4%, 2→8%
        else:
            comp_bonus = 0.0
        
        logger.info(f"📊 Competitor Count Bonus ({competitor_count} comps): +{comp_bonus:.0%}")
        
        # FAKTOR 4: Price Range Consistency (0-10%)
        # -------------------------------------------
        min_price, max_price = price_range
        avg_price = (min_price + max_price) / 2
        
        if avg_price > 0:
            range_spread = (max_price - min_price) / avg_price
            
            if range_spread < 0.30:  # <30% spread = sehr konsistent
                range_bonus = 0.10
            elif range_spread < 0.50:  # 30-50% spread = moderat
                range_bonus = 0.05
            else:  # >50% spread = fragmentiert
                range_bonus = 0.02
        else:
            range_bonus = 0.0
            range_spread = 0.0
        
        logger.info(f"📊 Range Consistency (spread: {range_spread:.0%}): +{range_bonus:.0%}")
        
        # KOMBINIERE
        confidence = position_baseline + diff_bonus + comp_bonus + range_bonus
        
        # 🆕 KRITISCH: Penalty für niedrige Competitor Count
        if competitor_count < 3:
            penalty = 0.15
            confidence *= (1 - penalty)  # -15% vom Total!
            logger.warning(f"⚠️ LOW SAMPLE SIZE PENALTY ({competitor_count} < 3): -{penalty:.0%} = {confidence:.0%}")
        
        logger.info(f"📊 → RAW TOTAL: {confidence:.0%}")
        
        # Cap zwischen 35% und 98%
        final = min(0.98, max(0.35, confidence))
        logger.info(f"📊 → FINAL (capped): {final:.0%}")
        
        return final
    
    def _apply_constraints(
        self, 
        current_price: float, 
        recommended_price: float,
        cost: Optional[float] = None
    ) -> float:
        """
        Apply safety constraints:
        - Keine prozentuale Deckelung mehr
        - Nur noch: Minimum 20% Marge, falls Kosten bekannt
        """

        # Margin constraint (untere Grenze)
        if cost and cost > 0:
            min_price = cost * 1.20  # 20% minimum margin
            if recommended_price < min_price:
                recommended_price = min_price
        
        return recommended_price


