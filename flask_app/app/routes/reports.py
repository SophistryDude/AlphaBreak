"""
Report Routes
=============
Endpoints for trend break reports:

1. GET /api/reports/latest              -- Latest report for a given frequency
2. GET /api/reports/history             -- Historical report summaries
3. GET /api/reports/ticker/<t>          -- All reports for a specific ticker
4. GET /api/reports/ticker/<t>/chart    -- OHLC chart data for a ticker
"""

import time
from app.utils import error_details
import logging
from flask import Blueprint, jsonify, request, current_app
from app.utils.auth import log_request, require_api_key

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__)

# ──────────────────────────────────────────────────────────────────────────────
# TTL cache for reports
# ──────────────────────────────────────────────────────────────────────────────

_cache = {}
CACHE_TTL = {
    'daily': 300,    # 5 minutes
    'hourly': 120,   # 2 minutes
    '10min': 60,     # 1 minute
}


def _get_cached(key, compute_fn, ttl=300):
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


VALID_FREQUENCIES = ('daily', 'hourly', '10min')
VALID_SORT_FIELDS = ('break_probability', 'ticker', 'price_change_pct', 'confidence')
VALID_DIRECTIONS = ('bullish', 'bearish')
VALID_CHART_INTERVALS = ('1d', '1h', '5m')

CHART_CACHE_TTL = {
    '5m': 60,
    '1h': 120,
    '1d': 300,
}


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/reports/latest
# ──────────────────────────────────────────────────────────────────────────────

