"""Add margin calculator tables

Revision ID: add_margin_calculator
Revises: add_recommendation_metrics
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_margin_calculator'
down_revision = 'add_recommendation_metrics'
branch_labels = None
depends_on = None


def upgrade():
    # Table: product_costs
    op.create_table(
        'product_costs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('product_id', sa.String(255), nullable=False),
        sa.Column('shop_id', sa.String(255), nullable=False),
        
        # Cost Components
        sa.Column('purchase_cost', sa.Numeric(10, 2), nullable=False, comment='Einkaufspreis netto in €'),
        sa.Column('shipping_cost', sa.Numeric(10, 2), server_default='0.00', comment='Versandkosten pro Einheit'),
        sa.Column('packaging_cost', sa.Numeric(10, 2), server_default='0.00', comment='Verpackungskosten pro Einheit'),
        
        # Payment Provider Settings
        sa.Column('payment_provider', sa.String(50), server_default='stripe', comment='stripe, paypal, klarna, custom'),
        sa.Column('payment_fee_percentage', sa.Numeric(5, 3), server_default='2.900', comment='z.B. 2.9 für 2.9%'),
        sa.Column('payment_fee_fixed', sa.Numeric(10, 2), server_default='0.30', comment='Fixe Fee in € z.B. 0.30'),
        
        # VAT Settings
        sa.Column('vat_rate', sa.Numeric(5, 3), server_default='0.190', comment='MwSt-Satz z.B. 0.19 für 19%'),
        sa.Column('country_code', sa.String(2), server_default='DE', comment='DE, AT, CH, US, GB'),
        
        # Metadata
        sa.Column('category', sa.String(100), nullable=True, comment='fashion, electronics, beauty, etc.'),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Create indexes
    op.create_index('ix_product_costs_product_id', 'product_costs', ['product_id'])
    op.create_index('ix_product_costs_shop_id', 'product_costs', ['shop_id'])
    op.create_index('ix_product_costs_shop_category', 'product_costs', ['shop_id', 'category'])
    
    # Create unique constraint
    op.create_unique_constraint('uq_product_costs_product_shop', 'product_costs', ['product_id', 'shop_id'])
    
    # Create check constraints
    op.create_check_constraint('ck_purchase_cost_positive', 'product_costs', 'purchase_cost >= 0')
    op.create_check_constraint('ck_shipping_cost_positive', 'product_costs', 'shipping_cost >= 0')
    op.create_check_constraint('ck_packaging_cost_positive', 'product_costs', 'packaging_cost >= 0')
    
    # Table: margin_calculations (History/Audit Trail)
    op.create_table(
        'margin_calculations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('product_id', sa.String(255), nullable=False),
        sa.Column('shop_id', sa.String(255), nullable=False),
        sa.Column('calculation_date', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        # Pricing Data
        sa.Column('selling_price', sa.Numeric(10, 2), nullable=False, comment='Verkaufspreis brutto'),
        sa.Column('net_revenue', sa.Numeric(10, 2), nullable=False, comment='Nettoerlös nach MwSt'),
        
        # Cost Breakdown
        sa.Column('purchase_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('shipping_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('packaging_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('payment_fee', sa.Numeric(10, 2), nullable=False),
        sa.Column('total_variable_costs', sa.Numeric(10, 2), nullable=False),
        
        # Margin Results
        sa.Column('contribution_margin_euro', sa.Numeric(10, 2), nullable=False, comment='DB I in €'),
        sa.Column('contribution_margin_percent', sa.Numeric(5, 2), nullable=False, comment='DB I in %'),
        
        # Reference Data
        sa.Column('break_even_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('recommended_min_price', sa.Numeric(10, 2), nullable=False, comment='Bei 20% Mindestmarge'),
        
        # Context
        sa.Column('triggered_by', sa.String(100), nullable=True, comment='pricing_engine, manual, autopilot'),
        sa.Column('calculation_metadata', postgresql.JSONB, nullable=True, comment='Additional context'),
    )
    
    # Create indexes for margin_calculations
    op.create_index('ix_margin_calc_product_id', 'margin_calculations', ['product_id'])
    op.create_index('ix_margin_calc_shop_id', 'margin_calculations', ['shop_id'])
    op.create_index('ix_margin_calc_calculation_date', 'margin_calculations', ['calculation_date'])
    op.create_index('ix_margin_calc_product_date', 'margin_calculations', ['product_id', 'calculation_date'])


def downgrade():
    op.drop_index('ix_margin_calc_product_date', 'margin_calculations')
    op.drop_index('ix_margin_calc_calculation_date', 'margin_calculations')
    op.drop_index('ix_margin_calc_shop_id', 'margin_calculations')
    op.drop_index('ix_margin_calc_product_id', 'margin_calculations')
    op.drop_table('margin_calculations')
    
    op.drop_check_constraint('ck_packaging_cost_positive', 'product_costs')
    op.drop_check_constraint('ck_shipping_cost_positive', 'product_costs')
    op.drop_check_constraint('ck_purchase_cost_positive', 'product_costs')
    op.drop_constraint('uq_product_costs_product_shop', 'product_costs', type_='unique')
    op.drop_index('ix_product_costs_shop_category', 'product_costs')
    op.drop_index('ix_product_costs_shop_id', 'product_costs')
    op.drop_index('ix_product_costs_product_id', 'product_costs')
    op.drop_table('product_costs')






























