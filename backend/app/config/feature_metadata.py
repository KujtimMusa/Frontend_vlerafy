"""
Feature Metadata - Categorization of all 80 features

Categorizes features into:
- MISSING_DATA_IF_ZERO: Zero means no data available (critical)
- LEGITIMATE_ZERO: Zero is a valid calculated result (not critical)
- NOT_IMPLEMENTED: Feature is hardcoded placeholder (code bug)
"""

from typing import Dict

# Feature Categories for Confidence Analysis
FEATURE_CATEGORIES: Dict[str, Dict] = {
    # ==================== TIER 1: BASIC FEATURES (5) ====================
    'current_price': {
        'category': 'BASIC',
        'type': 'ALWAYS_AVAILABLE',
        'critical': True,
        'zero_meaning': 'N/A',  # Should never be 0
        'explanation': 'Current product price (always available)'
    },
    # ==================== COST FEATURES (12) ====================
    # Legacy feature (for backward compatibility)
    'cost': {
        'category': 'COST',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'Cost data not provided (legacy product.cost or ProductCost missing)',
        'explanation': 'Product cost - alias for cost_total (backward compatibility)'
    },
    'cost_total': {
        'category': 'COST',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'No ProductCost data - purchase + shipping + packaging costs missing',
        'explanation': 'Total base costs (purchase + shipping + packaging) from ProductCost table'
    },
    'cost_purchase': {
        'category': 'COST',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'Purchase cost not provided in ProductCost',
        'explanation': 'Purchase cost (Einkaufspreis netto) from ProductCost table'
    },
    'cost_shipping': {
        'category': 'COST',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'Shipping cost not provided (may be 0 for free shipping)',
        'explanation': 'Shipping cost per unit from ProductCost table'
    },
    'cost_packaging': {
        'category': 'COST',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'Packaging cost not provided (may be 0)',
        'explanation': 'Packaging cost per unit from ProductCost table'
    },
    'cost_payment_fee_pct': {
        'category': 'COST',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'Payment fee percentage not configured',
        'explanation': 'Payment provider fee percentage (e.g., 2.9% for Stripe)'
    },
    'cost_payment_fee_abs': {
        'category': 'COST',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'Payment fee not calculated (no price or cost data)',
        'explanation': 'Absolute payment fee for current price (percentage + fixed fee)'
    },
    'cost_total_variable': {
        'category': 'COST',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'Total variable costs not calculated (no ProductCost data)',
        'explanation': 'Total variable costs (base costs + payment fees)'
    },
    'breakeven_price': {
        'category': 'COST',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'Break-even price not calculated (no ProductCost data)',
        'explanation': 'Break-even price (0% margin) based on variable costs and VAT'
    },
    'margin_euro': {
        'category': 'COST',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'Margin not calculated (no ProductCost or price data)',
        'explanation': 'Contribution margin in Euro (net revenue - variable costs)'
    },
    'margin_pct': {
        'category': 'COST',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'Margin percentage not calculated (no ProductCost or price data)',
        'explanation': 'Contribution margin percentage (margin_euro / net_revenue * 100)'
    },
    'margin_safety_buffer': {
        'category': 'COST',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Margin exactly at 20% target (or not calculated)',
        'explanation': 'Safety buffer: difference between current margin and 20% target margin'
    },
    'inventory_quantity': {
        'category': 'INVENTORY',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Product out of stock',
        'explanation': 'Stock quantity - 0 means out of stock (valid)'
    },
    'inventory_value': {
        'category': 'INVENTORY',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'No inventory (out of stock)',
        'explanation': 'Total inventory value - 0 if no stock'
    },
    
    # ==================== TIER 2: SALES FEATURES (19) ====================
    'sales_velocity_7d': {
        'category': 'SALES',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'No sales in last 7 days',
        'explanation': 'Sales per day (7d) - 0 means no sales data'
    },
    'sales_velocity_30d': {
        'category': 'SALES',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'No sales in last 30 days',
        'explanation': 'Sales per day (30d) - 0 means no sales data'
    },
    'sales_velocity_90d': {
        'category': 'SALES',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No sales in last 90 days',
        'explanation': 'Sales per day (90d) - 0 means no sales data'
    },
    'demand_growth_7d_vs_30d': {
        'category': 'SALES',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'No growth (stable demand)',
        'explanation': 'Growth rate - 0 means stable (valid result)'
    },
    'demand_growth_30d_vs_90d': {
        'category': 'SALES',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'No growth (stable demand)',
        'explanation': 'Growth rate - 0 means stable (valid result)'
    },
    'demand_trend': {
        'category': 'SALES',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Stable demand (no clear trend)',
        'explanation': 'Demand trend: -1=declining, 0=stable, 1=growing'
    },
    'sales_volatility_7d': {
        'category': 'SALES',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Very consistent sales (low variance)',
        'explanation': 'Sales volatility - 0 means perfectly consistent'
    },
    'sales_volatility_30d': {
        'category': 'SALES',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Very consistent sales (low variance)',
        'explanation': 'Sales volatility - 0 means perfectly consistent'
    },
    'sales_consistency': {
        'category': 'SALES',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'High volatility (inconsistent sales)',
        'explanation': 'Consistency score - 0 means very inconsistent'
    },
    'revenue_7d': {
        'category': 'SALES',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'No revenue in last 7 days',
        'explanation': 'Total revenue (7d) - 0 means no sales'
    },
    'revenue_30d': {
        'category': 'SALES',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'No revenue in last 30 days',
        'explanation': 'Total revenue (30d) - 0 means no sales'
    },
    'revenue_90d': {
        'category': 'SALES',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No revenue in last 90 days',
        'explanation': 'Total revenue (90d) - 0 means no sales'
    },
    'avg_order_value_7d': {
        'category': 'SALES',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No sales in last 7 days',
        'explanation': 'Average order value - 0 if no sales'
    },
    'avg_order_value_30d': {
        'category': 'SALES',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No sales in last 30 days',
        'explanation': 'Average order value - 0 if no sales'
    },
    'days_since_last_sale': {
        'category': 'SALES',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'No sales ever recorded (999 if no sales)',
        'explanation': 'Days since last sale - 999 means never sold'
    },
    'sales_frequency': {
        'category': 'SALES',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No sales in last 30 days',
        'explanation': 'Sales per week - 0 if no sales'
    },
    'peak_sales_day': {
        'category': 'SALES',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Monday is peak day (0 = Monday)',
        'explanation': 'Day of week with most sales (0-6)'
    },
    'weekend_sales_ratio': {
        'category': 'SALES',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'No weekend sales',
        'explanation': 'Weekend vs weekday ratio - 0 means no weekend sales'
    },
    'sales_acceleration': {
        'category': 'SALES',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'No change in sales velocity',
        'explanation': 'Change in velocity - 0 means stable'
    },
    
    # ==================== TIER 3: PRICE FEATURES (10) ====================
    'price_volatility_7d': {
        'category': 'PRICE',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Price has been stable (no changes)',
        'explanation': 'Price volatility - 0 means perfectly stable'
    },
    'price_volatility_30d': {
        'category': 'PRICE',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Price has been stable (no changes)',
        'explanation': 'Price volatility - 0 means perfectly stable'
    },
    'price_stability_score': {
        'category': 'PRICE',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Very unstable price (high volatility)',
        'explanation': 'Stability score - 0 means very unstable'
    },
    'price_trend_slope': {
        'category': 'PRICE',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'No price trend (stable)',
        'explanation': 'Price trend slope - 0 means no trend'
    },
    'price_change_frequency': {
        'category': 'PRICE',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'No price changes in last 30 days',
        'explanation': 'Number of price changes - 0 means stable'
    },
    'price_momentum': {
        'category': 'PRICE',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'No price change (stable)',
        'explanation': 'Price momentum: -1=down, 0=stable, 1=up'
    },
    'price_min_30d': {
        'category': 'PRICE',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No price history available',
        'explanation': 'Minimum price (30d) - 0 if no history'
    },
    'price_max_30d': {
        'category': 'PRICE',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No price history available',
        'explanation': 'Maximum price (30d) - 0 if no history'
    },
    'price_avg_30d': {
        'category': 'PRICE',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No price history available',
        'explanation': 'Average price (30d) - 0 if no history'
    },
    'price_vs_avg_30d_pct': {
        'category': 'PRICE',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Current price equals average',
        'explanation': 'Price vs average % - 0 means at average'
    },
    
    # ==================== TIER 4: INVENTORY FEATURES (15) ====================
    'inventory_turnover_30d': {
        'category': 'INVENTORY',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No sales or no inventory',
        'explanation': 'Inventory turnover - 0 if no sales'
    },
    'inventory_turnover_90d': {
        'category': 'INVENTORY',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No sales or no inventory',
        'explanation': 'Inventory turnover - 0 if no sales'
    },
    'stockout_risk': {
        'category': 'INVENTORY',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Low stockout risk (good stock levels)',
        'explanation': 'Stockout risk - 0 means low risk'
    },
    'days_of_stock_7d': {
        'category': 'INVENTORY',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No sales velocity (cannot calculate)',
        'explanation': 'Days of stock - 999 if no sales'
    },
    'days_of_stock_30d': {
        'category': 'INVENTORY',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No sales velocity (cannot calculate)',
        'explanation': 'Days of stock - 999 if no sales'
    },
    'days_of_stock_90d': {
        'category': 'INVENTORY',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No sales velocity (cannot calculate)',
        'explanation': 'Days of stock - 999 if no sales'
    },
    'stock_velocity_ratio': {
        'category': 'INVENTORY',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'No 7d velocity (stable)',
        'explanation': '7d vs 30d velocity ratio'
    },
    'inventory_trend': {
        'category': 'INVENTORY',
        'type': 'NOT_IMPLEMENTED',
        'critical': False,
        'zero_meaning': 'Feature not implemented (hardcoded 0.0)',
        'explanation': 'Inventory trend calculation not yet implemented'
    },
    'reorder_point': {
        'category': 'INVENTORY',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No sales velocity (cannot calculate)',
        'explanation': 'Reorder point - 0 if no sales data'
    },
    'safety_stock': {
        'category': 'INVENTORY',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No sales velocity (cannot calculate)',
        'explanation': 'Safety stock - 0 if no sales data'
    },
    'stock_health_score': {
        'category': 'INVENTORY',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Poor stock health (over/understocked)',
        'explanation': 'Stock health - 0.2 means poor health'
    },
    'overstock_risk': {
        'category': 'INVENTORY',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Low overstock risk',
        'explanation': 'Overstock risk - 0 means low risk'
    },
    'understock_risk': {
        'category': 'INVENTORY',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Low understock risk',
        'explanation': 'Understock risk - 0 means low risk'
    },
    
    # ==================== TIER 5: COMPETITIVE FEATURES (8) ====================
    'competitor_min_price': {
        'category': 'COMPETITOR',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'No competitor data available',
        'explanation': 'Lowest competitor price - 0 if no competitors found'
    },
    'competitor_max_price': {
        'category': 'COMPETITOR',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'No competitor data available',
        'explanation': 'Highest competitor price - 0 if no competitors found'
    },
    'competitor_avg_price': {
        'category': 'COMPETITOR',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'No competitor data available',
        'explanation': 'Average competitor price - 0 if no competitors found'
    },
    'competitor_price_diff': {
        'category': 'COMPETITOR',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Our price equals competitor average',
        'explanation': 'Price difference % - 0 means at average'
    },
    'competitor_count': {
        'category': 'COMPETITOR',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'No competitors found',
        'explanation': 'Number of competitors - 0 if none found'
    },
    'market_position': {
        'category': 'COMPETITOR',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Cheapest in market (position 0)',
        'explanation': 'Market position: 0=cheapest, 1=most expensive'
    },
    'price_rank': {
        'category': 'COMPETITOR',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No competitor data',
        'explanation': 'Price rank - 0 if no competitors'
    },
    'price_gap_to_leader': {
        'category': 'COMPETITOR',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'We are the price leader (cheapest)',
        'explanation': 'Gap to cheapest - 0 means we are cheapest'
    },
    
    # ==================== TIER 6: ADVANCED FEATURES (23) ====================
    'is_weekend': {
        'category': 'SEASONAL',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Current day is weekday',
        'explanation': 'Is weekend: 0=weekday, 1=weekend'
    },
    'is_holiday': {
        'category': 'SEASONAL',
        'type': 'NOT_IMPLEMENTED',
        'critical': False,
        'zero_meaning': 'Feature not implemented (hardcoded 0.0)',
        'explanation': 'Holiday detection not yet implemented'
    },
    'month_of_year': {
        'category': 'SEASONAL',
        'type': 'ALWAYS_AVAILABLE',
        'critical': False,
        'zero_meaning': 'N/A',
        'explanation': 'Month of year (1-12, always available)'
    },
    'day_of_week': {
        'category': 'SEASONAL',
        'type': 'ALWAYS_AVAILABLE',
        'critical': False,
        'zero_meaning': 'N/A',
        'explanation': 'Day of week (0-6, always available)'
    },
    'seasonality_score': {
        'category': 'SEASONAL',
        'type': 'ALWAYS_AVAILABLE',
        'critical': False,
        'zero_meaning': 'N/A',
        'explanation': 'Seasonal demand factor (always calculated)'
    },
    'price_elasticity': {
        'category': 'ADVANCED',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'Insufficient price/sales history for calculation',
        'explanation': 'Price elasticity - default -1.5 if cannot calculate'
    },
    'demand_sensitivity': {
        'category': 'ADVANCED',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'Low price sensitivity',
        'explanation': 'Demand sensitivity - 0 means low sensitivity'
    },
    'optimal_price_range_min': {
        'category': 'ADVANCED',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'Cost data missing',
        'explanation': 'Optimal min price - 0 if cost missing'
    },
    'optimal_price_range_max': {
        'category': 'ADVANCED',
        'type': 'ALWAYS_AVAILABLE',
        'critical': False,
        'zero_meaning': 'N/A',
        'explanation': 'Optimal max price (always calculated)'
    },
    'market_volatility': {
        'category': 'ADVANCED',
        'type': 'NOT_IMPLEMENTED',
        'critical': False,
        'zero_meaning': 'Feature not implemented (hardcoded 0.5)',
        'explanation': 'Market volatility calculation not yet implemented'
    },
    'competitive_intensity': {
        'category': 'ADVANCED',
        'type': 'NOT_IMPLEMENTED',
        'critical': False,
        'zero_meaning': 'Feature not implemented (hardcoded 0.5)',
        'explanation': 'Competitive intensity calculation not yet implemented'
    },
    'price_leadership': {
        'category': 'ADVANCED',
        'type': 'NOT_IMPLEMENTED',
        'critical': False,
        'zero_meaning': 'Feature not implemented (hardcoded 0.0)',
        'explanation': 'Price leadership detection not yet implemented'
    },
    'product_age_days': {
        'category': 'ADVANCED',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'Product creation date missing',
        'explanation': 'Product age - default 90 if created_at missing'
    },
    'lifecycle_stage': {
        'category': 'ADVANCED',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'Product age unknown',
        'explanation': 'Lifecycle stage - 0=new if age unknown'
    },
    'growth_rate': {
        'category': 'ADVANCED',
        'type': 'LEGITIMATE_ZERO',
        'critical': False,
        'zero_meaning': 'No growth (stable sales)',
        'explanation': 'Growth rate % - 0 means stable'
    },
    'profit_margin_optimized': {
        'category': 'ADVANCED',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': True,
        'zero_meaning': 'Cost data missing',
        'explanation': 'Optimized margin - 0 if cost missing'
    },
    'revenue_potential': {
        'category': 'ADVANCED',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No sales velocity (cannot calculate)',
        'explanation': 'Revenue potential - 0 if no sales'
    },
    'conversion_likelihood': {
        'category': 'ADVANCED',
        'type': 'NOT_IMPLEMENTED',
        'critical': False,
        'zero_meaning': 'Feature not implemented (hardcoded 0.5)',
        'explanation': 'Conversion likelihood calculation not yet implemented'
    },
    'customer_lifetime_value': {
        'category': 'ADVANCED',
        'type': 'MISSING_DATA_IF_ZERO',
        'critical': False,
        'zero_meaning': 'No revenue potential (cannot calculate)',
        'explanation': 'CLV - 0 if revenue_potential is 0'
    },
    'churn_risk': {
        'category': 'ADVANCED',
        'type': 'NOT_IMPLEMENTED',
        'critical': False,
        'zero_meaning': 'Feature not implemented (hardcoded 0.2)',
        'explanation': 'Churn risk calculation not yet implemented'
    },
    'market_share_estimate': {
        'category': 'ADVANCED',
        'type': 'NOT_IMPLEMENTED',
        'critical': False,
        'zero_meaning': 'Feature not implemented (hardcoded 0.1)',
        'explanation': 'Market share estimation not yet implemented'
    },
    'brand_strength': {
        'category': 'ADVANCED',
        'type': 'NOT_IMPLEMENTED',
        'critical': False,
        'zero_meaning': 'Feature not implemented (hardcoded 0.7)',
        'explanation': 'Brand strength calculation not yet implemented'
    },
    'product_category_score': {
        'category': 'ADVANCED',
        'type': 'NOT_IMPLEMENTED',
        'critical': False,
        'zero_meaning': 'Feature not implemented (hardcoded 0.6)',
        'explanation': 'Category performance score not yet implemented'
    }
}

