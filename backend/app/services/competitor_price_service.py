"""
CompetitorPriceService mit Serper API
Automatische Wettbewerberpreis-Suche über Google Shopping API
HYBRID-ARCHITEKTUR: Speichert optional in DB für ML-Training
"""
import requests
import json
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from app.config import settings

logger = logging.getLogger(__name__)


class CompetitorPriceService:
    """
    Service für automatische Wettbewerberpreis-Suche über Serper API (Google Shopping).
    
    Features:
    - In-Memory Cache (TTL konfigurierbar)
    - Rate-Limit-Tracking (2500 Calls/Monat Free Tier)
    - Automatische Preis-Parsing (deutsches Format)
    - Fehlerbehandlung mit Fallbacks
    """
    
    # FIX: GLOBALER Cache (Klassen-Variable) statt Instanz-Variable!
    # Verhindert dass Cache bei jeder neuen Instanz verloren geht
    _global_cache: Dict[str, tuple] = {}
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_ttl_seconds: int = 3600,
        enable_rate_limit_tracking: bool = True,
        db_session: Optional[object] = None,
        save_to_db: bool = False,
        product_id: Optional[int] = None
    ):
        """
        Initialisiert den CompetitorPriceService.
        
        Args:
            api_key: Serper API Key (optional, wird aus ENV oder Default genommen)
            cache_ttl_seconds: Cache-TTL in Sekunden (Standard: 3600 = 1h)
            enable_rate_limit_tracking: Ob Rate-Limits getrackt werden sollen
            db_session: SQLAlchemy Session für optionales DB-Speichern
            save_to_db: Ob API-Results in DB gespeichert werden sollen (für ML-Training)
            product_id: Product ID für DB-Speicherung (optional)
        """
        # API-Key: Parameter → ENV → Config
        from app.config import settings
        self.api_key = (
            api_key or
            getattr(settings, 'SERPER_API_KEY', None)
        )
        
        # Logging für Debugging
        if not self.api_key:
            logger.warning("[WARNING] SERPER_API_KEY nicht gesetzt - verwende Default Key")
        else:
            api_key_preview = self.api_key[:10] + "..." if len(self.api_key) > 10 else self.api_key
            logger.info(f"[OK] Serper API Key geladen: {api_key_preview}")
        
        self.cache_ttl_seconds = cache_ttl_seconds
        self.enable_rate_limit_tracking = enable_rate_limit_tracking
        
        # FIX: Erhöhe Cache TTL für bessere Determinismus (Standard: 5 Min → 15 Min)
        # Verhindert dass Competitor API bei jedem Call neue Daten liefert
        if cache_ttl_seconds == 300:  # Nur wenn Standard-Wert
            self.cache_ttl_seconds = 900  # 15 Minuten statt 5 Minuten
            logger.info(f"[CONFIG] Cache TTL erhoht auf {self.cache_ttl_seconds}s (15 Min) fur bessere Determinismus")
        
        # DB-Speicherung (Hybrid-Architektur)
        self.db_session = db_session
        self.save_to_db = save_to_db
        self.product_id = product_id
        
        # FIX: Nutze GLOBALEN Cache (Klassen-Variable) statt Instanz-Variable
        # Dadurch bleibt Cache erhalten auch wenn neue Instanzen erstellt werden
        # self._cache wird nicht mehr verwendet - nutze CompetitorPriceService._global_cache
        
        # Rate-Limit-Tracking
        self._api_calls_this_month = 0
        self._month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        
        # Logging
        logger.info("CompetitorPriceService initialized with Serper API")
        logger.info(f"Cache enabled: TTL = {cache_ttl_seconds}s")
        logger.info(f"Rate limit tracking: {enable_rate_limit_tracking}")
        if self.save_to_db and self.db_session:
            logger.info(f"[OK] DB-Speicherung aktiviert (Product ID: {product_id})")
        else:
            logger.info("DB-Speicherung deaktiviert (nur Live-API)")
        
        if not self.api_key:
            logger.warning("No API key provided, service will return empty results")
    
    def find_competitor_prices(
        self,
        product_title: str,
        max_results: int = 5,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Sucht automatisch nach Competitor-Preisen zu einem Produktnamen.
        
        Args:
            product_title: Produktname (z.B. "Nike Air Max 90")
            max_results: Maximale Anzahl Ergebnisse (Standard: 5)
            use_cache: Ob Cache verwendet werden soll (Standard: True)
        
        Returns:
            Liste von Dicts mit keys: source, title, price, url, rating, reviews, scraped_at
        """
        if not product_title or not product_title.strip():
            logger.warning("Empty product_title provided")
            return []
        
        product_title = product_title.strip()
        
        # 1. Cache-Check (GLOBALER Cache!)
        if use_cache and product_title in CompetitorPriceService._global_cache:
            cached_result, cached_at = CompetitorPriceService._global_cache[product_title]
            age = (datetime.now() - cached_at).total_seconds()
            
            if age < self.cache_ttl_seconds:
                logger.info(f"[OK] Cache HIT for '{product_title}' (age: {age:.0f}s, TTL: {self.cache_ttl_seconds}s)")
                logger.info(f"[DEBUG] Cached prices: {[c.get('price') for c in cached_result[:3]]}")
                return cached_result
            else:
                logger.info(f"[EXPIRED] Cache EXPIRED for '{product_title}' (age: {age:.0f}s > TTL: {self.cache_ttl_seconds}s)")
                # Entferne abgelaufenen Eintrag
                del CompetitorPriceService._global_cache[product_title]
        
        # 2. Rate-Limit-Check
        if self.enable_rate_limit_tracking:
            current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0)
            if current_month > self._month_start:
                logger.info("New month detected, resetting rate limit counter")
                self._api_calls_this_month = 0
                self._month_start = current_month
            
            if self._api_calls_this_month >= 2500:
                logger.error("Monthly rate limit exceeded (2500 calls)")
                return []
            
            self._api_calls_this_month += 1
        
        # 3. API-Request
        if not self.api_key:
            logger.error("❌ SERPER API KEY FEHLT!")
            logger.error("   Bitte setze SERPER_API_KEY in .env oder config.py")
            print(f"🔴 [COMPETITOR] SERPER API KEY FEHLT!", flush=True)
            return []
        
        logger.info(f"[API] Serper API Request: '{product_title}' (max_results: {max_results})")
        print(f"[COMPETITOR] Fetching prices for: '{product_title}'", flush=True)
        print(f"[COMPETITOR] SERPER_API_KEY exists: {bool(self.api_key)}", flush=True)
        print(f"[COMPETITOR] API Key preview: {self.api_key[:10]}..." if self.api_key else "N/A", flush=True)
        
        try:
            print(f"[COMPETITOR] Making API request to Serper...", flush=True)
            response = requests.post(
                "https://google.serper.dev/shopping",
                headers={
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "q": product_title,
                    "gl": "de",  # Deutschland
                    "hl": "de",  # Deutsch
                    "num": max_results
                },
                timeout=10
            )
            print(f"[COMPETITOR] API Response Status: {response.status_code}", flush=True)
        except requests.Timeout:
            logger.error(f"[TIMEOUT] Serper API timeout after 10s for '{product_title}'")
            print(f"[COMPETITOR ERROR] Timeout after 10s", flush=True)
            return []
        except requests.RequestException as e:
            logger.error(f"[ERROR] Serper API request failed: {e}", exc_info=True)
            print(f"[COMPETITOR ERROR] Request failed: {str(e)}", flush=True)
            import traceback
            print(f"[TRACEBACK]:\n{traceback.format_exc()}", flush=True)
            return []
        
        # 4. Response-Verarbeitung
        if response.status_code != 200:
            logger.error(
                f"[ERROR] Serper API error: HTTP {response.status_code}"
            )
            logger.error(f"   Response: {response.text[:500]}")
            print(f"[COMPETITOR ERROR] HTTP {response.status_code}", flush=True)
            print(f"[COMPETITOR ERROR] Response: {response.text[:500]}", flush=True)
            
            if response.status_code == 401:
                logger.error("   -> API Key ist ungultig oder fehlt!")
                print(f"[COMPETITOR ERROR] API Key ist ungultig oder fehlt!", flush=True)
            elif response.status_code == 429:
                logger.error("   -> Rate Limit erreicht! (2500 Calls/Monat)")
                print(f"[COMPETITOR ERROR] Rate Limit erreicht!", flush=True)
            elif response.status_code == 402:
                logger.error("   -> Payment Required - API Key hat keine Credits mehr")
                print(f"[COMPETITOR ERROR] Payment Required - keine Credits!", flush=True)
            
            return []
        
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from Serper API: {e}")
            return []
        
        if "error" in data:
            logger.error(f"Serper API error: {data['error']}")
            return []
        
        # 5. Parsing der Shopping-Ergebnisse
        results = []
        shopping_items = data.get("shopping", [])
        
        logger.info(f"[API] Serper API Response: {len(shopping_items)} Shopping-Items gefunden")
        print(f"[COMPETITOR] Found {len(shopping_items)} shopping items", flush=True)
        
        if not shopping_items:
            logger.warning(f"[WARNING] Keine Shopping-Items in Serper API Response fur '{product_title}'")
            logger.debug(f"   Response Keys: {list(data.keys())}")
            print(f"[COMPETITOR] NO shopping items in response!", flush=True)
            print(f"[COMPETITOR] Response keys: {list(data.keys())}", flush=True)
            if "organic" in data:
                organic_count = len(data.get('organic', []))
                logger.info(f"   -> {organic_count} organische Ergebnisse gefunden (aber keine Shopping-Items)")
                print(f"[COMPETITOR] {organic_count} organic results (but no shopping items)", flush=True)
        
        for item in shopping_items[:max_results]:
            try:
                price_float = self._parse_price(item.get("price", ""))
                
                if price_float is None:
                    logger.debug(f"Skipping item with invalid price: {item.get('title', 'Unknown')}")
                    continue
                
                results.append({
                    "source": item.get("source", "Google Shopping"),
                    "title": item.get("title", ""),
                    "price": price_float,
                    "url": item.get("link", ""),
                    "rating": item.get("rating"),
                    "reviews": item.get("reviews"),
                    "scraped_at": datetime.now().isoformat()
                })
            except Exception as e:
                logger.warning(f"Error parsing item: {e}")
                continue
        
        # 6. Cache-Update (bei Erfolg) - GLOBALER Cache!
        if results:
            CompetitorPriceService._global_cache[product_title] = (results, datetime.now())
            logger.info(f"[CACHE] Cache SAVED for '{product_title}' ({len(results)} results, TTL: {self.cache_ttl_seconds}s)")
            logger.info(f"[DEBUG] Cached prices: {[r.get('price') for r in results[:3]]}")
            logger.info(f"[DEBUG] Global cache size: {len(CompetitorPriceService._global_cache)} entries")
            
            # 7. Optional: Speichere in DB für ML-Training (Hybrid-Architektur)
            if self.save_to_db and self.db_session and self.product_id:
                self._save_to_database(results, product_title)
        
        return results
    
    def _save_to_database(self, results: List[Dict], product_title: str):
        """
        Speichert API-Results optional in DB für ML-Training und historische Analyse.
        Wird nur aufgerufen wenn save_to_db=True und db_session vorhanden.
        """
        if not results or not self.db_session or not self.product_id:
            return
        
        try:
            from app.models.competitor import CompetitorPrice
            
            saved_count = 0
            for result in results:
                # Prüfe ob bereits vorhanden (gleiche URL)
                existing = self.db_session.query(CompetitorPrice).filter(
                    CompetitorPrice.product_id == self.product_id,
                    CompetitorPrice.competitor_url == result.get('url', '')
                ).first()
                
                if existing:
                    # Update bestehenden Eintrag
                    existing.price = result.get('price')
                    existing.scraped_at = datetime.now()
                    existing.scrape_success = True
                    existing.in_stock = True
                    saved_count += 1
                else:
                    # Neuer Eintrag
                    new_competitor = CompetitorPrice(
                        product_id=self.product_id,
                        competitor_name=result.get('source', 'Google Shopping'),
                        competitor_url=result.get('url', ''),
                        price=result.get('price'),
                        scrape_success=True,
                        scraped_at=datetime.now(),
                        in_stock=True
                    )
                    self.db_session.add(new_competitor)
                    saved_count += 1
            
            if saved_count > 0:
                self.db_session.commit()
                logger.info(f"[DB] {saved_count} Competitor-Preise in DB gespeichert (fur ML-Training)")
        except Exception as e:
            logger.warning(f"[WARNING] Fehler beim DB-Speichern: {e}")
            if self.db_session:
                self.db_session.rollback()
    
    def _parse_price(self, price_text: str) -> Optional[float]:
        """
        Wandelt Preisstrings wie '€99,99', '99,99 €', 'ab 1.234,56 €' in float um.
        
        Args:
            price_text: Preis-String (z.B. "€99,99", "1.234,56 EUR")
        
        Returns:
            Float-Wert oder None wenn kein gültiger Preis gefunden
        """
        if not price_text:
            return None
        
        # Entferne Währungssymbole und Texte
        clean = re.sub(
            r'[€$£¥₹]|EUR|USD|GBP|CHF|ab|ca\.',
            '',
            price_text,
            flags=re.IGNORECASE
        )
        clean = clean.strip()
        
        # Ersetze deutsches Format: 1.234,56 -> 1234.56
        # Zuerst Tausender-Punkte entfernen (nur wenn gefolgt von 3 Ziffern)
        clean = re.sub(r'\.(?=\d{3})', '', clean)
        # Dann Komma durch Punkt ersetzen
        clean = clean.replace(',', '.')
        
        # Extrahiere erste Dezimalzahl
        match = re.search(r'\d+\.?\d*', clean)
        if not match:
            return None
        
        try:
            return float(match.group())
        except ValueError:
            return None
    
    def get_rate_limit_status(self) -> Dict:
        """
        Gibt aktuellen Rate-Limit-Status zurück.
        
        Returns:
            Dict mit calls_this_month, limit, remaining, resets_at
        """
        if not self.enable_rate_limit_tracking:
            return {
                "tracking_enabled": False,
                "message": "Rate limit tracking is disabled"
            }
        
        # Nächster Monatserster
        next_month = (self._month_start + timedelta(days=32)).replace(day=1)
        
        return {
            "calls_this_month": self._api_calls_this_month,
            "limit": 2500,
            "remaining": max(0, 2500 - self._api_calls_this_month),
            "resets_at": next_month.isoformat(),
            "tracking_enabled": True
        }






