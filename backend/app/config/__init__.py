"""
Configuration package for Vlerafy

This package provides:
- settings: Application settings (database, API keys, etc.)
- feature_metadata: Feature categorization for confidence analysis
"""

# Export settings for backward compatibility
from app.config.settings import settings, Settings

# Export feature metadata
from app.config.feature_metadata import (
    FEATURE_CATEGORIES,
    CATEGORY_NAMES,
    get_status
)

__all__ = [
    'settings',
    'Settings',
    'FEATURE_CATEGORIES',
    'CATEGORY_NAMES',
    'get_status'
]
