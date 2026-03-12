"""
FastAPI Main Application
Complete setup with all routers including Margin Calculator
"""

# ============================================================================
# CRITICAL: BASIC IMPORTS FIRST (for environment variables)
# ============================================================================
import os
import sys

# ============================================================================
# CRITICAL: SENTRY INIT FIRST (before FastAPI app and logging)
# ============================================================================
# Initialize Sentry (silent, only print status)
try:
    from app.core.sentry_config import init_sentry
    init_sentry()
except Exception as e:
    # If Sentry init fails, log it but don't crash the app
    import traceback
    traceback.print_exc()

# ============================================================================
# CRITICAL: LOGGING SETUP (after Sentry, before other imports)
# ============================================================================
import logging
import time
from datetime import datetime

# ============================================================================
# STDOUT FIX für Railway
# ============================================================================
os.environ['PYTHONUNBUFFERED'] = '1'

# ============================================================================
# CUSTOM LOGGING HANDLER - Forces stdout + flush
# ============================================================================

class StdoutHandler(logging.StreamHandler):
    """Custom handler that writes directly to stdout with immediate flush"""
    def emit(self, record):
        try:
            msg = self.format(record)
            sys.stdout.write(msg + '\n')
            sys.stdout.flush()
        except Exception:
            self.handleError(record)

# Remove all existing handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Get log level from environment
log_level_str = os.getenv('LOG_LEVEL', 'DEBUG').upper()
log_level = getattr(logging, log_level_str, logging.DEBUG)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[StdoutHandler(sys.stdout)],
    force=True
)

# Reduce Uvicorn noise only
logging.getLogger('uvicorn').setLevel(logging.WARNING)
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
logging.getLogger('uvicorn.error').setLevel(logging.WARNING)

# Suppress urllib3 DEBUG logs (Sentry spam)
logging.getLogger('urllib3').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ============================================================================
# STARTUP BANNER
# ============================================================================
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
DATABASE_URL = os.getenv('DATABASE_URL')
SERPER_API_KEY = os.getenv('SERPER_API_KEY')
SENTRY_DSN = os.getenv('SENTRY_DSN')

db_status = "✅" if DATABASE_URL else "❌"
serper_status = "✅" if SERPER_API_KEY else "❌"
sentry_status = "✅" if SENTRY_DSN else "⚠️"

