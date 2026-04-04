"""
Utility modules for the Trading Prediction API.

Modules:
- validation: Input validation decorators and schemas
- auth: API key authentication and request logging
- database: Database connection and query utilities
"""

from flask import current_app
from .validation import validate_request, ValidationError
from .auth import require_api_key, log_request, protected_endpoint


def error_details(e):
    """Return error details only in debug mode to prevent leaking internals."""
    if current_app.debug:
        return str(e)
    return None


__all__ = [
    'validate_request',
    'ValidationError',
    'require_api_key',
    'log_request',
    'protected_endpoint',
    'error_details',
]
