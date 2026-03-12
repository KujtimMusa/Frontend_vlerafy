"""
Shop-Context Management
Speichert aktiven Shop für Session in Redis
"""
import redis
import json
import logging
from typing import Optional
from fastapi import Request, Depends
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models.shop import Shop

logger = logging.getLogger(__name__)


def resolve_shop_by_domain(shop_domain: str, db: Session) -> Optional[Shop]:
    """
    Sucht Shop in DB anhand der Domain (z.B. example.myshopify.com).
    Gibt None zurück wenn kein Shop gefunden.
    """
    if not shop_domain or not isinstance(shop_domain, str):
        return None
    domain = shop_domain.strip().replace("https://", "").replace("http://", "").rstrip("/")
    if not domain:
        return None
    return db.query(Shop).filter(Shop.shop_url == domain, Shop.is_active == True).first()

# In-Memory Fallback (immer initialisiert)
_memory_store = {}

# Redis Client (lazy initialization, never blocks)
_redis_client = None
_redis_initialized = False

def get_redis_client():
    """Lazy Redis client initialization - returns None if Redis not available"""
    global _redis_client, _redis_initialized
    
    if _redis_initialized:
        return _redis_client
    
    _redis_initialized = True
    
    # Skip Redis if REDIS_URL is not set or is default/localhost
    redis_url = getattr(settings, 'REDIS_URL', None)
    if not redis_url or redis_url.startswith('redis://redis:') or redis_url.startswith('redis://localhost:'):
        logger.info("⚠️ Redis not configured, using In-Memory Fallback")
        _redis_client = None
        return None
    
    try:
        # Create Redis client with optimized settings for Railway
        _redis_client = redis.from_url(
            redis_url, 
            decode_responses=True,
            socket_connect_timeout=5,  # ✅ Increased for Railway (slower connections)
            socket_timeout=5,  # ✅ Increased for Railway
            retry_on_timeout=True,  # ✅ Retry for transient failures
            health_check_interval=30,
            max_connections=10  # ✅ Connection pooling
        )
        # Quick connection test (non-blocking)
        _redis_client.ping()
        logger.info("✅ Redis connected")
        return _redis_client
    except Exception as e:
        logger.warning(f"⚠️ Redis nicht verfügbar: {e}. Nutze In-Memory Fallback.")
        _redis_client = None
        return None


