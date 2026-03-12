"""Add price_history table

Revision ID: add_price_history
Revises: add_sales_history
Create Date: 2026-01-13 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_price_history'
down_revision = 'add_sales_history'
branch_labels = None
depends_on = None


def upgrade():
    """
    Erstellt price_history Tabelle für historisches Price-Tracking.
    Unterstützt Demo-Shop (shop_id=999) UND Live-Shop.
    Inkludiert PostgreSQL Trigger für automatisches Tracking.
    """
    
    # 1. Erstelle die Tabelle
    op.create_table(
        'price_history',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('shop_id', sa.Integer(), sa.ForeignKey('shops.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('price_date', sa.Date(), nullable=False, index=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('previous_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('price_change_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('triggered_by', sa.String(100), nullable=True),  # 'pricing_engine', 'manual', 'shopify_sync', 'recommendation'
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('meta_data', postgresql.JSONB, nullable=True),  # meta_data statt metadata!
        
        # Constraints
        sa.UniqueConstraint('product_id', 'shop_id', 'price_date', name='uq_price_history_unique'),
        sa.CheckConstraint('price > 0', name='ck_price_positive'),
    )
    
    # 2. Erstelle Indexes für Performance
    op.create_index('idx_price_product_date', 'price_history', ['product_id', 'price_date'], unique=False)
    op.create_index('idx_price_shop_date', 'price_history', ['shop_id', 'price_date'], unique=False)
    
    # 3. Erstelle PostgreSQL Trigger für automatisches Tracking
    # Wird aufgerufen wenn Product.price geändert wird
    op.execute("""
        CREATE OR REPLACE FUNCTION track_price_change()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Nur tracken wenn Preis sich geändert hat
            IF OLD.price IS DISTINCT FROM NEW.price THEN
                INSERT INTO price_history (
                    product_id, 
                    shop_id, 
                    price_date, 
                    price, 
                    previous_price, 
                    price_change_pct, 
                    triggered_by, 
                    meta_data
                )
                VALUES (
                    NEW.id,
                    NEW.shop_id,
                    CURRENT_DATE,
                    NEW.price,
                    OLD.price,
                    CASE 
                        WHEN OLD.price > 0 THEN 
                            ((NEW.price - OLD.price) / OLD.price) * 100 
                        ELSE 
                            NULL 
                    END,
                    'product_update',
                    jsonb_build_object('updated_at', NEW.updated_at)
                )
                ON CONFLICT (product_id, shop_id, price_date) 
                DO UPDATE SET 
                    price = EXCLUDED.price,
                    previous_price = EXCLUDED.previous_price,
                    price_change_pct = EXCLUDED.price_change_pct;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER product_price_change_trigger
        AFTER UPDATE OF price ON products
        FOR EACH ROW
        EXECUTE FUNCTION track_price_change();
    """)
    
    print("OK: Created price_history table with indexes, constraints, and PostgreSQL trigger")


def downgrade():
    """Rollback: Entfernt price_history Tabelle und Trigger"""
    # Lösche Trigger und Funktion
    op.execute("DROP TRIGGER IF EXISTS product_price_change_trigger ON products")
    op.execute("DROP FUNCTION IF EXISTS track_price_change()")
    
    # Lösche Indexes
    op.drop_index('idx_price_shop_date', table_name='price_history')
    op.drop_index('idx_price_product_date', table_name='price_history')
    
    # Lösche Tabelle
    op.drop_table('price_history')
    print("OK: Dropped price_history table and trigger")
