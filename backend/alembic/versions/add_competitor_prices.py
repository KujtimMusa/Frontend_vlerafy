"""Add competitor_prices table

Revision ID: add_competitor_prices
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_competitor_prices'
down_revision = '001_initial_tables'  # Nach initial tables
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'competitor_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('competitor_name', sa.String(length=255), nullable=False),
        sa.Column('competitor_url', sa.String(length=512), nullable=False),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('in_stock', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('scrape_success', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('last_error', sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_competitor_prices_id'), 'competitor_prices', ['id'], unique=False)
    op.create_index(op.f('ix_competitor_prices_product_id'), 'competitor_prices', ['product_id'], unique=False)
    op.create_index(op.f('ix_competitor_prices_scraped_at'), 'competitor_prices', ['scraped_at'], unique=False)
    op.create_index('idx_product_scraped', 'competitor_prices', ['product_id', 'scraped_at'], unique=False)


def downgrade():
    op.drop_index('idx_product_scraped', table_name='competitor_prices')
    op.drop_index(op.f('ix_competitor_prices_scraped_at'), table_name='competitor_prices')
    op.drop_index(op.f('ix_competitor_prices_product_id'), table_name='competitor_prices')
    op.drop_index(op.f('ix_competitor_prices_id'), table_name='competitor_prices')
    op.drop_table('competitor_prices')










