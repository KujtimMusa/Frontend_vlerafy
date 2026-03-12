import os
from cryptography.fernet import Fernet
from app.config import settings


def get_cipher():
    """
    Get Fernet cipher for encryption/decryption
    
    Raises:
        ValueError: If ENCRYPTION_KEY is not set
    """
    encryption_key = settings.ENCRYPTION_KEY or os.getenv("ENCRYPTION_KEY")
    
    if not encryption_key:
        raise ValueError(
            "ENCRYPTION_KEY environment variable must be set. "
            "Generate one with: python scripts/generate_keys.py"
        )
    
    return Fernet(encryption_key.encode())


def encrypt_token(token: str) -> str:
    """
    Encrypt access token for secure database storage
    
    Args:
        token: Plaintext Shopify access token
        
    Returns:
        Encrypted token string (Base64 encoded)
    """
    cipher = get_cipher()
    return cipher.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt access token from database
    
    Args:
        encrypted_token: Encrypted token from database
        
    Returns:
        Plaintext access token
    """
    cipher = get_cipher()
    return cipher.decrypt(encrypted_token.encode()).decode()