class ShopContext:
    """
    Speichert aktiven Shop für aktuelle Session.
    Nutzt Redis für Persistenz, Fallback auf In-Memory.
    """
    
    def __init__(self, session_id: str):
        """
        Args:
            session_id: Eindeutige Session-ID (z.B. aus Cookie oder Header)
        """
        self.session_id = session_id
        self._cache_key_shop = f"session:{session_id}:active_shop_id"
        self._cache_key_demo = f"session:{session_id}:demo_mode"
    
    def _get(self, key: str, default=None):
        """Hole Wert aus Redis oder Memory"""
        redis_client = get_redis_client()
        if redis_client:
            try:
                value = redis_client.get(key)
                if value:
                    try:
                        # Versuche JSON zu parsen
                        parsed = json.loads(value)
                        # Konvertiere bool Strings zu bool
                        if isinstance(parsed, str):
                            if parsed.lower() == 'true':
                                return True
                            elif parsed.lower() == 'false':
                                return False
                        return parsed
                    except json.JSONDecodeError:
                        # Fallback: Wert ist bereits String/Number
                        # Konvertiere bool Strings zu bool
                        if isinstance(value, str):
                            if value.lower() == 'true':
                                return True
                            elif value.lower() == 'false':
                                return False
                        return value
                return default
            except Exception as e:
                logger.warning(f"Redis GET Fehler: {e}")
                return _memory_store.get(key, default)
        else:
            return _memory_store.get(key, default)
    
    def _set(self, key: str, value, expire: int = 86400 * 7):  # 7 Tage
        """Setze Wert in Redis oder Memory"""
        redis_client = get_redis_client()
        if redis_client:
            try:
                # Speichere als String (für einfache Werte) oder JSON
                # WICHTIG: bool als "True"/"False" String speichern für konsistente Parsing
                if isinstance(value, bool):
                    redis_client.setex(key, expire, str(value))
                elif isinstance(value, (str, int, float)):
                    redis_client.setex(key, expire, str(value))
                else:
                    redis_client.setex(key, expire, json.dumps(value))
                logger.debug(f"Redis SET: {key} = {value} (type: {type(value).__name__})")
            except Exception as e:
                logger.warning(f"Redis SET Fehler: {e}")
                _memory_store[key] = value
        else:
            _memory_store[key] = value
            logger.debug(f"Memory SET: {key} = {value} (type: {type(value).__name__})")
    
    @property
    def active_shop_id(self) -> int:
        """Hole aktiven Shop-ID aus Session"""
        shop_id = self._get(self._cache_key_shop, 999)  # Default: Demo Shop
        # Konvertiere String zu int
        if isinstance(shop_id, str):
            try:
                shop_id = int(shop_id)
            except ValueError:
                shop_id = 999
        return int(shop_id) if shop_id else 999
    
    @active_shop_id.setter
    def active_shop_id(self, shop_id: int):
        """Speichere aktive Shop-ID in Session"""
        self._set(self._cache_key_shop, shop_id)
        logger.info(f"Session {self.session_id}: Active Shop ID = {shop_id}")
    
    @property
    def is_demo_mode(self) -> bool:
        """Prüfe ob Demo-Mode aktiv"""
        demo_mode = self._get(self._cache_key_demo, True)  # Default: Demo Mode
        return bool(demo_mode)
    
    @is_demo_mode.setter
    def is_demo_mode(self, value: bool):
        """Setze Demo-Mode"""
        self._set(self._cache_key_demo, value)
        logger.info(f"Session {self.session_id}: Demo Mode = {value}")
    
    def get_adapter(self):
        """Gibt korrekten Adapter zurück basierend auf Context"""
        from app.services.shop_adapter_factory import get_shop_adapter
        from app.database import SessionLocal
        from app.models.shop import Shop
        from app.utils.encryption import decrypt_token
        from cryptography.fernet import InvalidToken
        
        if self.is_demo_mode:
            return get_shop_adapter(use_demo=True)
        else:
            # Lade Shop aus DB
            db = SessionLocal()
            try:
                shop = db.query(Shop).filter(Shop.id == self.active_shop_id).first()
                if not shop:
                    logger.warning(f"Shop {self.active_shop_id} nicht gefunden, nutze Demo")
                    return get_shop_adapter(use_demo=True)
                
                if not shop.is_active:
                    logger.warning(f"Shop {self.active_shop_id} ist nicht aktiv, nutze Demo")
                    return get_shop_adapter(use_demo=True)
                
                # Versuche Token zu entschlüsseln
                try:
                    access_token = decrypt_token(shop.access_token)
                except InvalidToken as e:
                    # CRITICAL: Token kann nicht entschlüsselt werden (falscher Encryption Key)
                    logger.error(
                        f"🔴 CRITICAL: Cannot decrypt access_token for Shop {shop.id} ({shop.shop_url})\n"
                        f"   Error: {str(e)}\n"
                        f"   Reason: ENCRYPTION_KEY mismatch - Token wurde mit anderem Key verschlüsselt\n"
                        f"   Solution: Shop muss neu authentifiziert werden (OAuth Flow)\n"
                        f"   Fallback: Using Demo Mode"
                    )
                    # Fallback auf Demo Mode
                    return get_shop_adapter(use_demo=True)
                except Exception as e:
                    # Andere Encryption-Fehler
                    logger.error(
                        f"🔴 ERROR: Failed to decrypt access_token for Shop {shop.id} ({shop.shop_url})\n"
                        f"   Error: {type(e).__name__}: {str(e)}\n"
                        f"   Fallback: Using Demo Mode"
                    )
                    return get_shop_adapter(use_demo=True)
                
                return get_shop_adapter(
                    shop_id=shop.id,  # WICHTIG!
                    shop_url=shop.shop_url,
                    access_token=access_token,
                    use_demo=False
                )
            finally:
                db.close()
    
    def load(self):
        """Lade Context explizit aus Redis/Memory (für Debugging und Konsistenz)"""
        shop_id = self._get(self._cache_key_shop, 999)
        demo_mode = self._get(self._cache_key_demo, True)
        
        # Konvertiere String zu int für shop_id
        if isinstance(shop_id, str):
            try:
                shop_id = int(shop_id)
            except ValueError:
                shop_id = 999
        
        # Konvertiere String zu bool für demo_mode
        if isinstance(demo_mode, str):
            demo_mode = demo_mode.lower() == 'true'
        
        logger.info(
            f"[CONTEXT LOAD] Session {self.session_id}: "
            f"shop_id={shop_id}, is_demo={bool(demo_mode)}"
        )
        
        # Setze Werte direkt (ohne Setter, um Rekursion zu vermeiden)
        self._set(self._cache_key_shop, shop_id)
        self._set(self._cache_key_demo, bool(demo_mode))
        
        return {
            "shop_id": int(shop_id) if shop_id else 999,
            "is_demo": bool(demo_mode)
        }
    
    def save(self):
        """Speichere Context explizit in Redis/Memory (für Debugging und Konsistenz)"""
        shop_id = self.active_shop_id
        demo_mode = self.is_demo_mode
        
        self._set(self._cache_key_shop, shop_id)
        self._set(self._cache_key_demo, demo_mode)
        
        logger.info(
            f"[CONTEXT SAVE] Session {self.session_id}: "
            f"shop_id={shop_id}, is_demo={demo_mode}"
        )
    
    def clear(self):
        """Lösche Session-Daten"""
        redis_client = get_redis_client()
        if redis_client:
            try:
                redis_client.delete(self._cache_key_shop, self._cache_key_demo)
            except Exception as e:
                logger.warning(f"Redis DELETE Fehler: {e}")
        else:
            _memory_store.pop(self._cache_key_shop, None)
            _memory_store.pop(self._cache_key_demo, None)


