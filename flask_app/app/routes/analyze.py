"""
Analyze Routes
==============
Single-ticker deep-dive endpoints for the Analyze tab:

1. GET  /api/analyze/<ticker>           -- Full analyze data
2. GET  /api/analyze/<ticker>/chart     -- Enhanced chart data
3. GET  /api/analyze/search             -- Ticker autocomplete
"""

import re
from app.utils import error_details
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
CACHE_TTL = 300  # 5 minutes

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
        return jsonify({'error': error_details(e)}), 400

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
        return jsonify({'error': error_details(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Analyze error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to fetch analyze data for {ticker}',
            'details': error_details(e),
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
        return jsonify({'error': error_details(e)}), 400

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
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/trendlines
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/trendlines', methods=['GET'])
@log_request
@require_api_key
def analyze_trendlines(ticker):
    """
    Auto-detect trendlines with regime-aware confidence scoring.

    Query params:
        period: 1mo, 3mo, 6mo, 1y (default 6mo)
        interval: 1d (default 1d)
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': error_details(e)}), 400

    period = request.args.get('period', '6mo')
    interval = request.args.get('interval', '1d')

    try:
        db = _get_db_manager()
        cache_key = f'analyze_trendlines_{ticker}_{period}_{interval}'

        result = _get_cached(
            cache_key,
            lambda: _fetch_trendlines(ticker, period, interval, db),
            ttl=CACHE_TTL,
        )

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Trendline error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to detect trendlines for {ticker}',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/patterns
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/patterns', methods=['GET'])
@log_request
@require_api_key
def analyze_patterns(ticker):
    """Detect candlestick patterns + seasonality heatmap."""
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': error_details(e)}), 400

    period = request.args.get('period', '6mo')

    try:
        cache_key = f'analyze_patterns_{ticker}_{period}'
        result = _get_cached(
            cache_key,
            lambda: _fetch_patterns(ticker, period),
            ttl=CACHE_TTL,
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Pattern error for {ticker}: {e}")
        return jsonify({'error': error_details(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/compare
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/compare', methods=['GET'])
@log_request
@require_api_key
def analyze_compare(ticker):
    """
    Get comparison data: ticker vs SPY, VIX, sector ETF.
    Returns normalized % change series for overlay.
    """
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': error_details(e)}), 400

    period = request.args.get('period', '6mo')

    try:
        cache_key = f'analyze_compare_{ticker}_{period}'
        result = _get_cached(
            cache_key,
            lambda: _fetch_compare(ticker, period),
            ttl=CACHE_TTL,
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Compare error for {ticker}: {e}")
        return jsonify({'error': error_details(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_analyze(ticker, db_manager):
    from app.services.analyze_service import fetch_analyze_data
    return fetch_analyze_data(ticker, db_manager)


def _fetch_chart(ticker, interval, period):
    from app.services.analyze_service import fetch_enhanced_chart
    return fetch_enhanced_chart(ticker, interval, period)


def _fetch_trendlines(ticker, period, interval, db_manager):
    from app.services.trendline_service import detect_trendlines
    return detect_trendlines(ticker, period, interval, db_manager)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/<ticker>/grades
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/<ticker>/grades', methods=['GET'])
@log_request
@require_api_key
def analyze_grades(ticker):
    """Compute quant letter grades (A+ through F) across 6 factors."""
    try:
        ticker = _validate_ticker(ticker)
    except ValueError as e:
        return jsonify({'error': error_details(e)}), 400

    try:
        db = _get_db_manager()
        cache_key = f'analyze_grades_{ticker}'
        result = _get_cached(
            cache_key,
            lambda: _fetch_grades(ticker, db),
            ttl=CACHE_TTL,
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Grades error for {ticker}: {e}")
        return jsonify({'error': error_details(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/analyze/ai-dashboard
# ──────────────────────────────────────────────────────────────────────────────

@analyze_bp.route('/analyze/ai-dashboard', methods=['GET'])
@log_request
@require_api_key
def ai_dashboard():
    """Get full AI Dashboard data: market regime, top signals, model stats, sector regimes."""
    try:
        db = _get_db_manager()
        cache_key = 'ai_dashboard'
        result = _get_cached(
            cache_key,
            lambda: _fetch_ai_dashboard(db),
            ttl=120,  # 2 min cache (more dynamic than ticker data)
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"AI Dashboard error: {e}")
        return jsonify({'error': error_details(e)}), 500


def _fetch_ai_dashboard(db_manager):
    from app.services.ai_dashboard_service import get_ai_dashboard
    return get_ai_dashboard(db_manager)


def _fetch_grades(ticker, db_manager):
    from app.services.quant_grades_service import compute_quant_grades
    return compute_quant_grades(ticker, db_manager)


def _fetch_patterns(ticker, period):
    from app.services.pattern_service import detect_patterns
    return detect_patterns(ticker, period)


def _fetch_compare(ticker, period):
    """Fetch normalized % change series for ticker vs SPY, VIX, sector ETF."""
    import yfinance as yf
    import numpy as np

    symbols = [ticker, 'SPY', '^VIX']

    # Try to get sector ETF
    try:
        from app.services.report_service import TICKER_SECTOR_MAP, SECTOR_ETFS
        sector = TICKER_SECTOR_MAP.get(ticker)
        if sector:
            etf = SECTOR_ETFS.get(sector)
            if etf and etf not in symbols:
                symbols.append(etf)
    except Exception:
        pass

    result = {'symbols': []}

    for sym in symbols:
        try:
            stock = yf.Ticker(sym)
            hist = stock.history(period=period, interval='1d')
            if hist.empty or len(hist) < 5:
                continue

            hist = hist.reset_index()
            ts_col = 'Date' if 'Date' in hist.columns else 'Datetime'
            closes = hist['Close'].values
            base = closes[0]
            if base == 0:
                continue

            pct_changes = ((closes - base) / base * 100).tolist()
            timestamps = [
                t.isoformat() if hasattr(t, 'isoformat') else str(t)
                for t in hist[ts_col]
            ]

            label = sym
            if sym == '^VIX':
                label = 'VIX'
            elif sym == ticker:
                label = ticker

            result['symbols'].append({
                'symbol': sym,
                'label': label,
                'data': [
                    {'timestamp': ts, 'value': round(float(v), 2)}
                    for ts, v in zip(timestamps, pct_changes)
                    if not np.isnan(v)
                ],
            })
        except Exception as e:
            logger.debug(f"Compare fetch failed for {sym}: {e}")

    return result
