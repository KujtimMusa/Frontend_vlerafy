"""Add OAuth fields to Shop model

Revision ID: add_oauth_fields_to_shop
Revises: add_margin_calculator
Create Date: 2025-01-20 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_oauth_fields_to_shop'
down_revision = 'add_margin_calculator'
branch_labels = None
depends_on = None


def upgrade():
    # Prüfe ob shops Tabelle existiert
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'shops' not in tables:
        # Tabelle existiert nicht - sollte nicht passieren, aber sicherheitshalber
        return
    
    # Hole bestehende Spalten
    columns = [col['name'] for col in inspector.get_columns('shops')]
    
    # 1. Ändere access_token von nullable=False zu nullable=True
    if 'access_token' in columns:
        # Prüfe ob bereits nullable
        access_token_col = next(col for col in inspector.get_columns('shops') if col['name'] == 'access_token')
        if not access_token_col['nullable']:
            op.alter_column('shops', 'access_token',
                          existing_type=sa.String(),
                          nullable=True)
    
    # 2. Füge scope Spalte hinzu (falls nicht vorhanden)
    if 'scope' not in columns:
        op.add_column('shops', sa.Column('scope', sa.String(), nullable=True))
    
    # 3. Füge installed_at Spalte hinzu (falls nicht vorhanden)
    if 'installed_at' not in columns:
        op.add_column('shops', sa.Column('installed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    # Entferne installed_at Spalte
    op.drop_column('shops', 'installed_at')
    
    # Entferne scope Spalte
    op.drop_column('shops', 'scope')
    
    # Setze access_token zurück auf nullable=False (Vorsicht: kann Datenverlust verursachen!)
    # Nur wenn keine NULL-Werte vorhanden sind
    op.execute("""
        UPDATE shops 
        SET access_token = '' 
        WHERE access_token IS NULL
    """)
    op.alter_column('shops', 'access_token',
                  existing_type=sa.String(),
                  nullable=False)

