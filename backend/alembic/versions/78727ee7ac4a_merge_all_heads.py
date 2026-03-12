"""merge_all_heads

Revision ID: 78727ee7ac4a
Revises: create_demo_shop, add_waitlist_table
Create Date: 2026-03-12 16:07:23.182105

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '78727ee7ac4a'
down_revision = ('create_demo_shop', 'add_waitlist_table')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass



