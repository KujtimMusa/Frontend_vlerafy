"""
Shop-Context Management
Speichert aktiven Shop für Session in Redis
"""
import redis
import json
import logging
from typing import Optional
from fastapi import Request
from app.config import settings

logger = logging.getLogger(__name__)

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
    Nutzt Cookie oder Header, Fallback auf IP+User-Agent Hash.
    """
    # 1. Versuche Cookie
    session_id = request.cookies.get("session_id")
    if session_id:
        return session_id
    
    # 2. Versuche Header
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


def get_shop_context(request: Request) -> ShopContext:
    """
    Dependency: Gibt Shop-Context für aktuelle Session zurück.
    """
    session_id = get_session_id(request)
    
    logger.debug(f"\n🏪 SHOP CONTEXT REQUEST")
    logger.debug(f"   Session ID: {session_id}")
    
    context = ShopContext(session_id)
    
    logger.info(f"✅ Shop Context: Shop {context.active_shop_id} (Demo: {context.is_demo_mode})")
    
    return context

