"""
Earnings Routes
===============
Serves data for the Quarterly Earnings tab:

1. GET /api/earnings/calendar   -- Upcoming earnings for top 100 + custom tickers
2. GET /api/earnings/ticker/<ticker> -- Detail: CBOE activity, daily chart, news
"""

import re
import time
import logging
from flask import Blueprint, jsonify, request, current_app
from app.utils.auth import log_request, require_api_key

logger = logging.getLogger(__name__)

earnings_bp = Blueprint('earnings', __name__)

# ──────────────────────────────────────────────────────────────────────────────
# Simple TTL cache
# ──────────────────────────────────────────────────────────────────────────────

_cache = {}
CACHE_TTL = {
    'calendar': 300,       # 5 minutes
    'ticker_detail': 300,  # 5 minutes per ticker
}


def _get_cached(key, compute_fn):
    """Return cached data or compute + cache it."""
    now = time.time()
    if key in _cache:
        data, expiry = _cache[key]
        if now < expiry:
            return data
    data = compute_fn()
    ttl_key = 'calendar' if key.startswith('calendar') else 'ticker_detail'
    _cache[key] = (data, now + CACHE_TTL.get(ttl_key, 300))
    return data


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

TICKER_RE = re.compile(r'^[A-Z]{1,5}(-[A-Z])?$')


@earnings_bp.route('/earnings/calendar', methods=['GET'])
@log_request
@require_api_key
def earnings_calendar():
    """Upcoming earnings calendar for top stocks + custom tickers."""
    try:
        custom_tickers_param = request.args.get('custom_tickers', '')
        custom_tickers = None
        if custom_tickers_param:
            raw = [t.strip().upper() for t in custom_tickers_param.split(',')]
            custom_tickers = [t for t in raw if t and TICKER_RE.match(t)]

        cache_key = f"calendar:{custom_tickers_param}"
        db = _get_db_manager()

        from app.services.earnings_service import fetch_earnings_calendar
        data = _get_cached(cache_key, lambda: fetch_earnings_calendar(custom_tickers, db_manager=db))
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Earnings calendar error: {e}")
        return jsonify({'error': 'Failed to fetch earnings calendar', 'details': str(e)}), 500


@earnings_bp.route('/earnings/ticker/<ticker>', methods=['GET'])
@log_request
@require_api_key
def earnings_ticker_detail(ticker):
    """Detailed earnings data for a single ticker (CBOE, chart, news)."""
    ticker = ticker.strip().upper()
    if not TICKER_RE.match(ticker):
        return jsonify({'error': 'Invalid ticker format'}), 400

    try:
        cache_key = f"ticker_detail:{ticker}"

        from app.services.earnings_service import fetch_ticker_detail
        data = _get_cached(cache_key, lambda: fetch_ticker_detail(ticker))
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Earnings ticker detail error for {ticker}: {e}")
        return jsonify({'error': f'Failed to fetch data for {ticker}', 'details': str(e)}), 500
