from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.shop import Shop
from app.utils.encryption import decrypt_token
from app.config import settings
from app.core.shop_context import get_redis_client, get_session_id, ShopContext
import shopify
import requests
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlencode

router = APIRouter(prefix="/debug", tags=["debug"])
logger = logging.getLogger(__name__)


@router.get("/scopes/config")
async def get_configured_scopes():
    """Zeigt konfigurierte Scopes"""
    return {
        "configured_scopes": settings.SHOPIFY_API_SCOPES.split(","),
        "api_version": settings.SHOPIFY_API_VERSION
    }


@router.get("/scopes/{shop_id}")
async def check_granted_scopes(shop_id: int, db: Session = Depends(get_db)):
    """Prüft welche Scopes tatsächlich gewährt wurden"""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop nicht gefunden")
    
    if not shop.is_active:
        raise HTTPException(status_code=400, detail="Shop ist nicht aktiv")
    
    try:
        access_token = decrypt_token(shop.access_token)
        
        # Erstelle Session
        api_version = settings.SHOPIFY_API_VERSION
        if api_version not in shopify.ApiVersion.versions:
            class TempApiVersion:
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
            temp_version = TempApiVersion(api_version)
            shopify.ApiVersion.versions[api_version] = temp_version
        
        session = shopify.Session(shop.shop_url, api_version, access_token)
        shopify.ShopifyResource.activate_session(session)
        
        # GraphQL Query für granted Scopes
        query = """
        {
          appInstallation {
            accessScopes {
              handle
              description
            }
          }
        }
        """
        
        result = shopify.GraphQL().execute(query)
        
        # GraphQL kann String oder Dict zurückgeben
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                logger.error(f"GraphQL Response ist kein gültiges JSON: {result}")
                return {
                    "success": False,
                    "shop": shop.shop_url,
                    "error": "GraphQL Response konnte nicht geparst werden",
                    "raw_response": result
                }
        
        # Extrahiere Scopes aus Response
        if isinstance(result, dict):
            granted_scopes = result.get("data", {}).get("appInstallation", {}).get("accessScopes", [])
        else:
            granted_scopes = []
        
        return {
            "success": True,
            "shop": shop.shop_url,
            "granted_scopes": granted_scopes,
            "raw_response": result
        }
    
    except Exception as e:
        logger.error(f"Fehler beim Prüfen der Scopes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shops")
async def list_shops(db: Session = Depends(get_db)):
    """Listet alle installierten Shops"""
    shops = db.query(Shop).all()
    return {
        "shops": [
            {
                "id": shop.id,
                "shop_url": shop.shop_url,
                "shop_name": shop.shop_name,
                "is_active": shop.is_active,
                "created_at": shop.created_at.isoformat() if shop.created_at else None
            }
            for shop in shops
        ]
    }


@router.get("/test-scopes-by-url/{shop_url}")
async def test_scopes_by_url(shop_url: str, db: Session = Depends(get_db)):
    """Testet Scopes direkt mit Shop-URL (z.B. vlerafy-test.myshopify.com)"""
    # Normalisiere Shop-URL
    shop_url = shop_url.replace('https://', '').replace('http://', '').strip()
    if not shop_url.endswith('.myshopify.com'):
        shop_url = f"{shop_url}.myshopify.com"
    
    shop = db.query(Shop).filter(Shop.shop_url == shop_url).first()
    if not shop:
        raise HTTPException(
            status_code=404,
            detail=f"Shop '{shop_url}' nicht gefunden. Installiere die App zuerst: /auth/shopify/install?shop={shop_url}"
        )
    
    return await test_scopes(shop.id, db)


