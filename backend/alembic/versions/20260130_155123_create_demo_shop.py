"""Create Demo Shop (id=999) in database

Revision ID: create_demo_shop
Revises: enhance_recommendation
Create Date: 2026-01-30 15:51:23.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = 'create_demo_shop'
down_revision = 'enhance_recommendation'
branch_labels = None
depends_on = None


def upgrade():
    """
    Erstellt Demo Shop (id=999) in shops Tabelle.
    
    WICHTIG: Demo Shop wird benötigt für:
    - Price History Foreign Key Constraint
    - Recommendations mit shop_id=999
    - Sales History mit shop_id=999
    
    Demo Shop hat:
    - id=999
    - shop_url="demo.vlerafy.com" (NOT NULL Constraint erfordert Wert)
    - shop_name="Demo Shop"
    - is_active=True
    - access_token=None (nullable)
    """
    conn = op.get_bind()
    
    # Prüfe ob Demo Shop bereits existiert
    result = conn.execute(text("SELECT id FROM shops WHERE id = 999"))
    existing = result.fetchone()
    
    if existing:
        # Demo Shop existiert bereits - überspringe
        print("✅ Demo Shop (id=999) existiert bereits - überspringe")
        return
    
    # Erstelle Demo Shop
    # WICHTIG: shop_url ist NOT NULL, daher muss ein Wert gesetzt werden
    conn.execute(text("""
        INSERT INTO shops (id, shop_url, shop_name, is_active, access_token, created_at)
        VALUES (
            999,
            'demo.vlerafy.com',
            'Demo Shop',
            true,
            NULL,
            NOW()
        )
        ON CONFLICT (id) DO NOTHING
    """))
    
    print("✅ Demo Shop (id=999) erfolgreich erstellt")


def downgrade():
    """
    Entfernt Demo Shop aus DB.
    WICHTIG: Kann Foreign Key Errors verursachen wenn Price History/Recommendations existieren!
    """
    conn = op.get_bind()
    
    # Prüfe ob Demo Shop existiert
    result = conn.execute(text("SELECT id FROM shops WHERE id = 999"))
    existing = result.fetchone()
    
    if not existing:
        print("Demo Shop (id=999) existiert nicht - überspringe")
        return
    
    # WICHTIG: Lösche zuerst abhängige Daten (optional, kann auch übersprungen werden)
    # Price History
    conn.execute(text("DELETE FROM price_history WHERE shop_id = 999"))
    
    # Recommendations
    conn.execute(text("DELETE FROM recommendations WHERE shop_id = 999"))
    
    # Sales History
    conn.execute(text("DELETE FROM sales_history WHERE shop_id = 999"))
    
    # Products (falls vorhanden)
    conn.execute(text("DELETE FROM products WHERE shop_id = 999"))
    
    # Lösche Demo Shop
    conn.execute(text("DELETE FROM shops WHERE id = 999"))
    
    print("✅ Demo Shop (id=999) und abhängige Daten entfernt")
