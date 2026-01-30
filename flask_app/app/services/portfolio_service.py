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
    """Get database configuration from environment."""
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'trading_data'),
        'user': os.getenv('DB_USER', 'trading'),
        'password': os.getenv('DB_PASSWORD', 'trading123'),
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