logger.info("Vlerafy Backend v1.0")
logger.info(f"Environment: {ENVIRONMENT} | Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.info(f"Config: Database {db_status} | Serper {serper_status} | Sentry {sentry_status} | Debug: {'ON' if log_level == logging.DEBUG else 'OFF'}")

# ============================================================================
# NOW IMPORT EVERYTHING ELSE
# ============================================================================
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi import status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import shopify

# Sentry is already initialized at the top of the file via sentry_config.py

# Import database
from app.database import engine, Base, get_db

# Import models and utilities
from app.models.shop import Shop
from app.utils.oauth import verify_hmac, generate_install_url
from app.config import settings

# Import routers
from app.routers import auth, debug, products, recommendations, competitors, demo_shop, shops
from app.routers import margin
from app.routers import shopify_routes
from app.routers import dashboard
from app.routers import admin

# Workaround für 2025-10 API Version
try:
    if hasattr(shopify.ApiVersion, 'versions') and '2025-10' not in shopify.ApiVersion.versions:
        class CustomApiVersion:
            def __init__(self, name):
                self.name = name
            
            def api_path(self, url):
                if url.startswith('http://') or url.startswith('https://'):
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    path = parsed.path
                    api_path = f"/admin/api/{self.name}{path}"
                    return f"{parsed.scheme}://{parsed.netloc}{api_path}"
                else:
                    return f"/admin/api/{self.name}{url}"
        
        version_obj = CustomApiVersion('2025-10')
        shopify.ApiVersion.versions['2025-10'] = version_obj
except Exception:
    pass

# ============================================================================
# LIFESPAN EVENT HANDLER
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/Shutdown-Logik mit Lifespan-Handler.
    """
    
    # ==================== STARTUP ====================
    # DB-Migrationen ausführen (silent)
    try:
        from alembic import command
        from alembic.config import Config
        
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))
        
        # Suppress alembic verbose logs
        import logging
        alembic_logger = logging.getLogger("alembic")
        alembic_logger.setLevel(logging.WARNING)
        
        command.upgrade(alembic_cfg, "head")
    except Exception:
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass  # Silent fallback
    
    # Optional: ML-Modelle laden (non-blocking)
    try:
        from app.services.ml.train_ml_models import MLModelTrainer
        trainer = MLModelTrainer()
        trainer.load_models()
    except (FileNotFoundError, Exception):
        pass  # Silent fallback
    
    # ==================== DEMO SHOP ERSTELLEN ====================
    # Stelle sicher, dass Demo Shop (id=999) in DB existiert
    # Wird benötigt für Foreign Key Constraints (price_history, recommendations, etc.)
    try:
        from app.database import SessionLocal
        from app.models.shop import Shop
        from sqlalchemy import text
        
        db = SessionLocal()
        try:
            # Prüfe ob Demo Shop existiert
            demo_shop = db.query(Shop).filter(Shop.id == 999).first()
            
            if not demo_shop:
                logger.info("Demo Shop (id=999) nicht gefunden - erstelle...")
                # Erstelle Demo Shop
                # WICHTIG: shop_url ist NOT NULL, daher muss ein Wert gesetzt werden
                demo_shop = Shop(
                    id=999,
                    shop_url="demo.vlerafy.com",
                    shop_name="Demo Shop",
                    is_active=True,
                    access_token=None,  # nullable
                    scope=None
                )
                db.add(demo_shop)
                db.commit()
                logger.info("✅ Demo Shop (id=999) erfolgreich erstellt")
            else:
                logger.debug("✅ Demo Shop (id=999) existiert bereits")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"⚠️ Fehler beim Erstellen des Demo Shops: {e}")
        # Nicht kritisch - App kann trotzdem starten
    
    # ==================== APP LÄUFT ====================
    yield
    
    # ==================== SHUTDOWN ====================
    logger.info("Shutting down...")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Vlerafy API",
    description="AI-Powered Shopify Pricing Optimization",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# ============================================================================
# REQUEST LOGGING MIDDLEWARE
# ============================================================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request with timing"""
    start = time.time()
    
    # Log request
    logger.info(f"→ {request.method} {request.url.path}")
    if request.url.query:
        logger.debug(f"  Query: {request.url.query}")
    
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        logger.debug(f"  Session: {session_id}")
    
    # Process
    try:
        response = await call_next(request)
        duration = (time.time() - start) * 1000
        
        logger.info(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({duration:.0f}ms)"
        )
        
        return response
    
    except Exception as e:
        duration = (time.time() - start) * 1000
        logger.error(
            f"{request.method} {request.url.path} "
            f"→ FAILED ({duration:.0f}ms): {str(e)}",
            exc_info=True
        )
        raise

# ============================================================================
# CORS MIDDLEWARE
# ============================================================================

# CORS Configuration - Support both www and non-www domains
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://vlerafy.com",
    "https://www.vlerafy.com",
    "https://*.myshopify.com",
    "https://admin.shopify.com",
]

# Add FRONTEND_URL from environment if set
frontend_url = os.getenv("FRONTEND_URL", "")
if frontend_url:
    allowed_origins.append(frontend_url)
    # Also add www version if not present
    if not frontend_url.startswith("www.") and frontend_url.startswith("https://"):
        www_url = frontend_url.replace("https://", "https://www.")
        allowed_origins.append(www_url)

