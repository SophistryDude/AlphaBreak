"""
Dashboard Routes
================
Serves data for the 4 frontend dashboard widgets:

1. GET /api/dashboard/market-sentiment   -- Overall market bullish/bearish
2. GET /api/dashboard/sector-sentiment   -- Per-GICS-sector sentiment
3. GET /api/dashboard/index-sentiment    -- VIX, S&P/RUT/QQQ, inverse ETFs
4. GET /api/dashboard/commodities-crypto -- Gold, Silver, ETH, BTC hourly prices

All endpoints use a simple TTL cache to avoid hammering yfinance / DB.
"""

import time
import logging
from flask import Blueprint, jsonify, current_app
from app.utils.auth import log_request, require_api_key

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)

# ──────────────────────────────────────────────────────────────────────────────
# Simple TTL cache
# ──────────────────────────────────────────────────────────────────────────────

_cache = {}
CACHE_TTL = {
    'market_sentiment': 300,     # 5 minutes
    'sector_sentiment': 300,     # 5 minutes
    'index_sentiment': 300,      # 5 minutes
    'commodities_crypto': 60,    # 1 minute
}


def _get_cached(key, compute_fn):
    """Return cached data or compute + cache it."""
    now = time.time()
    if key in _cache:
        data, expiry = _cache[key]
        if now < expiry:
            return data
    data = compute_fn()
    _cache[key] = (data, now + CACHE_TTL.get(key, 300))
    return data


# ──────────────────────────────────────────────────────────────────────────────
# Helper: get optional DB manager
# ──────────────────────────────────────────────────────────────────────────────

def _get_db_manager():
    """Try to get the database manager, return None if unavailable."""
    try:
        from app.utils.database import db_manager
        return db_manager
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@dashboard_bp.route('/dashboard/market-sentiment', methods=['GET'])
@log_request
@require_api_key
def market_sentiment():
    """Overall market sentiment with weekly S&P 500 chart data."""
    try:
        from app.services.dashboard_service import compute_market_sentiment
        db = _get_db_manager()
        data = _get_cached('market_sentiment', lambda: compute_market_sentiment(db))
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Market sentiment error: {e}")
        return jsonify({'error': 'Failed to compute market sentiment', 'details': str(e)}), 500


@dashboard_bp.route('/dashboard/sector-sentiment', methods=['GET'])
@log_request
@require_api_key
def sector_sentiment():
    """Per-sector sentiment for all 11 GICS sectors."""
    try:
        from app.services.dashboard_service import compute_sector_sentiments
        data = _get_cached('sector_sentiment', compute_sector_sentiments)
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Sector sentiment error: {e}")
        return jsonify({'error': 'Failed to compute sector sentiment', 'details': str(e)}), 500


@dashboard_bp.route('/dashboard/index-sentiment', methods=['GET'])
@log_request
@require_api_key
def index_sentiment():
    """VIX fear level, S&P/RUT/QQQ sentiment, inverse ETF signal."""
    try:
        from app.services.dashboard_service import compute_index_sentiment
        db = _get_db_manager()
        data = _get_cached('index_sentiment', lambda: compute_index_sentiment(db))
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Index sentiment error: {e}")
        return jsonify({'error': 'Failed to compute index sentiment', 'details': str(e)}), 500


@dashboard_bp.route('/dashboard/commodities-crypto', methods=['GET'])
@log_request
@require_api_key
def commodities_crypto():
    """Gold, Silver, Ethereum, Bitcoin hourly prices with TLEV signals."""
    try:
        from app.services.dashboard_service import compute_commodities_crypto
        data = _get_cached('commodities_crypto', compute_commodities_crypto)
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Commodities/crypto error: {e}")
        return jsonify({'error': 'Failed to fetch commodity/crypto data', 'details': str(e)}), 500
