"""Enhance recommendation model with ML and status tracking

Revision ID: enhance_recommendation
Revises: add_price_history
Create Date: 2026-01-13 20:34:58.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'enhance_recommendation'
down_revision = 'add_price_history'
branch_labels = None
depends_on = None


def upgrade():
    """Erweitert recommendations Tabelle"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'recommendations' not in tables:
        # Erstelle Tabelle komplett
        op.create_table(
            'recommendations',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('shop_id', sa.Integer(), sa.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('is_demo', sa.Boolean(), nullable=False, server_default='false', index=True),
            sa.Column('current_price', sa.Float(), nullable=True),
            sa.Column('recommended_price', sa.Float(), nullable=False),
            sa.Column('price_change_pct', sa.Float(), nullable=True),
            sa.Column('strategy', sa.String(100), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=True),
            sa.Column('reasoning', sa.Text(), nullable=True),
            sa.Column('demand_growth', sa.Float(), nullable=True),
            sa.Column('days_of_stock', sa.Float(), nullable=True),
            sa.Column('sales_7d', sa.Integer(), nullable=True),
            sa.Column('competitor_avg_price', sa.Float(), nullable=True),
            sa.Column('base_confidence', sa.Float(), nullable=True),
            sa.Column('ml_confidence', sa.Float(), nullable=True),
            sa.Column('ml_detector_confidence', sa.Float(), nullable=True),
            sa.Column('meta_labeler_confidence', sa.Float(), nullable=True),
            sa.Column('meta_labeler_approved', sa.Boolean(), nullable=True, server_default='true'),
            sa.Column('status', sa.String(50), nullable=True, server_default='pending', index=True),
            sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True, index=True),
            sa.Column('applied_price', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, index=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()'), nullable=True),
            sa.Column('meta_data', postgresql.JSONB, nullable=True),
        )
        op.create_index('idx_recommendation_product_created', 'recommendations', ['product_id', 'created_at'], unique=False)
        op.create_index('idx_recommendation_shop_status', 'recommendations', ['shop_id', 'status'], unique=False)
    else:
        # Füge nur fehlende Spalten hinzu
        columns = [col['name'] for col in inspector.get_columns('recommendations')]
        
        if 'base_confidence' not in columns:
            op.add_column('recommendations', sa.Column('base_confidence', sa.Float(), nullable=True))
        if 'ml_confidence' not in columns:
            op.add_column('recommendations', sa.Column('ml_confidence', sa.Float(), nullable=True))
        if 'ml_detector_confidence' not in columns:
            op.add_column('recommendations', sa.Column('ml_detector_confidence', sa.Float(), nullable=True))
        if 'meta_labeler_confidence' not in columns:
            op.add_column('recommendations', sa.Column('meta_labeler_confidence', sa.Float(), nullable=True))
        if 'meta_labeler_approved' not in columns:
            op.add_column('recommendations', sa.Column('meta_labeler_approved', sa.Boolean(), nullable=True, server_default='true'))
        if 'status' not in columns:
            op.add_column('recommendations', sa.Column('status', sa.String(50), nullable=True, server_default='pending'))
        if 'applied_at' not in columns:
            op.add_column('recommendations', sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True))
        if 'applied_price' not in columns:
            op.add_column('recommendations', sa.Column('applied_price', sa.Float(), nullable=True))
        if 'updated_at' not in columns:
            op.add_column('recommendations', sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()'), nullable=True))
        if 'meta_data' not in columns:
            op.add_column('recommendations', sa.Column('meta_data', postgresql.JSONB, nullable=True))
        
        try:
            op.create_index('idx_recommendation_product_created', 'recommendations', ['product_id', 'created_at'], unique=False)
        except:
            pass
        try:
            op.create_index('idx_recommendation_shop_status', 'recommendations', ['shop_id', 'status'], unique=False)
        except:
            pass
        
        op.execute("UPDATE recommendations SET status = 'pending' WHERE status IS NULL")
    
    print("OK: Enhanced recommendations table with ML and status tracking")


def downgrade():
    """Rollback"""
    try:
        op.drop_index('idx_recommendation_shop_status', table_name='recommendations')
        op.drop_index('idx_recommendation_product_created', table_name='recommendations')
    except:
        pass
    
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'recommendations' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('recommendations')]
        
        if 'meta_data' in columns:
            op.drop_column('recommendations', 'meta_data')
        if 'updated_at' in columns:
            op.drop_column('recommendations', 'updated_at')
        if 'applied_price' in columns:
            op.drop_column('recommendations', 'applied_price')
        if 'applied_at' in columns:
            op.drop_column('recommendations', 'applied_at')
        if 'status' in columns:
            op.drop_column('recommendations', 'status')
        if 'meta_labeler_approved' in columns:
            op.drop_column('recommendations', 'meta_labeler_approved')
        if 'meta_labeler_confidence' in columns:
            op.drop_column('recommendations', 'meta_labeler_confidence')
        if 'ml_detector_confidence' in columns:
            op.drop_column('recommendations', 'ml_detector_confidence')
        if 'ml_confidence' in columns:
            op.drop_column('recommendations', 'ml_confidence')
        if 'base_confidence' in columns:
            op.drop_column('recommendations', 'base_confidence')
