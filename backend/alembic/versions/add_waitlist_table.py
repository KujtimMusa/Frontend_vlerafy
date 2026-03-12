"""Add waitlist_subscribers table

Revision ID: add_waitlist_table
Revises: add_margin_calculator
Create Date: 2026-01-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_waitlist_table'
down_revision = 'add_margin_calculator'
branch_labels = None
depends_on = None


def upgrade():
    # Table: waitlist_subscribers
    op.create_table(
        'waitlist_subscribers',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('source', sa.String(100), nullable=True, comment='z.B. "landing", "admin", "referral"'),
        sa.Column('extra_data', postgresql.JSON, nullable=True, comment='Für zukünftige Erweiterungen (z.B. Referrer, UTM-Parameter)'),
    )
    
    # Create indexes
    op.create_index('ix_waitlist_subscribers_email', 'waitlist_subscribers', ['email'], unique=True)
    op.create_index('ix_waitlist_subscribers_created_at', 'waitlist_subscribers', ['created_at'])


def downgrade():
    op.drop_index('ix_waitlist_subscribers_created_at', 'waitlist_subscribers')
    op.drop_index('ix_waitlist_subscribers_email', 'waitlist_subscribers')
    op.drop_table('waitlist_subscribers')
