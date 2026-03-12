"""Add sales_history table

Revision ID: add_sales_history
Revises: add_sales_30d_001
Create Date: 2026-01-13 19:52:55.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_sales_history'
down_revision = 'add_sales_30d_001'  # Latest revision
branch_labels = None
depends_on = None


def upgrade():
    """
    Erstellt sales_history Tabelle für persistente Sales-Daten Speicherung.
    Unterstützt Demo-Shop (shop_id=999, CSV) UND Live-Shop (Shopify).
    """
    op.create_table(
        'sales_history',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('shop_id', sa.Integer(), sa.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('sale_date', sa.Date(), nullable=False, index=True),
        sa.Column('quantity_sold', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('revenue', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('unit_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('order_id', sa.String(255), nullable=True, index=True),  # NULLABLE für CSV Demo-Daten!
        sa.Column('variant_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()'), nullable=True),
        sa.Column('meta_data', postgresql.JSONB, nullable=True),
        
        # Constraints
        # UniqueConstraint: Für Live-Shop (mit order_id) und Demo-Shop (ohne order_id)
        # PostgreSQL behandelt NULL in Unique Constraints als unterschiedlich, daher separate Constraints
        sa.CheckConstraint('quantity_sold >= 0', name='ck_quantity_positive'),
        sa.CheckConstraint('revenue >= 0', name='ck_revenue_positive'),
    )
    
    # Indexes für Performance
    op.create_index('idx_sales_product_date', 'sales_history', ['product_id', 'sale_date'], unique=False)
    op.create_index('idx_sales_shop_date', 'sales_history', ['shop_id', 'sale_date'], unique=False)
    op.create_index('idx_sales_date_range', 'sales_history', ['sale_date'], unique=False)
    op.create_index('idx_sales_demo_shop', 'sales_history', ['shop_id', 'sale_date'], 
                    unique=False, postgresql_where=sa.text('shop_id = 999'))
    
    # Unique Constraints: Separate für Live (mit order_id) und Demo (ohne order_id)
    # Für Live-Shop: Verhindere Duplikate mit order_id
    op.create_index('idx_sales_unique_live', 'sales_history', 
                    ['product_id', 'shop_id', 'sale_date', 'order_id'], 
                    unique=True, 
                    postgresql_where=sa.text('order_id IS NOT NULL'))
    
    # Für Demo-Shop: Verhindere Duplikate ohne order_id (tägliche Aggregation)
    op.create_index('idx_sales_unique_demo', 'sales_history', 
                    ['product_id', 'shop_id', 'sale_date'], 
                    unique=True, 
                    postgresql_where=sa.text('order_id IS NULL'))
    
    print("OK: Created sales_history table with indexes and constraints")


def downgrade():
    """Rollback: Entfernt sales_history Tabelle"""
    op.drop_index('idx_sales_unique_demo', table_name='sales_history')
    op.drop_index('idx_sales_unique_live', table_name='sales_history')
    op.drop_index('idx_sales_demo_shop', table_name='sales_history')
    op.drop_index('idx_sales_date_range', table_name='sales_history')
    op.drop_index('idx_sales_shop_date', table_name='sales_history')
    op.drop_index('idx_sales_product_date', table_name='sales_history')
    op.drop_table('sales_history')
    print("OK: Dropped sales_history table")