@reports_bp.route('/reports/latest', methods=['GET'])
@log_request
@require_api_key
def reports_latest():
    """
    Get the latest trend break report for a given frequency.

    Query params:
        frequency (required): 'daily', 'hourly', or '10min'
        limit: Max securities to return (default 50)
        sort_by: Sort field (default 'break_probability')
        direction_filter: Filter by 'bullish' or 'bearish'
        sector_filter: Filter by sector name
        alerts_only: If 'true', only return recent alerts
    """
    frequency = request.args.get('frequency', 'daily').lower()
    if frequency not in VALID_FREQUENCIES:
        return jsonify({
            'error': f'Invalid frequency. Must be one of: {", ".join(VALID_FREQUENCIES)}'
        }), 400

    limit = request.args.get('limit', 50, type=int)
    limit = min(max(limit, 1), 200)

    sort_by = request.args.get('sort_by', 'break_probability')
    if sort_by not in VALID_SORT_FIELDS:
        sort_by = 'break_probability'

    direction_filter = request.args.get('direction_filter', '').lower()
    sector_filter = request.args.get('sector_filter', '')
    alerts_only = request.args.get('alerts_only', 'false').lower() == 'true'

    try:
        db = _get_db_manager()

        # Try to serve from DB first
        report = _try_db_report(db, frequency)

        # If no recent DB report, generate on-demand
        if report is None:
            cache_key = f'report_{frequency}'
            ttl = CACHE_TTL.get(frequency, 300)
            include_options = frequency != '10min'

            report = _get_cached(
                cache_key,
                lambda: _generate_on_demand(frequency, db, include_options),
                ttl,
            )

        # Apply filters
        securities = report.get('securities', [])

        if direction_filter and direction_filter in VALID_DIRECTIONS:
            securities = [s for s in securities if s.get('break_direction') == direction_filter]

        if sector_filter:
            securities = [
                s for s in securities
                if (s.get('sector') or '').lower() == sector_filter.lower()
            ]

        if alerts_only:
            securities = [s for s in securities if s.get('is_recent_alert')]

        # Sort
        reverse = sort_by in ('break_probability', 'price_change_pct', 'confidence')
        securities.sort(
            key=lambda s: s.get(sort_by) or 0,
            reverse=reverse,
        )

        # Limit
        securities = securities[:limit]

        return jsonify({
            'report_id': report.get('report_id'),
            'frequency': report.get('frequency', frequency),
            'generated_at': report.get('generated_at'),
            'securities_count': len(securities),
            'alerts_count': sum(1 for s in securities if s.get('is_recent_alert')),
            'total_scanned': report.get('securities_count', len(securities)),
            'securities': securities,
        })

    except Exception as e:
        current_app.logger.error(f"Reports latest error: {e}")
        return jsonify({
            'error': 'Failed to generate report',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/reports/history
# ──────────────────────────────────────────────────────────────────────────────

@reports_bp.route('/reports/history', methods=['GET'])
@log_request
@require_api_key
def reports_history():
    """
    Get historical report summaries.

    Query params:
        frequency: Filter by frequency (optional)
        ticker: Filter by ticker (optional)
        days: Lookback period in days (default 7)
        limit: Max reports to return (default 100)
    """
    frequency = request.args.get('frequency', '').lower()
    ticker = request.args.get('ticker', '').upper()
    days = request.args.get('days', 7, type=int)
    days = min(max(days, 1), 90)
    limit = request.args.get('limit', 100, type=int)
    limit = min(max(limit, 1), 500)

    try:
        db = _get_db_manager()

        if db is None:
            return jsonify({
                'reports': [],
                'message': 'Database not available. History requires DB connection.',
            })

        # Build query dynamically based on filters
        conditions = ["report_generated_at >= NOW() - INTERVAL '%s days'"]
        params = [days]

        if frequency and frequency in VALID_FREQUENCIES:
            conditions.append("report_frequency = %s")
            params.append(frequency)

        if ticker:
            conditions.append("ticker = %s")
            params.append(ticker)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT report_id, report_frequency, report_generated_at,
                   COUNT(*) as securities_count,
                   SUM(CASE WHEN is_recent_alert THEN 1 ELSE 0 END) as alerts_count,
                   AVG(break_probability) as avg_probability
            FROM trend_break_reports
            WHERE {where_clause}
            GROUP BY report_id, report_frequency, report_generated_at
            ORDER BY report_generated_at DESC
            LIMIT %s
        """
        params.append(limit)

        rows = db.execute_query(query, tuple(params))

        reports = []
        for row in (rows or []):
            reports.append({
                'report_id': str(row[0]),
                'frequency': row[1],
                'generated_at': row[2].isoformat() if hasattr(row[2], 'isoformat') else str(row[2]),
                'securities_count': row[3],
                'alerts_count': row[4],
                'avg_probability': round(float(row[5]), 4) if row[5] else None,
            })

        return jsonify({'reports': reports})

    except Exception as e:
        current_app.logger.error(f"Reports history error: {e}")
        return jsonify({
            'error': 'Failed to fetch report history',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/reports/ticker/<ticker>
# ──────────────────────────────────────────────────────────────────────────────

@reports_bp.route('/reports/ticker/<ticker>', methods=['GET'])
@log_request
@require_api_key
def reports_by_ticker(ticker):
    """
    Get all report entries for a specific ticker across all frequencies.

    Query params:
        days: Lookback period in days (default 7)
        limit: Max entries to return (default 50)
    """
    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 10:
        return jsonify({'error': 'Invalid ticker'}), 400

    days = request.args.get('days', 7, type=int)
    days = min(max(days, 1), 90)
    limit = request.args.get('limit', 50, type=int)
    limit = min(max(limit, 1), 200)

    try:
        db = _get_db_manager()

        if db is None:
            # Without DB, generate a single on-demand entry
            return _on_demand_ticker_report(ticker)

        query = """
            SELECT report_id, report_frequency, report_generated_at,
                   break_probability, break_direction, confidence,
                   is_recent_alert, first_crossed_at, consecutive_reports,
                   current_price, price_change_pct,
                   cci_value, stochastic_k, stochastic_d, rsi_value,
                   adx_value, tlev_value, sma_20, sma_50,
                   sector, sector_sentiment, sector_confidence,
                   options_available, nearest_call_strike, nearest_call_fair_value,
                   nearest_put_strike, nearest_put_fair_value, implied_volatility
            FROM trend_break_reports
            WHERE ticker = %s
              AND report_generated_at >= NOW() - INTERVAL '%s days'
            ORDER BY report_generated_at DESC
            LIMIT %s
        """

        rows = db.execute_query(query, (ticker, days, limit))

        entries = []
        for row in (rows or []):
            entries.append({
                'report_id': str(row[0]),
                'frequency': row[1],
                'generated_at': row[2].isoformat() if hasattr(row[2], 'isoformat') else str(row[2]),
                'break_probability': float(row[3]) if row[3] else None,
                'break_direction': row[4],
                'confidence': float(row[5]) if row[5] else None,
                'is_recent_alert': row[6],
                'first_crossed_at': row[7].isoformat() if row[7] and hasattr(row[7], 'isoformat') else str(row[7]) if row[7] else None,
                'consecutive_reports': row[8],
                'current_price': float(row[9]) if row[9] else None,
                'price_change_pct': float(row[10]) if row[10] else None,
                'indicators': {
                    'cci': float(row[11]) if row[11] else None,
                    'stochastic_k': float(row[12]) if row[12] else None,
                    'stochastic_d': float(row[13]) if row[13] else None,
                    'rsi': float(row[14]) if row[14] else None,
                    'adx': float(row[15]) if row[15] else None,
                    'tlev': float(row[16]) if row[16] else None,
                    'sma_20': float(row[17]) if row[17] else None,
                    'sma_50': float(row[18]) if row[18] else None,
                },
                'sector': row[19],
                'sector_sentiment': {
                    'sentiment': row[20],
                    'confidence': float(row[21]) if row[21] else None,
                },
                'options_summary': {
                    'available': row[22] or False,
                    'nearest_call_strike': float(row[23]) if row[23] else None,
                    'nearest_call_fair_value': float(row[24]) if row[24] else None,
                    'nearest_put_strike': float(row[25]) if row[25] else None,
                    'nearest_put_fair_value': float(row[26]) if row[26] else None,
                    'implied_volatility': float(row[27]) if row[27] else None,
                },
            })

        return jsonify({
            'ticker': ticker,
            'entries_count': len(entries),
            'entries': entries,
        })

    except Exception as e:
        current_app.logger.error(f"Reports by ticker error: {e}")
        return jsonify({
            'error': f'Failed to fetch reports for {ticker}',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/reports/ticker/<ticker>/chart
# ──────────────────────────────────────────────────────────────────────────────

@reports_bp.route('/reports/ticker/<ticker>/chart', methods=['GET'])
@log_request
@require_api_key
def reports_ticker_chart(ticker):
    """
    Fetch OHLC candlestick chart data for a report ticker.

    Query params:
        interval: '1d', '1h', or '5m' (default '5m')
    """
    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 10:
        return jsonify({'error': 'Invalid ticker'}), 400

    interval = request.args.get('interval', '5m')
    if interval not in VALID_CHART_INTERVALS:
        return jsonify({
            'error': f'Invalid interval. Must be one of: {", ".join(VALID_CHART_INTERVALS)}'
        }), 400

    try:
        cache_key = f'report_chart_{ticker}_{interval}'
        ttl = CHART_CACHE_TTL.get(interval, 60)

        result = _get_cached(
            cache_key,
            lambda: _fetch_report_chart(ticker, interval),
            ttl,
        )

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Reports chart error for {ticker}: {e}")
        return jsonify({
            'error': f'Failed to fetch chart data for {ticker}',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_report_chart(ticker, interval):
    """Delegate to report_service for chart data fetch."""
    from app.services.report_service import fetch_report_chart_data
    return fetch_report_chart_data(ticker, interval)


def _generate_on_demand(frequency, db_manager, include_options):
    """Generate a report on-demand via report_service."""
    from app.services.report_service import generate_report
    return generate_report(
        frequency=frequency,
        db_manager=db_manager,
        include_options=include_options,
    )


def _try_db_report(db_manager, frequency):
    """Try to get the latest report from the database."""
    if db_manager is None:
        return None

    try:
        # Check how fresh the latest report is
        ttl = CACHE_TTL.get(frequency, 300)
        query = """
            SELECT report_id, report_frequency, report_generated_at
            FROM trend_break_reports
            WHERE report_frequency = %s
            ORDER BY report_generated_at DESC
            LIMIT 1
        """
        rows = db_manager.execute_query(query, (frequency,))
        if not rows:
            return None

        report_id = str(rows[0][0])
        generated_at = rows[0][2]

        # Check freshness
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if hasattr(generated_at, 'timestamp'):
            age = (now - generated_at.replace(tzinfo=timezone.utc)).total_seconds()
        else:
            return None

        if age > ttl * 2:  # Allow 2x TTL before regenerating
            return None

        # Fetch full report from DB
        detail_query = """
            SELECT ticker, break_probability, break_direction, confidence,
                   is_recent_alert, first_crossed_at, consecutive_reports,
                   current_price, price_change_pct,
                   cci_value, stochastic_k, stochastic_d, rsi_value,
                   adx_value, tlev_value, sma_20, sma_50,
                   sector, sector_etf, sector_sentiment, sector_confidence,
                   options_available, nearest_call_strike, nearest_call_fair_value,
                   nearest_put_strike, nearest_put_fair_value, implied_volatility
            FROM trend_break_reports
            WHERE report_id = %s
            ORDER BY break_probability DESC
        """
        detail_rows = db_manager.execute_query(detail_query, (report_id,))

        securities = []
        alerts_count = 0
        for row in (detail_rows or []):
            sec = {
                'ticker': row[0],
                'break_probability': float(row[1]) if row[1] else 0,
                'break_direction': row[2],
                'confidence': float(row[3]) if row[3] else 0,
                'is_recent_alert': row[4] or False,
                'first_crossed_at': row[5].isoformat() if row[5] and hasattr(row[5], 'isoformat') else str(row[5]) if row[5] else None,
                'consecutive_reports': row[6] or 1,
                'current_price': float(row[7]) if row[7] else None,
                'price_change_pct': float(row[8]) if row[8] else None,
                'indicators': {
                    'cci': float(row[9]) if row[9] else None,
                    'stochastic_k': float(row[10]) if row[10] else None,
                    'stochastic_d': float(row[11]) if row[11] else None,
                    'rsi': float(row[12]) if row[12] else None,
                    'adx': float(row[13]) if row[13] else None,
                    'tlev': float(row[14]) if row[14] else None,
                    'sma_20': float(row[15]) if row[15] else None,
                    'sma_50': float(row[16]) if row[16] else None,
                },
                'sector': row[17],
                'sector_etf': row[18],
                'sector_sentiment': {
                    'name': row[17],
                    'sentiment': row[19] or 'NEUTRAL',
                    'confidence': float(row[20]) if row[20] else 0,
                },
                'options_summary': {
                    'available': row[21] or False,
                    'nearest_call_strike': float(row[22]) if row[22] else None,
                    'nearest_call_fair_value': float(row[23]) if row[23] else None,
                    'nearest_put_strike': float(row[24]) if row[24] else None,
                    'nearest_put_fair_value': float(row[25]) if row[25] else None,
                    'implied_volatility': float(row[26]) if row[26] else None,
                },
            }
            if sec['is_recent_alert']:
                alerts_count += 1
            securities.append(sec)

        return {
            'report_id': report_id,
            'frequency': frequency,
            'generated_at': generated_at.isoformat() if hasattr(generated_at, 'isoformat') else str(generated_at),
            'securities_count': len(securities),
            'alerts_count': alerts_count,
            'securities': securities,
        }

    except Exception as e:
        logger.warning(f"DB report fetch failed: {e}")
        return None


def _on_demand_ticker_report(ticker):
    """Generate a single-ticker on-demand report without DB."""
    from app.services.report_service import generate_report

    cache_key = f'ticker_{ticker}'

    def compute():
        report = generate_report(
            frequency='daily',
            tickers=[ticker],
            include_options=True,
        )
        return report.get('securities', [])

    entries = _get_cached(cache_key, compute, ttl=120)

    return jsonify({
        'ticker': ticker,
        'entries_count': len(entries),
        'entries': entries,
        'source': 'on-demand',
    })
