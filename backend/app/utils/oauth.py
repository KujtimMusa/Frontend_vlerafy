import hmac
import hashlib
import secrets
from urllib.parse import urlencode
from app.config import settings


def generate_install_url(shop: str, state: str = None) -> str:
    """
    Generate Shopify OAuth install URL
    
    Args:
        shop: Shop domain (e.g. 'example.myshopify.com')
        state: CSRF token (auto-generated if not provided)
    
    Returns:
        Complete OAuth authorization URL
    """
    if not state:
        state = secrets.token_urlsafe(32)
    
    params = {
        'client_id': settings.SHOPIFY_CLIENT_ID,
        'scope': settings.SHOPIFY_API_SCOPES,
        'redirect_uri': settings.SHOPIFY_REDIRECT_URI,
        'state': state,
        'grant_options[]': 'per-user'
    }
    
    base_url = f"https://{shop}/admin/oauth/authorize"
    return f"{base_url}?{urlencode(params)}"


def verify_hmac(params: dict, hmac_to_verify: str) -> bool:
    """
    Verify Shopify HMAC signature for security validation
    
    Args:
        params: Query parameters from Shopify callback
        hmac_to_verify: HMAC value to verify
    
    Returns:
        True if HMAC is valid, False otherwise
    """
    # Remove hmac and signature from params
    encoded_params = {
        key: value for key, value in params.items() 
        if key not in ['hmac', 'signature']
    }
    
    # Sort and create query string
    query_string = "&".join(
        f"{key}={value}" for key, value in sorted(encoded_params.items())
    )
    
    # Calculate HMAC using SHA256
    calculated_hmac = hmac.new(
        settings.SHOPIFY_CLIENT_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(calculated_hmac, hmac_to_verify)


async def exchange_code_for_token(shop: str, code: str) -> dict:
    """
    Exchange authorization code for permanent access token
    
    Args:
        shop: Shop domain
        code: Authorization code from Shopify OAuth callback
    
    Returns:
        Dict containing 'access_token' and 'scope'
        
    Raises:
        httpx.HTTPError: If token exchange fails
    """
    import httpx
    
    url = f"https://{shop}/admin/oauth/access_token"
    
    payload = {
        'client_id': settings.SHOPIFY_CLIENT_ID,
        'client_secret': settings.SHOPIFY_CLIENT_SECRET,
        'code': code
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


