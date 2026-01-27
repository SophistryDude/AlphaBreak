"""
Authentication Module
======================
API key authentication and request logging utilities.

Provides:
- API key validation middleware
- Request logging decorator
- Rate limiting helpers
"""

from functools import wraps
from flask import request, jsonify, current_app, g
from typing import Callable, Optional
import hashlib
import time
import logging

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Custom authentication error."""
    def __init__(self, message: str, code: str = 'AUTH_ERROR'):
        self.message = message
        self.code = code
        super().__init__(message)


def require_api_key(f: Callable) -> Callable:
    """
    Decorator to require API key authentication.

    API key can be provided via:
    - Header: X-API-Key
    - Query parameter: api_key

    Example:
        @app.route('/api/protected')
        @require_api_key
        def protected_endpoint():
            return jsonify({'message': 'Access granted'})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if API key is required
        if not current_app.config.get('API_KEY_REQUIRED', True):
            return f(*args, **kwargs)

        # Get API key from header or query param
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')

        if not api_key:
            logger.warning(f"Missing API key from {request.remote_addr}")
            return jsonify({
                'error': 'API key required',
                'code': 'MISSING_API_KEY',
                'message': 'Please provide an API key via X-API-Key header or api_key query parameter'
            }), 401

        # Validate API key
        valid_keys = current_app.config.get('API_KEYS', [])

        if not valid_keys:
            # No keys configured - allow access in development
            if current_app.config.get('DEBUG', False):
                logger.warning("No API keys configured, allowing access in debug mode")
                return f(*args, **kwargs)
            else:
                logger.error("No API keys configured in production")
                return jsonify({
                    'error': 'Server configuration error',
                    'code': 'CONFIG_ERROR'
                }), 500

        # Check if provided key is valid
        if api_key not in valid_keys:
            logger.warning(f"Invalid API key attempt from {request.remote_addr}")
            return jsonify({
                'error': 'Invalid API key',
                'code': 'INVALID_API_KEY'
            }), 401

        # Store API key identifier in request context for logging
        g.api_key_id = hashlib.sha256(api_key.encode()).hexdigest()[:8]

        return f(*args, **kwargs)

    return decorated_function


def log_request(f: Callable) -> Callable:
    """
    Decorator to log API requests with timing information.

    Logs:
    - Request method and path
    - Client IP
    - API key identifier (if authenticated)
    - Response status
    - Request duration

    Example:
        @app.route('/api/endpoint')
        @log_request
        def my_endpoint():
            return jsonify({'status': 'ok'})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()

        # Log request
        api_key_id = getattr(g, 'api_key_id', 'anonymous')
        logger.info(
            f"REQUEST: {request.method} {request.path} | "
            f"IP: {request.remote_addr} | "
            f"Key: {api_key_id}"
        )

        # Execute function
        response = f(*args, **kwargs)

        # Calculate duration
        duration = time.time() - start_time

        # Get status code
        if isinstance(response, tuple):
            status_code = response[1]
        else:
            status_code = response.status_code if hasattr(response, 'status_code') else 200

        logger.info(
            f"RESPONSE: {request.method} {request.path} | "
            f"Status: {status_code} | "
            f"Duration: {duration:.3f}s"
        )

        return response

    return decorated_function


def get_client_ip() -> str:
    """
    Get the client's real IP address, accounting for proxies.

    Returns:
        Client IP address string
    """
    # Check for forwarded IP (behind proxy/load balancer)
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        # X-Forwarded-For can contain multiple IPs; first is the client
        return forwarded.split(',')[0].strip()

    # Check for real IP header
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip

    # Fall back to remote_addr
    return request.remote_addr or 'unknown'


def generate_api_key() -> str:
    """
    Generate a new random API key.

    Returns:
        32-character hexadecimal API key

    Note:
        This is a utility function for key generation.
        Generated keys should be stored securely.
    """
    import secrets
    return secrets.token_hex(16)


def hash_api_key(api_key: str) -> str:
    """
    Create a hash of an API key for secure storage.

    Args:
        api_key: The API key to hash

    Returns:
        SHA-256 hash of the key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    pass


def check_rate_limit(key: str, limit: int, window: int) -> bool:
    """
    Check if a rate limit has been exceeded.

    This is a simple in-memory implementation.
    For production, use Redis-based rate limiting via Flask-Limiter.

    Args:
        key: Unique identifier for rate limiting (e.g., IP or API key)
        limit: Maximum number of requests allowed
        window: Time window in seconds

    Returns:
        True if within limit, False if exceeded
    """
    # This is handled by Flask-Limiter in __init__.py
    # This function is here for custom rate limiting logic if needed
    return True


# Decorator combining auth and logging
def protected_endpoint(f: Callable) -> Callable:
    """
    Convenience decorator combining API key auth and request logging.

    Example:
        @app.route('/api/secure')
        @protected_endpoint
        def secure_endpoint():
            return jsonify({'data': 'secret'})
    """
    @wraps(f)
    @require_api_key
    @log_request
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function
