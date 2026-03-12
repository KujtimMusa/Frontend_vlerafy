"""Add recommendation metrics and shop context columns

Revision ID: add_recommendation_metrics
Revises: add_competitor_prices
Create Date: 2025-01-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_recommendation_metrics'
down_revision = 'add_competitor_prices'  # Anpassen falls andere Migrationen existieren
branch_labels = None
depends_on = None


def upgrade():
    # Prüfe ob recommendations Tabelle existiert
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'recommendations' not in tables:
        # Erstelle Tabelle komplett neu
        op.create_table(
            'recommendations',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=False),
            sa.Column('shop_id', sa.Integer(), nullable=False),
            sa.Column('is_demo', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('current_price', sa.Float(), nullable=True),
            sa.Column('recommended_price', sa.Float(), nullable=False),
            sa.Column('price_change_pct', sa.Float(), nullable=True),
            sa.Column('strategy', sa.String(), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=True),
            sa.Column('reasoning', sa.Text(), nullable=True),
            sa.Column('demand_growth', sa.Float(), nullable=True),
            sa.Column('days_of_stock', sa.Float(), nullable=True),
            sa.Column('sales_7d', sa.Integer(), nullable=True),
            sa.Column('competitor_avg_price', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
    else:
        # Tabelle existiert - füge fehlende Spalten hinzu
        columns = [col['name'] for col in inspector.get_columns('recommendations')]
        
        # Shop Context Spalten
        if 'shop_id' not in columns:
            op.add_column('recommendations', sa.Column('shop_id', sa.Integer(), nullable=True))
            # Setze Default-Wert für bestehende Einträge (999 = Demo Shop)
            op.execute("UPDATE recommendations SET shop_id = 999 WHERE shop_id IS NULL")
            op.alter_column('recommendations', 'shop_id', nullable=False)
        
        if 'is_demo' not in columns:
            op.add_column('recommendations', sa.Column('is_demo', sa.Boolean(), nullable=True, server_default='false'))
            op.alter_column('recommendations', 'is_demo', nullable=False)
        
        # Metrics Spalten
        if 'demand_growth' not in columns:
            op.add_column('recommendations', sa.Column('demand_growth', sa.Float(), nullable=True))
        
        if 'days_of_stock' not in columns:
            op.add_column('recommendations', sa.Column('days_of_stock', sa.Float(), nullable=True))
        
        if 'sales_7d' not in columns:
            op.add_column('recommendations', sa.Column('sales_7d', sa.Integer(), nullable=True))
        
        if 'competitor_avg_price' not in columns:
            op.add_column('recommendations', sa.Column('competitor_avg_price', sa.Float(), nullable=True))
        
        # Pricing Spalten (falls fehlen)
        if 'current_price' not in columns:
            op.add_column('recommendations', sa.Column('current_price', sa.Float(), nullable=True))
        
        if 'price_change_pct' not in columns:
            op.add_column('recommendations', sa.Column('price_change_pct', sa.Float(), nullable=True))
        
        if 'applied_at' not in columns:
            op.add_column('recommendations', sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True))
    
    # Erstelle Indexes
    try:
        op.create_index('idx_shop_product', 'recommendations', ['shop_id', 'product_id'], unique=False)
    except:
        pass  # Index existiert bereits
    
    try:
        op.create_index('idx_shop_demo', 'recommendations', ['shop_id', 'is_demo'], unique=False)
    except:
        pass
    
    try:
        op.create_index('idx_product_created', 'recommendations', ['product_id', 'created_at'], unique=False)
    except:
        pass
    
    try:
        op.create_index(op.f('ix_recommendations_shop_id'), 'recommendations', ['shop_id'], unique=False)
    except:
        pass
    
    try:
        op.create_index(op.f('ix_recommendations_is_demo'), 'recommendations', ['is_demo'], unique=False)
    except:
        pass


def downgrade():
    # Entferne Indexes
    try:
        op.drop_index('idx_product_created', table_name='recommendations')
    except:
        pass
    
    try:
        op.drop_index('idx_shop_demo', table_name='recommendations')
    except:
        pass
    
    try:
        op.drop_index('idx_shop_product', table_name='recommendations')
    except:
        pass
    
    # Entferne Spalten (nur wenn Tabelle existiert)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'recommendations' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('recommendations')]
        
        if 'competitor_avg_price' in columns:
            op.drop_column('recommendations', 'competitor_avg_price')
        if 'sales_7d' in columns:
            op.drop_column('recommendations', 'sales_7d')
        if 'days_of_stock' in columns:
            op.drop_column('recommendations', 'days_of_stock')
        if 'demand_growth' in columns:
            op.drop_column('recommendations', 'demand_growth')
        if 'is_demo' in columns:
            op.drop_column('recommendations', 'is_demo')
        if 'shop_id' in columns:
            op.drop_column('recommendations', 'shop_id')
        if 'applied_at' in columns:
            op.drop_column('recommendations', 'applied_at')
        if 'price_change_pct' in columns:
            op.drop_column('recommendations', 'price_change_pct')
        if 'current_price' in columns:
            op.drop_column('recommendations', 'current_price')
































