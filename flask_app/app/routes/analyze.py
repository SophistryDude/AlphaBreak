"""
Analyze Routes
==============
Single-ticker deep-dive endpoints for the Analyze tab:

1. GET  /api/analyze/<ticker>           -- Full analyze data
2. GET  /api/analyze/<ticker>/chart     -- Enhanced chart data
3. GET  /api/analyze/search             -- Ticker autocomplete
"""

import re
import time
import logging
from flask import Blueprint, jsonify, request, current_app
from app.utils.auth import log_request, require_api_key

logger = logging.getLogger(__name__)

analyze_bp = Blueprint('analyze', __name__)

# ──────────────────────────────────────────────────────────────────────────────
# Cache
# ──────────────────────────────────────────────────────────────────────────────

_cache = {}
CACHE_TTL = 60  # 1 minute

TICKER_PATTERN = re.compile(r'^[A-Z]{1,5}(-[A-Z])?$')


def _get_cached(key, compute_fn, ttl=CACHE_TTL):
    now = time.time()
    if key in _cache:
        data, expiry = _cache[key]
        if now < expiry:
            return data
    data = compute_fn()
    _cache[key] = (data, now + ttl)
    return data


def _get_db_manager():
    try:
        from app.utils.database import db_manager
        return db_manager
    except Exception:
        return None


def _validate_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if not ticker or len(ticker) > 10:
        raise ValueError(f"Invalid ticker: {ticker}")
    if not TICKER_PATTERN.match(ticker):
        raise ValueError(f"Invalid ticker format: {ticker}")
    return ticker


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/search?q=APP
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/search', methods=['GET'])
@log_request
@require_api_key
def analyze_search():
    """
    Ticker autocomplete search.

    Query params:
        q: Search query (min 1 char)

    Returns array of {ticker, name, sector}.
    """
    query = request.args.get('q', '').strip()
    if len(query) < 1:
        return jsonify([])

    try:
        from app.services.analyze_service import search_tickers
        results = search_tickers(query)
        return jsonify(results)
    except Exception as e:
        current_app.logger.error(f"Analyze search error: {e}")
        return jsonify([])


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>', methods=['GET'])
@log_request
@require_api_key
def analyze_ticker(ticker):
    """
    Fetch full analyze data for a single ticker.

    Returns: header, stats, trend_break, indicators, signals,
    options, analyst, earnings, institutional, sector.
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        db = _get_db_manager()
        cache_key = f'analyze_{ticker}'

        result = _get_cached(
            cache_key,
            lambda: _fetch_analyze(ticker, db),
            ttl=CACHE_TTL,
        )

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Analyze error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to fetch analyze data for {ticker}',
            'details': str(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/chart?interval=1d&period=3mo
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/chart', methods=['GET'])
@log_request
@require_api_key
def analyze_chart(ticker):
    """
    Fetch enhanced OHLCV chart data.

    Query params:
        interval: 1m, 5m, 15m, 1h, 1d, 1wk, 1mo (default 1d)
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max (default 3mo)
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    interval = request.args.get('interval', '1d')
    period = request.args.get('period', '3mo')

    try:
        cache_key = f'analyze_chart_{ticker}_{period}_{interval}'

        result = _get_cached(
            cache_key,
            lambda: _fetch_chart(ticker, interval, period),
            ttl=CACHE_TTL,
        )

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Analyze chart error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to fetch chart data for {ticker}',
            'details': str(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_analyze(ticker, db_manager):
    from app.services.analyze_service import fetch_analyze_data
    return fetch_analyze_data(ticker, db_manager)


def _fetch_chart(ticker, interval, period):
    from app.services.analyze_service import fetch_enhanced_chart
    return fetch_enhanced_chart(ticker, interval, period)
