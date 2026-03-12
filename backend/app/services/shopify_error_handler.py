"""
Shopify Error Handler - Verbesserte Error Messages und Handling
"""
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ShopifyErrorHandler:
    """
    Error Handler für Shopify API Errors.
    
    Konvertiert Shopify-spezifische Errors in benutzerfreundliche Messages.
    """
    
    # Bekannte Shopify Error Codes
    ERROR_MESSAGES = {
        'THROTTLED': 'Zu viele Anfragen. Bitte warte kurz und versuche es erneut.',
        'PRODUCT_NOT_FOUND': 'Produkt nicht auf Shopify gefunden.',
        'VARIANT_NOT_FOUND': 'Produkt-Variante nicht gefunden.',
        'INVALID_PRICE': 'Ungültiger Preis. Preis muss größer als 0 sein.',
        'PERMISSION_DENIED': 'Keine Berechtigung für diese Aktion. Prüfe Shopify API Scopes.',
        'GRAPHQL_ERROR': 'Shopify API Fehler. Bitte versuche es später erneut.',
        'NETWORK_ERROR': 'Netzwerkfehler. Prüfe Internetverbindung.',
        'TIMEOUT': 'Zeitüberschreitung. Shopify antwortet nicht.',
    }
    
    @staticmethod
    def parse_shopify_error(error: Exception) -> Dict:
        """
        Parsed Shopify Error und gibt benutzerfreundliche Message zurück.
        
        Args:
            error: Exception von Shopify API
            
        Returns:
            Dict mit error_code, message, details
        """
        error_str = str(error).lower()
        
        # Rate Limit / Throttling
        if 'throttled' in error_str or 'rate limit' in error_str or '429' in error_str:
            return {
                'error_code': 'THROTTLED',
                'message': ShopifyErrorHandler.ERROR_MESSAGES['THROTTLED'],
                'details': 'Shopify API Rate Limit erreicht',
                'retry_after': 2  # Sekunden
            }
        
        # Product Not Found
        if 'product not found' in error_str or '404' in error_str:
            return {
                'error_code': 'PRODUCT_NOT_FOUND',
                'message': ShopifyErrorHandler.ERROR_MESSAGES['PRODUCT_NOT_FOUND'],
                'details': str(error)
            }
        
        # Variant Not Found
        if 'variant not found' in error_str:
            return {
                'error_code': 'VARIANT_NOT_FOUND',
                'message': ShopifyErrorHandler.ERROR_MESSAGES['VARIANT_NOT_FOUND'],
                'details': str(error)
            }
        
        # Invalid Price
        if 'invalid price' in error_str or 'price must be' in error_str:
            return {
                'error_code': 'INVALID_PRICE',
                'message': ShopifyErrorHandler.ERROR_MESSAGES['INVALID_PRICE'],
                'details': str(error)
            }
        
        # Permission Denied
        if 'permission' in error_str or 'forbidden' in error_str or '403' in error_str:
            return {
                'error_code': 'PERMISSION_DENIED',
                'message': ShopifyErrorHandler.ERROR_MESSAGES['PERMISSION_DENIED'],
                'details': 'API Scopes: write_products erforderlich'
            }
        
        # Timeout
        if 'timeout' in error_str or 'timed out' in error_str:
            return {
                'error_code': 'TIMEOUT',
                'message': ShopifyErrorHandler.ERROR_MESSAGES['TIMEOUT'],
                'details': str(error)
            }
        
        # Network Error
        if 'connection' in error_str or 'network' in error_str:
            return {
                'error_code': 'NETWORK_ERROR',
                'message': ShopifyErrorHandler.ERROR_MESSAGES['NETWORK_ERROR'],
                'details': str(error)
            }
        
        # Generic GraphQL Error
        if 'graphql' in error_str:
            return {
                'error_code': 'GRAPHQL_ERROR',
                'message': ShopifyErrorHandler.ERROR_MESSAGES['GRAPHQL_ERROR'],
                'details': str(error)
            }
        
        # Unknown Error
        return {
            'error_code': 'UNKNOWN_ERROR',
            'message': 'Ein unbekannter Fehler ist aufgetreten.',
            'details': str(error)
        }
    
    @staticmethod
    def log_error(error: Exception, context: Optional[Dict] = None):
        """
        Loggt Shopify Error mit Context.
        
        Args:
            error: Exception
            context: Zusätzlicher Context (product_id, variant_id, etc.)
            
        Returns:
            Parsed error info
        """
        parsed = ShopifyErrorHandler.parse_shopify_error(error)
        
        log_message = f"❌ Shopify Error [{parsed['error_code']}]: {parsed['message']}"
        
        if context:
            log_message += f" | Context: {context}"
        
        logger.error(log_message, exc_info=True)
        
        return parsed
