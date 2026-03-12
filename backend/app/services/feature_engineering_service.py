"""
Feature Engineering Service - Extracts all ML features for Pricing Engine

Feature Tiers:
- Tier 1: Basic Features (3) - Product fundamentals (price, inventory)
- COST Features (12) - From ProductCost table via Margin Calculator
- Tier 2: Sales Features (19) - From sales_history table
- Tier 3: Price Features (10) - From price_history table
- Tier 4: Inventory Features (15) - Stock & turnover
- Tier 5: Competitive Features (8) - Market positioning
- Tier 6: Advanced Features (23) - Seasonality, elasticity, etc.

Total: ~90 Features (expanded from 80 with detailed COST features)
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
import numpy as np
import pandas as pd
from app.models.product import Product
from app.models.sales_history import SalesHistory
from app.models.price_history import PriceHistory
from app.models.margin import ProductCost
from datetime import datetime as dt
from decimal import Decimal

logger = logging.getLogger(__name__)


class FeatureEngineeringService:
    """
    Centralized Feature Engineering for ML Pricing Engine.
    
    Extracts all 80 features from various data sources:
    - Database (sales_history, price_history, products)
    - External APIs (competitor data)
    - Calculated metrics (velocity, volatility, etc.)
    """
    
    def __init__(self, db: Session, shop_id: int = None):
        self.db = db
        self.shop_id = shop_id
    
    def extract_all_features(
        self, 
        product: Product,
        competitor_data: Optional[List[Dict]] = None,
        custom_data: Optional[Dict] = None,
        cutoff_date: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Extracts all ML features for a product (including detailed COST features).
        
        Args:
            product: Product model instance
            competitor_data: List of competitor products (optional)
            custom_data: Additional data (optional)
            cutoff_date: Temporal cutoff date (for training = applied_at, for inference = None = now)
            
        Returns:
            Dictionary with all feature values (~90 features including 12 COST features)
        """
        try:
            print(f"[FEATURE EXTRACTION] Starting feature extraction for product {product.id}", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] Starting feature extraction for product {product.id}")
            
            # Log competitor data status
            competitor_count = len(competitor_data) if competitor_data else 0
            competitor_source = "Serper API" if competitor_data else "MISSING"
            print(f"[FEATURE EXTRACTION] Competitor data: {competitor_source} ({competitor_count} competitors)", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] Competitor data: {competitor_source} ({competitor_count} competitors)")
            if competitor_data:
                competitor_prices = [c.get('price', 0) for c in competitor_data if c.get('price')]
                if competitor_prices:
                    print(f"[FEATURE EXTRACTION] Competitor prices: min=€{min(competitor_prices):.2f}, max=€{max(competitor_prices):.2f}, avg=€{sum(competitor_prices)/len(competitor_prices):.2f}", flush=True)
                    logger.critical(f"[FEATURE EXTRACTION] Competitor prices: min=€{min(competitor_prices):.2f}, max=€{max(competitor_prices):.2f}, avg=€{sum(competitor_prices)/len(competitor_prices):.2f}")
            
            # Extract cutoff_date from custom_data if not provided directly
            if cutoff_date is None and custom_data and 'cutoff_date' in custom_data:
                cutoff_date = custom_data['cutoff_date']
                if isinstance(cutoff_date, str):
                    from datetime import datetime as dt
                    cutoff_date = dt.fromisoformat(cutoff_date)
                elif hasattr(cutoff_date, 'date'):
                    # Convert date to datetime
                    cutoff_date = datetime.combine(cutoff_date, datetime.min.time())
            
            features = {}
            
            # Tier 1: Basic Features (3) - No temporal dependency (cost features moved to COST tier)
            print("[FEATURE EXTRACTION] Extracting Tier 1: Basic Features (3)", flush=True)
            logger.critical("[FEATURE EXTRACTION] Extracting Tier 1: Basic Features (3)")
            basic_features = self.extract_basic_features(product)
            features.update(basic_features)
            basic_non_zero = sum(1 for v in basic_features.values() if abs(v) >= 1e-10)
            print(f"[FEATURE EXTRACTION] Tier 1: {basic_non_zero}/{len(basic_features)} features have values", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] Tier 1: {basic_non_zero}/{len(basic_features)} features have values")
            
            # COST Features (11) - From ProductCost table via Margin Calculator
            print("[FEATURE EXTRACTION] Extracting COST Features (11)", flush=True)
            logger.critical("[FEATURE EXTRACTION] Extracting COST Features (11)")
            cost_features = self.extract_cost_features(product)
            features.update(cost_features)
            cost_non_zero = sum(1 for v in cost_features.values() if abs(v) >= 1e-10)
            print(f"[FEATURE EXTRACTION] COST: {cost_non_zero}/{len(cost_features)} features have values", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] COST: {cost_non_zero}/{len(cost_features)} features have values")
            if cost_non_zero == 0:
                print("[FEATURE EXTRACTION] ⚠️ WARNING: No cost data found! Check ProductCost table or product.cost field", flush=True)
                logger.critical("[FEATURE EXTRACTION] ⚠️ WARNING: No cost data found! Check ProductCost table or product.cost field")
            
            # Tier 2: Sales Features (19) - Uses cutoff_date
            print("[FEATURE EXTRACTION] Extracting Tier 2: Sales Features (19)", flush=True)
            logger.critical("[FEATURE EXTRACTION] Extracting Tier 2: Sales Features (19)")
            sales_features = self.extract_sales_features(product, cutoff_date=cutoff_date)
            features.update(sales_features)
            sales_non_zero = sum(1 for v in sales_features.values() if abs(v) >= 1e-10)
            print(f"[FEATURE EXTRACTION] Tier 2 (Sales): {sales_non_zero}/{len(sales_features)} features have values", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] Tier 2 (Sales): {sales_non_zero}/{len(sales_features)} features have values")
            if sales_non_zero == 0:
                print("[FEATURE EXTRACTION] ⚠️ WARNING: No sales history data! Check sales_history table", flush=True)
                logger.critical("[FEATURE EXTRACTION] ⚠️ WARNING: No sales history data! Check sales_history table")
            
            # Tier 3: Price Features (10) - Uses cutoff_date
            print("[FEATURE EXTRACTION] Extracting Tier 3: Price Features (10)", flush=True)
            logger.critical("[FEATURE EXTRACTION] Extracting Tier 3: Price Features (10)")
            price_features = self.extract_price_features(product, cutoff_date=cutoff_date)
            features.update(price_features)
            price_non_zero = sum(1 for v in price_features.values() if abs(v) >= 1e-10)
            print(f"[FEATURE EXTRACTION] Tier 3 (Price): {price_non_zero}/{len(price_features)} features have values", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] Tier 3 (Price): {price_non_zero}/{len(price_features)} features have values")
            if price_non_zero == 0:
                print("[FEATURE EXTRACTION] ⚠️ WARNING: No price history data! Check price_history table", flush=True)
                logger.critical("[FEATURE EXTRACTION] ⚠️ WARNING: No price history data! Check price_history table")
            
            # Tier 4: Inventory Features (15) - Uses cutoff_date
            print("[FEATURE EXTRACTION] Extracting Tier 4: Inventory Features (15)", flush=True)
            logger.critical("[FEATURE EXTRACTION] Extracting Tier 4: Inventory Features (15)")
            inventory_features = self.extract_inventory_features(product, cutoff_date=cutoff_date)
            features.update(inventory_features)
            inventory_non_zero = sum(1 for v in inventory_features.values() if abs(v) >= 1e-10)
            print(f"[FEATURE EXTRACTION] Tier 4 (Inventory): {inventory_non_zero}/{len(inventory_features)} features have values", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] Tier 4 (Inventory): {inventory_non_zero}/{len(inventory_features)} features have values")
            
            # Tier 5: Competitive Features (8) - No temporal dependency
            print("[FEATURE EXTRACTION] Extracting Tier 5: Competitive Features (8)", flush=True)
            logger.critical("[FEATURE EXTRACTION] Extracting Tier 5: Competitive Features (8)")
            if competitor_data:
                competitive_features = self.extract_competitive_features(product, competitor_data)
                features.update(competitive_features)
                competitive_non_zero = sum(1 for v in competitive_features.values() if abs(v) >= 1e-10)
                print(f"[FEATURE EXTRACTION] Tier 5 (Competitive): {competitive_non_zero}/{len(competitive_features)} features have values (from Serper API)", flush=True)
                logger.critical(f"[FEATURE EXTRACTION] Tier 5 (Competitive): {competitive_non_zero}/{len(competitive_features)} features have values (from Serper API)")
            else:
                competitive_features = self._get_empty_competitive_features()
                features.update(competitive_features)
                print("[FEATURE EXTRACTION] Tier 5 (Competitive): 0/8 features (MISSING: No competitor_data from Serper API)", flush=True)
                logger.critical("[FEATURE EXTRACTION] Tier 5 (Competitive): 0/8 features (MISSING: No competitor_data from Serper API)")
            
            # Tier 6: Advanced Features (23) - Uses cutoff_date
            print("[FEATURE EXTRACTION] Extracting Tier 6: Advanced Features (23)", flush=True)
            logger.critical("[FEATURE EXTRACTION] Extracting Tier 6: Advanced Features (23)")
            advanced_features = self.extract_advanced_features(product, custom_data, cutoff_date=cutoff_date)
            features.update(advanced_features)
            advanced_non_zero = sum(1 for v in advanced_features.values() if abs(v) >= 1e-10)
            print(f"[FEATURE EXTRACTION] Tier 6 (Advanced): {advanced_non_zero}/{len(advanced_features)} features have values", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] Tier 6 (Advanced): {advanced_non_zero}/{len(advanced_features)} features have values")
            
            # ==================== PHASE 1: QUICK WINS (15 Features) ====================
            # Seasonality Features (6)
            features.update(self.extract_seasonality_features(cutoff_date=cutoff_date))
            
            # Review Proxy Features (3)
            features.update(self.extract_review_proxy_features(product, cutoff_date=cutoff_date))
            
            # Shopify-Specific Features (3)
            features.update(self.extract_shopify_features(product))
            
            # Quality Composite Proxy (1)
            features.update(self.extract_quality_proxy_features(product, cutoff_date=cutoff_date))
            
            # Market Store-Scoped Features (2)
            features.update(self.extract_market_store_features(product, cutoff_date=cutoff_date))
            
            # ==================== PHASE 2: CORE TRANSFORMATIONS (10 Features) ====================
            # Brand Features (2)
            features.update(self.extract_brand_features(product, cutoff_date=cutoff_date))
            
            # Price Elasticity Proxy (1)
            features.update(self.extract_price_elasticity_proxy(product, cutoff_date=cutoff_date))
            
            # Category Features (4)
            features.update(self.extract_category_features(product, cutoff_date=cutoff_date))
            
            # Inventory Transformations (2)
            features.update(self.extract_inventory_transformations(product, cutoff_date=cutoff_date))
            
            # Demand Volatility (1)
            features.update(self.extract_demand_volatility_features(product, cutoff_date=cutoff_date))
            
            # ==================== PHASE 3: ADVANCED FEATURES (5 Features) ====================
            # Holiday Calendar (1)
            features.update(self.extract_holiday_features(cutoff_date=cutoff_date))
            
            # Customer Churn Rate (1)
            features.update(self.extract_churn_features(product, cutoff_date=cutoff_date))
            
            # Profitability Index (1)
            features.update(self.extract_profitability_features(product, cutoff_date=cutoff_date))
            
            # Product Lifecycle Stage (1) - Already in advanced_features, but ensure it's there
            # Return Rate (1) - Already calculated in review_proxy_features
            
            # STEP 2: Feature extraction complete - Log detailed summary
            print("=" * 80, flush=True)
            print("[FEATURE EXTRACTION] Feature Extraction Summary", flush=True)
            print("=" * 80, flush=True)
            logger.critical("=" * 80)
            logger.critical("[FEATURE EXTRACTION] Feature Extraction Summary")
            logger.critical("=" * 80)
            
            total_features = len(features)
            features_with_values = sum(1 for v in features.values() if abs(v) >= 1e-10)
            features_zero = total_features - features_with_values
            coverage_pct = (features_with_values / total_features * 100) if total_features > 0 else 0
            
            print(f"[FEATURE EXTRACTION] Total features extracted: {total_features}", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] Total features extracted: {total_features}")
            print(f"[FEATURE EXTRACTION] Features with values: {features_with_values}/{total_features} ({coverage_pct:.1f}%)", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] Features with values: {features_with_values}/{total_features} ({coverage_pct:.1f}%)")
            print(f"[FEATURE EXTRACTION] Features with zero values: {features_zero}/{total_features} ({100-coverage_pct:.1f}%)", flush=True)
            logger.critical(f"[FEATURE EXTRACTION] Features with zero values: {features_zero}/{total_features} ({100-coverage_pct:.1f}%)")
            
            # Identify missing data sources
            missing_sources = []
            if cost_non_zero == 0:
                missing_sources.append("Cost Data (ProductCost table or product.cost)")
            if sales_non_zero == 0:
                missing_sources.append("Sales History (sales_history table)")
            if price_non_zero == 0:
                missing_sources.append("Price History (price_history table)")
            if not competitor_data:
                missing_sources.append("Competitor Data (Serper API)")
            
            if missing_sources:
                print(f"[FEATURE EXTRACTION] ⚠️ MISSING DATA SOURCES:", flush=True)
                logger.critical(f"[FEATURE EXTRACTION] ⚠️ MISSING DATA SOURCES:")
                for source in missing_sources:
                    print(f"[FEATURE EXTRACTION]   - {source}", flush=True)
                    logger.critical(f"[FEATURE EXTRACTION]   - {source}")
            else:
                print("[FEATURE EXTRACTION] ✅ All data sources available", flush=True)
                logger.critical("[FEATURE EXTRACTION] ✅ All data sources available")
            
            print("=" * 80, flush=True)
            logger.critical("=" * 80)
            
            logger.info("STEP 2: Feature extraction complete")
            logger.info(f"  - All features extracted: {len(features)} (will be filtered for XGBoost: 74, Meta Labeler: 56)")
            logger.info(f"  - Feature categories:")
            
            # Count features by category
            basic_count = len([k for k in features.keys() if k in ['current_price', 'inventory_quantity', 'price_original']])
            cost_count = len([k for k in features.keys() if k.startswith('cost_')])
            sales_count = len([k for k in features.keys() if 'sales' in k.lower() or 'velocity' in k.lower() or 'revenue' in k.lower()])
            price_count = len([k for k in features.keys() if 'price' in k.lower() and not k.startswith('cost_') and k != 'current_price' and k != 'price_original'])
            competitor_count = len([k for k in features.keys() if 'competitor' in k.lower()])
            advanced_count = len(features) - basic_count - cost_count - sales_count - price_count - competitor_count
            
            logger.info(f"    - Basic: {basic_count}")
            logger.info(f"    - Cost: {cost_count}")
            logger.info(f"    - Sales: {sales_count}")
            logger.info(f"    - Price: {price_count}")
            logger.info(f"    - Competitor: {competitor_count}")
            logger.info(f"    - Advanced: {advanced_count}")
            
            # Missing Data Warnings (Priority 2)
            missing_data_warnings = []
            if cost_count == 0:
                missing_data_warnings.append("No cost data available")
            if sales_count == 0:
                missing_data_warnings.append("No sales history available")
            if price_count == 0:
                missing_data_warnings.append("No price history available")
            if competitor_count == 0:
                missing_data_warnings.append("No competitor data available")
            
            if missing_data_warnings:
                logger.warning(f"  WARNING: Missing data detected:")
                for warning in missing_data_warnings:
                    logger.warning(f"     - {warning}")
            
            # KEY FEATURE STATUS - Critical features for ML pricing
            logger.info("  - Key features status:")
            
            # Sales History (CRITICAL)
            sales_velocity_30d = features.get('sales_velocity_30d', 0)
            sales_90d = features.get('sales_90d', 0)
            sales_7d = features.get('sales_7d', 0)
            has_sales_data = sales_90d > 0 or sales_velocity_30d > 0 or sales_7d > 0
            logger.info(f"    - Sales History: {'AVAILABLE' if has_sales_data else 'MISSING'} (90d: {sales_90d}, velocity 30d: {sales_velocity_30d:.1f}, 7d: {sales_7d})")
            
            # Competitor Data (CRITICAL)
            competitor_count_val = features.get('competitor_count', 0)
            competitor_avg_price = features.get('competitor_avg_price', 0)
            has_competitor_data = competitor_count_val > 0
            logger.info(f"    - Competitor Data: {'AVAILABLE' if has_competitor_data else 'MISSING'} (count: {competitor_count_val}, avg: €{competitor_avg_price:.2f})")
            
            # Price History (IMPORTANT)
            price_avg_30d = features.get('price_avg_30d', 0)
            price_change_pct_30d = features.get('price_change_pct_30d', 0)
            has_price_history = price_avg_30d > 0
            logger.info(f"    - Price History: {'AVAILABLE' if has_price_history else 'MISSING'} (avg 30d: €{price_avg_30d:.2f}, change: {price_change_pct_30d:+.1f}%)")
            
            # Cost Data (CRITICAL)
            cost_total = features.get('cost_total', 0)
            breakeven_price = features.get('breakeven_price', 0)
            has_cost_data = cost_total > 0 or breakeven_price > 0
            logger.info(f"    - Cost Data: {'AVAILABLE' if has_cost_data else 'MISSING'} (total: €{cost_total:.2f}, breakeven: €{breakeven_price:.2f})")
            
            # Feature Availability Summary
            features_with_data = sum(1 for v in features.values() if v != 0.0 and v is not None)
            features_total = len(features)
            features_availability_pct = (features_with_data / features_total * 100) if features_total > 0 else 0
            logger.info(f"  - Feature availability: {features_with_data}/{features_total} ({features_availability_pct:.1f}%) have data")
            
            return features
        
        except Exception as e:
            import traceback
            print(f"🔴 [FE_SERVICE ERROR] Product {product.id}: {str(e)}", flush=True)
            print(f"🔴 [TRACEBACK]:\n{traceback.format_exc()}", flush=True)
            logger.error(f"🔴 [FE_SERVICE ERROR] Product {product.id}: {str(e)}")
            logger.error(f"🔴 [TRACEBACK]:\n{traceback.format_exc()}")
            raise
    
    # ==================== TIER 1: BASIC FEATURES (3) ====================
    
    def extract_basic_features(self, product: Product) -> Dict[str, float]:
        """
        Extracts basic product features (without cost - moved to extract_cost_features).
        
        Features:
        1. current_price
        2. inventory_quantity
        3. inventory_value
        """
        current_price = float(product.price) if product.price else 0.0
        inventory_qty = product.inventory_quantity or 0
        inventory_value = current_price * inventory_qty
        
        return {
            'current_price': current_price,
            'inventory_quantity': float(inventory_qty),
            'inventory_value': inventory_value
        }
    
    # ==================== COST FEATURES (11) ====================
    
    def extract_cost_features(self, product: Product) -> Dict[str, float]:
        """
        Extracts all COST-related features from ProductCost table and Margin Calculator.
        
        Features (all COST category):
        1. cost_total - Sum of purchase + shipping + packaging
        2. cost_purchase - Purchase cost
        3. cost_shipping - Shipping cost
        4. cost_packaging - Packaging cost
        5. cost_payment_fee_pct - Payment fee percentage
        6. cost_payment_fee_abs - Absolute payment fee for current price
        7. cost_total_variable - Total variable costs (incl. payment fee)
        8. breakeven_price - Break-even price (0% margin)
        9. margin_euro - Margin in Euro (net revenue - variable costs)
        10. margin_pct - Margin in % (net revenue - variable costs) / net revenue
        11. margin_safety_buffer - Difference between current margin and 20% target
        
        Returns:
            Dictionary with all COST features (defaults to 0 if no cost data available)
        """
        current_price = float(product.price) if product.price else 0.0
        
        # Default values (if no cost data)
        # Try legacy product.cost as fallback
        legacy_cost = float(product.cost) if hasattr(product, 'cost') and product.cost else 0.0
        
        default_features = {
            'cost_total': legacy_cost,  # Use legacy cost if available
            'cost_purchase': legacy_cost,  # Assume legacy cost is purchase cost
            'cost_shipping': 0.0,
            'cost_packaging': 0.0,
            'cost_payment_fee_pct': 0.0,
            'cost_payment_fee_abs': 0.0,
            'cost_total_variable': legacy_cost,
            'breakeven_price': 0.0,
            'margin_euro': 0.0,
            'margin_pct': 0.0,
            'margin_safety_buffer': 0.0,
            'cost': legacy_cost  # Legacy compatibility
        }
        
        # Calculate legacy margin_pct if we have price and legacy cost
        if current_price > 0 and legacy_cost > 0:
            default_features['margin_pct'] = ((current_price - legacy_cost) / current_price * 100.0)
        
        # Try to get ProductCost from database
        try:
            # Get shop_id (handle both int and string)
            shop_id = getattr(product, 'shop_id', None)
            if shop_id is None:
                shop_id = getattr(product, 'shopid', None)
            
            # Normalize shop_id to string (for ProductCost table)
            shop_id_str = str(shop_id) if shop_id else "999"
            if shop_id_str.lower() == "demo" or (shop_id_str.isdigit() and int(shop_id_str) == 999):
                shop_id_str = "999"
            
            # Get product_id (handle both int and string)
            product_id_str = str(getattr(product, 'shopify_product_id', None) or product.id)
            
            # Query ProductCost
            cost_data = self.db.query(ProductCost).filter(
                ProductCost.product_id == product_id_str,
                ProductCost.shop_id == shop_id_str
            ).first()
            
            if not cost_data:
                logger.debug(f"No ProductCost data for product {product.id} (shop {shop_id_str}) - using defaults")
                return default_features
            
            # Extract cost components
            purchase_cost = float(cost_data.purchase_cost) if cost_data.purchase_cost else 0.0
            shipping_cost = float(cost_data.shipping_cost) if cost_data.shipping_cost else 0.0
            packaging_cost = float(cost_data.packaging_cost) if cost_data.packaging_cost else 0.0
            
            # Total base costs
            cost_total = purchase_cost + shipping_cost + packaging_cost
            
            # Payment fee configuration
            from app.services.margin_calculator_service import MarginCalculatorService
            margin_calc = MarginCalculatorService(db=self.db)
            
            payment_config = margin_calc.PAYMENT_PROVIDERS.get(
                cost_data.payment_provider or 'stripe',
                margin_calc.PAYMENT_PROVIDERS['stripe']
            )
            
            payment_fee_pct = float(cost_data.payment_fee_percentage) if cost_data.payment_fee_percentage else float(payment_config['percentage'])
            payment_fee_fixed = float(cost_data.payment_fee_fixed) if cost_data.payment_fee_fixed else float(payment_config['fixed'])
            
            # VAT rate
            vat_rate = float(cost_data.vat_rate) if cost_data.vat_rate else 0.19  # Default 19% for DE
            
            # Calculate net revenue (if current_price > 0)
            if current_price > 0:
                net_revenue = current_price / (1.0 + vat_rate)
                
                # Payment fee (absolute)
                payment_fee_abs = (net_revenue * payment_fee_pct / 100.0) + payment_fee_fixed
                
                # Total variable costs
                cost_total_variable = cost_total + payment_fee_abs
                
                # Margin in Euro
                margin_euro = net_revenue - cost_total_variable
                
                # Margin in %
                margin_pct = (margin_euro / net_revenue * 100.0) if net_revenue > 0 else 0.0
                
                # Safety buffer (difference to 20% target margin)
                target_margin_pct = 20.0
                margin_safety_buffer = margin_pct - target_margin_pct
            else:
                payment_fee_abs = 0.0
                cost_total_variable = cost_total
                margin_euro = 0.0
                margin_pct = 0.0
                margin_safety_buffer = 0.0
            
            # Break-even price calculation
            # Formula: break_even = (base_costs + fixed_fee) * (1 + vat_rate) / (1 - payment_pct/100)
            payment_pct_decimal = payment_fee_pct / 100.0
            if payment_pct_decimal < 1.0:  # Safety check
                numerator = (cost_total + payment_fee_fixed) * (1.0 + vat_rate)
                denominator = 1.0 - payment_pct_decimal
                breakeven_price = numerator / denominator if denominator > 0 else cost_total * (1.0 + vat_rate)
            else:
                breakeven_price = cost_total * (1.0 + vat_rate)
            
            logger.debug(f"✅ Extracted COST features for product {product.id} (has_cost_data=True)")
            
            # Build feature dict
            cost_features = {
                'cost_total': cost_total,
                'cost_purchase': purchase_cost,
                'cost_shipping': shipping_cost,
                'cost_packaging': packaging_cost,
                'cost_payment_fee_pct': payment_fee_pct,
                'cost_payment_fee_abs': payment_fee_abs,
                'cost_total_variable': cost_total_variable,
                'breakeven_price': breakeven_price,
                'margin_euro': margin_euro,
                'margin_pct': margin_pct,
                'margin_safety_buffer': margin_safety_buffer
            }
            
            # Legacy compatibility: 'cost' as alias for 'cost_total'
            cost_features['cost'] = cost_total
            
            return cost_features
            
        except Exception as e:
            logger.warning(f"⚠️ Error extracting COST features for product {product.id}: {e}")
            logger.debug(f"   Using default values (all 0.0)")
            return default_features
    
    # ==================== TIER 2: SALES FEATURES (19) ====================
    
    def extract_sales_features(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Extracts sales-based features from sales_history table.
        
        🔍 [DEBUG] Method entry point for sales_30d error tracking
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Features (19):
        Sales Velocity:
        1. sales_velocity_7d - Sales per day (last 7 days)
        2. sales_velocity_30d - Sales per day (last 30 days)
        3. sales_velocity_90d - Sales per day (last 90 days)
        
        Demand Growth:
        4. demand_growth_7d_vs_30d - Growth rate comparison
        5. demand_growth_30d_vs_90d - Growth rate comparison
        6. demand_trend - Overall demand trend (-1, 0, 1)
        
        Sales Volatility:
        7. sales_volatility_7d - Std dev of daily sales (7d)
        8. sales_volatility_30d - Std dev of daily sales (30d)
        9. sales_consistency - 1 - (volatility / mean)
        
        Revenue Features:
        10. revenue_7d - Total revenue last 7 days
        11. revenue_30d - Total revenue last 30 days
        12. revenue_90d - Total revenue last 90 days
        13. avg_order_value_7d - Average order value
        14. avg_order_value_30d - Average order value
        
        Sales Patterns:
        15. days_since_last_sale - Days since last sale
        16. sales_frequency - Sales per week
        17. peak_sales_day - Day of week with most sales (0-6)
        18. weekend_sales_ratio - Weekend vs weekday sales
        19. sales_acceleration - Change in velocity trend
        """
        logger.debug(f"Extracting sales features for product {product.id}")
        
        # ✅ BULLETPROOF: Initialize ALL variables at start with safe defaults
        sales_7d = []
        sales_30d = []
        sales_90d = []
        now = datetime.now()  # Default
        end_date = now  # Default
        
        try:
            # Use cutoff_date if provided (for training), otherwise use effective_now (for inference)
            if cutoff_date:
                now = cutoff_date
            else:
                try:
                    now = self._get_effective_now(product.id)
                except Exception:
                    # Fallback: Use current datetime if _get_effective_now fails
                    now = datetime.now()
            
            end_date = now
            
            # ✅ PROTECTED: Try to get sales data with fallback (each call separately protected)
            try:
                sales_7d = self._get_sales_in_period(product.id, end_date - timedelta(days=7), end_date, strict_before=True) or []
            except Exception as e:
                logger.warning(f"Could not fetch sales_7d for product {product.id}: {e}")
                sales_7d = []  # Explicit fallback
            
            try:
                sales_30d = self._get_sales_in_period(product.id, end_date - timedelta(days=30), end_date, strict_before=True) or []
            except Exception as e:
                logger.warning(f"Could not fetch sales_30d for product {product.id}: {e}")
                sales_30d = []  # Explicit fallback
            
            try:
                sales_90d = self._get_sales_in_period(product.id, end_date - timedelta(days=90), end_date, strict_before=True) or []
            except Exception as e:
                logger.warning(f"Could not fetch sales_90d for product {product.id}: {e}")
                sales_90d = []  # Explicit fallback
                
        except Exception as e:
            logger.error(f"Error in extract_sales_features for product {product.id}: {e}")
            # ✅ All variables already initialized above - safe defaults!
            pass
        
        # ✅ GUARANTEED: All variables are defined (either from query or default [])
        
        # Sales Velocity
        velocity_7d = len(sales_7d) / 7.0 if sales_7d else 0.0
        velocity_30d = len(sales_30d) / 30.0 if sales_30d else 0.0
        velocity_90d = len(sales_90d) / 90.0 if sales_90d else 0.0
        
        # Demand Growth
        growth_7d_vs_30d = ((velocity_7d - velocity_30d) / velocity_30d * 100) if velocity_30d > 0 else 0.0
        growth_30d_vs_90d = ((velocity_30d - velocity_90d) / velocity_90d * 100) if velocity_90d > 0 else 0.0
        
        demand_trend = 0.0
        if growth_7d_vs_30d > 10:
            demand_trend = 1.0  # Growing
        elif growth_7d_vs_30d < -10:
            demand_trend = -1.0  # Declining
        
        # Sales Volatility
        daily_sales_7d = self._calculate_daily_sales(sales_7d, 7)
        daily_sales_30d = self._calculate_daily_sales(sales_30d, 30)
        
        volatility_7d = np.std(daily_sales_7d) if len(daily_sales_7d) > 1 else 0.0
        volatility_30d = np.std(daily_sales_30d) if len(daily_sales_30d) > 1 else 0.0
        
        mean_sales_7d = np.mean(daily_sales_7d) if daily_sales_7d else 0.0
        consistency = 1.0 - (volatility_7d / mean_sales_7d) if mean_sales_7d > 0 else 0.0
        consistency = max(0.0, min(1.0, consistency))  # Clamp to [0, 1]
        
        # Revenue Features
        revenue_7d = sum([float(s.revenue) for s in sales_7d if s.revenue]) if sales_7d else 0.0
        revenue_30d = sum([float(s.revenue) for s in sales_30d if s.revenue]) if sales_30d else 0.0
        revenue_90d = sum([float(s.revenue) for s in sales_90d if s.revenue]) if sales_90d else 0.0
        
        total_qty_7d = sum([s.quantity_sold for s in sales_7d]) if sales_7d else 0
        total_qty_30d = sum([s.quantity_sold for s in sales_30d]) if sales_30d else 0
        
        avg_order_value_7d = revenue_7d / total_qty_7d if total_qty_7d > 0 else 0.0
        avg_order_value_30d = revenue_30d / total_qty_30d if total_qty_30d > 0 else 0.0
        
        # Sales Patterns
        days_since_last_sale = self._days_since_last_sale(product.id, now)
        sales_frequency = len(sales_30d) / 4.0 if sales_30d else 0.0  # Sales per week
        
        peak_sales_day = self._calculate_peak_sales_day(sales_30d)
        weekend_sales_ratio = self._calculate_weekend_ratio(sales_30d)
        
        # Sales Acceleration (change in velocity)
        acceleration = velocity_7d - velocity_30d
        
        return {
            'sales_velocity_7d': velocity_7d,
            'sales_velocity_30d': velocity_30d,
            'sales_velocity_90d': velocity_90d,
            'demand_growth_7d_vs_30d': growth_7d_vs_30d,
            'demand_growth_30d_vs_90d': growth_30d_vs_90d,
            'demand_trend': demand_trend,
            'sales_volatility_7d': volatility_7d,
            'sales_volatility_30d': volatility_30d,
            'sales_consistency': consistency,
            'revenue_7d': revenue_7d,
            'revenue_30d': revenue_30d,
            'revenue_90d': revenue_90d,
            'avg_order_value_7d': avg_order_value_7d,
            'avg_order_value_30d': avg_order_value_30d,
            'days_since_last_sale': float(days_since_last_sale),
            'sales_frequency': sales_frequency,
            'peak_sales_day': float(peak_sales_day),
            'weekend_sales_ratio': weekend_sales_ratio,
            'sales_acceleration': acceleration
        }
    
    # ==================== TIER 3: PRICE FEATURES (10) ====================
    
    def extract_price_features(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Extracts price-based features from price_history table.
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Features (10):
        Price Volatility:
        1. price_volatility_7d - Std dev of price changes (7d)
        2. price_volatility_30d - Std dev of price changes (30d)
        3. price_stability_score - 1 - (volatility / mean_price)
        
        Price Trend:
        4. price_trend_slope - Linear regression slope (30d)
        5. price_change_frequency - Number of price changes (30d)
        6. price_momentum - Recent price change direction
        
        Price Statistics:
        7. price_min_30d - Minimum price (30d)
        8. price_max_30d - Maximum price (30d)
        9. price_avg_30d - Average price (30d)
        10. price_vs_avg_30d_pct - Current vs average price (%)
        """
        # Use cutoff_date if provided (for training), otherwise use effective_now (for inference)
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except Exception:
                # Fallback: Use current datetime if _get_effective_now fails
                now = datetime.now()
        
        # Get price history (STRICTLY BEFORE cutoff_date for training!)
        # Use < instead of <= to exclude cutoff_date itself
        price_history = self._get_price_history(product.id, now - timedelta(days=30), now, strict_before=True)
        
        if not price_history or len(price_history) < 2:
            # Return default values if no price history
            current_price = float(product.price) if product.price else 0.0
            return {
                'price_volatility_7d': 0.0,
                'price_volatility_30d': 0.0,
                'price_stability_score': 1.0,
                'price_trend_slope': 0.0,
                'price_change_frequency': 0.0,
                'price_momentum': 0.0,
                'price_min_30d': current_price,
                'price_max_30d': current_price,
                'price_avg_30d': current_price,
                'price_vs_avg_30d_pct': 0.0
            }
        
        # Convert to DataFrame for easier calculations
        prices = [float(p.price) for p in price_history]
        dates = [p.price_date for p in price_history]
        
        df = pd.DataFrame({'date': dates, 'price': prices})
        df = df.sort_values('date')
        
        # Price Volatility
        price_changes = df['price'].diff().dropna()
        volatility_7d = price_changes.tail(7).std() if len(price_changes) >= 7 else 0.0
        volatility_30d = price_changes.std() if len(price_changes) > 1 else 0.0
        
        mean_price = df['price'].mean()
        stability_score = 1.0 - (volatility_30d / mean_price) if mean_price > 0 else 1.0
        stability_score = max(0.0, min(1.0, stability_score))
        
        # Price Trend Slope (linear regression)
        if len(df) >= 2:
            x = np.arange(len(df))
            y = df['price'].values
            try:
                slope = np.polyfit(x, y, 1)[0]
            except:
                slope = 0.0
        else:
            slope = 0.0
        
        # Price Change Frequency
        change_frequency = len(price_changes[price_changes != 0])
        
        # Price Momentum (recent change direction)
        if len(df) >= 2:
            recent_change = df['price'].iloc[-1] - df['price'].iloc[-2]
            momentum = 1.0 if recent_change > 0 else (-1.0 if recent_change < 0 else 0.0)
        else:
            momentum = 0.0
        
        # Price Statistics
        price_min = df['price'].min()
        price_max = df['price'].max()
        price_avg = df['price'].mean()
        
        # For training: Use price at cutoff_date (last price BEFORE cutoff)
        # For inference: Use current product price
        if cutoff_date and len(df) > 0:
            # Use last price in history (before cutoff)
            current_price = df['price'].iloc[-1]
        else:
            current_price = float(product.price) if product.price else price_avg
        
        price_vs_avg_pct = ((current_price - price_avg) / price_avg * 100) if price_avg > 0 else 0.0
        
        return {
            'price_volatility_7d': volatility_7d,
            'price_volatility_30d': volatility_30d,
            'price_stability_score': stability_score,
            'price_trend_slope': slope,
            'price_change_frequency': float(change_frequency),
            'price_momentum': momentum,
            'price_min_30d': price_min,
            'price_max_30d': price_max,
            'price_avg_30d': price_avg,
            'price_vs_avg_30d_pct': price_vs_avg_pct
        }
    
    # ==================== TIER 4: INVENTORY FEATURES (15) ====================
    
    def extract_inventory_features(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Extracts inventory-based features.
        
        🔍 [DEBUG] Method entry point for sales_30d error tracking
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Features (15):
        Stock Levels:
        1. inventory_quantity - Current stock
        2. inventory_value - Stock value
        3. inventory_turnover_30d - Stock turnover rate
        4. inventory_turnover_90d - Stock turnover rate
        5. stockout_risk - Probability of stockout
        
        Days of Stock:
        6. days_of_stock_7d - Days until stockout (7d velocity)
        7. days_of_stock_30d - Days until stockout (30d velocity)
        8. days_of_stock_90d - Days until stockout (90d velocity)
        9. stock_velocity_ratio - 7d vs 30d velocity
        
        Inventory Trends:
        10. inventory_trend - Stock level trend
        11. reorder_point - Suggested reorder point
        12. safety_stock - Safety stock level
        13. stock_health_score - Overall stock health (0-1)
        14. overstock_risk - Risk of overstocking
        15. understock_risk - Risk of understocking
        """
        inventory_qty = product.inventory_quantity or 0
        current_price = float(product.price) if product.price else 0.0
        inventory_value = current_price * inventory_qty
        
        # Use cutoff_date if provided (for training), otherwise use effective_now (for inference)
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except Exception:
                # Fallback: Use current datetime if _get_effective_now fails
                now = datetime.now()
        
        logger.debug(f"Extracting inventory features for product {product.id}")
        
        # Get sales for turnover calculation (STRICTLY BEFORE cutoff_date for training!)
        # ✅ BULLETPROOF: Initialize and protect sales_30d and sales_90d
        sales_30d = []
        sales_90d = []
        try:
            sales_30d = self._get_sales_in_period(
                product.id, 
                now - timedelta(days=30), 
                now, 
                strict_before=True
            ) or []
        except Exception as e:
            logger.warning(f"Could not fetch sales_30d for product {product.id} in extract_inventory_features: {e}")
            sales_30d = []  # Explicit fallback
        
        try:
            sales_90d = self._get_sales_in_period(
                product.id, 
                now - timedelta(days=90), 
                now, 
                strict_before=True
            ) or []
        except Exception as e:
            logger.warning(f"Could not fetch sales_90d for product {product.id} in extract_inventory_features: {e}")
            sales_90d = []  # Explicit fallback
        
        total_qty_30d = sum([s.quantity_sold for s in sales_30d]) if sales_30d else 0
        total_qty_90d = sum([s.quantity_sold for s in sales_90d]) if sales_90d else 0
        
        # Inventory Turnover
        avg_inventory = inventory_qty  # Simplified
        turnover_30d = total_qty_30d / avg_inventory if avg_inventory > 0 else 0.0
        turnover_90d = total_qty_90d / avg_inventory if avg_inventory > 0 else 0.0
        
        # Stockout Risk (based on velocity)
        velocity_30d = total_qty_30d / 30.0 if sales_30d else 0.0
        stockout_risk = 0.0
        if velocity_30d > 0 and inventory_qty > 0:
            days_until_stockout = inventory_qty / velocity_30d
            if days_until_stockout < 7:
                stockout_risk = 1.0
            elif days_until_stockout < 14:
                stockout_risk = 0.5
            else:
                stockout_risk = 0.0
        
        # Days of Stock
        velocity_7d = total_qty_30d / 30.0 * 7 / 7.0 if sales_30d else 0.0  # Approximate
        velocity_90d = total_qty_90d / 90.0 if sales_90d else 0.0
        
        days_of_stock_7d = inventory_qty / velocity_7d if velocity_7d > 0 else 999.0
        days_of_stock_30d = inventory_qty / velocity_30d if velocity_30d > 0 else 999.0
        days_of_stock_90d = inventory_qty / velocity_90d if velocity_90d > 0 else 999.0
        
        stock_velocity_ratio = velocity_7d / velocity_30d if velocity_30d > 0 else 1.0
        
        # Inventory Trends (simplified)
        inventory_trend = 0.0  # Would need historical inventory data
        
        # Reorder Point & Safety Stock
        avg_daily_demand = velocity_30d
        lead_time_days = 7  # Assumed
        reorder_point = avg_daily_demand * lead_time_days
        safety_stock = avg_daily_demand * 3  # 3 days safety
        
        # Stock Health Score
        if days_of_stock_30d > 60:
            health_score = 0.3  # Overstocked
        elif days_of_stock_30d < 7:
            health_score = 0.2  # Understocked
        elif 14 <= days_of_stock_30d <= 45:
            health_score = 1.0  # Optimal
        else:
            health_score = 0.7  # Acceptable
        
        # Overstock/Understock Risk
        overstock_risk = 1.0 if days_of_stock_30d > 90 else (0.5 if days_of_stock_30d > 60 else 0.0)
        understock_risk = 1.0 if days_of_stock_30d < 7 else (0.5 if days_of_stock_30d < 14 else 0.0)
        
        return {
            'inventory_quantity': float(inventory_qty),
            'inventory_value': inventory_value,
            'inventory_turnover_30d': turnover_30d,
            'inventory_turnover_90d': turnover_90d,
            'stockout_risk': stockout_risk,
            'days_of_stock_7d': days_of_stock_7d,
            'days_of_stock_30d': days_of_stock_30d,
            'days_of_stock_90d': days_of_stock_90d,
            'stock_velocity_ratio': stock_velocity_ratio,
            'inventory_trend': inventory_trend,
            'reorder_point': reorder_point,
            'safety_stock': safety_stock,
            'stock_health_score': health_score,
            'overstock_risk': overstock_risk,
            'understock_risk': understock_risk
        }
    
    # ==================== TIER 5: COMPETITIVE FEATURES (8) ====================
    
    def extract_competitive_features(self, product: Product, competitor_data: List[Dict]) -> Dict[str, float]:
        """
        Extracts competitive market features.
        
        Features (8):
        1. competitor_min_price - Lowest competitor price
        2. competitor_max_price - Highest competitor price
        3. competitor_avg_price - Average competitor price
        4. competitor_price_diff - Our price vs avg (%)
        5. competitor_count - Number of competitors
        6. market_position - Position in market (0=cheapest, 1=most expensive)
        7. price_rank - Rank among competitors (1=cheapest)
        8. price_gap_to_leader - Gap to cheapest competitor
        """
        if not competitor_data:
            return self._get_empty_competitive_features()
        
        prices = [c.get('price', 0) for c in competitor_data if c.get('price')]
        
        if not prices:
            return self._get_empty_competitive_features()
        
        competitor_min = min(prices)
        competitor_max = max(prices)
        competitor_avg = np.mean(prices)
        competitor_count = len(prices)
        
        current_price = float(product.price) if product.price else competitor_avg
        
        # Price difference
        price_diff = ((current_price - competitor_avg) / competitor_avg * 100) if competitor_avg > 0 else 0.0
        
        # Market Position (0 = cheapest, 1 = most expensive)
        if competitor_max > competitor_min:
            market_position = (current_price - competitor_min) / (competitor_max - competitor_min)
        else:
            market_position = 0.5
        
        # Price Rank (1 = cheapest)
        all_prices = sorted(prices + [current_price])
        price_rank = all_prices.index(current_price) + 1
        
        # Gap to leader (cheapest)
        price_gap_to_leader = current_price - competitor_min
        
        return {
            'competitor_min_price': competitor_min,
            'competitor_max_price': competitor_max,
            'competitor_avg_price': competitor_avg,
            'competitor_price_diff': price_diff,
            'competitor_count': float(competitor_count),
            'market_position': market_position,
            'price_rank': float(price_rank),
            'price_gap_to_leader': price_gap_to_leader
        }
    
    # ==================== TIER 6: ADVANCED FEATURES (23) ====================
    
    def extract_advanced_features(self, product: Product, custom_data: Optional[Dict] = None, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Extracts advanced features (seasonality, elasticity, etc.).
        
        🔍 [DEBUG] Method entry point for sales_30d error tracking
        
        Features (23):
        Seasonality:
        1. is_weekend - Is current day weekend (0/1)
        2. is_holiday - Is current day holiday (0/1)
        3. month_of_year - Month (1-12)
        4. day_of_week - Day of week (0-6)
        5. seasonality_score - Seasonal demand factor
        
        Price Elasticity:
        6. price_elasticity - Estimated price elasticity
        7. demand_sensitivity - Price sensitivity score
        8. optimal_price_range_min - Suggested min price
        9. optimal_price_range_max - Suggested max price
        
        Market Dynamics:
        10. market_volatility - Market price volatility
        11. competitive_intensity - Number of competitors / market size
        12. price_leadership - Are we price leader (0/1)
        
        Product Lifecycle:
        13. product_age_days - Days since product creation
        14. lifecycle_stage - Stage (0=new, 1=growth, 2=mature, 3=decline)
        15. growth_rate - Product growth rate
        
        Advanced Metrics:
        16. profit_margin_optimized - Optimized margin
        17. revenue_potential - Potential revenue increase
        18. conversion_likelihood - Likelihood of conversion
        19. customer_lifetime_value - Estimated CLV
        20. churn_risk - Risk of losing customers
        21. market_share_estimate - Estimated market share
        22. brand_strength - Brand strength score
        23. product_category_score - Category performance score
        """
        logger.debug(f"Extracting advanced features for product {product.id}")
        
        # ✅ FIX: end_date IMMER definiert (nicht nur in if-Block)
        # Use cutoff_date if provided (for training), otherwise use effective_now (for inference)
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except Exception:
                # Fallback: Use current datetime if _get_effective_now fails
                now = datetime.now()
        
        # Ensure now is always defined (for variable scope)
        end_date = now
        
        # NOTE: Seasonality features (day_of_week, is_weekend, month_of_year, seasonality_score, is_holiday)
        # are now extracted in extract_seasonality_features() and extract_holiday_features()
        # to avoid duplication. These are removed from advanced_features.
        
        # Price Elasticity (simplified estimation)
        # Based on price changes vs demand changes - STRICTLY BEFORE cutoff_date for training!
        # ✅ FIX: Use end_date (always defined)
        price_history = self._get_price_history(product.id, end_date - timedelta(days=90), end_date, strict_before=True)
        # ✅ BULLETPROOF: Initialize and protect sales_30d
        sales_30d = []
        try:
            sales_30d = self._get_sales_in_period(
                product.id, 
                end_date - timedelta(days=30), 
                end_date, 
                strict_before=True
            ) or []
        except Exception as e:
            logger.warning(f"Could not fetch sales_30d for product {product.id} in extract_advanced_features (line 654): {e}")
            sales_30d = []  # Explicit fallback
        
        elasticity = -1.5  # Default (elastic)
        if price_history and len(price_history) >= 2 and sales_30d:
            # Simplified elasticity calculation
            price_changes = [float(p.price) for p in price_history]
            if len(price_changes) >= 2:
                price_change_pct = (price_changes[-1] - price_changes[0]) / price_changes[0] if price_changes[0] > 0 else 0.0
                demand_change = len(sales_30d) / 30.0  # Simplified
                if abs(price_change_pct) > 0.01:
                    elasticity = (demand_change / price_change_pct) if price_change_pct != 0 else -1.5
        
        demand_sensitivity = abs(elasticity) / 3.0  # Normalize to 0-1
        demand_sensitivity = min(1.0, max(0.0, demand_sensitivity))
        
        # Optimal Price Range (simplified)
        current_price = float(product.price) if product.price else 0.0
        cost = float(product.cost) if product.cost else 0.0
        
        optimal_min = cost * 1.2  # 20% margin minimum
        optimal_max = current_price * 1.5  # 50% increase max
        
        # Market Dynamics
        market_volatility = 0.5  # Would need competitor price history
        competitive_intensity = 0.5  # Would need market size data
        price_leadership = 0.0  # Would need to compare with competitors
        
        # Product Lifecycle
        # Calculate product_age_days for lifecycle stage calculation
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        product_age_days = (now - product.created_at).days if product.created_at else 0
        
        # Lifecycle Stage (simplified)
        if product_age_days < 30:
            lifecycle_stage = 0.0  # New
        elif product_age_days < 180:
            lifecycle_stage = 1.0  # Growth
        elif product_age_days < 365:
            lifecycle_stage = 2.0  # Mature
        else:
            lifecycle_stage = 3.0  # Decline
        
        # Growth Rate (based on sales trend)
        # ✅ FIX: Use end_date (always defined) and ensure variables are always initialized
        # ✅ BULLETPROOF: Initialize and protect sales_7d and sales_30d
        sales_7d = []
        sales_30d = []
        try:
            sales_7d = self._get_sales_in_period(
                product.id, 
                end_date - timedelta(days=7), 
                end_date, 
                strict_before=True
            ) or []
        except Exception as e:
            logger.warning(f"Could not fetch sales_7d for product {product.id} in extract_advanced_features (line 708): {e}")
            sales_7d = []  # Explicit fallback
        
        try:
            sales_30d = self._get_sales_in_period(
                product.id, 
                end_date - timedelta(days=30), 
                end_date, 
                strict_before=True
            ) or []
        except Exception as e:
            logger.warning(f"Could not fetch sales_30d for product {product.id} in extract_advanced_features (line 708): {e}")
            sales_30d = []  # Explicit fallback
        
        velocity_7d = len(sales_7d) / 7.0 if sales_7d else 0.0
        velocity_30d = len(sales_30d) / 30.0 if sales_30d else 0.0
        
        growth_rate = ((velocity_7d - velocity_30d) / velocity_30d * 100) if velocity_30d > 0 else 0.0
        
        # Advanced Metrics (simplified)
        profit_margin_optimized = ((current_price - cost) / current_price * 100) if current_price > 0 else 0.0
        revenue_potential = velocity_30d * current_price * 30  # Monthly potential
        conversion_likelihood = 0.5  # Would need conversion data
        customer_lifetime_value = revenue_potential * 0.1  # Simplified
        churn_risk = 0.2  # Would need customer data
        market_share_estimate = 0.1  # Would need market data
        brand_strength = 0.7  # Would need brand data
        product_category_score = 0.6  # Would need category data
        
        return {
            # NOTE: Removed duplicate seasonality features (now in extract_seasonality_features):
            # - is_weekend, is_holiday, month_of_year, day_of_week, seasonality_score
            
            # NOTE: Removed price_elasticity (replaced by price_elasticity_proxy in Phase 2)
            # - price_elasticity
            
            # NOTE: Removed product_age_days (replaced by shopify_product_age_days in Phase 1)
            # - product_age_days
            
            # Price Elasticity (legacy - kept for backward compatibility, but price_elasticity_proxy is preferred)
            'price_elasticity': elasticity,
            'demand_sensitivity': demand_sensitivity,
            'optimal_price_range_min': optimal_min,
            'optimal_price_range_max': optimal_max,
            'market_volatility': market_volatility,
            'competitive_intensity': competitive_intensity,
            'price_leadership': price_leadership,
            'lifecycle_stage': lifecycle_stage,
            'growth_rate': growth_rate,
            'profit_margin_optimized': profit_margin_optimized,
            'revenue_potential': revenue_potential,
            'conversion_likelihood': conversion_likelihood,
            'customer_lifetime_value': customer_lifetime_value,
            'churn_risk': churn_risk,
            'market_share_estimate': market_share_estimate,
            'brand_strength': brand_strength,
            'product_category_score': product_category_score
        }
    
    # ==================== HELPER METHODS ====================
    
    def _get_sales_in_period(self, product_id: int, start_date: datetime, end_date: datetime, strict_before: bool = False) -> List[SalesHistory]:
        """
        Get sales records in time period
        
        Args:
            product_id: Product ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive if strict_before=False, exclusive if strict_before=True)
            strict_before: If True, use < instead of <= for end_date (prevents future data leakage)
        """
        query = self.db.query(SalesHistory).filter(
            SalesHistory.product_id == product_id,
            SalesHistory.sale_date >= start_date.date()
        )
        
        # Use < instead of <= if strict_before (for training to prevent leakage)
        if strict_before:
            query = query.filter(SalesHistory.sale_date < end_date.date())
        else:
            query = query.filter(SalesHistory.sale_date <= end_date.date())
        
        # Filter by shop_id if provided
        if self.shop_id:
            query = query.filter(SalesHistory.shop_id == self.shop_id)
        
        return query.all()
    
    def _get_price_history(self, product_id: int, start_date: datetime, end_date: datetime, strict_before: bool = False) -> List[PriceHistory]:
        """
        Get price history records in time period
        
        Args:
            product_id: Product ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive if strict_before=False, exclusive if strict_before=True)
            strict_before: If True, use < instead of <= for end_date (prevents future data leakage)
        """
        query = self.db.query(PriceHistory).filter(
            PriceHistory.product_id == product_id,
            PriceHistory.price_date >= start_date.date()
        )
        
        # Use < instead of <= if strict_before (for training to prevent leakage)
        if strict_before:
            query = query.filter(PriceHistory.price_date < end_date.date())
        else:
            query = query.filter(PriceHistory.price_date <= end_date.date())
        
        # Filter by shop_id if provided
        if self.shop_id:
            query = query.filter(PriceHistory.shop_id == self.shop_id)
        
        return query.order_by(PriceHistory.price_date.asc()).all()
    
    def _calculate_daily_sales(self, sales: List[SalesHistory], days: int) -> List[float]:
        """Calculate daily sales quantities"""
        if not sales:
            return [0.0] * days
        
        # Group by date
        sales_by_date = {}
        for sale in sales:
            date_key = sale.sale_date
            if date_key not in sales_by_date:
                sales_by_date[date_key] = 0
            sales_by_date[date_key] += sale.quantity_sold
        
        return list(sales_by_date.values())
    
    def _days_since_last_sale(self, product_id: int, now: datetime) -> int:
        """Calculate days since last sale"""
        query = self.db.query(SalesHistory).filter(
            SalesHistory.product_id == product_id
        )
        
        if self.shop_id:
            query = query.filter(SalesHistory.shop_id == self.shop_id)
        
        last_sale = query.order_by(SalesHistory.sale_date.desc()).first()
        
        if last_sale:
            delta = now.date() - last_sale.sale_date
            return delta.days
        return 999  # No sales found
    
    def _calculate_peak_sales_day(self, sales: List[SalesHistory]) -> int:
        """Calculate day of week with most sales (0=Monday, 6=Sunday)"""
        if not sales:
            return 0
        
        day_counts = {i: 0 for i in range(7)}
        for sale in sales:
            day = sale.sale_date.weekday()
            day_counts[day] += sale.quantity_sold
        
        return max(day_counts, key=day_counts.get)
    
    def _calculate_weekend_ratio(self, sales: List[SalesHistory]) -> float:
        """Calculate weekend vs weekday sales ratio"""
        if not sales:
            return 0.0
        
        weekend_sales = 0
        weekday_sales = 0
        
        for sale in sales:
            if sale.sale_date.weekday() >= 5:  # Saturday or Sunday
                weekend_sales += sale.quantity_sold
            else:
                weekday_sales += sale.quantity_sold
        
        total = weekend_sales + weekday_sales
        return weekend_sales / total if total > 0 else 0.0
    
    def _get_effective_now(self, product_id: int) -> datetime:
        """
        Get effective 'now' date for calculations.
        For demo mode (shop_id=999), uses max date from sales_history.
        For live mode, uses datetime.now().
        """
        if self.shop_id == 999:  # Demo mode
            # Get max date from sales_history for this product
            query = self.db.query(SalesHistory).filter(
                SalesHistory.product_id == product_id,
                SalesHistory.shop_id == 999
            )
            last_sale = query.order_by(SalesHistory.sale_date.desc()).first()
            if last_sale:
                # Return as datetime (midnight)
                return datetime.combine(last_sale.sale_date, datetime.min.time())
        
        # Live mode or no sales data: use real now
        return datetime.now()
    
    def _get_empty_competitive_features(self) -> Dict[str, float]:
        """Return empty competitive features when no data available"""
        return {
            'competitor_min_price': 0.0,
            'competitor_max_price': 0.0,
            'competitor_avg_price': 0.0,
            'competitor_price_diff': 0.0,
            'competitor_count': 0.0,
            'market_position': 0.5,
            'price_rank': 0.0,
            'price_gap_to_leader': 0.0
        }
    
    # ==================== PHASE 1: QUICK WINS (15 Features) ====================
    
    def extract_seasonality_features(self, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Extract time-based seasonality features.
        
        Features (6):
        - day_of_week: 0=Monday, 6=Sunday
        - week_of_month: 1-5
        - month_of_year: 1-12
        - is_weekend: 0/1
        - seasonality_score: 0.5-2.0 (seasonal multiplier)
        - quarter: 1-4
        
        Args:
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            dict: Seasonality features
        """
        if cutoff_date:
            now = cutoff_date
        else:
            now = datetime.now()
        
        # Calculate quarter
        quarter = (now.month - 1) // 3 + 1
        
        # Calculate seasonality score
        seasonality_score = self._calculate_seasonality_score(now)
        
        return {
            'day_of_week': float(now.weekday()),  # 0=Monday, 6=Sunday
            'week_of_month': float((now.day - 1) // 7 + 1),  # 1-5
            'month_of_year': float(now.month),  # 1-12
            'is_weekend': 1.0 if now.weekday() >= 5 else 0.0,
            'seasonality_score': seasonality_score,
            'quarter': float(quarter),  # 1-4
        }
    
    def _calculate_seasonality_score(self, date: datetime) -> float:
        """
        Calculate seasonality multiplier based on month.
        
        E-commerce typical seasonality:
        - November: 1.5 (Black Friday)
        - December: 1.8 (Christmas)
        - January: 0.8 (Post-holiday slump)
        - February: 0.7 (Low season)
        - Q2-Q3: 1.0-1.1 (Normal)
        
        Args:
            date: Date to calculate seasonality for
        
        Returns:
            float: Seasonality multiplier (0.5-2.0)
        """
        seasonal_months = {
            1: 0.8,   # January (post-holiday)
            2: 0.7,   # February (low season)
            3: 0.9,   # March
            4: 1.0,   # April
            5: 1.0,   # May
            6: 1.1,   # June (summer start)
            7: 1.1,   # July
            8: 1.0,   # August
            9: 1.0,   # September (back to school)
            10: 1.2,  # October (fall shopping)
            11: 1.5,  # November (Black Friday)
            12: 1.8,  # December (Christmas)
        }
        return seasonal_months.get(date.month, 1.0)
    
    def extract_review_proxy_features(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Transform review features to Shopify behavioral proxies.
        
        Since Shopify doesn't have native review fields, we use:
        - Order count → Social proof (reviews = popularity)
        - Return rate → Satisfaction (low returns = good reviews)
        - Repeat purchases → Quality signal
        
        Features (3):
        - order_count_proxy: Proxy for review_count
        - satisfaction_proxy: Proxy for review_score_avg
        - customer_satisfaction_proxy: Composite proxy for review_sentiment
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            dict: Review proxy features
        """
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except:
                now = datetime.now()
        
        # Get required data
        sales_30d = self._get_sales_in_period(
            product.id, 
            now - timedelta(days=30), 
            now, 
            strict_before=True if cutoff_date else False
        ) or []
        
        sales_count_30d = len(sales_30d)
        return_rate = self._calculate_return_rate(product.id, cutoff_date=cutoff_date)
        repeat_rate = self._calculate_repeat_purchase_rate(product.id, cutoff_date=cutoff_date)
        
        # Calculate AOV
        if sales_30d:
            total_revenue = sum(float(s.revenue) for s in sales_30d)
            aov_30d = total_revenue / sales_count_30d if sales_count_30d > 0 else 0.0
        else:
            aov_30d = 0.0
        
        # Price ratio (AOV / price indicates premium perception)
        current_price = float(product.price) if product.price else 0.0
        price_ratio = (aov_30d / current_price) if current_price > 0 else 0.5
        price_ratio = min(1.0, max(0.0, price_ratio))  # Cap at 0-1
        
        return {
            # Review count → Order count (social proof)
            'order_count_proxy': float(sales_count_30d),
            
            # Review score avg → Satisfaction (1 - return rate)
            'satisfaction_proxy': max(0.0, min(1.0, 1.0 - return_rate)),
            
            # Review sentiment → Customer satisfaction composite
            'customer_satisfaction_proxy': (
                0.4 * max(0.0, min(1.0, 1.0 - return_rate)) +  # Low returns = happy
                0.35 * min(1.0, repeat_rate) +                  # Repeat purchases = satisfied
                0.25 * price_ratio                               # Premium AOV = quality perception
            ),
        }
    
    def _calculate_return_rate(self, product_id: int, cutoff_date: Optional[datetime] = None) -> float:
        """
        Calculate product return rate from refunds/cancellations.
        
        Return rate = refunded_orders / total_orders
        
        Args:
            product_id: Product ID
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            float: Return rate (0.0-1.0)
        """
        from datetime import datetime, timedelta
        
        if cutoff_date:
            now = cutoff_date
        else:
            now = datetime.now()
        
        cutoff = now - timedelta(days=90)
        
        # Get total sales count (proxy for orders)
        total_sales = self._get_sales_in_period(
            product_id, 
            cutoff, 
            now, 
            strict_before=True if cutoff_date else False
        ) or []
        
        total_orders = len(total_sales)
        
        if total_orders == 0:
            return 0.05  # Default 5% return rate if no data
        
        # TODO: Implement proper refund tracking
        # For now, use conservative estimate
        # If you have refund/return tracking, replace this:
        # refunded_orders = self.db.query(func.count(Refund.id)).filter(
        #     Refund.product_id == product_id,
        #     Refund.created_at >= cutoff
        # ).scalar() or 0
        
        # Placeholder: Use default low return rate
        refunded_orders = int(total_orders * 0.05)  # Assume 5% return rate
        
        return_rate = refunded_orders / total_orders if total_orders > 0 else 0.05
        
        return min(1.0, float(return_rate))
    
    def _calculate_repeat_purchase_rate(self, product_id: int, cutoff_date: Optional[datetime] = None) -> float:
        """
        Calculate repeat purchase rate for product.
        
        Repeat rate = customers_with_2+_purchases / total_customers
        
        Args:
            product_id: Product ID
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            float: Repeat purchase rate (0.0-1.0)
        """
        from datetime import datetime, timedelta
        
        if cutoff_date:
            now = cutoff_date
        else:
            now = datetime.now()
        
        cutoff = now - timedelta(days=90)
        
        # Get sales with order_id (for customer tracking)
        sales = self._get_sales_in_period(
            product_id, 
            cutoff, 
            now, 
            strict_before=True if cutoff_date else False
        ) or []
        
        if not sales:
            return 0.0
        
        # Group by order_id (proxy for customer_id if not available)
        # If order_id is None (CSV data), use sale_date as proxy
        customer_purchases = {}
        for sale in sales:
            customer_key = sale.order_id if sale.order_id else f"customer_{sale.sale_date}"
            if customer_key not in customer_purchases:
                customer_purchases[customer_key] = 0
            customer_purchases[customer_key] += 1
        
        if not customer_purchases:
            return 0.0
        
        total_customers = len(customer_purchases)
        repeat_customers = sum(1 for count in customer_purchases.values() if count > 1)
        
        return float(repeat_customers / total_customers) if total_customers > 0 else 0.0
    
    def extract_shopify_features(self, product: Product) -> Dict[str, float]:
        """
        Extract Shopify-native features not available in Kaggle datasets.
        
        Features (3):
        - shopify_product_age_days: Days since product creation
        - shopify_update_frequency_days: Days since last update
        - shopify_listing_quality_score: Composite listing quality (0.0-1.0)
        
        Args:
            product: Product model instance
        
        Returns:
            dict: Shopify-specific features
        """
        now = datetime.now()
        
        # Product age
        created_at = product.created_at or now
        updated_at = product.updated_at or now
        
        # Handle timezone-aware vs naive datetime
        if hasattr(created_at, 'tzinfo') and created_at.tzinfo is not None:
            created_at = created_at.replace(tzinfo=None)
        if hasattr(updated_at, 'tzinfo') and updated_at.tzinfo is not None:
            updated_at = updated_at.replace(tzinfo=None)
        if hasattr(now, 'tzinfo') and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        
        product_age_days = (now - created_at).days
        update_frequency_days = (now - updated_at).days
        
        # Extract from meta_data JSON if available
        meta = {}
        if hasattr(product, 'meta_data') and product.meta_data:
            if isinstance(product.meta_data, str):
                import json
                try:
                    meta = json.loads(product.meta_data)
                except:
                    meta = {}
            elif isinstance(product.meta_data, dict):
                meta = product.meta_data
        
        # Calculate listing quality score
        listing_quality = self._calculate_listing_quality(product, meta)
        
        return {
            'shopify_product_age_days': float(product_age_days),
            'shopify_update_frequency_days': float(update_frequency_days),
            'shopify_listing_quality_score': listing_quality,
        }
    
    def _calculate_listing_quality(self, product: Product, meta: dict) -> float:
        """
        Calculate listing quality composite score.
        
        Weighted factors:
        - Images: 30% (5+ images = 1.0)
        - Description: 25% (500+ chars = 1.0)
        - Has description: 20% (boolean)
        - Tags: 15% (5+ tags = 1.0)
        - Variants: 10% (multiple variants = 1.0)
        
        Args:
            product: Product object
            meta: Product metadata dict
        
        Returns:
            float: Quality score (0.0-1.0)
        """
        # Extract listing attributes
        image_count = meta.get('image_count', 1)
        description = getattr(product, 'description', '') or ''
        description_length = len(description)
        has_description = 1.0 if description_length > 0 else 0.0
        tags = meta.get('tags', [])
        tags_count = len(tags) if isinstance(tags, list) else 0
        variants_count = meta.get('variants_count', 1)
        
        # Calculate weighted score
        quality_score = (
            0.30 * min(1.0, image_count / 5.0) +          # 5+ images = max
            0.25 * min(1.0, description_length / 500.0) + # 500+ chars = max
            0.20 * has_description +                       # Has any description
            0.15 * min(1.0, tags_count / 5.0) +            # 5+ tags = max
            0.10 * (1.0 if variants_count > 1 else 0.0)   # Has variants
        )
        
        return float(quality_score)
    
    def extract_quality_proxy_features(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Quality composite proxy from behavioral data.
        
        Since we don't have explicit quality scores, we infer quality from:
        - Low return rate (30%)
        - High repeat purchases (25%)
        - Premium AOV relative to price (20%)
        - High sales velocity percentile (15%)
        - High inventory turnover (10%)
        
        Features (1):
        - quality_composite_proxy: Weighted quality score (0.0-1.0)
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            dict: Quality proxy features
        """
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except:
                now = datetime.now()
        
        # Get required metrics
        return_rate = self._calculate_return_rate(product.id, cutoff_date=cutoff_date)
        repeat_rate = self._calculate_repeat_purchase_rate(product.id, cutoff_date=cutoff_date)
        
        # Get AOV
        sales_30d = self._get_sales_in_period(
            product.id, 
            now - timedelta(days=30), 
            now, 
            strict_before=True if cutoff_date else False
        ) or []
        
        if sales_30d:
            total_revenue = sum(float(s.revenue) for s in sales_30d)
            aov_30d = total_revenue / len(sales_30d)
        else:
            aov_30d = 0.0
        
        current_price = float(product.price) if product.price else 0.0
        price_ratio = (aov_30d / current_price) if current_price > 0 else 0.5
        price_ratio = min(1.0, max(0.0, price_ratio))
        
        # Get velocity percentile
        velocity_pct = self._get_sales_velocity_percentile(product.id, cutoff_date=cutoff_date)
        
        # Get inventory turnover
        turnover_30d = self._get_inventory_turnover(product.id, days=30, cutoff_date=cutoff_date)
        
        # Turnover score (normalize to 0-1, assuming 12 turnovers/year = excellent)
        turnover_score = min(1.0, turnover_30d / 12.0)
        
        # Calculate composite quality score
        quality_score = (
            0.30 * max(0.0, 1.0 - return_rate) +  # Low returns = quality
            0.25 * min(1.0, repeat_rate) +         # Loyalty = quality
            0.20 * price_ratio +                    # Premium = quality
            0.15 * velocity_pct +                   # Demand = quality
            0.10 * turnover_score                   # Fast mover = quality
        )
        
        return {
            'quality_composite_proxy': float(quality_score),
        }
    
    def _get_sales_velocity_percentile(self, product_id: int, cutoff_date: Optional[datetime] = None) -> float:
        """
        Get product's sales velocity percentile compared to all products.
        
        Args:
            product_id: Product ID
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            float: Percentile (0.0-1.0)
        """
        from datetime import datetime, timedelta
        
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product_id)
            except:
                now = datetime.now()
        
        cutoff = now - timedelta(days=30)
        
        # Get this product's velocity
        product_sales = self._get_sales_in_period(
            product_id, 
            cutoff, 
            now, 
            strict_before=True if cutoff_date else False
        ) or []
        
        product_velocity = len(product_sales) / 30.0
        
        # Get all products' velocities (sample-based for performance)
        # For production, you might want to cache this or calculate periodically
        try:
            all_products = self.db.query(Product.id).limit(1000).all()  # Sample 1000 products
            velocities = []
            
            for prod in all_products:
                if prod.id == product_id:
                    continue
                sales = self._get_sales_in_period(
                    prod.id, 
                    cutoff, 
                    now, 
                    strict_before=True if cutoff_date else False
                ) or []
                velocity = len(sales) / 30.0
                velocities.append(velocity)
            
            if not velocities:
                return 0.5  # Default to median
            
            velocities_sorted = sorted(velocities)
            
            # Find percentile
            rank = sum(1 for v in velocities_sorted if v <= product_velocity)
            percentile = rank / len(velocities_sorted)
            
            return float(percentile)
        except Exception as e:
            logger.warning(f"Could not calculate velocity percentile: {e}")
            return 0.5  # Default to median
    
    def _get_inventory_turnover(self, product_id: int, days: int = 30, cutoff_date: Optional[datetime] = None) -> float:
        """
        Calculate inventory turnover rate.
        
        Turnover = units_sold / avg_inventory
        
        Args:
            product_id: Product ID
            days: Time period
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            float: Turnover rate (annualized)
        """
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return 0.0
        
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product_id)
            except:
                now = datetime.now()
        
        sales = self._get_sales_in_period(
            product_id, 
            now - timedelta(days=days), 
            now, 
            strict_before=True if cutoff_date else False
        ) or []
        
        units_sold = sum(s.quantity_sold for s in sales)
        avg_inventory = product.inventory_quantity or 1.0  # Avoid division by zero
        
        # Calculate turnover (annualized)
        turnover = (units_sold / avg_inventory) * (365 / days) if avg_inventory > 0 else 0.0
        
        return float(turnover)
    
    def extract_market_store_features(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Market features scoped to store (not external market).
        
        Transform external market features to store-internal metrics:
        - market_share_estimate → category_share_in_store
        - market_growth_rate → category_growth_rate_in_store
        
        Features (2):
        - category_share_in_store: Product sales / category sales
        - category_growth_rate_in_store: Category growth trend
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            dict: Market store-scoped features
        """
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except:
                now = datetime.now()
        
        # Get category (adjust field name based on your schema)
        # Try multiple possible field names
        category = (
            getattr(product, 'category', None) or 
            getattr(product, 'product_type', None) or 
            'unknown'
        )
        
        if category == 'unknown':
            return {
                'category_share_in_store': 0.0,
                'category_growth_rate_in_store': 0.0,
            }
        
        # Get sales data
        product_sales_30d = self._get_product_sales_revenue(product.id, days=30, cutoff_date=cutoff_date)
        category_sales_30d = self._get_category_sales(category, days=30, cutoff_date=cutoff_date)
        category_sales_90d = self._get_category_sales(category, days=90, cutoff_date=cutoff_date)
        
        # Calculate category share
        category_share = (
            product_sales_30d / category_sales_30d
            if category_sales_30d > 0 else 0.0
        )
        
        # Calculate category growth rate
        # Growth = (recent_sales - old_sales) / old_sales
        category_growth = (
            (category_sales_30d - category_sales_90d) / category_sales_90d
            if category_sales_90d > 0 else 0.0
        )
        
        return {
            'category_share_in_store': float(category_share),
            'category_growth_rate_in_store': float(category_growth),
        }
    
    def _get_product_sales_revenue(self, product_id: int, days: int, cutoff_date: Optional[datetime] = None) -> float:
        """Get product revenue for time period"""
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product_id)
            except:
                now = datetime.now()
        
        cutoff = now - timedelta(days=days)
        
        sales = self._get_sales_in_period(
            product_id, 
            cutoff, 
            now, 
            strict_before=True if cutoff_date else False
        ) or []
        
        revenue = sum(float(s.revenue) for s in sales)
        
        return float(revenue)
    
    def _get_category_sales(self, category: str, days: int, cutoff_date: Optional[datetime] = None) -> float:
        """
        Get total category sales revenue for time period.
        
        Args:
            category: Product category/type
            days: Time period in days
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            float: Total category revenue
        """
        if not category or category == 'unknown':
            return 0.0
        
        if cutoff_date:
            now = cutoff_date
        else:
            now = datetime.now()
        
        cutoff = now - timedelta(days=days)
        
        # Try to get category from Product model
        # Adjust field name based on your schema
        try:
            # Option 1: product.category
            products = self.db.query(Product.id).filter(
                Product.category == category
            ).all()
            
            if not products:
                # Option 2: product.product_type
                products = self.db.query(Product.id).filter(
                    Product.product_type == category
                ).all()
        except:
            products = []
        
        if not products:
            return 0.0
        
        product_ids = [p.id for p in products]
        
        # Get sales for all products in category
        sales = self.db.query(SalesHistory).filter(
            SalesHistory.product_id.in_(product_ids),
            SalesHistory.sale_date >= cutoff.date(),
            SalesHistory.sale_date <= now.date() if not cutoff_date else SalesHistory.sale_date < now.date()
        ).all()
        
        total_revenue = sum(float(s.revenue) for s in sales)
        
        return float(total_revenue)
    
    # ==================== PHASE 2: CORE TRANSFORMATIONS (10 Features) ====================
    
    def extract_brand_features(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Brand features from pricing and behavioral data.
        
        Transform external brand metrics to Shopify data:
        - brand_strength → brand_price_premium_index
        - brand_loyalty → brand_repeat_purchase_rate
        
        Features (2):
        - brand_price_premium_index: Brand avg price / category avg price
        - brand_repeat_purchase_rate: Brand customer repeat rate
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            dict: Brand features
        """
        # Get brand (Shopify: vendor = brand)
        brand = getattr(product, 'vendor', None) or 'unknown'
        category = (
            getattr(product, 'category', None) or 
            getattr(product, 'product_type', None) or 
            'unknown'
        )
        
        if brand == 'unknown':
            return {
                'brand_price_premium_index': 1.0,
                'brand_repeat_purchase_rate': 0.0,
            }
        
        # Calculate brand price premium
        brand_avg_price = self._get_brand_avg_price(brand)
        category_avg_price = self._get_category_avg_price(category)
        
        price_premium = (
            brand_avg_price / category_avg_price
            if category_avg_price > 0 else 1.0
        )
        
        # Calculate brand loyalty
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except:
                now = datetime.now()
        
        brand_customers_total = self._get_brand_customer_count(brand, cutoff_date=cutoff_date)
        brand_customers_repeat = self._get_brand_repeat_customer_count(brand, cutoff_date=cutoff_date)
        
        repeat_rate = (
            brand_customers_repeat / brand_customers_total
            if brand_customers_total > 0 else 0.0
        )
        
        return {
            'brand_price_premium_index': float(price_premium),
            'brand_repeat_purchase_rate': float(repeat_rate),
        }
    
    def _get_brand_avg_price(self, brand: str) -> float:
        """Get average price for brand"""
        avg_price = self.db.query(func.avg(Product.price)).filter(
            Product.vendor == brand
        ).scalar()
        
        return float(avg_price or 0.0)
    
    def _get_category_avg_price(self, category: str) -> float:
        """Get average price for category"""
        # Try category field first
        avg_price = self.db.query(func.avg(Product.price)).filter(
            Product.category == category
        ).scalar()
        
        if avg_price is None:
            # Try product_type field
            avg_price = self.db.query(func.avg(Product.price)).filter(
                Product.product_type == category
            ).scalar()
        
        return float(avg_price or 0.0)
    
    def _get_brand_customer_count(self, brand: str, cutoff_date: Optional[datetime] = None) -> int:
        """Get total unique customers who bought brand"""
        from datetime import datetime, timedelta
        
        if cutoff_date:
            now = cutoff_date
        else:
            now = datetime.now()
        
        cutoff = now - timedelta(days=180)
        
        # Get products from brand
        brand_products = self.db.query(Product.id).filter(
            Product.vendor == brand
        ).all()
        
        if not brand_products:
            return 0
        
        product_ids = [p.id for p in brand_products]
        
        # Count unique customers (using order_id as proxy)
        sales = self.db.query(SalesHistory.order_id).filter(
            SalesHistory.product_id.in_(product_ids),
            SalesHistory.sale_date >= cutoff.date(),
            SalesHistory.order_id.isnot(None)
        ).distinct().all()
        
        return len(sales)
    
    def _get_brand_repeat_customer_count(self, brand: str, cutoff_date: Optional[datetime] = None) -> int:
        """Get customers who bought brand 2+ times"""
        from datetime import datetime, timedelta
        
        if cutoff_date:
            now = cutoff_date
        else:
            now = datetime.now()
        
        cutoff = now - timedelta(days=180)
        
        # Get products from brand
        brand_products = self.db.query(Product.id).filter(
            Product.vendor == brand
        ).all()
        
        if not brand_products:
            return 0
        
        product_ids = [p.id for p in brand_products]
        
        # Get customer purchase counts
        customer_counts = self.db.query(
            SalesHistory.order_id,
            func.count(SalesHistory.id).label('purchase_count')
        ).filter(
            SalesHistory.product_id.in_(product_ids),
            SalesHistory.sale_date >= cutoff.date(),
            SalesHistory.order_id.isnot(None)
        ).group_by(SalesHistory.order_id).all()
        
        repeat_customers = sum(1 for _, count in customer_counts if count > 1)
        
        return repeat_customers
    
    def extract_price_elasticity_proxy(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Approximate price elasticity from historical data.
        
        Elasticity = (% change in quantity) / (% change in price)
        
        Calculated from price history and sales changes.
        
        Features (1):
        - price_elasticity_proxy: Estimated elasticity (-5.0 to 0.0, typically -1.5)
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            dict: Price elasticity proxy
        """
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except:
                now = datetime.now()
        
        # Get price changes and corresponding sales changes
        price_changes = self._get_price_changes_with_sales(product.id, days=90, cutoff_date=cutoff_date)
        
        if len(price_changes) < 2:
            # Default: -1.5 (typical e-commerce elasticity)
            return {'price_elasticity_proxy': -1.5}
        
        # Calculate elasticity from price/sales changes
        elasticities = []
        
        for i in range(1, len(price_changes)):
            prev = price_changes[i-1]
            curr = price_changes[i]
            
            # Calculate % changes
            price_change_pct = (
                (curr['price'] - prev['price']) / prev['price']
                if prev['price'] > 0 else 0.0
            )
            
            sales_change_pct = (
                (curr['sales'] - prev['sales']) / prev['sales']
                if prev['sales'] > 0 else 0.0
            )
            
            # Calculate elasticity (if significant price change)
            if abs(price_change_pct) > 0.01:  # >1% price change
                elasticity = sales_change_pct / price_change_pct
                # Cap elasticity at reasonable bounds
                elasticity = max(-5.0, min(0.0, elasticity))
                elasticities.append(elasticity)
        
        # Average elasticities
        avg_elasticity = float(np.mean(elasticities)) if elasticities else -1.5
        
        return {
            'price_elasticity_proxy': avg_elasticity,
        }
    
    def _get_price_changes_with_sales(self, product_id: int, days: int, cutoff_date: Optional[datetime] = None) -> List[Dict]:
        """
        Get price changes and corresponding sales for product.
        
        Returns list of dicts: [{'date': ..., 'price': ..., 'sales': ...}, ...]
        """
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product_id)
            except:
                now = datetime.now()
        
        cutoff = now - timedelta(days=days)
        
        # Get price history
        price_history = self._get_price_history(
            product_id, 
            cutoff, 
            now, 
            strict_before=True if cutoff_date else False
        )
        
        if not price_history:
            return []
        
        # For each price point, calculate sales velocity
        result = []
        for i, ph in enumerate(price_history):
            # Get sales 7 days after price change
            sales_start = datetime.combine(ph.price_date, datetime.min.time())
            sales_end = sales_start + timedelta(days=7)
            
            if cutoff_date and sales_end > cutoff_date:
                sales_end = cutoff_date
            
            sales = self._get_sales_in_period(
                product_id, 
                sales_start, 
                sales_end, 
                strict_before=True if cutoff_date else False
            ) or []
            
            sales_count = len(sales)
            
            result.append({
                'date': ph.price_date,
                'price': float(ph.price),
                'sales': sales_count / 7.0,  # Daily average
            })
        
        return result
    
    def extract_category_features(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Category-level features for market context.
        
        Features (4):
        - category_momentum_score: Short-term category growth
        - category_trend_in_store: Long-term category trend
        - category_popularity: Category share of total sales
        - category_lifecycle_stage: Estimated lifecycle (0=intro, 0.5=growth, 1.0=mature, 1.5=decline)
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            dict: Category features
        """
        category = (
            getattr(product, 'category', None) or 
            getattr(product, 'product_type', None) or 
            'unknown'
        )
        
        if category == 'unknown':
            return {
                'category_momentum_score': 0.0,
                'category_trend_in_store': 0.0,
                'category_popularity': 0.0,
                'category_lifecycle_stage': 1.0,
            }
        
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except:
                now = datetime.now()
        
        # Get category sales over time
        cat_sales_7d = self._get_category_sales(category, days=7, cutoff_date=cutoff_date)
        cat_sales_30d = self._get_category_sales(category, days=30, cutoff_date=cutoff_date)
        cat_sales_90d = self._get_category_sales(category, days=90, cutoff_date=cutoff_date)
        total_sales_30d = self._get_total_sales(days=30, cutoff_date=cutoff_date)
        
        # Calculate momentum (short-term acceleration)
        momentum = (
            (cat_sales_7d - cat_sales_30d) / cat_sales_30d
            if cat_sales_30d > 0 else 0.0
        )
        
        # Calculate trend (long-term growth)
        trend = (
            (cat_sales_30d - cat_sales_90d) / cat_sales_90d
            if cat_sales_90d > 0 else 0.0
        )
        
        # Calculate popularity (share of store sales)
        popularity = (
            cat_sales_30d / total_sales_30d
            if total_sales_30d > 0 else 0.0
        )
        
        # Estimate lifecycle stage
        lifecycle = self._calculate_lifecycle_stage(cat_sales_7d, cat_sales_30d, cat_sales_90d)
        
        return {
            'category_momentum_score': float(momentum),
            'category_trend_in_store': float(trend),
            'category_popularity': float(popularity),
            'category_lifecycle_stage': float(lifecycle),
        }
    
    def _get_total_sales(self, days: int, cutoff_date: Optional[datetime] = None) -> float:
        """Get total store sales revenue for period"""
        if cutoff_date:
            now = cutoff_date
        else:
            now = datetime.now()
        
        cutoff = now - timedelta(days=days)
        
        total = self.db.query(func.sum(SalesHistory.revenue)).filter(
            SalesHistory.sale_date >= cutoff.date(),
            SalesHistory.sale_date <= now.date() if not cutoff_date else SalesHistory.sale_date < now.date()
        ).scalar()
        
        return float(total or 0.0)
    
    def _calculate_lifecycle_stage(self, sales_7d: float, sales_30d: float, sales_90d: float) -> float:
        """
        Estimate product lifecycle stage from sales trend.
        
        Stages:
        - 0.0-0.3: Introduction (new category, low sales)
        - 0.3-0.7: Growth (accelerating sales)
        - 0.7-1.3: Maturity (stable sales)
        - 1.3-2.0: Decline (declining sales)
        
        Args:
            sales_7d: Recent 7-day sales
            sales_30d: 30-day sales
            sales_90d: 90-day sales
        
        Returns:
            float: Lifecycle stage (0.0-2.0)
        """
        if sales_30d == 0 or sales_90d == 0:
            return 0.0  # Introduction
        
        # Calculate growth rates
        growth_rate_30d = (sales_30d - sales_90d) / sales_90d
        growth_rate_7d = (sales_7d * 4.3 - sales_30d) / sales_30d if sales_30d > 0 else 0.0  # Annualize
        
        # Classify lifecycle stage
        if growth_rate_30d > 0.2 and growth_rate_7d > 0.1:
            return 0.5  # Growth stage (strong growth)
        elif growth_rate_30d > 0.0 and growth_rate_7d > 0.0:
            return 0.7  # Early maturity (moderate growth)
        elif -0.1 < growth_rate_30d < 0.2 and -0.1 < growth_rate_7d < 0.1:
            return 1.0  # Maturity (stable)
        elif growth_rate_30d < -0.1 or growth_rate_7d < -0.1:
            return 1.5  # Decline
        else:
            return 1.0  # Default to maturity
    
    def extract_inventory_transformations(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Inventory transformation features.
        
        Features (2):
        - slow_moving_stock_days: Days inventory hasn't moved (for slow movers)
        - inventory_change_30d: Inventory delta over 30 days
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            dict: Inventory transformation features
        """
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except:
                now = datetime.now()
        
        # Get days since last sale
        days_since_last_sale = self._days_since_last_sale(product.id, now)
        
        # Get sales velocity
        sales_7d = self._get_sales_in_period(
            product.id, 
            now - timedelta(days=7), 
            now, 
            strict_before=True if cutoff_date else False
        ) or []
        
        velocity_7d = len(sales_7d) / 7.0
        
        # Slow moving threshold (if velocity < 1 unit/day, it's slow)
        slow_moving_threshold = 1.0
        
        slow_moving_days = (
            float(days_since_last_sale)
            if velocity_7d < slow_moving_threshold
            else 0.0
        )
        
        # Inventory change
        inventory_now = product.inventory_quantity or 0
        inventory_30d_ago = self._get_historical_inventory(product.id, days_ago=30, cutoff_date=cutoff_date)
        
        inventory_change = inventory_now - inventory_30d_ago
        
        return {
            'slow_moving_stock_days': slow_moving_days,
            'inventory_change_30d': float(inventory_change),
        }
    
    def _get_historical_inventory(self, product_id: int, days_ago: int, cutoff_date: Optional[datetime] = None) -> int:
        """
        Get inventory level X days ago.
        
        If no inventory history tracking, estimate from:
        current_inventory + sales_since_then
        """
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product_id)
            except:
                now = datetime.now()
        
        target_date = now - timedelta(days=days_ago)
        
        # Option 2: Estimate from current inventory + recent sales
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return 0
        
        current_inventory = product.inventory_quantity or 0
        
        # Get sales since target_date
        sales_since = self._get_sales_in_period(
            product_id, 
            target_date, 
            now, 
            strict_before=True if cutoff_date else False
        ) or []
        
        sales_count = sum(s.quantity_sold for s in sales_since)
        
        # Estimate: past inventory = current + sales_since
        estimated_inventory = current_inventory + sales_count
        
        return int(estimated_inventory)
    
    def extract_demand_volatility_features(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Demand volatility feature.
        
        Features (1):
        - demand_volatility: Coefficient of variation in sales (std / mean)
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            dict: Demand volatility features
        """
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except:
                now = datetime.now()
        
        # Get daily sales for past 30 days
        daily_sales = []
        
        for i in range(30):
            day_start = now - timedelta(days=i+1)
            day_end = now - timedelta(days=i)
            
            if cutoff_date and day_end > cutoff_date:
                day_end = cutoff_date
            
            sales = self._get_sales_in_period(
                product.id, 
                day_start, 
                day_end, 
                strict_before=True if cutoff_date else False
            ) or []
            
            sales_count = len(sales)
            daily_sales.append(sales_count)
        
        if not daily_sales or sum(daily_sales) == 0:
            return {'demand_volatility': 0.0}
        
        # Calculate coefficient of variation
        mean_sales = np.mean(daily_sales)
        std_sales = np.std(daily_sales)
        
        cv = std_sales / mean_sales if mean_sales > 0 else 0.0
        
        return {
            'demand_volatility': float(cv),
        }
    
    # ==================== PHASE 3: ADVANCED FEATURES (5 Features) ====================
    
    def extract_holiday_features(self, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Holiday calendar features.
        
        Features (1):
        - is_holiday: Whether today is a major holiday (0/1)
        
        Args:
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            dict: Holiday features
        """
        if cutoff_date:
            now = cutoff_date
        else:
            now = datetime.now()
        
        # Define major e-commerce holidays (US/EU)
        holidays = [
            # Format: (month, day)
            (1, 1),    # New Year
            (2, 14),   # Valentine's Day
            (3, 17),   # St. Patrick's Day
            (5, 12),   # Mother's Day (approximate)
            (6, 21),   # Father's Day (approximate)
            (7, 4),    # Independence Day (US)
            (10, 31),  # Halloween
            (11, 27),  # Black Friday (approximate - 4th Fri of Nov)
            (11, 30),  # Cyber Monday (approximate)
            (12, 24),  # Christmas Eve
            (12, 25),  # Christmas
            (12, 26),  # Boxing Day
            (12, 31),  # New Year's Eve
        ]
        
        # Check if today is holiday
        is_holiday = 1.0 if (now.month, now.day) in holidays else 0.0
        
        # Check Black Friday (4th Friday of November)
        if now.month == 11:
            # Calculate 4th Friday
            first_day = datetime(now.year, 11, 1)
            first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
            fourth_friday = first_friday + timedelta(days=21)
            if now.date() == fourth_friday.date():
                is_holiday = 1.0
        
        # Check Cyber Monday (Monday after Black Friday)
        if now.month == 11:
            first_day = datetime(now.year, 11, 1)
            first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
            fourth_friday = first_friday + timedelta(days=21)
            cyber_monday = fourth_friday + timedelta(days=3)
            if now.date() == cyber_monday.date():
                is_holiday = 1.0
        
        return {
            'is_holiday': is_holiday,
        }
    
    def extract_churn_features(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Customer churn rate feature.
        
        Churn = customers_lost / total_customers (90-day window)
        
        Features (1):
        - churn_rate: Customer churn rate
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            dict: Churn features
        """
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except:
                now = datetime.now()
        
        # Define time windows
        period_1_start = now - timedelta(days=180)
        period_1_end = now - timedelta(days=90)
        period_2_start = now - timedelta(days=90)
        period_2_end = now
        
        # Get customers from period 1 (using order_id as proxy)
        sales_period_1 = self._get_sales_in_period(
            product.id, 
            period_1_start, 
            period_1_end, 
            strict_before=True if cutoff_date else False
        ) or []
        
        customers_period_1 = set(
            s.order_id if s.order_id else f"customer_{s.sale_date}"
            for s in sales_period_1
        )
        
        # Get customers from period 2
        sales_period_2 = self._get_sales_in_period(
            product.id, 
            period_2_start, 
            period_2_end, 
            strict_before=True if cutoff_date else False
        ) or []
        
        customers_period_2 = set(
            s.order_id if s.order_id else f"customer_{s.sale_date}"
            for s in sales_period_2
        )
        
        if not customers_period_1:
            return {'churn_rate': 0.0}
        
        # Calculate churn
        churned_customers = customers_period_1 - customers_period_2
        churn_rate = len(churned_customers) / len(customers_period_1)
        
        return {
            'churn_rate': float(churn_rate),
        }
    
    def extract_profitability_features(self, product: Product, cutoff_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        Profitability index feature.
        
        Profitability Index = profit / revenue (profit margin)
        
        Features (1):
        - profitability_index: Profit margin ratio
        
        Args:
            product: Product model instance
            cutoff_date: Temporal cutoff (for training = applied_at, for inference = None = now)
        
        Returns:
            dict: Profitability features
        """
        if cutoff_date:
            now = cutoff_date
        else:
            try:
                now = self._get_effective_now(product.id)
            except:
                now = datetime.now()
        
        cutoff = now - timedelta(days=30)
        
        # Get revenue
        sales = self._get_sales_in_period(
            product.id, 
            cutoff, 
            now, 
            strict_before=True if cutoff_date else False
        ) or []
        
        revenue = sum(float(s.revenue) for s in sales)
        
        if revenue == 0:
            return {'profitability_index': 0.0}
        
        # Get product cost
        cost_per_unit = float(product.cost) if hasattr(product, 'cost') and product.cost else 0.0
        
        # Calculate profit
        units_sold = sum(s.quantity_sold for s in sales)
        total_cost = cost_per_unit * units_sold
        profit = revenue - total_cost
        
        profitability_index = profit / revenue if revenue > 0 else 0.0
        
        return {
            'profitability_index': float(profitability_index),
        }