def get_session_id(request: Request) -> str:
    """
    Extrahiere Session-ID aus Request.
    Reihenfolge: Cookie → Header X-Session-ID → Fallback MD5(IP+User-Agent).
    """
    # 1. Cookie session_id
    session_id = request.cookies.get("session_id")
    if session_id:
        return session_id

    # 2. Header X-Session-ID
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        return session_id

    # 3. Fallback: Hash aus IP + User-Agent
    import hashlib
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    hash_input = f"{client_ip}:{user_agent}"
    session_id = hashlib.md5(hash_input.encode()).hexdigest()[:16]
    return session_id


def _extract_shop_id_from_token(request: Request, db) -> Optional[int]:
    """Extrahiert shop_id aus Bearer Token (Shopify Session oder App JWT)."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    token = auth.replace("Bearer ", "")
    if not token:
        return None

    try:
        # Shopify Session Token (dest claim)
        from app.utils.shopify_token_validator import validate_shopify_session_token
        payload = validate_shopify_session_token(token)
        if payload.get("dest"):
            shop_url = payload["dest"].replace("https://", "").replace("http://", "").strip().rstrip("/")
            from app.models.shop import Shop
            shop = db.query(Shop).filter(Shop.shop_url == shop_url).first()
            return shop.id if shop else None
    except (ValueError, Exception):
        pass

    try:
        # App JWT Token (shop_id claim)
        from app.core.jwt_manager import verify_token
        payload = verify_token(token, token_type="access")
        return payload.get("shop_id")
    except Exception:
        return None


def get_active_shop_for_request(request: Request, db: Session) -> tuple[int, bool]:
    """
    Ermittelt (shop_id, is_demo) mit Priorität (Shop-Auth Fix):

    1. X-Shop-ID Header → direkt verwenden
    2. X-Shop-Domain Header → Shop in DB suchen
    3. Bearer Token → shop aus token["dest"] in DB suchen
    4. Query Parameter ?shop=xxx.myshopify.com → Shop in DB suchen
    5. session_id Cookie/Header → ShopContext
    6. Fallback MD5 → Demo (999, True)
    """
    # 1. X-Shop-ID Header (direkt)
    x_shop_id = request.headers.get("X-Shop-ID")
    if x_shop_id:
        try:
            sid = int(x_shop_id.strip())
            if sid > 0:
                logger.info(f"[ACTIVE_SHOP] X-Shop-ID Header: shop_id={sid}, demo=False")
                return (sid, False)
        except ValueError:
            pass

    # 2. X-Shop-Domain Header
    shop_domain = request.headers.get("X-Shop-Domain")
    if shop_domain:
        shop = resolve_shop_by_domain(shop_domain, db)
        if shop:
            logger.info(f"[ACTIVE_SHOP] X-Shop-Domain Header: shop_id={shop.id}, demo=False")
            return (shop.id, False)

    # 3. Bearer Token
    shop_id_from_token = _extract_shop_id_from_token(request, db)
    if shop_id_from_token:
        logger.info(f"[ACTIVE_SHOP] Bearer Token: shop_id={shop_id_from_token}, demo=False")
        return (shop_id_from_token, False)

    # 4. Query Parameter ?shop=
    query_shop = request.query_params.get("shop")
    if query_shop:
        shop = resolve_shop_by_domain(query_shop, db)
        if shop:
            logger.info(f"[ACTIVE_SHOP] Query ?shop=: shop_id={shop.id}, demo=False")
            return (shop.id, False)

    # 5 + 6: Session-basiert (Cookie, X-Session-ID, oder MD5-Fallback)
    session_id = get_session_id(request)
    context = ShopContext(session_id)
    context.load()
    logger.info(
        f"[ACTIVE_SHOP] Session {session_id[:8]}...: shop_id={context.active_shop_id}, demo={context.is_demo_mode}"
    )
    return (context.active_shop_id, context.is_demo_mode)


def get_shop_context(request: Request, db: Session = Depends(get_db)) -> ShopContext:
    """
    Dependency: Gibt Shop-Context für aktuelle Session zurück.
    Nutzt get_active_shop_for_request für einheitliche Priorität
    (X-Shop-ID, X-Shop-Domain, Bearer, ?shop=, Session, Fallback).
    """
    return _resolve_shop_context(request, db)


def _resolve_shop_context(request: Request, db: Session) -> ShopContext:
    session_id = get_session_id(request)
    shop_id, is_demo = get_active_shop_for_request(request, db)

    class ResolvedShopContext(ShopContext):
        """ShopContext mit überlagerten Werten aus Request-Priorität."""
        def __init__(self, sid: str, resolved_shop_id: int, resolved_demo: bool):
            super().__init__(sid)
            self._resolved_shop_id = resolved_shop_id
            self._resolved_is_demo = resolved_demo

        @property
        def active_shop_id(self) -> int:
            return self._resolved_shop_id

        @active_shop_id.setter
        def active_shop_id(self, value: int):
            self._resolved_shop_id = value

        @property
        def is_demo_mode(self) -> bool:
            return self._resolved_is_demo

        @is_demo_mode.setter
        def is_demo_mode(self, value: bool):
            self._resolved_is_demo = value

    ctx = ResolvedShopContext(session_id, shop_id, is_demo)
    logger.info(f"✅ Shop Context: Shop {ctx.active_shop_id} (Demo: {ctx.is_demo_mode})")
    return ctx

