from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # Database - WICHTIG: Wird überschrieben von get_database_url() in database.py
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/vlerafy"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Shopify Public App OAuth Configuration
    SHOPIFY_CLIENT_ID: str = ""  # OAuth Client ID from Shopify Partner Dashboard
    SHOPIFY_CLIENT_SECRET: str = ""  # OAuth Client Secret from Shopify Partner Dashboard
    SHOPIFY_API_SCOPES: str = "read_products,write_products"
    SHOPIFY_REDIRECT_URI: str = "https://api.vlerafy.com/auth/shopify/callback"
    SHOPIFY_APP_URL: str = "https://api.vlerafy.com"
    SHOPIFY_APP_NAME: str = "Vlerafy"
    SHOPIFY_API_VERSION: str = "2025-10"
    
    # Frontend URL (for OAuth redirects)
    FRONTEND_URL: str = "https://vlerafy.com"
    
    # App
    APP_URL: str = "http://localhost:8000"
    ENVIRONMENT: str = "development"  # development | staging | production
    
    # Encryption (MUST be set via environment variable in production)
    ENCRYPTION_KEY: str = ""  # Will raise error if not set

    # Scraping / Competitor Discovery
    SCRAPINGANT_API_KEY: Optional[str] = None
    
    # Serper API (Google Shopping)
    SERPER_API_KEY: Optional[str] = "03747d151fc1c88012b79a24dc19c4397becbd3d"
    
    # JWT Configuration (MUST be set via environment variable in production)
    JWT_SECRET: str = ""  # Will use SECRET_KEY as fallback
    JWT_ALGORITHM: str = "HS256"
    
    # SMTP Configuration (IONOS)
    SMTP_HOST: str = "smtp.ionos.de"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    
    # Email Settings
    NOTIFICATION_EMAIL: str = "support@vlerafy.com"
    SMTP_FROM_EMAIL: str = "hello@vlerafy.com"
    SMTP_FROM_NAME: str = "Vlerafy"
    
    # ═══════════════════════════════════════════════════════════════
    # ML ENGINE FEATURE FLAGS
    # ═══════════════════════════════════════════════════════════════
    
    # Master switch: Enable new ML engine
    USE_NEW_ML_ENGINE: bool = False  # DEFAULT: OFF (safe!)
    
    # Gradual rollout percentage (0-100)
    # 0 = All traffic uses OLD engine
    # 50 = 50% traffic uses NEW, 50% uses OLD
    # 100 = All traffic uses NEW engine
    ML_ENGINE_ROLLOUT_PCT: int = 0  # DEFAULT: 0% (safe!)
    
    # Confidence threshold for ML predictions
    ML_CONFIDENCE_THRESHOLD: float = 0.6
    
    # Business constraints (can be overridden per request)
    ML_MIN_MARGIN_PCT: float = 0.15         # 15% minimum margin
    ML_MAX_PRICE_CHANGE_PCT: float = 0.20   # ±20% max price change
    ML_COMPETITOR_CEILING_PCT: float = 1.20 # Max 120% of competitor avg
    ML_PSYCHOLOGICAL_PRICING: bool = True    # .99 pricing
    
    class Config:
        env_file = ".env"
        case_sensitive = False  # Railway ENV-Vars sind uppercase
        extra = "ignore"  # Ignore extra environment variables


settings = Settings()
