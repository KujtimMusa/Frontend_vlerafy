"""
Web Scraper für Competitor Price Tracking
Unterstützt Shopify, WooCommerce und generische E-Commerce Sites
"""
import requests
from bs4 import BeautifulSoup
import re
from typing import Dict, Optional
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)


def scrape_competitor_price(url: str, delay: float = 0.0) -> Dict:
    """
    Scrape price from competitor URL.
    Returns dict with success status, price, error message.
    
    Supports:
    - Shopify Standard
    - WooCommerce
    - Meta Tags (og:price, product:price)
    - Generic E-Commerce patterns
    
    Args:
        url: Competitor product URL
        delay: Optional delay before request (for rate limiting)
        
    Returns:
        Dict with keys: success, price, error, in_stock, scraped_at
    """
    
    if delay > 0:
        time.sleep(delay)
    
    try:
        # Request with realistic User-Agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return {
                'success': False,
                'price': None,
                'error': f'HTTP {response.status_code}',
                'in_stock': False,
                'scraped_at': datetime.utcnow()
            }
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Price Extraction Patterns (prioritized by reliability)
        price_patterns = [
            # Meta Tags (most reliable)
            {'selector': 'meta[property="og:price:amount"]', 'attr': 'content', 'priority': 1},
            {'selector': 'meta[property="product:price:amount"]', 'attr': 'content', 'priority': 1},
            {'selector': 'meta[name="product:price:amount"]', 'attr': 'content', 'priority': 1},
            {'selector': 'meta[itemprop="price"]', 'attr': 'content', 'priority': 1},
            
            # Shopify Standard
            {'selector': 'span.price', 'attr': None, 'priority': 2},
            {'selector': 'span[data-product-price]', 'attr': 'data-product-price', 'priority': 2},
            {'selector': '.product-price span', 'attr': None, 'priority': 2},
            {'selector': '[data-price]', 'attr': 'data-price', 'priority': 2},
            {'selector': '.price--current', 'attr': None, 'priority': 2},
            
            # WooCommerce
            {'selector': 'span.woocommerce-Price-amount', 'attr': None, 'priority': 3},
            {'selector': 'p.price span.amount', 'attr': None, 'priority': 3},
            {'selector': '.price ins .amount', 'attr': None, 'priority': 3},
            {'selector': '.woocommerce-Price-amount.amount', 'attr': None, 'priority': 3},
            
            # Generic fallbacks
            {'selector': '.product-price', 'attr': None, 'priority': 4},
            {'selector': '[itemprop="price"]', 'attr': 'content', 'priority': 4},
            {'selector': '.price', 'attr': None, 'priority': 4},
            {'selector': '#price', 'attr': None, 'priority': 4},
        ]
        
        # Sort by priority
        price_patterns.sort(key=lambda x: x['priority'])
        
        for pattern in price_patterns:
            try:
                element = soup.select_one(pattern['selector'])
                if element:
                    price_text = element.get(pattern['attr']) if pattern['attr'] else element.text
                    
                    if not price_text:
                        continue
                    
                    # Extract numeric value
                    # Handles: €299.99, $299,99, 299.99 EUR, 299,99, 299.99€
                    price_text_clean = price_text.replace(' ', '').replace('\n', '').replace('\t', '')
                    
                    # Try multiple patterns
                    patterns = [
                        r'(\d+[.,]\d+)',  # 299.99 or 299,99
                        r'(\d+)',  # 299
                    ]
                    
                    for regex_pattern in patterns:
                        price_match = re.search(regex_pattern, price_text_clean)
                        if price_match:
                            price_str = price_match.group(1).replace(',', '.')
                            price = float(price_str)
                            
                            # Validation: Price should be reasonable (€1 - €10000)
                            if 1.0 <= price <= 10000.0:
                                logger.info(f"Successfully scraped {url}: €{price} (pattern: {pattern['selector']})")
                                
                                return {
                                    'success': True,
                                    'price': price,
                                    'error': None,
                                    'in_stock': True,
                                    'scraped_at': datetime.utcnow()
                                }
            except Exception as e:
                logger.debug(f"Pattern {pattern['selector']} failed: {e}")
                continue
        
        # No price found
        logger.warning(f"Price not found on {url}")
        return {
            'success': False,
            'price': None,
            'error': 'Price element not found',
            'in_stock': False,
            'scraped_at': datetime.utcnow()
        }
        
    except requests.Timeout:
        logger.error(f"Timeout scraping {url}")
        return {
            'success': False,
            'price': None,
            'error': 'Timeout',
            'in_stock': False,
            'scraped_at': datetime.utcnow()
        }
    
    except requests.RequestException as e:
        logger.error(f"Request error scraping {url}: {str(e)}")
        return {
            'success': False,
            'price': None,
            'error': f'Request error: {str(e)}',
            'in_stock': False,
            'scraped_at': datetime.utcnow()
        }
    
    except Exception as e:
        logger.error(f"Scraping error for {url}: {str(e)}", exc_info=True)
        return {
            'success': False,
            'price': None,
            'error': str(e),
            'in_stock': False,
            'scraped_at': datetime.utcnow()
        }


def validate_url(url: str) -> bool:
    """
    Validate competitor URL format
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    
    return url.startswith(('http://', 'https://')) and len(url) > 10
































