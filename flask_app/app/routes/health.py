"""
Health Check API Routes
========================
Endpoints for service health monitoring and status checks.

Endpoints:
- GET /api/health - Basic health check
- GET /api/health/detailed - Detailed health with component status
- GET /api/status - Service status and version info
"""

from flask import Blueprint, jsonify, current_app
from app.utils import error_details
from app.models import model_manager
from app.utils.auth import log_request
import datetime
import os
import sys

health_bp = Blueprint('health', __name__)

# Service version
VERSION = '1.0.0'


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Basic health check endpoint.

    Response:
        {
            "status": "healthy",
            "timestamp": "2024-01-15T10:30:00Z",
            "version": "1.0.0"
        }
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'version': VERSION
    })


@health_bp.route('/health/detailed', methods=['GET'])
@log_request
def detailed_health():
    """
    Detailed health check with component status.

    Response:
        {
            "status": "healthy",
            "components": {
                "api": {"status": "healthy"},
                "models": {
                    "status": "healthy",
                    "trend_model": "loaded",
                    "meta_model": "loaded"
                },
                "database": {"status": "healthy"}
            },
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    components = {}
    overall_status = 'healthy'

    # Check API
    components['api'] = {'status': 'healthy'}

    # Check models
    try:
        trend_model = model_manager.get_trend_model()
        meta_model = model_manager.get_meta_model()

        models_status = {
            'status': 'healthy',
            'trend_model': 'loaded' if trend_model is not None else 'not_loaded',
            'meta_model': 'loaded' if meta_model is not None else 'not_loaded',
            'models_loaded': model_manager._loaded
        }

        # If no models are loaded, mark as degraded (not unhealthy)
        if trend_model is None and meta_model is None:
            models_status['status'] = 'degraded'
            models_status['note'] = 'No ML models loaded - using rule-based predictions'

        components['models'] = models_status

    except Exception as e:
        components['models'] = {
            'status': 'unhealthy',
            'error': error_details(e)
        }
        overall_status = 'degraded'

    # Check database connection
    try:
        from app.utils.database import db_manager, get_ticker_summary
        # Try a simple query to verify connectivity
        tickers = get_ticker_summary()
        components['database'] = {
            'status': 'healthy',
            'tickers_available': len(tickers),
            'tickers': [t['ticker'] for t in tickers]
        }
    except ImportError:
        components['database'] = {
            'status': 'not_configured',
            'note': 'Database module not installed'
        }
    except Exception as e:
        components['database'] = {
            'status': 'unhealthy',
            'error': error_details(e)
        }
        overall_status = 'degraded'

    # Check src modules availability
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        from src.data_fetcher import get_stock_data
        from src.technical_indicators import calculate_all_indicators
        from src.options_pricing import analyze_option_pricing

        components['src_modules'] = {
            'status': 'healthy',
            'modules_available': ['data_fetcher', 'technical_indicators', 'options_pricing']
        }
    except ImportError as e:
        components['src_modules'] = {
            'status': 'unhealthy',
            'error': error_details(e)
        }
        overall_status = 'unhealthy'

    return jsonify({
        'status': overall_status,
        'components': components,
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'version': VERSION
    })


@health_bp.route('/status', methods=['GET'])
@log_request
def service_status():
    """
    Get service status and configuration info.

    Response:
        {
            "service": "trading-api",
            "version": "1.0.0",
            "environment": "development",
            "config": {
                "api_key_required": false,
                "rate_limiting": true,
                "cors_enabled": true
            },
            "uptime": "2h 15m",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    # Get environment
    env = 'production' if not current_app.config.get('DEBUG', False) else 'development'
    if current_app.config.get('TESTING', False):
        env = 'testing'

    return jsonify({
        'service': 'trading-prediction-api',
        'version': VERSION,
        'environment': env,
        'config': {
            'api_key_required': current_app.config.get('API_KEY_REQUIRED', False),
            'rate_limiting': current_app.config.get('RATELIMIT_ENABLED', True),
            'cors_enabled': True,
            'debug_mode': current_app.config.get('DEBUG', False)
        },
        'endpoints': {
            'predictions': [
                'POST /api/predict',
                'POST /api/analyze',
                'GET /api/indicators/<ticker>'
            ],
            'options': [
                'POST /api/options/analyze',
                'POST /api/options/price',
                'GET /api/options/chain/<ticker>',
                'GET /api/options/expirations/<ticker>'
            ],
            'health': [
                'GET /api/health',
                'GET /api/health/detailed',
                'GET /api/status'
            ]
        },
        'timestamp': datetime.datetime.utcnow().isoformat()
    })


@health_bp.route('/ready', methods=['GET'])
def readiness_check():
    """
    Kubernetes readiness probe endpoint.

    Returns 200 if service is ready to accept traffic.
    Returns 503 if service is not ready.
    """
    try:
        from app.utils.database import db_manager
        with db_manager.get_cursor() as cursor:
            cursor.execute("SELECT 1")
        return jsonify({
            'ready': True,
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        return jsonify({
            'ready': False,
            'reason': str(e),
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 503


@health_bp.route('/live', methods=['GET'])
def liveness_check():
    """
    Kubernetes liveness probe endpoint.

    Returns 200 if service is alive.
    """
    return jsonify({
        'alive': True,
        'timestamp': datetime.datetime.utcnow().isoformat()
    }), 200
