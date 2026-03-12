"""
Shopify Variant Detector - Intelligente Variant-Auswahl für Multi-Variant Produkte
"""
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class VariantDetector:
    """
    Intelligente Variant-Detection für Shopify Produkte.
    
    Problem: Shopify Produkte können mehrere Variants haben (z.B. Größen, Farben).
    Lösung: Wähle automatisch die beste Variant basierend auf:
    1. Höchster Lagerbestand
    2. Höchster Preis (Default Variant)
    3. Erste Variant (Fallback)
    """
    
    @staticmethod
    def find_best_variant(variants: List[Dict]) -> Optional[Dict]:
        """
        Findet die beste Variant für Preis-Update.
        
        Args:
            variants: Liste von Shopify Variants (aus GraphQL edges format)
            
        Returns:
            Beste Variant oder None
        """
        if not variants:
            return None
        
        # Konvertiere GraphQL edges Format zu einfachem Dict Format
        variant_list = []
        for variant in variants:
            if isinstance(variant, dict):
                # Falls es ein GraphQL edge Format ist
                if 'node' in variant:
                    variant_list.append(variant['node'])
                elif 'id' in variant:
                    variant_list.append(variant)
                else:
                    variant_list.append(variant)
            else:
                variant_list.append(variant)
        
        if len(variant_list) == 1:
            # Nur eine Variant → einfach
            return variant_list[0]
        
        # Multi-Variant Logik
        logger.info(f"🔍 Multi-Variant Produkt: {len(variant_list)} Variants gefunden")
        
        # Strategie 1: Variant mit höchstem Lagerbestand
        variants_with_inventory = [
            v for v in variant_list 
            if v.get('inventoryQuantity', v.get('inventory_quantity', 0)) > 0
        ]
        
        if variants_with_inventory:
            best = max(
                variants_with_inventory, 
                key=lambda v: v.get('inventoryQuantity', v.get('inventory_quantity', 0))
            )
            logger.info(f"✅ Beste Variant (höchster Bestand): {best.get('id')} (Bestand: {best.get('inventoryQuantity', best.get('inventory_quantity', 0))})")
            return best
        
        # Strategie 2: Variant mit höchstem Preis (meist Default)
        variants_with_price = [
            v for v in variant_list 
            if v.get('price') is not None
        ]
        
        if variants_with_price:
            best = max(
                variants_with_price, 
                key=lambda v: float(v.get('price', 0))
            )
            logger.info(f"✅ Beste Variant (höchster Preis): {best.get('id')} (Preis: {best.get('price')})")
            return best
        
        # Strategie 3: Erste Variant (Fallback)
        logger.warning(f"⚠️ Fallback: Nutze erste Variant {variant_list[0].get('id')}")
        return variant_list[0]
    
    @staticmethod
    def validate_variant(variant: Dict, product_variants: List[Dict]) -> bool:
        """
        Validiert ob eine Variant zu einem Produkt gehört.
        
        Args:
            variant: Zu validierende Variant (ID oder Dict)
            product_variants: Alle Variants des Produkts (GraphQL edges Format)
            
        Returns:
            True wenn valid, False sonst
        """
        if not variant or not product_variants:
            return False
        
        # Extrahiere Variant ID
        if isinstance(variant, str):
            variant_id = variant
        elif isinstance(variant, dict):
            variant_id = str(variant.get('id', ''))
        else:
            return False
        
        # Normalisiere Variant ID (entferne gid:// falls vorhanden)
        variant_id_normalized = variant_id.replace('gid://shopify/ProductVariant/', '')
        
        # Prüfe ob Variant in Product Variants existiert
        for pv in product_variants:
            # Handle GraphQL edges Format
            pv_node = pv.get('node', pv) if isinstance(pv, dict) else pv
            pv_id = str(pv_node.get('id', ''))
            pv_id_normalized = pv_id.replace('gid://shopify/ProductVariant/', '')
            
            if pv_id_normalized == variant_id_normalized or pv_id == variant_id:
                return True
        
        return False
