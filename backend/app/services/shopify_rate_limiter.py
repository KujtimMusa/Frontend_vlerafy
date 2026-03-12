"""
Rate Limiter für Shopify API - Verhindert Rate Limit Errors
"""
import time
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)


class ShopifyRateLimiter:
    """
    Rate Limiter für Shopify API Calls.
    
    Shopify Limits:
    - Standard: 2 Requests/Sekunde
    - Plus: 4 Requests/Sekunde
    - Advanced: 10 Requests/Sekunde
    
    Default: 2 Requests/Sekunde (konservativ)
    """
    
    def __init__(self, requests_per_second: int = 2):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second  # Zeit zwischen Requests
        self.last_request_time = None
    
    async def wait_if_needed(self):
        """Wartet falls nötig um Rate Limit einzuhalten"""
        if self.last_request_time is None:
            self.last_request_time = time.time()
            return
        
        elapsed = time.time() - self.last_request_time
        
        if elapsed < self.min_interval:
            wait_time = self.min_interval - elapsed
            logger.debug(f"⏱️ Rate Limit: Warte {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    async def execute_with_retry(
        self, 
        func: Callable, 
        *args, 
        max_retries: int = 3,
        **kwargs
    ) -> Any:
        """
        Führt Funktion mit Retry-Logic aus.
        
        Args:
            func: Async Funktion
            max_retries: Maximale Anzahl Retries
            *args, **kwargs: Argumente für func
            
        Returns:
            Result von func
        """
        for attempt in range(max_retries):
            try:
                # Warte für Rate Limit
                await self.wait_if_needed()
                
                # Führe Funktion aus
                result = await func(*args, **kwargs)
                
                return result
            
            except Exception as e:
                error_str = str(e).lower()
                
                # Shopify Rate Limit Error?
                if 'throttled' in error_str or 'rate limit' in error_str or '429' in error_str:
                    if attempt < max_retries - 1:
                        # Exponential Backoff
                        wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                        logger.warning(f"⚠️ Rate Limit! Retry {attempt + 1}/{max_retries} nach {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"❌ Rate Limit nach {max_retries} Retries überschritten")
                        raise
                
                # Andere Fehler → sofort werfen
                raise
        
        raise Exception(f"Max Retries ({max_retries}) erreicht")


# Global Instance
rate_limiter = ShopifyRateLimiter(requests_per_second=2)
