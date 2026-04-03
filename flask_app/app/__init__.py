"""
Flask Application Factory

Creates and configures the Flask application with all necessary extensions,
blueprints, and error handlers.
"""

from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from logging.handlers import RotatingFileHandler
import os


def create_app(config_name='development'):
    """
    Flask application factory.

    Args:
        config_name: Configuration environment (development, production, testing)

    Returns:
        Flask app instance
    """
    app = Flask(__name__)

    # Load configuration
    config_module = f'app.config.{config_name.capitalize()}Config'
    app.config.from_object(config_module)

    # Enable CORS for frontend access
    CORS(app, resources={r"/api/*": {"origins": app.config.get('CORS_ORIGINS', '*')}})

    # Rate limiting to prevent abuse
    # Exempt health check endpoints from rate limiting
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri=app.config.get('RATELIMIT_STORAGE_URL', 'memory://'),
        default_limits_exempt_when=lambda: False,  # Apply limits by default
    )

    # Exempt health/ready/live endpoints from rate limiting (for K8s probes)
    @limiter.request_filter
    def exempt_health_endpoints():
        from flask import request
        exempt_paths = ['/api/health', '/api/ready', '/api/live']
        return any(request.path.startswith(path) for path in exempt_paths)

    # Setup logging
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')

        file_handler = RotatingFileHandler(
            'logs/trading_api.log',
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Trading API startup')

    # Register blueprints
    from app.routes.health import health_bp
    from app.routes.predictions import predictions_bp
    from app.routes.options import options_bp
    from app.routes.frontend_compat import frontend_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.reports import reports_bp
    from app.routes.watchlist import watchlist_bp
    from app.routes.earnings import earnings_bp
    from app.routes.longterm import longterm_bp
    from app.routes.portfolio import portfolio_bp
    from app.routes.forex import forex_bp
    from app.routes.auth import auth_bp
    from app.routes.user import user_bp
    from app.routes.notifications import notifications_bp

    app.register_blueprint(health_bp, url_prefix='/api')
    app.register_blueprint(predictions_bp, url_prefix='/api')
    app.register_blueprint(options_bp, url_prefix='/api')
    app.register_blueprint(frontend_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp, url_prefix='/api')
    app.register_blueprint(reports_bp, url_prefix='/api')
    app.register_blueprint(watchlist_bp, url_prefix='/api')
    app.register_blueprint(earnings_bp, url_prefix='/api')
    app.register_blueprint(longterm_bp, url_prefix='/api')
    app.register_blueprint(portfolio_bp, url_prefix='/api')
    app.register_blueprint(forex_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(user_bp, url_prefix='/api')
    app.register_blueprint(notifications_bp, url_prefix='/api')

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Server Error: {error}')
        return jsonify({'error': 'Internal server error'}), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        app.logger.error(f'Unhandled Exception: {error}')
        return jsonify({'error': 'An unexpected error occurred'}), 500

    # Initialize model manager on startup
    # Note: before_first_request is deprecated in Flask 2.3+
    # Using with app.app_context() instead
    with app.app_context():
        from app.models import model_manager
        try:
            model_manager.load_models()
            app.logger.info('Models loaded successfully')
        except Exception as e:
            app.logger.warning(f'Models not loaded (this is OK if models not trained yet): {e}')

    return app
