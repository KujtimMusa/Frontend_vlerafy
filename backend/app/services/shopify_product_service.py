"""
Shopify Product Service
Handles fetching product data from Shopify API with caching and rate limit management
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import httpx
import asyncio
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.shop import Shop

logger = logging.getLogger(__name__)


class ShopifyProductService:
    """Service for fetching product data from Shopify API"""
    
    # Cache configuration
    CACHE_TTL = 300  # 5 minutes in seconds
    _price_cache: Dict[str, Dict] = {}  # {cache_key: {'price': float, 'expires_at': datetime}}
    
    # Shopify API configuration
    API_VERSION = '2025-10'
    BATCH_SIZE = 250  # Shopify limit per request
    
    def __init__(self, db: Session = None):
        self.db = db
    
    def _get_db(self):
        """Get database session"""
        if self.db:
            return self.db
        return next(get_db())
    
    
    def _get_shop_credentials(self, shop_id: str) -> Optional[Dict]:
        """
        Get Shopify access token and domain from database
        
        Args:
            shop_id: Shop identifier (can be shop_id, shop_url, or shop_name)
        
        Returns:
            Dict with 'access_token' and 'shop_domain' or None
        """
        try:
            db = self._get_db()
            
            # Try to find shop by different fields
            shop = db.query(Shop).filter(
                (Shop.id == shop_id) | 
                (Shop.shop_url.contains(shop_id)) |
                (Shop.shop_name == shop_id)
            ).first()
            
            if not shop or not shop.access_token:
                logger.error(f"Shop {shop_id} not found or missing access token")
                return None
            
            # Extract shop domain from shop_url (e.g., "shop123.myshopify.com")
            shop_domain = shop.shop_url.replace('https://', '').replace('http://', '').split('/')[0]
            
            from app.utils.encryption import decrypt_token
            return {
                'access_token': decrypt_token(shop.access_token),
                'shop_domain': shop_domain
            }
        except Exception as e:
            logger.error(f"Failed to get shop credentials: {e}")
            return None
    
    
    def _get_cache_key(self, shop_id: str, product_id: str) -> str:
        """Generate cache key for a product price"""
        return f"{shop_id}:{product_id}"
    
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached price is still valid"""
        if cache_key not in self._price_cache:
            return False
        
        cached = self._price_cache[cache_key]
        return datetime.utcnow() < cached['expires_at']
    
    
    def _set_cache(self, cache_key: str, price: float, title: str = None):
        """Store price in cache"""
        self._price_cache[cache_key] = {
            'price': price,
            'title': title,
            'expires_at': datetime.utcnow() + timedelta(seconds=self.CACHE_TTL)
        }
    
    
    def _get_from_cache(self, cache_key: str) -> Optional[float]:
        """Get price from cache if valid"""
        if self._is_cache_valid(cache_key):
            return self._price_cache[cache_key]['price']
        return None
    
    
    async def get_product_price(
        self,
        product_id: str,
        shop_id: str,
        use_cache: bool = True
    ) -> Optional[float]:
        """
        Get current price for a single product from Shopify
        
        Args:
            product_id: Shopify Product ID
            shop_id: Shop identifier
            use_cache: Whether to use cached price
        
        Returns:
            Product price as float or None if not found
        """
        
        # Check cache first
        cache_key = self._get_cache_key(shop_id, product_id)
        if use_cache:
            cached_price = self._get_from_cache(cache_key)
            if cached_price is not None:
                logger.debug(f"Cache hit for product {product_id}")
                return cached_price
        
        # Get shop credentials
        credentials = self._get_shop_credentials(shop_id)
        if not credentials:
            return None
        
        # Fetch from Shopify API
        try:
            url = f"https://{credentials['shop_domain']}/admin/api/{self.API_VERSION}/products/{product_id}.json"
            headers = {
                'X-Shopify-Access-Token': credentials['access_token'],
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"Rate limited, retry after {retry_after}s")
                    await asyncio.sleep(retry_after)
                    # Retry once
                    response = await client.get(url, headers=headers, timeout=10.0)
                
                response.raise_for_status()
                data = response.json()
                
                # Extract price from first variant
                product = data.get('product', {})
                variants = product.get('variants', [])
                
                if not variants:
                    logger.warning(f"Product {product_id} has no variants")
                    return None
                
                # Get price from first variant
                price_str = variants[0].get('price', '0')
                price = float(price_str)
                
                # Cache the result
                title = product.get('title', '')
                self._set_cache(cache_key, price, title)
                
                logger.info(f"Fetched price for {product_id}: €{price:.2f}")
                return price
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching product {product_id}: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error fetching product {product_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching product {product_id}: {e}")
            return None
    
    
    async def get_multiple_product_prices(
        self,
        product_ids: List[str],
        shop_id: str,
        use_cache: bool = True
    ) -> Dict[str, Optional[float]]:
        """
        Get prices for multiple products (batch operation)
        
        Args:
            product_ids: List of Shopify Product IDs
            shop_id: Shop identifier
            use_cache: Whether to use cached prices
        
        Returns:
            Dict mapping product_id to price
        """
        
        results = {}
        uncached_ids = []
        
        # Check cache first
        if use_cache:
            for product_id in product_ids:
                cache_key = self._get_cache_key(shop_id, product_id)
                cached_price = self._get_from_cache(cache_key)
                if cached_price is not None:
                    results[product_id] = cached_price
                else:
                    uncached_ids.append(product_id)
        else:
            uncached_ids = product_ids
        
        # If all cached, return early
        if not uncached_ids:
            logger.debug(f"All {len(product_ids)} prices from cache")
            return results
        
        logger.info(f"Fetching {len(uncached_ids)} prices from Shopify (cached: {len(results)})")
        
        # Get shop credentials
        credentials = self._get_shop_credentials(shop_id)
        if not credentials:
            # Fill missing with None
            for product_id in uncached_ids:
                results[product_id] = None
            return results
        
        # Batch fetch from Shopify using parallel requests
        try:
            # Fetch in parallel (with semaphore to limit concurrency)
            semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
            
            async def fetch_with_semaphore(pid):
                async with semaphore:
                    price = await self.get_product_price(pid, shop_id, use_cache=False)
                    return pid, price
            
            tasks = [fetch_with_semaphore(pid) for pid in uncached_ids]
            fetched = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in fetched:
                if isinstance(result, Exception):
                    logger.error(f"Failed to fetch price: {result}")
                    continue
                
                product_id, price = result
                results[product_id] = price
            
            return results
            
        except Exception as e:
            logger.error(f"Batch fetch failed: {e}")
            # Fill missing with None
            for product_id in uncached_ids:
                if product_id not in results:
                    results[product_id] = None
            return results
    
    
    async def get_all_products_with_prices(
        self,
        shop_id: str,
        limit: int = 250
    ) -> List[Dict]:
        """
        Get all products with prices from Shopify
        
        Args:
            shop_id: Shop identifier
            limit: Max products per page
        
        Returns:
            List of dicts with product data
        """
        
        credentials = self._get_shop_credentials(shop_id)
        if not credentials:
            return []
        
        try:
            all_products = []
            url = f"https://{credentials['shop_domain']}/admin/api/{self.API_VERSION}/products.json"
            headers = {
                'X-Shopify-Access-Token': credentials['access_token'],
                'Content-Type': 'application/json'
            }
            params = {'limit': min(limit, self.BATCH_SIZE)}
            
            async with httpx.AsyncClient() as client:
                while url:
                    response = await client.get(url, headers=headers, params=params, timeout=30.0)
                    
                    # Handle rate limiting
                    if response.status_code == 429:
                        retry_after = int(response.headers.get('Retry-After', 2))
                        logger.warning(f"Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    products = data.get('products', [])
                    
                    for product in products:
                        # Extract data
                        product_id = str(product.get('id'))
                        title = product.get('title', '')
                        variants = product.get('variants', [])
                        
                        if variants:
                            price = float(variants[0].get('price', 0))
                            
                            # Cache it
                            cache_key = self._get_cache_key(shop_id, product_id)
                            self._set_cache(cache_key, price, title)
                            
                            all_products.append({
                                'product_id': product_id,
                                'title': title,
                                'price': price,
                                'inventory_quantity': sum(v.get('inventory_quantity', 0) for v in variants)
                            })
                    
                    # Pagination using Link header
                    link_header = response.headers.get('Link', '')
                    url = self._extract_next_page_url(link_header)
                    params = None  # Params are in the next URL
                    
                    logger.info(f"Fetched {len(products)} products, total: {len(all_products)}")
                
                return all_products
                
        except Exception as e:
            logger.error(f"Failed to fetch all products: {e}")
            return []
    
    
    def _extract_next_page_url(self, link_header: str) -> Optional[str]:
        """Extract next page URL from Link header"""
        if not link_header:
            return None
        
        # Parse Link header: <url>; rel="next"
        parts = link_header.split(',')
        for part in parts:
            if 'rel="next"' in part or "rel='next'" in part:
                url = part.split(';')[0].strip('<> ')
                return url
        
        return None
    
    
    def clear_cache(self, shop_id: str = None, product_id: str = None):
        """
        Clear price cache
        
        Args:
            shop_id: Clear cache for specific shop (all products)
            product_id: Clear cache for specific product
        """
        if shop_id and product_id:
            # Clear specific product
            cache_key = self._get_cache_key(shop_id, product_id)
            self._price_cache.pop(cache_key, None)
            logger.info(f"Cleared cache for {product_id}")
        elif shop_id:
            # Clear all products for shop
            keys_to_remove = [k for k in self._price_cache.keys() if k.startswith(f"{shop_id}:")]
            for key in keys_to_remove:
                self._price_cache.pop(key, None)
            logger.info(f"Cleared cache for shop {shop_id} ({len(keys_to_remove)} products)")
        else:
            # Clear all cache
            count = len(self._price_cache)
            self._price_cache.clear()
            logger.info(f"Cleared entire cache ({count} entries)")


# Singleton instance (optional, for convenience)
_shopify_service_instance = None

def get_shopify_service(db: Session = None) -> ShopifyProductService:
    """Get or create ShopifyProductService instance"""
    global _shopify_service_instance
    if _shopify_service_instance is None or db is not None:
        _shopify_service_instance = ShopifyProductService(db)
    return _shopify_service_instance






























