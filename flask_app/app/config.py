"""
Configuration Management

Manages different configurations for development, production, and testing
environments using environment variables.
"""

import os
from datetime import timedelta


class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Model paths
    MODEL_DIR = os.environ.get('MODEL_DIR') or 'models'
    META_MODEL_PATH = os.path.join(MODEL_DIR, 'indicator_reliability_model.h5')
    TREND_MODEL_PATH = os.path.join(MODEL_DIR, 'trend_break_model.json')
    METADATA_PATH = os.path.join(MODEL_DIR, 'model_metadata.pkl')

    # API Configuration
    API_KEY_REQUIRED = os.environ.get('API_KEY_REQUIRED', 'True') == 'True'
    API_KEYS = os.environ.get('API_KEYS', '').split(',') if os.environ.get('API_KEYS') else []

    # CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')

    # Caching
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes

    # Rate limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URL = 'memory://'

    # Scheduler
    SCHEDULER_API_ENABLED = True

    # JWT Authentication
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-dev-secret-change-in-production'
    JWT_ACCESS_EXPIRES = 900  # 15 minutes
    JWT_REFRESH_EXPIRES = 604800  # 7 days
    JWT_ALGORITHM = 'HS256'
    BCRYPT_ROUNDS = 12

    # Password requirements
    PASSWORD_MIN_LENGTH = 8

    # Data Source Configuration
    # Options data source: 'yfinance', 'polygon', 'database'
    OPTIONS_DATA_SOURCE = os.environ.get('OPTIONS_DATA_SOURCE', 'yfinance')

    # Stock data source: 'yfinance', 'polygon', 'database'
    STOCK_DATA_SOURCE = os.environ.get('STOCK_DATA_SOURCE', 'yfinance')

    # Forex data source: 'yfinance', 'fred', 'database'
    FOREX_DATA_SOURCE = os.environ.get('FOREX_DATA_SOURCE', 'yfinance')

    # Notifications (AWS SES)
    SES_FROM_EMAIL = os.environ.get('SES_FROM_EMAIL', 'noreply@alphabreak.vip')
    SES_REGION = os.environ.get('AWS_SES_REGION', 'us-east-1')
    NOTIFICATIONS_ENABLED = os.environ.get('NOTIFICATIONS_ENABLED', 'true').lower() == 'true'


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    RATELIMIT_ENABLED = False
    API_KEY_REQUIRED = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

    # Use Redis for caching in production
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = os.environ.get('REDIS_URL') or 'redis://redis:6379/0'

    # Stricter rate limits
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL') or 'redis://redis:6379/1'

    # API key requirement (can be overridden via env var API_KEY_REQUIRED=false)
    API_KEY_REQUIRED = os.environ.get('API_KEY_REQUIRED', 'True').lower() not in ('false', '0', 'no')


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    RATELIMIT_ENABLED = False
    API_KEY_REQUIRED = False
