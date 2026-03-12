"""
Feature Inventory - Complete Documentation of ALL 80 ML Features

This file documents every feature extracted by FeatureEngineeringService,
including data sources, availability conditions, and reliability indicators.
"""

from typing import Dict, List

# ==================== FEATURE INVENTORY ====================

FEATURE_INVENTORY: Dict[str, Dict] = {
    # ==================== TIER 1: BASIC FEATURES (5) ====================
    'current_price': {
        'tier': 1,
        'method': 'extract_basic_features',
        'data_source': 'product.price (Product table)',
        'availability': 'always',
        'reliability': 'very_high',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Current product price'
    },
    'cost': {
        'tier': 1,
        'method': 'extract_basic_features',
        'data_source': 'product.cost (Product table)',
        'availability': 'conditional (may be None)',
        'reliability': 'high if available',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Product cost'
    },
    'margin_pct': {
        'tier': 1,
        'method': 'extract_basic_features',
        'data_source': 'calculated: ((price - cost) / price * 100)',
        'availability': 'always (0 if cost missing)',
        'reliability': 'high if cost available',
        'type': 'float',
        'range': '-infinity to 100',
        'description': 'Profit margin percentage'
    },
    'inventory_quantity': {
        'tier': 1,
        'method': 'extract_basic_features',
        'data_source': 'product.inventory_quantity (Product table)',
        'availability': 'always (0 if None)',
        'reliability': 'very_high',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Current stock quantity'
    },
    'inventory_value': {
        'tier': 1,
        'method': 'extract_basic_features',
        'data_source': 'calculated: price * inventory_quantity',
        'availability': 'always',
        'reliability': 'very_high',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Total inventory value'
    },
    
    # ==================== TIER 2: SALES FEATURES (19) ====================
    'sales_velocity_7d': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'sales_history table (last 7 days)',
        'availability': 'requires 7+ days sales data',
        'reliability': 'high if > 10 sales, medium if 3-10, low if < 3',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Sales per day (last 7 days)'
    },
    'sales_velocity_30d': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'sales_history table (last 30 days)',
        'availability': 'requires 30+ days sales data',
        'reliability': 'very_high if > 30 sales, high if 10-30, medium if 3-10',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Sales per day (last 30 days)'
    },
    'sales_velocity_90d': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'sales_history table (last 90 days)',
        'availability': 'requires 90+ days sales data',
        'reliability': 'very_high if > 90 sales, high if 30-90',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Sales per day (last 90 days)'
    },
    'demand_growth_7d_vs_30d': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'calculated: ((velocity_7d - velocity_30d) / velocity_30d * 100)',
        'availability': 'requires both 7d and 30d sales data',
        'reliability': 'high if both velocities > 0',
        'type': 'float',
        'range': '-infinity to infinity',
        'description': 'Growth rate comparison (7d vs 30d)'
    },
    'demand_growth_30d_vs_90d': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'calculated: ((velocity_30d - velocity_90d) / velocity_90d * 100)',
        'availability': 'requires both 30d and 90d sales data',
        'reliability': 'high if both velocities > 0',
        'type': 'float',
        'range': '-infinity to infinity',
        'description': 'Growth rate comparison (30d vs 90d)'
    },
    'demand_trend': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'calculated: based on growth_7d_vs_30d',
        'availability': 'requires 7d and 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '-1.0, 0.0, 1.0',
        'description': 'Overall demand trend (-1=declining, 0=stable, 1=growing)'
    },
    'sales_volatility_7d': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'calculated: std dev of daily sales (7d)',
        'availability': 'requires 7+ days sales data',
        'reliability': 'medium if > 7 sales, low if < 7',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Standard deviation of daily sales (7d)'
    },
    'sales_volatility_30d': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'calculated: std dev of daily sales (30d)',
        'availability': 'requires 30+ days sales data',
        'reliability': 'high if > 30 sales, medium if 10-30',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Standard deviation of daily sales (30d)'
    },
    'sales_consistency': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'calculated: 1 - (volatility_7d / mean_sales_7d)',
        'availability': 'requires 7d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0.0 to 1.0',
        'description': 'Sales consistency score (1 = very consistent)'
    },
    'revenue_7d': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'sales_history.revenue (sum last 7 days)',
        'availability': 'requires 7+ days sales data with revenue',
        'reliability': 'high if revenue data available',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Total revenue last 7 days'
    },
    'revenue_30d': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'sales_history.revenue (sum last 30 days)',
        'availability': 'requires 30+ days sales data with revenue',
        'reliability': 'very_high if revenue data available',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Total revenue last 30 days'
    },
    'revenue_90d': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'sales_history.revenue (sum last 90 days)',
        'availability': 'requires 90+ days sales data with revenue',
        'reliability': 'very_high if revenue data available',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Total revenue last 90 days'
    },
    'avg_order_value_7d': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'calculated: revenue_7d / total_qty_7d',
        'availability': 'requires 7d sales data with revenue',
        'reliability': 'high if revenue data available',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Average order value (7d)'
    },
    'avg_order_value_30d': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'calculated: revenue_30d / total_qty_30d',
        'availability': 'requires 30d sales data with revenue',
        'reliability': 'high if revenue data available',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Average order value (30d)'
    },
    'days_since_last_sale': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'sales_history table (max sale_date)',
        'availability': 'requires at least 1 sale',
        'reliability': 'very_high',
        'type': 'float',
        'range': '0 to 999',
        'description': 'Days since last sale (999 if no sales)'
    },
    'sales_frequency': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'calculated: len(sales_30d) / 4.0',
        'availability': 'requires 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Sales per week'
    },
    'peak_sales_day': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'calculated: day of week with most sales',
        'availability': 'requires 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0 to 6',
        'description': 'Day of week with most sales (0=Monday, 6=Sunday)'
    },
    'weekend_sales_ratio': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'calculated: weekend_sales / total_sales',
        'availability': 'requires 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0.0 to 1.0',
        'description': 'Weekend vs weekday sales ratio'
    },
    'sales_acceleration': {
        'tier': 2,
        'method': 'extract_sales_features',
        'data_source': 'calculated: velocity_7d - velocity_30d',
        'availability': 'requires both 7d and 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '-infinity to infinity',
        'description': 'Change in velocity trend'
    },
    
    # ==================== TIER 3: PRICE FEATURES (10) ====================
    'price_volatility_7d': {
        'tier': 3,
        'method': 'extract_price_features',
        'data_source': 'price_history table (std dev of price changes, 7d)',
        'availability': 'requires 7+ days price history',
        'reliability': 'medium if > 7 price records',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Price volatility (7d)'
    },
    'price_volatility_30d': {
        'tier': 3,
        'method': 'extract_price_features',
        'data_source': 'price_history table (std dev of price changes, 30d)',
        'availability': 'requires 30+ days price history',
        'reliability': 'high if > 30 price records',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Price volatility (30d)'
    },
    'price_stability_score': {
        'tier': 3,
        'method': 'extract_price_features',
        'data_source': 'calculated: 1 - (volatility_30d / mean_price)',
        'availability': 'requires 30d price history',
        'reliability': 'medium',
        'type': 'float',
        'range': '0.0 to 1.0',
        'description': 'Price stability score (1 = very stable)'
    },
    'price_trend_slope': {
        'tier': 3,
        'method': 'extract_price_features',
        'data_source': 'calculated: linear regression slope (30d)',
        'availability': 'requires 30d price history with >= 2 records',
        'reliability': 'medium',
        'type': 'float',
        'range': '-infinity to infinity',
        'description': 'Price trend slope (positive = increasing)'
    },
    'price_change_frequency': {
        'tier': 3,
        'method': 'extract_price_features',
        'data_source': 'calculated: count of non-zero price changes (30d)',
        'availability': 'requires 30d price history',
        'reliability': 'high',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Number of price changes (30d)'
    },
    'price_momentum': {
        'tier': 3,
        'method': 'extract_price_features',
        'data_source': 'calculated: recent price change direction',
        'availability': 'requires >= 2 price history records',
        'reliability': 'medium',
        'type': 'float',
        'range': '-1.0, 0.0, 1.0',
        'description': 'Price momentum (-1=down, 0=stable, 1=up)'
    },
    'price_min_30d': {
        'tier': 3,
        'method': 'extract_price_features',
        'data_source': 'price_history table (min price, 30d)',
        'availability': 'requires 30d price history',
        'reliability': 'high',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Minimum price (30d)'
    },
    'price_max_30d': {
        'tier': 3,
        'method': 'extract_price_features',
        'data_source': 'price_history table (max price, 30d)',
        'availability': 'requires 30d price history',
        'reliability': 'high',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Maximum price (30d)'
    },
    'price_avg_30d': {
        'tier': 3,
        'method': 'extract_price_features',
        'data_source': 'price_history table (avg price, 30d)',
        'availability': 'requires 30d price history',
        'reliability': 'high',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Average price (30d)'
    },
    'price_vs_avg_30d_pct': {
        'tier': 3,
        'method': 'extract_price_features',
        'data_source': 'calculated: ((current_price - avg_30d) / avg_30d * 100)',
        'availability': 'requires 30d price history',
        'reliability': 'high',
        'type': 'float',
        'range': '-infinity to infinity',
        'description': 'Current vs average price (%)'
    },
    
    # ==================== TIER 4: INVENTORY FEATURES (15) ====================
    'inventory_quantity': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'product.inventory_quantity (duplicate from Tier 1)',
        'availability': 'always',
        'reliability': 'very_high',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Current stock quantity'
    },
    'inventory_value': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: price * inventory_quantity (duplicate from Tier 1)',
        'availability': 'always',
        'reliability': 'very_high',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Total inventory value'
    },
    'inventory_turnover_30d': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: total_qty_30d / avg_inventory',
        'availability': 'requires 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Inventory turnover rate (30d)'
    },
    'inventory_turnover_90d': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: total_qty_90d / avg_inventory',
        'availability': 'requires 90d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Inventory turnover rate (90d)'
    },
    'stockout_risk': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: based on velocity_30d and inventory',
        'availability': 'requires 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0.0, 0.5, 1.0',
        'description': 'Stockout risk (0=low, 0.5=medium, 1.0=high)'
    },
    'days_of_stock_7d': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: inventory / velocity_7d',
        'availability': 'requires 7d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0 to 999',
        'description': 'Days until stockout (7d velocity)'
    },
    'days_of_stock_30d': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: inventory / velocity_30d',
        'availability': 'requires 30d sales data',
        'reliability': 'high',
        'type': 'float',
        'range': '0 to 999',
        'description': 'Days until stockout (30d velocity)'
    },
    'days_of_stock_90d': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: inventory / velocity_90d',
        'availability': 'requires 90d sales data',
        'reliability': 'high',
        'type': 'float',
        'range': '0 to 999',
        'description': 'Days until stockout (90d velocity)'
    },
    'stock_velocity_ratio': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: velocity_7d / velocity_30d',
        'availability': 'requires both 7d and 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0 to infinity',
        'description': '7d vs 30d velocity ratio'
    },
    'inventory_trend': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'simplified: always 0.0 (would need historical inventory)',
        'availability': 'always (but not meaningful)',
        'reliability': 'low (not implemented)',
        'type': 'float',
        'range': '0.0',
        'description': 'Stock level trend (not implemented)'
    },
    'reorder_point': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: avg_daily_demand * lead_time_days',
        'availability': 'requires 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Suggested reorder point'
    },
    'safety_stock': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: avg_daily_demand * 3',
        'availability': 'requires 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Safety stock level (3 days)'
    },
    'stock_health_score': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: based on days_of_stock_30d',
        'availability': 'requires 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0.2 to 1.0',
        'description': 'Overall stock health (0.2=bad, 1.0=optimal)'
    },
    'overstock_risk': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: based on days_of_stock_30d',
        'availability': 'requires 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0.0, 0.5, 1.0',
        'description': 'Overstock risk (0=low, 0.5=medium, 1.0=high)'
    },
    'understock_risk': {
        'tier': 4,
        'method': 'extract_inventory_features',
        'data_source': 'calculated: based on days_of_stock_30d',
        'availability': 'requires 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0.0, 0.5, 1.0',
        'description': 'Understock risk (0=low, 0.5=medium, 1.0=high)'
    },
    
    # ==================== TIER 5: COMPETITIVE FEATURES (8) ====================
    'competitor_min_price': {
        'tier': 5,
        'method': 'extract_competitive_features',
        'data_source': 'competitor_data API (Serper API)',
        'availability': 'requires competitor_data from API',
        'reliability': 'high if >= 3 competitors, medium if 1-2',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Lowest competitor price'
    },
    'competitor_max_price': {
        'tier': 5,
        'method': 'extract_competitive_features',
        'data_source': 'competitor_data API (Serper API)',
        'availability': 'requires competitor_data from API',
        'reliability': 'high if >= 3 competitors, medium if 1-2',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Highest competitor price'
    },
    'competitor_avg_price': {
        'tier': 5,
        'method': 'extract_competitive_features',
        'data_source': 'competitor_data API (Serper API)',
        'availability': 'requires competitor_data from API',
        'reliability': 'very_high if >= 5 competitors, high if 3-4, medium if 1-2',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Average competitor price'
    },
    'competitor_price_diff': {
        'tier': 5,
        'method': 'extract_competitive_features',
        'data_source': 'calculated: ((current_price - avg) / avg * 100)',
        'availability': 'requires competitor_data from API',
        'reliability': 'high if competitor_avg_price available',
        'type': 'float',
        'range': '-infinity to infinity',
        'description': 'Our price vs avg competitor (%)'
    },
    'competitor_count': {
        'tier': 5,
        'method': 'extract_competitive_features',
        'data_source': 'competitor_data API (count)',
        'availability': 'requires competitor_data from API',
        'reliability': 'very_high',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Number of competitors found'
    },
    'market_position': {
        'tier': 5,
        'method': 'extract_competitive_features',
        'data_source': 'calculated: (current_price - min) / (max - min)',
        'availability': 'requires competitor_data from API',
        'reliability': 'high if >= 3 competitors',
        'type': 'float',
        'range': '0.0 to 1.0',
        'description': 'Market position (0=cheapest, 1=most expensive)'
    },
    'price_rank': {
        'tier': 5,
        'method': 'extract_competitive_features',
        'data_source': 'calculated: rank among all prices',
        'availability': 'requires competitor_data from API',
        'reliability': 'high if >= 3 competitors',
        'type': 'float',
        'range': '1 to infinity',
        'description': 'Price rank (1=cheapest)'
    },
    'price_gap_to_leader': {
        'tier': 5,
        'method': 'extract_competitive_features',
        'data_source': 'calculated: current_price - competitor_min',
        'availability': 'requires competitor_data from API',
        'reliability': 'high if competitor_min_price available',
        'type': 'float',
        'range': '-infinity to infinity',
        'description': 'Gap to cheapest competitor'
    },
    
    # ==================== TIER 6: ADVANCED FEATURES (23) ====================
    'is_weekend': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: now.weekday() >= 5',
        'availability': 'always',
        'reliability': 'very_high',
        'type': 'float',
        'range': '0.0, 1.0',
        'description': 'Is current day weekend (0/1)'
    },
    'is_holiday': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'simplified: always 0.0 (would need holiday calendar)',
        'availability': 'always (but not meaningful)',
        'reliability': 'low (not implemented)',
        'type': 'float',
        'range': '0.0',
        'description': 'Is current day holiday (not implemented)'
    },
    'month_of_year': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: now.month',
        'availability': 'always',
        'reliability': 'very_high',
        'type': 'float',
        'range': '1 to 12',
        'description': 'Month of year (1-12)'
    },
    'day_of_week': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: now.weekday()',
        'availability': 'always',
        'reliability': 'very_high',
        'type': 'float',
        'range': '0 to 6',
        'description': 'Day of week (0=Monday, 6=Sunday)'
    },
    'seasonality_score': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: based on month (Q4=1.2, summer=1.0, other=0.9)',
        'availability': 'always',
        'reliability': 'medium (simplified)',
        'type': 'float',
        'range': '0.9 to 1.2',
        'description': 'Seasonal demand factor'
    },
    'price_elasticity': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: based on price changes vs demand changes',
        'availability': 'requires 90d price history and 30d sales data',
        'reliability': 'low (simplified estimation)',
        'type': 'float',
        'range': '-infinity to infinity',
        'description': 'Estimated price elasticity (default: -1.5)'
    },
    'demand_sensitivity': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: abs(elasticity) / 3.0',
        'availability': 'requires price_elasticity',
        'reliability': 'low (depends on elasticity)',
        'type': 'float',
        'range': '0.0 to 1.0',
        'description': 'Price sensitivity score'
    },
    'optimal_price_range_min': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: cost * 1.2 (20% margin minimum)',
        'availability': 'requires cost data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Suggested minimum price'
    },
    'optimal_price_range_max': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: current_price * 1.5 (50% increase max)',
        'availability': 'always',
        'reliability': 'medium',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Suggested maximum price'
    },
    'market_volatility': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'simplified: always 0.5 (would need competitor price history)',
        'availability': 'always (but not meaningful)',
        'reliability': 'low (not implemented)',
        'type': 'float',
        'range': '0.5',
        'description': 'Market price volatility (not implemented)'
    },
    'competitive_intensity': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'simplified: always 0.5 (would need market size data)',
        'availability': 'always (but not meaningful)',
        'reliability': 'low (not implemented)',
        'type': 'float',
        'range': '0.5',
        'description': 'Competitive intensity (not implemented)'
    },
    'price_leadership': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'simplified: always 0.0 (would need competitor comparison)',
        'availability': 'always (but not meaningful)',
        'reliability': 'low (not implemented)',
        'type': 'float',
        'range': '0.0',
        'description': 'Are we price leader (not implemented)'
    },
    'product_age_days': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: (now - product.created_at).days',
        'availability': 'requires product.created_at',
        'reliability': 'high',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Days since product creation'
    },
    'lifecycle_stage': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: based on product_age_days',
        'availability': 'requires product.created_at',
        'reliability': 'medium',
        'type': 'float',
        'range': '0.0, 1.0, 2.0, 3.0',
        'description': 'Lifecycle stage (0=new, 1=growth, 2=mature, 3=decline)'
    },
    'growth_rate': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: ((velocity_7d - velocity_30d) / velocity_30d * 100)',
        'availability': 'requires both 7d and 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '-infinity to infinity',
        'description': 'Product growth rate (%)'
    },
    'profit_margin_optimized': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: ((current_price - cost) / current_price * 100)',
        'availability': 'requires cost data',
        'reliability': 'high if cost available',
        'type': 'float',
        'range': '-infinity to 100',
        'description': 'Optimized margin (same as margin_pct)'
    },
    'revenue_potential': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: velocity_30d * current_price * 30',
        'availability': 'requires 30d sales data',
        'reliability': 'medium',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Monthly revenue potential'
    },
    'conversion_likelihood': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'simplified: always 0.5 (would need conversion data)',
        'availability': 'always (but not meaningful)',
        'reliability': 'low (not implemented)',
        'type': 'float',
        'range': '0.5',
        'description': 'Likelihood of conversion (not implemented)'
    },
    'customer_lifetime_value': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'calculated: revenue_potential * 0.1',
        'availability': 'requires revenue_potential',
        'reliability': 'low (simplified)',
        'type': 'float',
        'range': '0 to infinity',
        'description': 'Estimated CLV (simplified)'
    },
    'churn_risk': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'simplified: always 0.2 (would need customer data)',
        'availability': 'always (but not meaningful)',
        'reliability': 'low (not implemented)',
        'type': 'float',
        'range': '0.2',
        'description': 'Risk of losing customers (not implemented)'
    },
    'market_share_estimate': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'simplified: always 0.1 (would need market data)',
        'availability': 'always (but not meaningful)',
        'reliability': 'low (not implemented)',
        'type': 'float',
        'range': '0.1',
        'description': 'Estimated market share (not implemented)'
    },
    'brand_strength': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'simplified: always 0.7 (would need brand data)',
        'availability': 'always (but not meaningful)',
        'reliability': 'low (not implemented)',
        'type': 'float',
        'range': '0.7',
        'description': 'Brand strength score (not implemented)'
    },
    'product_category_score': {
        'tier': 6,
        'method': 'extract_advanced_features',
        'data_source': 'simplified: always 0.6 (would need category data)',
        'availability': 'always (but not meaningful)',
        'reliability': 'low (not implemented)',
        'type': 'float',
        'range': '0.6',
        'description': 'Category performance score (not implemented)'
    }
}

