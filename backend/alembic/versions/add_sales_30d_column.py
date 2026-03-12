"""add sales_30d column to recommendations

Revision ID: add_sales_30d_001
Revises: add_recommendation_metrics
Create Date: 2026-01-01 16:40:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_sales_30d_001'
down_revision = 'add_oauth_fields_to_shop'  # Latest revision
branch_labels = None
depends_on = None

def upgrade():
    # Add sales_30d column
    op.add_column(
        'recommendations',
        sa.Column('sales_30d', sa.Integer(), nullable=True)
    )
    print("✅ Added sales_30d column to recommendations table")

def downgrade():
    # Remove sales_30d column
    op.drop_column('recommendations', 'sales_30d')

