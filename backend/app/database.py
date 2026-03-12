from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config_helper import get_database_url
import logging
import os

logger = logging.getLogger(__name__)

# Lade DATABASE_URL sicher mit Encoding-Fixes
SQLALCHEMY_DATABASE_URL = get_database_url()

# Create engine with encoding fix and connection pooling
# WICHTIG: Nutze URL direkt, psycopg2 kann mit Encoding-Problemen umgehen
try:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={
            "options": "-c client_encoding=utf8"
        },
        pool_pre_ping=True,  # Testet Connection vor Verwendung
        pool_size=10,  # Connection Pool Size
        max_overflow=20  # Max zusätzliche Connections
    )
except Exception as e:
    logger.error(f"Fehler beim Erstellen der Engine: {e}")
    # Fallback: Nutze minimale Config
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Log successful connection
logger.info("Database connected")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()