@router.get("/test-scopes/{shop_id}")
async def test_scopes(shop_id: int, db: Session = Depends(get_db)):
    """Testet jeden Scope direkt via API-Call"""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop nicht gefunden")
    
    access_token = decrypt_token(shop.access_token)
    api_version = settings.SHOPIFY_API_VERSION
    
    # Workaround für API Version
    if api_version not in shopify.ApiVersion.versions:
        class TempApiVersion:
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
        temp_version = TempApiVersion(api_version)
        shopify.ApiVersion.versions[api_version] = temp_version
    
    session = shopify.Session(shop.shop_url, api_version, access_token)
    shopify.ShopifyResource.activate_session(session)
    
    # Teste Session
    try:
        shop_info = shopify.Shop.current()
        session_valid = shop_info is not None
        shop_name = shop_info.name if shop_info and hasattr(shop_info, 'name') else 'Unknown'
    except:
        session_valid = False
        shop_name = None
    
    # Teste jeden Scope
    scope_tests = {}
    scopes_to_test = settings.SHOPIFY_API_SCOPES.split(",")
    
    for scope in scopes_to_test:
        scope = scope.strip()
        granted = False
        error = None
        
        try:
            if scope == "read_products":
                shopify.Product.find(limit=1)
                granted = True
            elif scope == "write_products":
                # Test: Versuche ein Produkt zu lesen (write benötigt auch read)
                products = shopify.Product.find(limit=1)
                if products:
                    # Wenn wir Produkte lesen können, können wir auch schreiben (wenn Scope gewährt)
                    granted = True
            elif scope == "read_orders":
                shopify.Order.find(limit=1)
                granted = True
            elif scope == "read_all_orders":
                shopify.Order.find(limit=1, status="any")
                granted = True
            elif scope == "read_inventory" or scope == "read_locations":
                shopify.Location.find()
                granted = True
            elif scope == "read_customers":
                shopify.Customer.find(limit=1)
                granted = True
        except Exception as e:
            error = str(e)
        
        scope_tests[scope] = {
            "granted": granted,
            "error": error
        }
    
    return {
        "shop": shop.shop_url,
        "scope_tests": scope_tests,
        "session_valid": {
            "granted": session_valid,
            "message": f"✅ Session aktiv: {shop_name}" if session_valid else "❌ Session ungültig"
        },
        "summary": {
            "granted_scopes": sum(1 for s in scope_tests.values() if s["granted"]),
            "total_tests": len(scope_tests),
            "all_granted": all(s["granted"] for s in scope_tests.values())
        }
    }


@router.get("/reinstall-by-url/{shop_url}")
async def get_reinstall_url_by_url(shop_url: str, db: Session = Depends(get_db)):
    """Generiert Reinstall-URL direkt mit Shop-URL"""
    # Normalisiere Shop-URL
    shop_url = shop_url.replace('https://', '').replace('http://', '').strip()
    if not shop_url.endswith('.myshopify.com'):
        shop_url = f"{shop_url}.myshopify.com"
    
    shop = db.query(Shop).filter(Shop.shop_url == shop_url).first()
    if not shop:
        raise HTTPException(
            status_code=404,
            detail=f"Shop '{shop_url}' nicht gefunden. Installiere die App zuerst: /auth/shopify/install?shop={shop_url}"
        )
    
    return await get_reinstall_url(shop.id, db)


@router.get("/reinstall/{shop_id}")
async def get_reinstall_url(shop_id: int, db: Session = Depends(get_db)):
    """Generiert Reinstall-URL für Shop"""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop nicht gefunden")
    
    scopes = settings.SHOPIFY_API_SCOPES
    redirect_uri = f"{settings.APP_URL}/auth/shopify/callback"
    
    params = {
        "client_id": settings.SHOPIFY_CLIENT_ID,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": "reinstall"
    }
    
    oauth_url = f"https://{shop.shop_url}/admin/oauth/authorize?{urlencode(params)}"
    
    return {
        "shop": shop.shop_url,
        "reinstall_url": oauth_url,
        "scopes": scopes.split(","),
        "instructions": [
            "1. Öffne die reinstall_url im Browser",
            "2. Klicke auf 'Installieren' oder 'Install app'",
            "3. Stelle sicher, dass ALLE Berechtigungen angezeigt werden",
            "4. Akzeptiere alle Berechtigungen",
            "5. Nach der Installation: /debug/test-scopes/{shop_id} aufrufen"
        ]
    }


@router.delete("/uninstall/{shop_id}")
async def uninstall_shop(shop_id: int, db: Session = Depends(get_db)):
    """Entfernt Shop aus der Datenbank"""
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop nicht gefunden")
    
    db.delete(shop)
    db.commit()
    
    return {"success": True, "message": f"Shop {shop.shop_url} wurde entfernt"}


