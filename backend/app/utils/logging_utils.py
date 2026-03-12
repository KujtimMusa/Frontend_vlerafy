"""
Logging Utilities
Decorators and helpers for execution time tracking
"""
import logging
import functools
import time
import asyncio
from typing import Callable

def log_execution_time(func: Callable):
    """Decorator to log function execution time"""
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        start = time.time()
        
        try:
            logger.debug(f"⏱️  {func.__name__}() started")
            result = await func(*args, **kwargs)
            duration = (time.time() - start) * 1000
            logger.debug(f"✅ {func.__name__}() completed in {duration:.2f}ms")
            return result
        
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"❌ {func.__name__}() failed after {duration:.2f}ms: {e}", exc_info=True)
            raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        start = time.time()
        
        try:
            logger.debug(f"⏱️  {func.__name__}() started")
            result = func(*args, **kwargs)
            duration = (time.time() - start) * 1000
            logger.debug(f"✅ {func.__name__}() completed in {duration:.2f}ms")
            return result
        
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"❌ {func.__name__}() failed after {duration:.2f}ms: {e}", exc_info=True)
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper















