"""
Automatische Wettbewerber-Erkennung
Findet automatisch Wettbewerber basierend auf Produktnamen und scraped deren Preise
"""
import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional
import logging
import time
from urllib.parse import quote_plus, urljoin, urlparse, parse_qs

from app.services.competitor_scraper import scrape_competitor_price
from app.config import settings

logger = logging.getLogger(__name__)


class CompetitorDiscovery:
    """
    Automatische Wettbewerber-Erkennung durch Web-Scraping / ScrapingAnt
    """
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }
        # ScrapingAnt Konfiguration
        self.scrapingant_api_key: Optional[str] = settings.SCRAPINGANT_API_KEY
        self.api_base_url: str = "https://api.scrapingant.com/v2/general"
    
    # ✅ NEU: Google Shopping via ScrapingAnt
    def _scrape_with_api(self, product_title: str, max_results: int = 10) -> List[Dict]:
        """
        Nutzt ScrapingAnt API, rendert Google Shopping mit JS und extrahiert
        Wettbewerber (Name, URL, geschätzter Preis).
        """
        competitors: List[Dict] = []

        if not self.scrapingant_api_key:
            logger.warning("ScrapingAnt API Key nicht konfiguriert")
            return competitors

        try:
            search_query = quote_plus(f"{product_title} kaufen")
            search_url = f"https://www.google.com/search?tbm=shop&q={search_query}&hl=de"

            params = {
                "url": search_url,
                # optional: weitere Parameter wie browser, proxy_country etc.
            }
            headers = {
                "x-api-key": self.scrapingant_api_key
            }

            logger.info(f"ScrapingAnt: Google Shopping Suche für '{product_title}' → {search_url}")
            response = requests.get(self.api_base_url, params=params, headers=headers, timeout=30)

            # Error-Handling nach Statuscode
            if response.status_code == 401:
                logger.error("ScrapingAnt: Ungültiger API-Key (401)")
                return competitors
            if response.status_code == 402:
                logger.error("ScrapingAnt: Credits aufgebraucht (402)")
                return competitors
            if response.status_code != 200:
                logger.error(f"ScrapingAnt Fehler: HTTP {response.status_code} - Body: {response.text[:500]}")
                return competitors

            soup = BeautifulSoup(response.text, "html.parser")

            # Mehrere Selektor-Strategien
            products = soup.find_all("div", attrs={"data-pla-item": True})
            if not products:
                products = soup.find_all("a", href=re.compile(r"/shopping/product/"))
            if not products:
                products = soup.find_all("div", class_=re.compile(r"sh-dgr|product"))
            if not products:
                all_links = soup.find_all("a", href=True)
                products = [
                    link for link in all_links
                    if re.search(r"€|EUR|\d+[.,]\d+", str(link))
                ]

            if not products:
                logger.warning("Google Shopping: keine Produkte gefunden, HTML-Struktur evtl. geändert")
                # Debug-HTML optional speichern (nur im Container sinnvoll)
                debug_path = f"/tmp/google_shopping_debug_{int(time.time())}.html"
                try:
                    with open(debug_path, "w", encoding="utf-8") as f:
                        f.write(response.text)
                    logger.info(f"Debug HTML gespeichert unter {debug_path}")
                except Exception as e:
                    logger.debug(f"Konnte Debug-HTML nicht speichern: {e}")
                return competitors

            for idx, product in enumerate(products[:max_results]):
                try:
                    # Link
                    if product.name == "a":
                        link = product.get("href")
                    else:
                        link_elem = product.find("a", href=True)
                        link = link_elem["href"] if link_elem else None
                    if not link:
                        continue

                    if link.startswith("/url?"):
                        parsed = parse_qs(link)
                        link = parsed.get("q", [None])[0]
                    elif link.startswith("/shopping"):
                        link = f"https://www.google.com{link}"

                    if not link or not link.startswith("http"):
                        continue

                    # Preis (best effort)
                    price = None
                    price_elem = product.find(string=re.compile(r"€|EUR"))
                    if price_elem:
                        price_text = str(price_elem).replace(" ", "").replace("\n", "")
                        m = re.search(r"(\d+[.,]\d+)", price_text)
                        if m:
                            try:
                                price = float(m.group(1).replace(",", "."))
                            except ValueError:
                                price = None

                    # Shop-Name aus Domain
                    domain = urlparse(link).netloc
                    shop_name = domain.replace("www.", "").split(".")[0].capitalize() if domain else "Unknown"

                    competitors.append(
                        {
                            "competitor_name": shop_name,
                            "competitor_url": link,
                            "estimated_price": price,
                            "source": "google_shopping_api",
                        }
                    )
                    logger.info(f"[Google {idx+1}] {shop_name}: {price} – {link[:80]}...")

                except Exception as e:
                    logger.debug(f"Fehler beim Parsen eines Google-Produkts: {e}")
                    continue

            logger.info(f"ScrapingAnt: {len(competitors)} Wettbewerber gefunden")
            return competitors

        except requests.Timeout:
            logger.error("ScrapingAnt Timeout (30s)")
            return competitors
        except Exception as e:
            logger.error(f"ScrapingAnt Fehler: {e}", exc_info=True)
            return competitors

    def discover_competitors_google_shopping(self, product_title: str, max_results: int = 10) -> List[Dict]:
        """
        Primäre Methode: Google Shopping via ScrapingAnt.
        Fallback: Manuelle Google-Suche falls API nicht verfügbar.
        """
        # 1) Primär über ScrapingAnt API
        competitors = self._scrape_with_api(product_title, max_results)
        if competitors:
            return competitors

        # 2) Fallback: Manuelle Suche
        logger.warning("Nutze Fallback: Manuelle Google-Shopping-Suche (kein automatisches Scraping).")
        manual_url = f"https://www.google.com/search?tbm=shop&q={quote_plus(product_title)}&hl=de"
        return [
            {
                "competitor_name": "Manual Search",
                "competitor_url": manual_url,
                "estimated_price": None,
                "source": "fallback",
                "instructions": "API nicht verfügbar oder keine Ergebnisse. Bitte Link öffnen und Wettbewerber-URLs manuell hinzufügen.",
            }
        ]
    
    def discover_competitors_idealo(self, product_title: str, max_results: int = 10) -> List[Dict]:
        """
        Findet Wettbewerber über Idealo (deutsche Preisvergleichsseite)
        
        Args:
            product_title: Produktname/Titel
            max_results: Maximale Anzahl Ergebnisse
            
        Returns:
            List of Dicts mit competitor_name, competitor_url, estimated_price
        """
        competitors = []
        
        try:
            search_query = quote_plus(product_title)
            search_url = f"https://www.idealo.de/preisvergleich/MainSearchProduct.html?q={search_query}"
            
            logger.info(f"Suche Wettbewerber auf Idealo für: {product_title}")
            
            response = requests.get(search_url, headers=self.headers, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"Idealo Request fehlgeschlagen: {response.status_code}")
                return competitors
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Idealo Ergebnisse parsen
            # Typische Struktur: Angebote mit Shop-Links
            offers = soup.find_all('div', class_=re.compile(r'offer|priceRow|merchant'))
            
            for offer in offers[:max_results]:
                try:
                    # Preis
                    price_elem = offer.find(text=re.compile(r'€|\d+[.,]\d+'))
                    if not price_elem:
                        price_elem = offer.find('span', class_=re.compile(r'price'))
                    
                    estimated_price = None
                    if price_elem:
                        price_text = price_elem.get_text() if hasattr(price_elem, 'get_text') else str(price_elem)
                        price_match = re.search(r'(\d+[.,]\d+|\d+)', price_text.replace(' ', ''))
                        if price_match:
                            estimated_price = float(price_match.group(1).replace(',', '.'))
                    
                    # Link
                    link_elem = offer.find('a', href=True)
                    if not link_elem:
                        continue
                    
                    url = link_elem['href']
                    if not url.startswith('http'):
                        url = urljoin('https://www.idealo.de', url)
                    
                    # Shop-Name
                    shop_elem = offer.find(text=re.compile(r'bei|von|shop', re.I))
                    shop_name = "Idealo Shop"
                    if shop_elem:
                        shop_name = shop_elem.strip()
                    
                    competitors.append({
                        'competitor_name': shop_name,
                        'competitor_url': url,
                        'estimated_price': estimated_price,
                        'source': 'idealo'
                    })
                    
                except Exception as e:
                    logger.debug(f"Fehler beim Parsen Idealo-Ergebnis: {e}")
                    continue
            
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Fehler bei Idealo Suche: {e}", exc_info=True)
        
        return competitors
    
    def discover_competitors_geizhals(self, product_title: str, max_results: int = 10) -> List[Dict]:
        """
        Findet Wettbewerber über Geizhals (österreichische/deutsche Preisvergleichsseite)
        
        Args:
            product_title: Produktname/Titel
            max_results: Maximale Anzahl Ergebnisse
            
        Returns:
            List of Dicts mit competitor_name, competitor_url, estimated_price
        """
        competitors = []
        
        try:
            search_query = quote_plus(product_title)
            search_url = f"https://geizhals.de/?fs={search_query}"
            
            logger.info(f"Suche Wettbewerber auf Geizhals für: {product_title}")
            
            response = requests.get(search_url, headers=self.headers, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"Geizhals Request fehlgeschlagen: {response.status_code}")
                return competitors
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Geizhals Ergebnisse parsen
            offers = soup.find_all('tr', class_=re.compile(r'offer|price'))
            
            for offer in offers[:max_results]:
                try:
                    # Preis
                    price_elem = offer.find('span', class_=re.compile(r'price|amount'))
                    estimated_price = None
                    if price_elem:
                        price_text = price_elem.get_text()
                        price_match = re.search(r'(\d+[.,]\d+|\d+)', price_text.replace(' ', ''))
                        if price_match:
                            estimated_price = float(price_match.group(1).replace(',', '.'))
                    
                    # Link
                    link_elem = offer.find('a', href=True)
                    if not link_elem:
                        continue
                    
                    url = link_elem['href']
                    if not url.startswith('http'):
                        url = urljoin('https://geizhals.de', url)
                    
                    # Shop-Name
                    shop_name = "Geizhals Shop"
                    shop_elem = offer.find('span', class_=re.compile(r'merchant|shop'))
                    if shop_elem:
                        shop_name = shop_elem.get_text().strip()
                    
                    competitors.append({
                        'competitor_name': shop_name,
                        'competitor_url': url,
                        'estimated_price': estimated_price,
                        'source': 'geizhals'
                    })
                    
                except Exception as e:
                    logger.debug(f"Fehler beim Parsen Geizhals-Ergebnis: {e}")
                    continue
            
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Fehler bei Geizhals Suche: {e}", exc_info=True)
        
        return competitors
    
    def discover_all_competitors(self, product_title: str, max_per_source: int = 5) -> List[Dict]:
        """
        Findet Wettbewerber über alle verfügbaren Quellen (Google via API, Idealo, Geizhals)
        """
        all_competitors: List[Dict] = []
        seen_urls = set()

        # 1) Google Shopping (ScrapingAnt)
        google = self.discover_competitors_google_shopping(product_title, max_per_source)
        for comp in google:
            url = comp.get("competitor_url")
            if url and url not in seen_urls:
                all_competitors.append(comp)
                seen_urls.add(url)

        # 2) Idealo (wenn Google wenig liefert)
        if len(all_competitors) < 3:
            idealo = self.discover_competitors_idealo(product_title, max_per_source)
            for comp in idealo:
                url = comp.get("competitor_url")
                if url and url not in seen_urls:
                    all_competitors.append(comp)
                    seen_urls.add(url)

        # 3) Geizhals (wenn immer noch wenig)
        if len(all_competitors) < 5:
            geizhals = self.discover_competitors_geizhals(product_title, max_per_source)
            for comp in geizhals:
                url = comp.get("competitor_url")
                if url and url not in seen_urls:
                    all_competitors.append(comp)
                    seen_urls.add(url)

        logger.info(f"Gesamt {len(all_competitors)} Wettbewerber für '{product_title}' gefunden")
        return all_competitors
    
    def discover_and_scrape(self, product_title: str, product_id: int, db) -> Dict:
        """
        Findet Wettbewerber automatisch und scraped deren Preise
        
        Args:
            product_title: Produktname
            product_id: Product ID für Datenbank
            db: Database Session
            
        Returns:
            Dict mit success, competitors_found, competitors_scraped, errors
        """
        from app.models.competitor import CompetitorPrice
        
        logger.info(f"Starte automatische Wettbewerber-Erkennung für Produkt {product_id}: {product_title}")
        
        # Finde Wettbewerber
        discovered = self.discover_all_competitors(product_title, max_per_source=5)
        
        if not discovered:
            return {
                'success': False,
                'competitors_found': 0,
                'competitors_scraped': 0,
                'errors': ['Keine Wettbewerber gefunden']
            }
        
        # Scrape Preise für jeden gefundenen Wettbewerber
        scraped_count = 0
        errors = []
        
        for idx, comp in enumerate(discovered):
            try:
                # Prüfe ob bereits vorhanden
                existing = db.query(CompetitorPrice).filter(
                    CompetitorPrice.product_id == product_id,
                    CompetitorPrice.competitor_url == comp['competitor_url']
                ).first()
                
                if existing:
                    logger.debug(f"Wettbewerber bereits vorhanden: {comp['competitor_url']}")
                    continue
                
                # Scrape Preis
                logger.info(f"[{idx+1}/{len(discovered)}] Scrape {comp['competitor_name']}")
                scrape_result = scrape_competitor_price(comp['competitor_url'], delay=2.5 if idx > 0 else 0)
                
                # Speichere in DB
                new_competitor = CompetitorPrice(
                    product_id=product_id,
                    competitor_name=comp['competitor_name'],
                    competitor_url=comp['competitor_url'],
                    price=scrape_result.get('price') or comp.get('estimated_price'),
                    scrape_success=scrape_result['success'],
                    last_error=scrape_result.get('error'),
                    in_stock=scrape_result.get('in_stock', True)
                )
                
                db.add(new_competitor)
                scraped_count += 1
                
                if not scrape_result['success']:
                    errors.append(f"{comp['competitor_name']}: {scrape_result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Fehler beim Scrapen von {comp['competitor_url']}: {e}")
                errors.append(f"{comp['competitor_name']}: {str(e)}")
                continue
        
        db.commit()
        
        logger.info(f"Automatische Erkennung abgeschlossen: {scraped_count}/{len(discovered)} erfolgreich")
        
        return {
            'success': True,
            'competitors_found': len(discovered),
            'competitors_scraped': scraped_count,
            'errors': errors
        }