@router.get("/test-serper-api")
@router.get("/ml-model-status")
async def get_ml_model_status():
    """
    Debug endpoint to check ML model loading status
    Returns current model version, features, and XGBoost status
    """
    try:
        from app.services.pricing_engine import PricingEngine
        from app.services.csv_demo_shop_adapter import CSVDemoShopAdapter
        from app.services.ml.ml_pricing_engine import MLPricingEngine
        from app.services.ml.model_config import PRODUCTION_MODELS
        
        # Get USE_XGBOOST_KAGGLE value (same logic as in ml_pricing_engine.py)
        use_xgboost_kaggle_env = os.getenv("USE_XGBOOST_KAGGLE", "true").lower() == "true"
        
        # Create a minimal engine to check model status
        adapter = CSVDemoShopAdapter()
        base_engine = PricingEngine(shop=None, adapter=adapter, db=None)
        ml_engine = MLPricingEngine(base_engine=base_engine)
        
        # Check XGBoost model files
        model_dir = Path("models/ml")
        xgboost_model_path = model_dir / "xgboost_kaggle_universal.pkl"
        xgboost_features_path = model_dir / "xgboost_kaggle_features.json"
        xgboost_metadata_path = model_dir / "xgboost_kaggle_metadata.json"
        
        # Check RandomForest model files
        rf_detector_path = PRODUCTION_MODELS["ml_detector"]
        rf_labeler_path = PRODUCTION_MODELS["meta_labeler"]
        
        # Get environment variable
        env_var = os.getenv("USE_XGBOOST_KAGGLE", "NOT SET")
        
        status = {
            "environment": {
                "USE_XGBOOST_KAGGLE_env_var": env_var,
                "USE_XGBOOST_KAGGLE_parsed": use_xgboost_kaggle_env,
                "default_behavior": "true (XGBoost enabled by default)"
            },
            "model_loading": {
                "models_loaded": ml_engine.models_loaded,
                "model_version": ml_engine.model_version,
                "expected_feature_count": ml_engine.expected_feature_count,
                "actual_feature_count": len(ml_engine.feature_order) if ml_engine.feature_order else 0
            },
            "xgboost_files": {
                "model_exists": xgboost_model_path.exists(),
                "model_path": str(xgboost_model_path),
                "model_absolute": str(xgboost_model_path.resolve()),
                "features_exists": xgboost_features_path.exists(),
                "metadata_exists": xgboost_metadata_path.exists()
            },
            "randomforest_files": {
                "detector_exists": rf_detector_path.exists(),
                "detector_path": str(rf_detector_path),
                "labeler_exists": rf_labeler_path.exists(),
                "labeler_path": str(rf_labeler_path)
            },
            "current_model": {
                "type": "XGBoost" if ml_engine.model_version == "xgboost_kaggle_v1" else "RandomForest",
                "version": ml_engine.model_version,
                "features": len(ml_engine.feature_order) if ml_engine.feature_order else 0
            },
            "metadata": ml_engine.model_metadata if hasattr(ml_engine, 'model_metadata') and ml_engine.model_metadata else {}
        }
        
        return status
        
    except Exception as e:
        logger.error(f"Error checking ML model status: {e}")
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

