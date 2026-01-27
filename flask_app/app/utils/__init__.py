"""
Utility modules for the Trading Prediction API.

Modules:
- validation: Input validation decorators and schemas
- auth: API key authentication and request logging
- database: Database connection and query utilities
"""

from .validation import validate_request, ValidationError
from .auth import require_api_key, log_request, protected_endpoint

__all__ = [
    'validate_request',
    'ValidationError',
    'require_api_key',
    'log_request',
    'protected_endpoint'
]
