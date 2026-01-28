"""
Watchlist Routes
================
Endpoints for user watchlist data:

1. POST /api/watchlist/data          -- Batch fetch data for multiple tickers
2. GET  /api/watchlist/ticker/<t>    -- Fetch data for a single ticker
"""

import re
import time
import logging
from flask import Blueprint, jsonify, request, current_app
from app.utils.auth import log_request, require_api_key

logger = logging.getLogger(__name__)

watchlist_bp = Blueprint('watchlist', __name__)

# ──────────────────────────────────────────────────────────────────────────────
# TTL cache for watchlist data
# ──────────────────────────────────────────────────────────────────────────────

_cache = {}
CACHE_TTL = 60  # 1 minute

TICKER_PATTERN = re.compile(r'^[A-Z]{1,5}(-[A-Z])?$')
MAX_TICKERS = 50


def _get_cached(key, compute_fn, ttl=CACHE_TTL):
    """Return cached data or compute + cache it."""
    now = time.time()
    if key in _cache:
        data, expiry = _cache[key]
        if now < expiry:
            return data
    data = compute_fn()
    _cache[key] = (data, now + ttl)
    return data


def _get_db_manager():
    """Try to get the database manager, return None if unavailable."""
    try:
        from app.utils.database import db_manager
        return db_manager
    except Exception:
        return None


def _validate_ticker(ticker: str) -> str:
    """Validate and normalize a ticker symbol. Returns uppercase ticker or raises ValueError."""
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Empty ticker")
    if len(ticker) > 10:
        raise ValueError(f"Ticker too long: {ticker}")
    if not TICKER_PATTERN.match(ticker):
        raise ValueError(f"Invalid ticker format: {ticker}")
    return ticker


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/watchlist/data
# ──────────────────────────────────────────────────────────────────────────────

@watchlist_bp.route('/watchlist/data', methods=['POST'])
@log_request
@require_api_key
def watchlist_data():
    """
    Batch fetch data for watchlisted tickers.

    Request body:
        {"tickers": ["AAPL", "NVDA", "TSLA"]}

    Returns securities data array + errors array.
    """
    data = request.get_json(silent=True)
    if not data or 'tickers' not in data:
        return jsonify({
            'error': 'Request must include JSON body with "tickers" array',
        }), 400

    raw_tickers = data['tickers']
    if not isinstance(raw_tickers, list):
        return jsonify({'error': '"tickers" must be an array'}), 400

    if len(raw_tickers) > MAX_TICKERS:
        return jsonify({
            'error': f'Too many tickers. Maximum is {MAX_TICKERS}.',
        }), 400

    # Validate tickers
    tickers = []
    validation_errors = []
    for t in raw_tickers:
        try:
            tickers.append(_validate_ticker(str(t)))
        except ValueError as e:
            validation_errors.append({'ticker': str(t), 'error': str(e)})

    # Deduplicate
    tickers = list(dict.fromkeys(tickers))

    if not tickers:
        return jsonify({
            'securities': [],
            'errors': validation_errors,
            'fetched_at': None,
        })

    try:
        db = _get_db_manager()

        # Use cache key based on sorted ticker set
        cache_key = 'watchlist_' + '_'.join(sorted(tickers))

        result = _get_cached(
            cache_key,
            lambda: _fetch_batch(tickers, db),
            ttl=CACHE_TTL,
        )

        # Merge validation errors into result
        all_errors = validation_errors + result.get('errors', [])

        return jsonify({
            'securities': result.get('securities', []),
            'errors': all_errors,
            'fetched_at': result.get('fetched_at'),
        })

    except Exception as e:
        current_app.logger.error(f"Watchlist batch error: {e}")
        return jsonify({
            'error': 'Failed to fetch watchlist data',
            'details': str(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/watchlist/ticker/<ticker>
# ──────────────────────────────────────────────────────────────────────────────

@watchlist_bp.route('/watchlist/ticker/<ticker>', methods=['GET'])
@log_request
@require_api_key
def watchlist_ticker(ticker):
    """
    Fetch watchlist data for a single ticker.

    Returns full security data (price, trend_break, indicators, options).
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        db = _get_db_manager()

        cache_key = f'watchlist_single_{ticker}'

        result = _get_cached(
            cache_key,
            lambda: _fetch_single(ticker, db),
            ttl=CACHE_TTL,
        )

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Watchlist ticker error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to fetch data for {ticker}',
            'details': str(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/watchlist/ticker/<ticker>/chart
# ──────────────────────────────────────────────────────────────────────────────

VALID_CHART_INTERVALS = ('1d', '1h', '5m')

@watchlist_bp.route('/watchlist/ticker/<ticker>/chart', methods=['GET'])
@log_request
@require_api_key
def watchlist_ticker_chart(ticker):
    """
    Fetch OHLC candlestick chart data for a watchlist ticker.

    Query params:
        interval: '1d', '1h', or '5m' (default '1h')
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    interval = request.args.get('interval', '1h')
    if interval not in VALID_CHART_INTERVALS:
        return jsonify({
            'error': f'Invalid interval. Must be one of: {", ".join(VALID_CHART_INTERVALS)}'
        }), 400

    try:
        cache_key = f'watchlist_chart_{ticker}_{interval}'

        result = _get_cached(
            cache_key,
            lambda: _fetch_chart(ticker, interval),
            ttl=CACHE_TTL,
        )

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Watchlist chart error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to fetch chart data for {ticker}',
            'details': str(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_batch(tickers, db_manager):
    """Delegate to watchlist_service for batch fetch."""
    from app.services.watchlist_service import fetch_watchlist_data
    return fetch_watchlist_data(tickers, db_manager)


def _fetch_single(ticker, db_manager):
    """Delegate to watchlist_service for single ticker fetch."""
    from app.services.watchlist_service import fetch_single_ticker_data
    return fetch_single_ticker_data(ticker, db_manager)


def _fetch_chart(ticker, interval):
    """Delegate to watchlist_service for chart data fetch."""
    from app.services.watchlist_service import fetch_chart_data
    return fetch_chart_data(ticker, interval)
