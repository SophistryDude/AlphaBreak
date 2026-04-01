"""
Portfolio Service
=================
Provides PortfolioManager instance for Flask routes.
Manages database connection lifecycle.
"""

import os
import sys
import logging
from contextlib import contextmanager

# Add src to path for importing portfolio_manager
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

logger = logging.getLogger(__name__)

# Global manager instance (lazy initialized)
_manager = None


def get_db_config():
    """Get database configuration from environment.

    Reads TIMESERIES_DB_* env vars (set by K8s api-deployment.yaml),
    falling back to DB_* for Airflow compatibility.
    """
    return {
        'host': os.getenv('TIMESERIES_DB_HOST', os.getenv('DB_HOST', 'localhost')),
        'port': int(os.getenv('TIMESERIES_DB_PORT', os.getenv('DB_PORT', '5432'))),
        'database': os.getenv('TIMESERIES_DB_NAME', os.getenv('DB_NAME', 'trading_data')),
        'user': os.getenv('TIMESERIES_DB_USER', os.getenv('DB_USER', 'trading')),
        'password': os.getenv('TIMESERIES_DB_PASSWORD', os.getenv('DB_PASSWORD', 'trading_password')),
        'sslmode': os.getenv('DB_SSLMODE', 'prefer')
    }


def get_portfolio_manager():
    """
    Get or create the PortfolioManager instance.
    Uses lazy initialization with connection pooling.
    """
    global _manager

    if _manager is None:
        try:
            from portfolio_manager import PortfolioManager
            import psycopg2

            # Create connection with config
            config = get_db_config()
            conn = psycopg2.connect(**config)
            conn.autocommit = False

            _manager = PortfolioManager(conn=conn)
            logger.info("PortfolioManager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize PortfolioManager: {e}")
            raise

    # Check if connection is still alive
    try:
        _manager.conn.cursor().execute("SELECT 1")
    except Exception:
        # Reconnect
        logger.warning("Database connection lost, reconnecting...")
        import psycopg2
        config = get_db_config()
        _manager.conn = psycopg2.connect(**config)
        _manager.conn.autocommit = False

    return _manager


@contextmanager
def get_portfolio_manager_context():
    """
    Context manager for portfolio manager.
    Ensures proper cleanup of resources.
    """
    pm = get_portfolio_manager()
    try:
        yield pm
    except Exception:
        pm.conn.rollback()
        raise
    finally:
        pass  # Keep connection open for reuse