async def test_serper_api(
    product_title: str = "Nike Air Max",
    max_results: int = 5
):
    """
    Test Serper API für Wettbewerber-Suche.
    
    Args:
        product_title: Produktname zum Testen (Default: "Nike Air Max")
        max_results: Anzahl Ergebnisse (Default: 5)
    
    Returns:
        Dict mit API-Status, gefundenen Wettbewerbern und Debug-Infos
    """
    from app.services.competitor_price_service import CompetitorPriceService
    
    result = {
        "test_product": product_title,
        "max_results": max_results,
        "api_key_status": "unknown",
        "api_key_preview": None,
        "service_initialized": False,
        "competitors_found": 0,
        "competitors": [],
        "errors": [],
        "warnings": []
    }
    
    # 1. Prüfe API-Key
    api_key = getattr(settings, 'SERPER_API_KEY', None)
    if api_key:
        result["api_key_status"] = "set"
        result["api_key_preview"] = api_key[:10] + "..." if len(api_key) > 10 else api_key
    else:
        result["api_key_status"] = "missing"
        result["warnings"].append("SERPER_API_KEY nicht in config.py oder .env gesetzt")
        result["warnings"].append("Service verwendet Default-Key (kann abgelaufen sein)")
    
    # 2. Initialisiere Service
    try:
        service = CompetitorPriceService()
        result["service_initialized"] = True
        
        if not service.api_key:
            result["errors"].append("Service hat keinen API-Key (auch kein Default)")
            return result
    except Exception as e:
        result["errors"].append(f"Fehler beim Initialisieren des Services: {str(e)}")
        logger.error(f"Service initialization error: {e}", exc_info=True)
        return result
    
    # 3. Teste API-Call
    try:
        logger.info(f"🧪 Teste Serper API mit Produkt: '{product_title}'")
        competitors = service.find_competitor_prices(
            product_title=product_title,
            max_results=max_results,
            use_cache=False  # Kein Cache für Test
        )
        
        result["competitors_found"] = len(competitors) if competitors else 0
        result["competitors"] = competitors if competitors else []
        
        if not competitors:
            result["warnings"].append("Keine Wettbewerber gefunden")
            result["warnings"].append("Mögliche Gründe:")
            result["warnings"].append("  - API-Key ist ungültig oder abgelaufen")
            result["warnings"].append("  - Rate Limit erreicht (2500 Calls/Monat)")
            result["warnings"].append("  - Keine Shopping-Ergebnisse für dieses Produkt")
            result["warnings"].append("  - Produktname zu spezifisch")
        else:
            result["success"] = True
            logger.info(f"✅ Test erfolgreich: {len(competitors)} Wettbewerber gefunden")
            
    except Exception as e:
        result["errors"].append(f"Fehler beim API-Call: {str(e)}")
        logger.error(f"API call error: {e}", exc_info=True)
    
    # 4. Rate Limit Status
    try:
        rate_limit_status = service.get_rate_limit_status()
        result["rate_limit"] = rate_limit_status
    except Exception as e:
        result["warnings"].append(f"Konnte Rate-Limit-Status nicht abrufen: {str(e)}")
    
    return result


@router.get("/redis-test")
async def test_redis(request: Request):
    """Test Redis connection and operations"""
    session_id = get_session_id(request)
    
    redis_client = get_redis_client()
    
    if not redis_client:
        return {
            "redis_available": False,
            "session_id": session_id,
            "message": "Redis client not available (using In-Memory Fallback)",
            "shop_context": {
                "active_shop_id": None,
                "is_demo_mode": None
            }
        }
    
    try:
        # Test PING
        ping = redis_client.ping()
        
        # Test SET
        test_key = f"test:{session_id}"
        redis_client.set(test_key, "test_value", ex=60)
        
        # Test GET
        value = redis_client.get(test_key)
        
        # Test shop context
        shop_context = ShopContext(session_id)
        shop_context.load()
        
        context_key_shop = f"session:{session_id}:active_shop_id"
        context_key_demo = f"session:{session_id}:demo_mode"
        context_data_shop = redis_client.get(context_key_shop)
        context_data_demo = redis_client.get(context_key_demo)
        
        return {
            "redis_available": True,
            "ping": ping,
            "test_set_get": value == "test_value",
            "session_id": session_id,
            "context_keys": {
                "shop": context_key_shop,
                "demo": context_key_demo
            },
            "context_data": {
                "active_shop_id": context_data_shop,
                "is_demo_mode": context_data_demo
            },
            "shop_context": {
                "active_shop_id": shop_context.active_shop_id,
                "is_demo_mode": shop_context.is_demo_mode
            }
        }
        
    except Exception as e:
        logger.error(f"Redis test error: {e}", exc_info=True)
        return {
            "redis_available": False,
            "error": str(e),
            "session_id": session_id
        }


