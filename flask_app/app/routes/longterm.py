"""
Long Term Trading Routes
========================
Endpoints for the Long Term Trading tab:

1. GET /api/longterm/holdings                -- Top institutional holdings
2. GET /api/longterm/ticker/<ticker>         -- Full detail for a ticker
3. GET /api/longterm/ticker/<ticker>/compare -- Weekly comparison only
4. GET /api/longterm/sectors                 -- Sector-level summary
"""

import re
import time
import logging
from flask import Blueprint, jsonify, request, current_app
from app.utils.auth import log_request, require_api_key

logger = logging.getLogger(__name__)

longterm_bp = Blueprint('longterm', __name__)

# ──────────────────────────────────────────────────────────────────────────────
# Simple TTL cache
# ──────────────────────────────────────────────────────────────────────────────

_cache = {}
CACHE_TTL = {
    'holdings': 600,        # 10 minutes (13F data is quarterly)
    'ticker_detail': 300,   # 5 minutes
    'comparison': 600,      # 10 minutes
    'sectors': 600,         # 10 minutes
}


def _get_cached(key, compute_fn, ttl_key='ticker_detail'):
    """Return cached data or compute + cache it."""
    now = time.time()
    if key in _cache:
        data, expiry = _cache[key]
        if now < expiry:
            return data
    data = compute_fn()
    _cache[key] = (data, now + CACHE_TTL.get(ttl_key, 300))
    return data


def _get_db_manager():
    """Try to get the database manager, return None if unavailable."""
    try:
        from app.utils.database import db_manager
        return db_manager
    except Exception:
        return None


TICKER_RE = re.compile(r'^[A-Z]{1,5}(-[A-Z])?$')


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/longterm/holdings
# ──────────────────────────────────────────────────────────────────────────────

@longterm_bp.route('/longterm/holdings', methods=['GET'])
@log_request
@require_api_key
def longterm_holdings():
    """Top institutional holdings from 13F filings."""
    min_funds = request.args.get('min_funds', 3, type=int)
    limit = request.args.get('limit', 50, type=int)
    sector = request.args.get('sector', '', type=str).strip()

    min_funds = max(1, min(min_funds, 20))
    limit = max(10, min(limit, 200))

    try:
        cache_key = f"longterm_holdings:{min_funds}:{limit}"
        data = _get_cached(cache_key, lambda: _fetch_holdings(min_funds, limit),
                           ttl_key='holdings')

        if sector:
            filtered = [h for h in data.get('holdings', [])
                        if h.get('sector', '').lower() == sector.lower()]
            data = {**data, 'holdings': filtered}

        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Longterm holdings error: {e}")
        return jsonify({
            'error': 'Failed to fetch institutional holdings',
            'details': str(e),
        }), 500


def _fetch_holdings(min_funds, limit):
    """Delegate to longterm_service."""
    from app.services.longterm_service import fetch_top_institutional_holdings
    db = _get_db_manager()
    return fetch_top_institutional_holdings(db, min_funds, limit)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/longterm/ticker/<ticker>
# ──────────────────────────────────────────────────────────────────────────────

@longterm_bp.route('/longterm/ticker/<ticker>', methods=['GET'])
@log_request
@require_api_key
def longterm_ticker_detail(ticker):
    """Full long-term analysis for a single ticker."""
    ticker = ticker.strip().upper()
    if not TICKER_RE.match(ticker):
        return jsonify({'error': 'Invalid ticker format'}), 400

    weeks = request.args.get('weeks', 52, type=int)
    weeks = max(4, min(weeks, 260))

    try:
        cache_key = f"longterm_detail:{ticker}:{weeks}"
        data = _get_cached(cache_key, lambda: _fetch_detail(ticker, weeks),
                           ttl_key='ticker_detail')
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Longterm detail error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to fetch detail for {ticker}',
            'details': str(e),
        }), 500


def _fetch_detail(ticker, weeks):
    """Delegate to longterm_service."""
    from app.services.longterm_service import fetch_ticker_longterm_detail
    db = _get_db_manager()
    return fetch_ticker_longterm_detail(ticker, period_weeks=weeks, db_manager=db)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/longterm/ticker/<ticker>/compare
# ──────────────────────────────────────────────────────────────────────────────

@longterm_bp.route('/longterm/ticker/<ticker>/compare', methods=['GET'])
@log_request
@require_api_key
def longterm_ticker_compare(ticker):
    """Weekly comparison chart data only (lighter payload)."""
    ticker = ticker.strip().upper()
    if not TICKER_RE.match(ticker):
        return jsonify({'error': 'Invalid ticker format'}), 400

    weeks = request.args.get('weeks', 52, type=int)
    weeks = max(4, min(weeks, 260))

    try:
        cache_key = f"longterm_compare:{ticker}:{weeks}"
        data = _get_cached(cache_key, lambda: _fetch_comparison(ticker, weeks),
                           ttl_key='comparison')
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Longterm compare error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to fetch comparison for {ticker}',
            'details': str(e),
        }), 500


def _fetch_comparison(ticker, weeks):
    """Delegate to longterm_service."""
    from app.services.longterm_service import fetch_weekly_comparison
    return fetch_weekly_comparison(ticker, period_weeks=weeks)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/longterm/sectors
# ──────────────────────────────────────────────────────────────────────────────

@longterm_bp.route('/longterm/sectors', methods=['GET'])
@log_request
@require_api_key
def longterm_sectors():
    """Sector-level institutional holdings summary."""
    try:
        cache_key = "longterm_sectors"
        data = _get_cached(cache_key, _fetch_sectors, ttl_key='sectors')
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Longterm sectors error: {e}")
        return jsonify({
            'error': 'Failed to fetch sector summary',
            'details': str(e),
        }), 500


def _fetch_sectors():
    """Delegate to longterm_service."""
    from app.services.longterm_service import fetch_sector_holdings_summary
    db = _get_db_manager()
    return fetch_sector_holdings_summary(db)
