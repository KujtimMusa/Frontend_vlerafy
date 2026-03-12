"""
Celery Tasks für Competitor Price Tracking
Tägliches automatisches Scraping von Wettbewerberpreisen
"""
from celery import shared_task
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import time
import logging

from app.database import SessionLocal
from app.models.competitor import CompetitorPrice
from app.models.product import Product
from app.services.competitor_scraper import scrape_competitor_price
from app.services.competitor_discovery import CompetitorDiscovery

logger = logging.getLogger(__name__)


@shared_task(name="update_competitor_prices")
def update_competitor_prices():
    """
    Daily task: Update all competitor prices.
    Runs at 3 AM to avoid peak traffic.
    """
    
    db = SessionLocal()
    
    try:
        # Get all competitors
        competitors = db.query(CompetitorPrice).all()
        
        total = len(competitors)
        success_count = 0
        fail_count = 0
        
        logger.info(f"Starting competitor price update: {total} competitors")
        
        for idx, comp in enumerate(competitors, 1):
            logger.info(f"[{idx}/{total}] Scraping {comp.competitor_name} ({comp.competitor_url})")
            
            # Scrape with rate limiting (2.5s delay)
            delay = 2.5 if idx > 1 else 0  # No delay for first request
            result = scrape_competitor_price(comp.competitor_url, delay=delay)
            
            # Update database
            if result['success']:
                comp.price = result['price']
                comp.scrape_success = True
                comp.last_error = None
                comp.in_stock = result.get('in_stock', True)
                success_count += 1
                logger.info(f"  ✅ Success: €{result['price']}")
            else:
                comp.scrape_success = False
                comp.last_error = result['error']
                comp.in_stock = result.get('in_stock', False)
                fail_count += 1
                logger.warning(f"  ❌ Failed: {result['error']}")
            
            comp.scraped_at = result.get('scraped_at', datetime.utcnow())
            db.commit()
        
        logger.info(f"Competitor update completed: {success_count} success, {fail_count} failed")
        
        return {
            'total': total,
            'success': success_count,
            'failed': fail_count
        }
        
    except Exception as e:
        logger.error(f"Task failed: {str(e)}", exc_info=True)
        db.rollback()
        raise
    
    finally:
        db.close()


@shared_task(name="auto_discover_competitors_daily")
def auto_discover_competitors_daily():
    """
    Tägliche automatische Wettbewerber-Erkennung für alle Produkte.
    Läuft täglich um 4:00 AM (nach Preis-Updates).
    """
    
    db = SessionLocal()
    
    try:
        # Hole alle aktiven Produkte ohne oder mit wenigen Wettbewerbern
        products = db.query(Product).all()
        
        logger.info(f"Starte automatische Wettbewerber-Erkennung für {len(products)} Produkte")
        
        discovery = CompetitorDiscovery()
        total_found = 0
        total_scraped = 0
        
        for idx, product in enumerate(products, 1):
            # Prüfe ob bereits Wettbewerber vorhanden
            existing_count = db.query(CompetitorPrice).filter(
                CompetitorPrice.product_id == product.id,
                CompetitorPrice.scrape_success == True
            ).count()
            
            # Nur wenn weniger als 3 erfolgreiche Wettbewerber vorhanden
            if existing_count >= 3:
                logger.debug(f"Produkt {product.id} hat bereits {existing_count} Wettbewerber, überspringe")
                continue
            
            logger.info(f"[{idx}/{len(products)}] Suche Wettbewerber für: {product.title}")
            
            try:
                result = discovery.discover_and_scrape(
                    product_title=product.title,
                    product_id=product.id,
                    db=db
                )
                
                total_found += result.get('competitors_found', 0)
                total_scraped += result.get('competitors_scraped', 0)
                
                # Rate Limiting zwischen Produkten
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Fehler bei automatischer Erkennung für Produkt {product.id}: {e}")
                continue
        
        logger.info(f"Automatische Erkennung abgeschlossen: {total_found} gefunden, {total_scraped} gescraped")
        
        return {
            'products_processed': len(products),
            'competitors_found': total_found,
            'competitors_scraped': total_scraped
        }
        
    except Exception as e:
        logger.error(f"Auto-Discovery Task fehlgeschlagen: {str(e)}", exc_info=True)
        db.rollback()
        raise
    
    finally:
        db.close()


@shared_task(name="retry_failed_scrapes")
def retry_failed_scrapes():
    """
    Retry competitors that failed in last scrape.
    Runs at 6 AM (3 hours after main update).
    """
    
    db = SessionLocal()
    
    try:
        # Get failed scrapes from last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        failed = db.query(CompetitorPrice).filter(
            CompetitorPrice.scrape_success == False,
            CompetitorPrice.scraped_at >= yesterday
        ).all()
        
        logger.info(f"Retrying {len(failed)} failed scrapes")
        
        retry_success = 0
        
        for idx, comp in enumerate(failed, 1):
            logger.info(f"[{idx}/{len(failed)}] Retrying {comp.competitor_name}")
            
            # Scrape with delay
            delay = 3.0 if idx > 1 else 0
            result = scrape_competitor_price(comp.competitor_url, delay=delay)
            
            if result['success']:
                comp.price = result['price']
                comp.scrape_success = True
                comp.last_error = None
                comp.in_stock = result.get('in_stock', True)
                comp.scraped_at = result.get('scraped_at', datetime.utcnow())
                db.commit()
                retry_success += 1
                logger.info(f"  ✅ Retry success: €{result['price']}")
            else:
                comp.last_error = result['error']
                comp.scraped_at = result.get('scraped_at', datetime.utcnow())
                db.commit()
                logger.warning(f"  ❌ Retry failed: {result['error']}")
        
        logger.info(f"Retry completed: {retry_success}/{len(failed)} recovered")
        
        return {'retried': len(failed), 'success': retry_success}
        
    except Exception as e:
        logger.error(f"Retry task failed: {str(e)}", exc_info=True)
        db.rollback()
        raise
    
    finally:
        db.close()