# ==================== FEATURE GROUPS ====================

FEATURE_GROUPS = {
    'basic': [k for k, v in FEATURE_INVENTORY.items() if v['tier'] == 1],
    'sales': [k for k, v in FEATURE_INVENTORY.items() if v['tier'] == 2],
    'price': [k for k, v in FEATURE_INVENTORY.items() if v['tier'] == 3],
    'inventory': [k for k, v in FEATURE_INVENTORY.items() if v['tier'] == 4],
    'competitive': [k for k, v in FEATURE_INVENTORY.items() if v['tier'] == 5],
    'advanced': [k for k, v in FEATURE_INVENTORY.items() if v['tier'] == 6]
}

# ==================== CRITICAL FEATURES ====================

CRITICAL_FEATURES = [
    'sales_velocity_30d',
    'revenue_30d',
    'inventory_quantity',
    'days_since_last_sale',
    'competitor_avg_price',
    'margin_pct',
    'demand_growth_30d_vs_90d'
]

# ==================== HELPER FUNCTIONS ====================

def get_feature_info(feature_name: str) -> Dict:
    """Get information about a specific feature"""
    return FEATURE_INVENTORY.get(feature_name, {})

def get_features_by_tier(tier: int) -> List[str]:
    """Get all features in a specific tier"""
    return [k for k, v in FEATURE_INVENTORY.items() if v['tier'] == tier]

def get_features_by_method(method: str) -> List[str]:
    """Get all features extracted by a specific method"""
    return [k for k, v in FEATURE_INVENTORY.items() if v['method'] == method]

def get_always_available_features() -> List[str]:
    """Get features that are always available"""
    return [k for k, v in FEATURE_INVENTORY.items() if v['availability'] == 'always']

def get_conditional_features() -> List[str]:
    """Get features that require specific conditions"""
    return [k for k, v in FEATURE_INVENTORY.items() if v['availability'] != 'always']

def count_features_by_reliability(reliability: str) -> int:
    """Count features with specific reliability level"""
    return len([k for k, v in FEATURE_INVENTORY.items() if reliability in v['reliability']])
