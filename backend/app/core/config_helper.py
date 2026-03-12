"""
Config Helper - Sicheres Laden der DATABASE_URL mit Encoding-Fixes
"""
import os
import logging
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """
    Lädt DATABASE_URL sicher mit Encoding-Fixes.
    
    Returns:
        Saubere DATABASE_URL
    """
    # Versuche aus Environment Variable
    db_url = os.getenv("DATABASE_URL")
    
    if db_url:
        # Entferne BOM falls vorhanden
        db_url = db_url.strip('\ufeff').strip()
        
        # Versuche Encoding zu fixen
        try:
            # Versuche zu UTF-8 zu konvertieren
            if isinstance(db_url, bytes):
                db_url = db_url.decode('utf-8', errors='replace')
            
            # Entferne problematische Bytes (BOM, etc.)
            db_url = db_url.encode('utf-8', errors='ignore').decode('utf-8')
            
            # Prüfe ob URL gültig ist
            if not db_url.startswith(('postgresql://', 'postgres://')):
                logger.warning("DATABASE_URL hat ungültiges Format, nutze Fallback...")
                return build_database_url_from_components()
            
            return db_url
        except Exception as e:
            logger.warning(f"Fehler beim Parsen der DATABASE_URL: {e}, nutze Fallback...")
            return build_database_url_from_components()
    
    # Fallback: Baue URL aus einzelnen Komponenten
    logger.warning("DATABASE_URL nicht gefunden, nutze Fallback...")
    return build_database_url_from_components()


def fix_database_url_encoding(url: str) -> str:
    """Fixet Encoding-Probleme in DATABASE_URL"""
    try:
        # Parse URL und encode Passwort
        # postgresql://user:password@host:port/db
        parts = url.split("://")
        if len(parts) != 2:
            return url
        
        protocol = parts[0]
        rest = parts[1]
        
        # Split in user:password@host:port/db
        if "@" in rest:
            auth_part, host_part = rest.split("@", 1)
            
            if ":" in auth_part:
                user, password = auth_part.split(":", 1)
                # URL-encode Passwort
                password_encoded = quote_plus(password)
                
                return f"{protocol}://{user}:{password_encoded}@{host_part}"
        
        return url
    except Exception as e:
        logger.error(f"Fehler beim Fixen der DATABASE_URL: {e}")
        return url


def build_database_url_from_components() -> str:
    """Baut DATABASE_URL aus einzelnen Komponenten (Fallback)"""
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "vlerafy")
    
    # URL-encode Passwort
    db_password_encoded = quote_plus(db_password)
    
    return f"postgresql://{db_user}:{db_password_encoded}@{db_host}:{db_port}/{db_name}"


# Test-Funktion
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    url = get_database_url()
    # Verstecke Passwort in Output
    if "@" in url:
        parts = url.split("@")
        if len(parts) == 2:
            user_pass = parts[0].split("//")[-1]
            if ":" in user_pass:
                user = user_pass.split(":")[0]
                url_safe = url.replace(user_pass, f"{user}:***")
                print(f"DATABASE_URL: {url_safe}")
            else:
                print(f"DATABASE_URL: {url}")
        else:
            print(f"DATABASE_URL: {url}")
    else:
        print(f"DATABASE_URL: {url}")
