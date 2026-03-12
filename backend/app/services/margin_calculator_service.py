"""
Margin Calculator Service
Calculates margins, break-even prices, and validates pricing recommendations
"""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
import logging
import asyncio

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.margin import ProductCost, MarginCalculation
from app.database import get_db

logger = logging.getLogger(__name__)


class MarginCalculatorService:
    """Service for margin calculations and price validation"""
    
    # Payment Provider Configurations
    PAYMENT_PROVIDERS = {
        'stripe': {'percentage': Decimal('2.90'), 'fixed': Decimal('0.30')},
        'paypal': {'percentage': Decimal('2.49'), 'fixed': Decimal('0.35')},
        'klarna': {'percentage': Decimal('4.50'), 'fixed': Decimal('0.00')},
        'custom': {'percentage': Decimal('0.00'), 'fixed': Decimal('0.00')},
    }
    
    # VAT Rates by Country
    VAT_RATES = {
        'DE': Decimal('0.19'),   # Germany: 19%
        'AT': Decimal('0.20'),   # Austria: 20%
        'CH': Decimal('0.077'),  # Switzerland: 7.7%
        'US': Decimal('0.00'),   # USA: Varies (0% for most e-commerce)
        'GB': Decimal('0.20'),   # UK: 20%
        'FR': Decimal('0.20'),   # France: 20%
        'IT': Decimal('0.22'),   # Italy: 22%
        'ES': Decimal('0.21'),   # Spain: 21%
    }
    
    # Category-Based Defaults for Onboarding
    CATEGORY_DEFAULTS = {
        'fashion': {
            'typical_margin': Decimal('0.50'),
            'shipping_estimate': Decimal('4.50'),
            'packaging_estimate': Decimal('1.20'),
        },
        'electronics': {
            'typical_margin': Decimal('0.15'),
            'shipping_estimate': Decimal('6.90'),
            'packaging_estimate': Decimal('2.50'),
        },
        'beauty': {
            'typical_margin': Decimal('0.60'),
            'shipping_estimate': Decimal('3.20'),
            'packaging_estimate': Decimal('0.80'),
        },
        'home': {
            'typical_margin': Decimal('0.40'),
            'shipping_estimate': Decimal('7.50'),
            'packaging_estimate': Decimal('3.00'),
        },
        'food': {
            'typical_margin': Decimal('0.35'),
            'shipping_estimate': Decimal('5.00'),
            'packaging_estimate': Decimal('2.00'),
        },
    }
    
    def __init__(self, db: Session = None):
        self.db = db
    
    def _get_db(self):
        """Get database session"""
        if self.db:
            return self.db
        return next(get_db())
    
    
    # ==========================================
    # CORE CALCULATION METHODS
    # ==========================================
    
    def calculate_margin(
        self,
        product_id: str,
        shop_id: str,
        selling_price: float,
        save_to_history: bool = True,
        triggered_by: str = 'manual'
    ) -> Dict:
        """
        Calculate margin for a product at a given selling price
        
        Args:
            product_id: Shopify Product ID
            shop_id: Shop ID
            selling_price: Proposed selling price (brutto)
            save_to_history: Whether to save calculation to history
            triggered_by: Source of calculation (pricing_engine, manual, autopilot)
        
        Returns:
            Dict with complete margin analysis
        """
        
        db = self._get_db()
        
        # Normalize shop_id to string (handle "demo" → "999")
        shop_id_str = str(shop_id) if shop_id else "999"
        if shop_id_str.lower() == "demo" or not shop_id_str.isdigit():
            shop_id_str = "999"
        
        # Get cost data
        cost_data = db.query(ProductCost).filter(
            and_(
                ProductCost.product_id == product_id,
                ProductCost.shop_id == shop_id_str  # String (matches DB schema)
            )
        ).first()
        
        if not cost_data:
            logger.warning(f"No cost data found for product {product_id}")
            return {
                'has_cost_data': False,
                'error': 'NO_COST_DATA',
                'message': 'Bitte hinterlege zuerst die Kosten für dieses Produkt'
            }
        
        # Convert to Decimal for precise calculations
        selling_price_decimal = Decimal(str(selling_price))
        
        # 1. Calculate Net Revenue (after VAT)
        vat_rate = cost_data.vat_rate
        net_revenue = selling_price_decimal / (Decimal('1') + vat_rate)
        
        # 2. Calculate Payment Fee (percentage + fixed)
        payment_config = self.PAYMENT_PROVIDERS.get(
            cost_data.payment_provider,
            self.PAYMENT_PROVIDERS['stripe']
        )
        payment_fee = (
            (net_revenue * payment_config['percentage'] / Decimal('100')) +
            payment_config['fixed']
        )
        
        # 3. Calculate Total Variable Costs
        total_variable_costs = (
            cost_data.purchase_cost +
            cost_data.shipping_cost +
            cost_data.packaging_cost +
            payment_fee
        )
        
        # 4. Calculate Contribution Margin (DB I)
        contribution_margin_euro = net_revenue - total_variable_costs
        contribution_margin_percent = (
            (contribution_margin_euro / net_revenue * Decimal('100'))
            if net_revenue > 0 else Decimal('0')
        )
        
        # 5. Calculate Break-Even Price
        break_even_price = self._calculate_break_even_price(cost_data)
        
        # 6. Calculate Recommended Minimum Price (20% margin)
        recommended_min_price = self._calculate_min_price(cost_data, target_margin=Decimal('0.20'))
        
        # Round values
        result = {
            'has_cost_data': True,
            'selling_price': float(selling_price_decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            'net_revenue': float(net_revenue.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            
            # Cost Breakdown
            'costs': {
                'purchase': float(cost_data.purchase_cost),
                'shipping': float(cost_data.shipping_cost),
                'packaging': float(cost_data.packaging_cost),
                'payment_fee': float(payment_fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                'total_variable': float(total_variable_costs.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            },
            
            # Margin Results
            'margin': {
                'euro': float(contribution_margin_euro.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                'percent': float(contribution_margin_percent.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            },
            
            # Reference Prices
            'break_even_price': float(break_even_price),
            'recommended_min_price': float(recommended_min_price),
            
            # Validation
            'is_above_break_even': selling_price_decimal >= break_even_price,
            'is_above_min_margin': contribution_margin_percent >= Decimal('20'),
            
            # Context
            'vat_rate': float(vat_rate * 100),  # as percentage
            'country_code': cost_data.country_code,
            'payment_provider': cost_data.payment_provider,
        }
        
        # Save to history if requested
        if save_to_history:
            self._save_to_history(
                db=db,
                product_id=product_id,
                shop_id=shop_id_str,  # Use normalized string
                selling_price=selling_price_decimal,
                net_revenue=net_revenue,
                cost_data=cost_data,
                payment_fee=payment_fee,
                total_variable_costs=total_variable_costs,
                contribution_margin_euro=contribution_margin_euro,
                contribution_margin_percent=contribution_margin_percent,
                break_even_price=break_even_price,
                recommended_min_price=recommended_min_price,
                triggered_by=triggered_by
            )
        
        logger.info(f"""
        📊 MARGIN CALCULATION: Product {product_id}
           Selling Price: €{result['selling_price']:.2f}
           Margin: €{result['margin']['euro']:.2f} ({result['margin']['percent']:.1f}%)
           Break-Even: €{result['break_even_price']:.2f}
           Status: {'✅ Profitable' if result['is_above_break_even'] else '❌ Below Break-Even'}
        """)
        
        return result
    
    
    def _calculate_break_even_price(self, cost_data: ProductCost) -> Decimal:
        """
        Calculate break-even price (0% margin)
        
        Formula:
        break_even = (purchase + shipping + packaging + fixed_fee) * (1 + vat_rate) / 
                     (1 - payment_fee_percentage)
        """
        
        # Base costs (excluding payment fee which depends on price)
        base_costs = (
            cost_data.purchase_cost +
            cost_data.shipping_cost +
            cost_data.packaging_cost
        )
        
        # Get payment config
        payment_config = self.PAYMENT_PROVIDERS.get(
            cost_data.payment_provider,
            self.PAYMENT_PROVIDERS['stripe']
        )
        
        # Fixed fee (needs to be added to numerator)
        fixed_fee = payment_config['fixed']
        
        # Payment percentage (as decimal, e.g., 0.029 for 2.9%)
        payment_pct = payment_config['percentage'] / Decimal('100')
        
        # VAT rate (e.g., 0.19 for 19%)
        vat_rate = cost_data.vat_rate
        
        # Break-even formula accounting for VAT and payment fees
        # break_even_gross = (base_costs + fixed_fee) * (1 + vat_rate) / (1 - payment_pct)
        numerator = (base_costs + fixed_fee) * (Decimal('1') + vat_rate)
        denominator = Decimal('1') - payment_pct
        
        if denominator <= 0:
            logger.error("Invalid payment percentage - denominator <= 0")
            return base_costs * (Decimal('1') + vat_rate)
        
        break_even_price = numerator / denominator
        
        return break_even_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    
    def _calculate_min_price(
        self,
        cost_data: ProductCost,
        target_margin: Decimal = Decimal('0.20')
    ) -> Decimal:
        """
        Calculate minimum recommended price for target margin
        
        Args:
            cost_data: ProductCost object
            target_margin: Target margin as decimal (0.20 = 20%)
        
        Returns:
            Minimum price to achieve target margin
        """
        
        # Base costs
        base_costs = (
            cost_data.purchase_cost +
            cost_data.shipping_cost +
            cost_data.packaging_cost
        )
        
        # Payment config
        payment_config = self.PAYMENT_PROVIDERS.get(
            cost_data.payment_provider,
            self.PAYMENT_PROVIDERS['stripe']
        )
        fixed_fee = payment_config['fixed']
        payment_pct = payment_config['percentage'] / Decimal('100')
        
        # VAT rate
        vat_rate = cost_data.vat_rate
        
        # Formula: min_price = (base_costs + fixed_fee) * (1 + vat_rate) / ((1 - payment_pct) * (1 - target_margin))
        numerator = (base_costs + fixed_fee) * (Decimal('1') + vat_rate)
        denominator = (Decimal('1') - payment_pct) * (Decimal('1') - target_margin)
        
        if denominator <= 0:
            logger.error("Invalid calculation - denominator <= 0")
            return base_costs * (Decimal('1') + vat_rate) * Decimal('1.25')  # Fallback
        
        min_price = numerator / denominator
        
        return min_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    
    def validate_price_recommendation(
        self,
        product_id: str,
        shop_id: str,
        recommended_price: float
    ) -> Dict:
        """
        Validate if a recommended price is profitable
        
        Returns:
            {
                'is_safe': bool,
                'margin': float,
                'warning': str or None,
                'message': str,
                'details': Dict
            }
        """
        
        # Calculate margin at recommended price
        margin_result = self.calculate_margin(
            product_id=product_id,
            shop_id=shop_id,
            selling_price=recommended_price,
            save_to_history=False  # Don't save validation checks
        )
        
        if not margin_result.get('has_cost_data'):
            return {
                'is_safe': False,
                'margin': None,
                'warning': 'NO_COST_DATA',
                'message': 'Keine Kostendaten hinterlegt - bitte ergänzen',
                'details': margin_result
            }
        
        # Validation checks
        is_above_break_even = margin_result['is_above_break_even']
        is_above_min_margin = margin_result['is_above_min_margin']
        margin_percent = margin_result['margin']['percent']
        
        # Determine safety and warnings
        if not is_above_break_even:
            return {
                'is_safe': False,
                'margin': margin_percent,
                'warning': 'BELOW_BREAK_EVEN',
                'message': f'❌ KRITISCH: Preis liegt unter Break-Even (€{margin_result["break_even_price"]:.2f})! Du würdest Verlust machen.',
                'details': margin_result
            }
        
        elif not is_above_min_margin:
            return {
                'is_safe': True,  # Profitable, but warning
                'margin': margin_percent,
                'warning': 'LOW_MARGIN',
                'message': f'⚠️ Niedrige Marge: {margin_percent:.1f}% (Empfohlen: >20%). Trotzdem anwenden?',
                'details': margin_result
            }
        
        else:
            return {
                'is_safe': True,
                'margin': margin_percent,
                'warning': None,
                'message': f'✅ Gesunde Marge: {margin_percent:.1f}%',
                'details': margin_result
            }
    
    
    # ==========================================
    # COST MANAGEMENT
    # ==========================================
    
    def save_product_costs(
        self,
        product_id: str,
        shop_id: str,
        purchase_cost: float,
        shipping_cost: float = 0.0,
        packaging_cost: float = 0.0,
        payment_provider: str = 'stripe',
        payment_fee_percentage: Optional[float] = None,
        payment_fee_fixed: Optional[float] = None,
        country_code: str = 'DE',
        category: Optional[str] = None
    ) -> ProductCost:
        """
        Save or update cost data for a product
        """
        
        db = self._get_db()
        
        # Normalize shop_id to string (handle "demo" → "999")
        shop_id_str = str(shop_id) if shop_id else "999"
        if shop_id_str.lower() == "demo" or not shop_id_str.isdigit():
            shop_id_str = "999"
        
        # Get or create cost record
        cost_record = db.query(ProductCost).filter(
            and_(
                ProductCost.product_id == product_id,
                ProductCost.shop_id == shop_id_str  # String (matches DB schema)
            )
        ).first()
        
        # Get payment provider config
        provider_config = self.PAYMENT_PROVIDERS.get(payment_provider, self.PAYMENT_PROVIDERS['stripe'])
        
        # Use defaults if not provided
        if payment_fee_percentage is None:
            payment_fee_percentage = float(provider_config['percentage'])
        if payment_fee_fixed is None:
            payment_fee_fixed = float(provider_config['fixed'])
        
        # Get VAT rate
        vat_rate = float(self.VAT_RATES.get(country_code, self.VAT_RATES['DE']))
        
        if cost_record:
            # Update existing
            cost_record.purchase_cost = Decimal(str(purchase_cost))
            cost_record.shipping_cost = Decimal(str(shipping_cost))
            cost_record.packaging_cost = Decimal(str(packaging_cost))
            cost_record.payment_provider = payment_provider
            cost_record.payment_fee_percentage = Decimal(str(payment_fee_percentage))
            cost_record.payment_fee_fixed = Decimal(str(payment_fee_fixed))
            cost_record.vat_rate = Decimal(str(vat_rate))
            cost_record.country_code = country_code
            cost_record.category = category
            cost_record.last_updated = datetime.utcnow()
        else:
            # Create new
            cost_record = ProductCost(
                product_id=product_id,
                shop_id=shop_id_str,  # Use normalized string
                purchase_cost=Decimal(str(purchase_cost)),
                shipping_cost=Decimal(str(shipping_cost)),
                packaging_cost=Decimal(str(packaging_cost)),
                payment_provider=payment_provider,
                payment_fee_percentage=Decimal(str(payment_fee_percentage)),
                payment_fee_fixed=Decimal(str(payment_fee_fixed)),
                vat_rate=Decimal(str(vat_rate)),
                country_code=country_code,
                category=category
            )
            db.add(cost_record)
        
        db.commit()
        db.refresh(cost_record)
        
        logger.info(f"✅ Saved costs for product {product_id}: EK €{purchase_cost}, Shipping €{shipping_cost}")
        
        return cost_record
    
    
    def get_product_costs(self, product_id: str, shop_id: str) -> Optional[ProductCost]:
        """Get cost data for a product"""
        db = self._get_db()
        
        # Normalize shop_id to string (handle "demo" → "999")
        shop_id_str = str(shop_id) if shop_id else "999"
        if shop_id_str.lower() == "demo" or not shop_id_str.isdigit():
            shop_id_str = "999"
        
        return db.query(ProductCost).filter(
            and_(
                ProductCost.product_id == product_id,
                ProductCost.shop_id == shop_id_str  # String (matches DB schema)
            )
        ).first()
    
    
    def has_cost_data(self, product_id: str, shop_id: str) -> bool:
        """Check if product has cost data"""
        return self.get_product_costs(product_id, shop_id) is not None
    
    
    # ==========================================
    # HISTORY & ANALYTICS
    # ==========================================
    
    def _save_to_history(
        self,
        db: Session,
        product_id: str,
        shop_id: str,
        selling_price: Decimal,
        net_revenue: Decimal,
        cost_data: ProductCost,
        payment_fee: Decimal,
        total_variable_costs: Decimal,
        contribution_margin_euro: Decimal,
        contribution_margin_percent: Decimal,
        break_even_price: Decimal,
        recommended_min_price: Decimal,
        triggered_by: str
    ):
        """Save calculation to history table"""
        
        history_record = MarginCalculation(
            product_id=product_id,
            shop_id=shop_id,
            selling_price=selling_price,
            net_revenue=net_revenue,
            purchase_cost=cost_data.purchase_cost,
            shipping_cost=cost_data.shipping_cost,
            packaging_cost=cost_data.packaging_cost,
            payment_fee=payment_fee,
            total_variable_costs=total_variable_costs,
            contribution_margin_euro=contribution_margin_euro,
            contribution_margin_percent=contribution_margin_percent,
            break_even_price=break_even_price,
            recommended_min_price=recommended_min_price,
            triggered_by=triggered_by
        )
        
        db.add(history_record)
        db.commit()
    
    
    def get_margin_history(
        self,
        product_id: str,
        shop_id: str,
        days: int = 30
    ) -> List[Dict]:
        """
        Get margin history for a product
        Used for trend charts
        """
        
        db = self._get_db()
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Normalize shop_id to string (handle "demo" → "999")
        shop_id_str = str(shop_id) if shop_id else "999"
        if shop_id_str.lower() == "demo" or not shop_id_str.isdigit():
            shop_id_str = "999"
        
        history = db.query(MarginCalculation).filter(
            and_(
                MarginCalculation.product_id == product_id,
                MarginCalculation.shop_id == shop_id_str,  # String (matches DB schema)
                MarginCalculation.calculation_date >= since_date
            )
        ).order_by(desc(MarginCalculation.calculation_date)).all()
        
        return [
            {
                'date': record.calculation_date.isoformat(),
                'selling_price': float(record.selling_price),
                'margin_euro': float(record.contribution_margin_euro),
                'margin_percent': float(record.contribution_margin_percent),
                'triggered_by': record.triggered_by
            }
            for record in history
        ]
    
    
    # ==========================================
    # CATEGORY DEFAULTS
    # ==========================================
    
    def get_category_defaults(self, category: str) -> Dict:
        """
        Get default values for a product category
        Used for quick onboarding
        """
        
        defaults = self.CATEGORY_DEFAULTS.get(
            category.lower(),
            self.CATEGORY_DEFAULTS['fashion']  # Fallback
        )
        
        return {
            'category': category,
            'typical_margin': float(defaults['typical_margin']),
            'shipping_estimate': float(defaults['shipping_estimate']),
            'packaging_estimate': float(defaults['packaging_estimate']),
        }
    
    
    def estimate_costs_from_price(
        self,
        selling_price: float,
        category: str,
        country_code: str = 'DE'
    ) -> Dict:
        """
        Reverse-engineer costs from selling price and category
        Used for quick setup
        
        Example: "Ich verkaufe Fashion für €99, was sind typische Kosten?"
        """
        
        defaults = self.CATEGORY_DEFAULTS.get(
            category.lower(),
            self.CATEGORY_DEFAULTS['fashion']
        )
        
        # Estimate purchase cost based on typical margin
        typical_margin = defaults['typical_margin']
        
        # Simple estimation (not perfect, but good enough for onboarding)
        estimated_purchase_cost = selling_price / (1 + float(typical_margin))
        
        return {
            'estimated_purchase_cost': round(estimated_purchase_cost, 2),
            'estimated_shipping_cost': float(defaults['shipping_estimate']),
            'estimated_packaging_cost': float(defaults['packaging_estimate']),
            'category': category,
            'note': 'Diese Werte sind Schätzungen. Bitte mit echten Daten ersetzen.'
        }