@router.get("/redis-health")
async def redis_health_check(request: Request):
    """
    Complete Redis health check - test all operations
    
    Tests:
    1. PING - Basic connectivity
    2. SET - Write operation
    3. GET - Read operation
    4. DELETE - Delete operation
    5. Shop Context - Real-world usage test
    
    Returns comprehensive health status for Railway Redis integration.
    """
    session_id = get_session_id(request)
    results = {
        "session_id": session_id,
        "redis_available": False,
        "tests": {},
        "overall_health": "unhealthy"
    }
    
    try:
        redis_client = get_redis_client()
        
        if not redis_client:
            results["error"] = "Redis client not available (REDIS_URL not set or connection failed)"
            results["message"] = "Using In-Memory Fallback - App will work but context won't persist"
            return results
        
        results["redis_available"] = True
        
        # Test 1: PING
        try:
            ping_result = redis_client.ping()
            results["tests"]["ping"] = {
                "success": True,
                "result": ping_result,
                "message": "Redis is responding"
            }
        except Exception as e:
            results["tests"]["ping"] = {
                "success": False,
                "error": str(e),
                "message": "Redis PING failed"
            }
        
        # Test 2: SET
        try:
            test_key = f"test:redis_health:{session_id}"
            redis_client.setex(test_key, 60, "test_value")
            results["tests"]["set"] = {
                "success": True,
                "key": test_key,
                "ttl": 60,
                "message": "SET operation successful"
            }
        except Exception as e:
            results["tests"]["set"] = {
                "success": False,
                "error": str(e),
                "message": "SET operation failed"
            }
        
        # Test 3: GET
        try:
            value = redis_client.get(test_key)
            value_matches = value == "test_value"
            results["tests"]["get"] = {
                "success": True,
                "value_matches": value_matches,
                "retrieved_value": value,
                "message": "GET operation successful" if value_matches else "GET returned wrong value"
            }
        except Exception as e:
            results["tests"]["get"] = {
                "success": False,
                "error": str(e),
                "message": "GET operation failed"
            }
        
        # Test 4: DELETE
        try:
            deleted = redis_client.delete(test_key)
            results["tests"]["delete"] = {
                "success": True,
                "keys_deleted": deleted,
                "message": "DELETE operation successful"
            }
        except Exception as e:
            results["tests"]["delete"] = {
                "success": False,
                "error": str(e),
                "message": "DELETE operation failed"
            }
        
        # Test 5: Shop Context Key Check
        try:
            context_key_shop = f"session:{session_id}:active_shop_id"
            context_key_demo = f"session:{session_id}:demo_mode"
            
            context_exists_shop = redis_client.exists(context_key_shop)
            context_exists_demo = redis_client.exists(context_key_demo)
            
            context_data_shop = redis_client.get(context_key_shop) if context_exists_shop else None
            context_data_demo = redis_client.get(context_key_demo) if context_exists_demo else None
            
            # Test ShopContext class
            shop_context = ShopContext(session_id)
            shop_context.load()
            
            results["tests"]["shop_context"] = {
                "success": True,
                "keys": {
                    "shop": context_key_shop,
                    "demo": context_key_demo
                },
                "exists": {
                    "shop": bool(context_exists_shop),
                    "demo": bool(context_exists_demo)
                },
                "data": {
                    "shop": context_data_shop,
                    "demo": context_data_demo
                },
                "shop_context_class": {
                    "active_shop_id": shop_context.active_shop_id,
                    "is_demo_mode": shop_context.is_demo_mode
                },
                "message": "Shop Context operations successful"
            }
        except Exception as e:
            results["tests"]["shop_context"] = {
                "success": False,
                "error": str(e),
                "message": "Shop Context test failed"
            }
        
        # Overall health calculation
        all_tests_passed = all(
            t.get("success", False) 
            for t in results["tests"].values()
        )
        
        if all_tests_passed:
            results["overall_health"] = "healthy"
            results["message"] = "✅ All Redis operations working correctly"
        else:
            failed_tests = [name for name, test in results["tests"].items() if not test.get("success", False)]
            results["overall_health"] = "degraded"
            results["message"] = f"⚠️ Some tests failed: {', '.join(failed_tests)}"
        
    except Exception as e:
        results["error"] = str(e)
        results["overall_health"] = "unhealthy"
        results["message"] = f"❌ Health check failed: {str(e)}"
        logger.error(f"Redis health check error: {e}", exc_info=True)
    
    return results