# Category display names
CATEGORY_NAMES = {
    'BASIC': 'Basic Product Data',
    'SALES': 'Sales History',
    'PRICE': 'Price History',
    'INVENTORY': 'Inventory & Stock',
    'COST': 'Cost & Margin',
    'COMPETITOR': 'Competitor Data',
    'SEASONAL': 'Seasonal & Temporal',
    'ADVANCED': 'Advanced Analytics'
}

# Status thresholds
STATUS_THRESHOLDS = {
    'excellent': 80.0,
    'good': 70.0,
    'ok': 50.0,
    'low': 0.0
}

def get_status(percentage: float) -> str:
    """Get status label for percentage"""
    if percentage >= STATUS_THRESHOLDS['excellent']:
        return 'excellent'
    elif percentage >= STATUS_THRESHOLDS['good']:
        return 'good'
    elif percentage >= STATUS_THRESHOLDS['ok']:
        return 'ok'
    else:
        return 'low'

# ==================== VALIDATION ====================

# Validate all features have valid categories
VALID_CATEGORIES = set(CATEGORY_NAMES.keys())

# Validate at import time
for feature_name, metadata in FEATURE_CATEGORIES.items():
    category = metadata.get('category')
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category '{category}' for feature '{feature_name}'. "
            f"Must be one of {sorted(VALID_CATEGORIES)}"
        )
