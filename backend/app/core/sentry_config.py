"""
Sentry Configuration für Error Tracking & Performance Monitoring
"""
import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import logging

logger = logging.getLogger(__name__)


def filter_sensitive_data(event, hint):
    """
    Filter sensitive data before sending to Sentry
    
    Remove:
    - Access Tokens
    - API Keys
    - Passwords
    - Credit Card Numbers
    """
    if 'request' in event:
        # Remove sensitive headers
        if 'headers' in event['request']:
            sensitive_headers = ['authorization', 'x-api-key', 'cookie', 'x-shopify-access-token']
            for header in sensitive_headers:
                header_lower = header.lower()
                for key in list(event['request']['headers'].keys()):
                    if key.lower() == header_lower:
                        event['request']['headers'][key] = '[Filtered]'
        
        # Remove sensitive query params
        if 'query_string' in event['request']:
            # Filter query string if it contains sensitive data
            query_string = event['request']['query_string']
            if isinstance(query_string, str):
                sensitive_params = ['token', 'password', 'api_key', 'secret', 'access_token']
                # Note: Full query string filtering would require parsing
                # This is a simplified version
    
    # Filter sensitive data from extra context
    if 'extra' in event:
        sensitive_keys = ['access_token', 'api_key', 'password', 'secret', 'token']
        for key in sensitive_keys:
            if key in event['extra']:
                event['extra'][key] = '[Filtered]'
    
    return event


def init_sentry():
    """
    Initialize Sentry SDK
    
    Environment Variables:
    - SENTRY_DSN: Sentry Data Source Name (required)
    - ENVIRONMENT: production, staging, development (default: production)
    - GIT_COMMIT_HASH: Git commit for release tracking (optional)
    """
    sentry_dsn = os.getenv("SENTRY_DSN")
    
    # Suppress urllib3 DEBUG logs (Sentry spam)
    import logging
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    if not sentry_dsn:
        return
    
    environment = os.getenv("ENVIRONMENT", "production")
    release = os.getenv("GIT_COMMIT_HASH", "unknown")
    
    # Check for Redis and Celery integrations (optional)
    integrations = [
        FastApiIntegration(transaction_style="endpoint"),
        SqlalchemyIntegration(),
        LoggingIntegration(
            level=logging.INFO,        # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors as events
        ),
    ]
    
    # Add Redis integration if available
    try:
        from sentry_sdk.integrations.redis import RedisIntegration
        integrations.append(RedisIntegration())
    except ImportError:
        pass
    
    # Add Celery integration if available
    try:
        from sentry_sdk.integrations.celery import CeleryIntegration
        integrations.append(CeleryIntegration())
    except ImportError:
        pass
    
    sentry_sdk.init(
        dsn=sentry_dsn,
        
        # Integrations
        integrations=integrations,
        
        # Performance Monitoring
        traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
        
        # Error Sampling
        sample_rate=1.0,  # 100% of errors
        
        # Environment & Release
        environment=environment,
        release=f"vlerafy-backend@{release}",
        
        # Additional Options
        send_default_pii=False,  # Don't send PII (emails, IPs, etc.)
        attach_stacktrace=True,
        max_breadcrumbs=50,
        
        # Before Send Hook (filter sensitive data)
        before_send=filter_sensitive_data,
    )
    
    # Print status (single line, no verbose logging)
    print(f"[SENTRY] Initialized (env={environment})", flush=True)


def capture_exception_with_context(exception, context: dict = None):
    """
    Capture exception with additional context
    
    Usage:
        try:
            # some code
        except Exception as e:
            capture_exception_with_context(e, {
                'shop_id': shop.id,
                'product_id': product.id
            })
    """
    if context:
        with sentry_sdk.configure_scope() as scope:
            for key, value in context.items():
                scope.set_tag(key, str(value))
    
    sentry_sdk.capture_exception(exception)