# Remove duplicates and empty strings
allowed_origins = [origin for origin in allowed_origins if origin]
allowed_origins = list(set(allowed_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# RATE LIMITING SETUP
# ============================================================================
from app.middleware.rate_limiter import setup_rate_limiting
setup_rate_limiting(app)

# ============================================================================
# ROUTER REGISTRATION
# ============================================================================

app.include_router(auth.router)
if settings.ENVIRONMENT != "production":
    app.include_router(debug.router)
app.include_router(competitors.router)
app.include_router(demo_shop.router, prefix="/api")
app.include_router(shops.router)
app.include_router(products.router)
app.include_router(recommendations.router)
app.include_router(margin.router)
app.include_router(shopify_routes.router)
app.include_router(dashboard.router)
app.include_router(admin.router)

# ML Pricing Endpoints
try:
    from app.api.v1.endpoints.pricing_ml import router as pricing_ml_router
    app.include_router(pricing_ml_router, prefix="/api/v1/pricing", tags=["ML Pricing"])
except Exception:
    pass  # Expected if module doesn't exist

logger.info("CORS configured | Rate limiting enabled")
logger.info("Routers registered | Application ready")

# ============================================================================
# HEALTH CHECK & ROOT ENDPOINTS
# ============================================================================

@app.get("/")
async def root(request: Request, db: Session = Depends(get_db)):
    """
    Root endpoint with Shopify Admin redirect logic
    
    - Normal API calls (no shop/hmac params) → JSON API info
    - Shopify Admin calls (with shop/hmac params) → Redirect to frontend or install flow
    """
    params = dict(request.query_params)
    logger.debug(f"Root endpoint called - params: {params}")
    
    shop = params.get("shop")
    hmac_param = params.get("hmac")
    
    # Fall 1: Kein Shopify-Aufruf → API-Info zurückgeben
    if not shop or not hmac_param:
        return {
            "message": "Pricing Optimization API",
            "status": "running",
            "version": "2.0.0",
            "docs": "/docs",
            "health": "/health"
        }
    
    # Fall 2: Aufruf aus Shopify-Admin → HMAC prüfen
    try:
        if not verify_hmac(params, hmac_param):
            logger.warning(f"Invalid HMAC for shop: {shop}")
            raise HTTPException(status_code=400, detail="Invalid HMAC")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HMAC verification error: {e}")
        raise HTTPException(status_code=400, detail="Invalid HMAC")
    
    # Shop aus DB holen
    try:
        shop_record = db.query(Shop).filter(Shop.shop_url == shop).first()
        
        # Wenn kein Shop oder nicht aktiv → Install/Reauth-Flow starten
        if not shop_record or not shop_record.is_active:
            host = params.get("host", "")
            state = __import__("secrets").token_urlsafe(32)
            from app.routers.auth import save_oauth_state
            from app.core.shop_context import get_redis_client
            redis_client = get_redis_client()
            await save_oauth_state(state, shop, redis_client, host)
            install_url = generate_install_url(shop, state)
            logger.info(f"Redirecting to install URL: {install_url}")
            return RedirectResponse(url=install_url, status_code=302)
        
        # Wenn authentifiziert → ins Frontend embedded /app (mit host falls vorhanden)
        host = params.get("host", "")
        if host:
            redirect_url = f"{settings.FRONTEND_URL}/app?shop={shop}&host={host}&shop_id={shop_record.id}"
        else:
            redirect_url = f"{settings.FRONTEND_URL}/dashboard?shop_id={shop_record.id}"
        logger.info(f"Shop authenticated: {shop}, redirecting to frontend")
        return RedirectResponse(url=redirect_url, status_code=302)
        
    except Exception as e:
        logger.error(f"Error processing shop redirect: {e}", exc_info=True)
        install_url = generate_install_url(shop)
        return RedirectResponse(url=install_url, status_code=302)

@app.get("/health", tags=["System"])
async def health_check():
    """Railway healthcheck endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "vlerafy-backend",
        "version": "1.0.0"
    }

# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "details": exc.errors()
        }
    )

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors"""
    logger.error(f"Database error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Database Error",
            "message": "An error occurred while accessing the database"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred"
        }
    )

# ============================================================================
# ADDITIONAL ROUTES
# ============================================================================

@app.get("/api/status")
async def api_status():
    """Get API status and statistics"""
    from app.database import SessionLocal
    
    try:
        db = SessionLocal()
        
        # Count records in key tables
        from app.models.margin import ProductCost, MarginCalculation
        
        product_costs_count = db.query(ProductCost).count()
        margin_calcs_count = db.query(MarginCalculation).count()
        
        db.close()
        
        return {
            "status": "operational",
            "database": "connected",
            "statistics": {
                "products_with_costs": product_costs_count,
                "total_margin_calculations": margin_calcs_count
            }
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {
            "status": "degraded",
            "database": "error",
            "error": str(e)
        }


@app.get("/debug/sentry-test")
async def sentry_test(trigger_error: bool = False):
    """
    Test endpoint to verify Sentry is working
    Returns Sentry status and can trigger a test error
    
    Query Parameters:
    - trigger_error: Set to true to trigger a test error (default: false)
    """
    import sentry_sdk
    
    # Check if Sentry is initialized
    sentry_dsn = os.getenv("SENTRY_DSN")
    environment = os.getenv("ENVIRONMENT", "production")
    
    status_info = {
        "sentry_configured": sentry_dsn is not None,
        "sentry_dsn_set": bool(sentry_dsn),
        "environment": environment,
        "sentry_client": "initialized" if sentry_sdk.Hub.current.client else "not initialized",
        "message": "Sentry is working" if sentry_dsn else "Sentry DSN not set"
    }
    
    # Trigger a test error if requested (via query param)
    if trigger_error:
        try:
            raise Exception("Sentry Test Error - This is intentional for testing!")
        except Exception as e:
            sentry_sdk.capture_exception(e)
            status_info["test_error_triggered"] = True
            status_info["error_message"] = str(e)
    
    return status_info

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

logger.info("🎯 Application ready")
logger.info("="*70)

if __name__ == "__main__":
    import uvicorn
    
    # Get port from Railway environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
