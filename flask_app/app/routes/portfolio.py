"""
Portfolio Routes
================
Endpoints for theoretical portfolio management:

1. GET  /api/portfolio/summary         -- Get complete portfolio overview
2. GET  /api/portfolio/holdings        -- Get current holdings
3. GET  /api/portfolio/transactions    -- Get transaction history
4. GET  /api/portfolio/performance     -- Get performance history
5. POST /api/portfolio/trade           -- Execute a trade
6. POST /api/portfolio/signal          -- Add a trade signal
7. GET  /api/portfolio/signals         -- Get pending signals
8. POST /api/portfolio/update-prices   -- Update current prices
9. POST /api/portfolio/snapshot        -- Create daily snapshot
"""

import re
from app.utils import error_details
import time
import logging
import json
from datetime import datetime, date
from decimal import Decimal
import uuid
from flask import Blueprint, jsonify, request, current_app
from app.utils.auth import log_request, require_api_key

logger = logging.getLogger(__name__)

portfolio_bp = Blueprint('portfolio', __name__)

# ──────────────────────────────────────────────────────────────────────────────
# TTL cache for portfolio data
# ──────────────────────────────────────────────────────────────────────────────

_cache = {}
CACHE_TTL = 30  # 30 seconds for portfolio data (needs to be fresh)

TICKER_PATTERN = re.compile(r'^[A-Z]{1,5}(-[A-Z])?$')


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


def _invalidate_cache():
    """Invalidate all portfolio cache entries."""
    global _cache
    _cache = {}


def _get_portfolio_manager():
    """Get a PortfolioManager instance."""
    try:
        from app.services.portfolio_service import get_portfolio_manager
        return get_portfolio_manager()
    except Exception as e:
        logger.error(f"Failed to get portfolio manager: {e}")
        raise


def _serialize(obj):
    """JSON serializer for special types."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _validate_ticker(ticker: str) -> str:
    """Validate and normalize a ticker symbol."""
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Empty ticker")
    if len(ticker) > 10:
        raise ValueError(f"Ticker too long: {ticker}")
    if not TICKER_PATTERN.match(ticker):
        raise ValueError(f"Invalid ticker format: {ticker}")
    return ticker


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/portfolio/summary
# ──────────────────────────────────────────────────────────────────────────────

@portfolio_bp.route('/portfolio/summary', methods=['GET'])
@log_request
@require_api_key
def portfolio_summary():
    """
    Get complete portfolio summary including account, holdings, and recent transactions.
    """
    try:
        pm = _get_portfolio_manager()

        def compute():
            summary = pm.get_portfolio_summary()
            return json.loads(json.dumps(summary, default=_serialize))

        result = _get_cached('portfolio_summary', compute, ttl=CACHE_TTL)
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Portfolio summary error: {e}")
        return jsonify({
            'error': 'Failed to fetch portfolio summary',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/portfolio/holdings
# ──────────────────────────────────────────────────────────────────────────────

@portfolio_bp.route('/portfolio/holdings', methods=['GET'])
@log_request
@require_api_key
def portfolio_holdings():
    """
    Get current portfolio holdings.

    Query params:
        type: 'long_term' or 'swing' (optional, filters by holding type)
    """
    holding_type = request.args.get('type')
    if holding_type and holding_type not in ('long_term', 'swing'):
        return jsonify({'error': 'Invalid type. Must be "long_term" or "swing"'}), 400

    try:
        pm = _get_portfolio_manager()

        def compute():
            holdings = pm.get_holdings(holding_type)
            return json.loads(json.dumps(holdings, default=_serialize))

        cache_key = f'portfolio_holdings_{holding_type or "all"}'
        result = _get_cached(cache_key, compute, ttl=CACHE_TTL)

        return jsonify({
            'holdings': result,
            'count': len(result),
            'type_filter': holding_type,
        })

    except Exception as e:
        current_app.logger.error(f"Portfolio holdings error: {e}")
        return jsonify({
            'error': 'Failed to fetch holdings',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/portfolio/transactions
# ──────────────────────────────────────────────────────────────────────────────

@portfolio_bp.route('/portfolio/transactions', methods=['GET'])
@log_request
@require_api_key
def portfolio_transactions():
    """
    Get portfolio transaction history.

    Query params:
        limit: Maximum number of transactions (default 50, max 200)
        ticker: Filter by ticker symbol (optional)
    """
    limit = request.args.get('limit', 50, type=int)
    limit = min(max(1, limit), 200)
    ticker = request.args.get('ticker')

    if ticker:
        try:
            ticker = _validate_ticker(ticker)
        except ValueError as e:
            return jsonify({'error': error_details(e)}), 400

    try:
        pm = _get_portfolio_manager()

        def compute():
            transactions = pm.get_transactions(limit=limit, ticker=ticker)
            return json.loads(json.dumps(transactions, default=_serialize))

        cache_key = f'portfolio_transactions_{limit}_{ticker or "all"}'
        result = _get_cached(cache_key, compute, ttl=CACHE_TTL)

        return jsonify({
            'transactions': result,
            'count': len(result),
            'limit': limit,
            'ticker_filter': ticker,
        })

    except Exception as e:
        current_app.logger.error(f"Portfolio transactions error: {e}")
        return jsonify({
            'error': 'Failed to fetch transactions',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/portfolio/performance
# ──────────────────────────────────────────────────────────────────────────────

@portfolio_bp.route('/portfolio/performance', methods=['GET'])
@log_request
@require_api_key
def portfolio_performance():
    """
    Get portfolio performance history.

    Query params:
        days: Number of days of history (default 30, max 365)
    """
    days = request.args.get('days', 30, type=int)
    days = min(max(1, days), 365)

    try:
        pm = _get_portfolio_manager()

        def compute():
            history = pm.get_performance_history(days=days)
            return json.loads(json.dumps(history, default=_serialize))

        cache_key = f'portfolio_performance_{days}'
        result = _get_cached(cache_key, compute, ttl=60)  # 1 minute cache for performance

        # Calculate summary stats
        if result:
            latest = result[-1] if result else {}
            return jsonify({
                'history': result,
                'days': days,
                'latest': latest,
                'total_return_pct': float(latest.get('total_pnl_pct', 0)) * 100,
            })

        return jsonify({
            'history': [],
            'days': days,
            'latest': None,
            'total_return_pct': 0,
        })

    except Exception as e:
        current_app.logger.error(f"Portfolio performance error: {e}")
        return jsonify({
            'error': 'Failed to fetch performance history',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/portfolio/trade
# ──────────────────────────────────────────────────────────────────────────────

@portfolio_bp.route('/portfolio/trade', methods=['POST'])
@log_request
@require_api_key
def portfolio_trade():
    """
    Execute a portfolio trade.

    Request body:
    {
        "ticker": "AAPL",
        "action": "buy",           // buy, sell, buy_to_open, sell_to_close
        "quantity": 10,
        "price": 185.50,
        "holding_type": "swing",   // long_term or swing
        "asset_type": "stock",     // stock, option, etf (optional, default stock)
        "signal_source": "manual", // optional
        "signal_details": {}       // optional JSON
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must include JSON body'}), 400

    # Validate required fields
    required = ['ticker', 'action', 'quantity', 'price', 'holding_type']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    # Validate action
    valid_actions = ['buy', 'sell', 'buy_to_open', 'sell_to_close', 'buy_to_close', 'sell_to_open']
    if data['action'] not in valid_actions:
        return jsonify({'error': f'Invalid action. Must be one of: {", ".join(valid_actions)}'}), 400

    # Validate holding_type
    if data['holding_type'] not in ('long_term', 'swing'):
        return jsonify({'error': 'Invalid holding_type. Must be "long_term" or "swing"'}), 400

    # Validate ticker
    try:
        ticker = _validate_ticker(data['ticker'])
    except ValueError as e:
        return jsonify({'error': error_details(e)}), 400

    # Validate numbers
    try:
        quantity = float(data['quantity'])
        price = float(data['price'])
        if quantity <= 0 or price <= 0:
            raise ValueError("Quantity and price must be positive")
    except (ValueError, TypeError) as e:
        return jsonify({'error': f'Invalid quantity or price: {e}'}), 400

    try:
        pm = _get_portfolio_manager()

        result = pm.execute_trade(
            action=data['action'],
            ticker=ticker,
            quantity=quantity,
            price=price,
            holding_type=data['holding_type'],
            asset_type=data.get('asset_type', 'stock'),
            signal_source=data.get('signal_source'),
            signal_details=data.get('signal_details'),
            option_type=data.get('option_type'),
            strike_price=float(data['strike_price']) if data.get('strike_price') else None,
            expiration_date=data.get('expiration_date'),
        )

        _invalidate_cache()  # Clear cache after trade

        return jsonify(json.loads(json.dumps(result, default=_serialize)))

    except Exception as e:
        current_app.logger.error(f"Portfolio trade error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to execute trade',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/portfolio/signal
# ──────────────────────────────────────────────────────────────────────────────

@portfolio_bp.route('/portfolio/signal', methods=['POST'])
@log_request
@require_api_key
def portfolio_add_signal():
    """
    Add a trade signal to the queue.

    Request body:
    {
        "ticker": "AAPL",
        "signal_type": "trend_break_bullish",
        "suggested_action": "buy",
        "holding_type": "swing",
        "signal_strength": 0.85,     // optional, 0.0-1.0
        "signal_price": 185.50,      // optional
        "source_data": {},           // optional JSON
        "expires_hours": 24          // optional, default 24
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request must include JSON body'}), 400

    required = ['ticker', 'signal_type', 'suggested_action', 'holding_type']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    try:
        ticker = _validate_ticker(data['ticker'])
    except ValueError as e:
        return jsonify({'error': error_details(e)}), 400

    try:
        pm = _get_portfolio_manager()

        signal_id = pm.add_signal(
            ticker=ticker,
            signal_type=data['signal_type'],
            suggested_action=data['suggested_action'],
            holding_type=data['holding_type'],
            signal_strength=data.get('signal_strength'),
            signal_price=data.get('signal_price'),
            source_data=data.get('source_data'),
            expires_hours=data.get('expires_hours', 24),
        )

        return jsonify({
            'success': True,
            'signal_id': signal_id,
            'ticker': ticker,
            'signal_type': data['signal_type'],
        })

    except Exception as e:
        current_app.logger.error(f"Portfolio add signal error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to add signal',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/portfolio/signals
# ──────────────────────────────────────────────────────────────────────────────

@portfolio_bp.route('/portfolio/signals', methods=['GET'])
@log_request
@require_api_key
def portfolio_signals():
    """
    Get pending trade signals.
    """
    try:
        pm = _get_portfolio_manager()

        def compute():
            signals = pm.get_pending_signals()
            return json.loads(json.dumps(signals, default=_serialize))

        result = _get_cached('portfolio_signals', compute, ttl=30)

        return jsonify({
            'signals': result,
            'count': len(result),
        })

    except Exception as e:
        current_app.logger.error(f"Portfolio signals error: {e}")
        return jsonify({
            'error': 'Failed to fetch signals',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/portfolio/update-prices
# ──────────────────────────────────────────────────────────────────────────────

@portfolio_bp.route('/portfolio/update-prices', methods=['POST'])
@log_request
@require_api_key
def portfolio_update_prices():
    """
    Update current prices for holdings.

    Request body:
    {
        "prices": {
            "AAPL": 185.50,
            "NVDA": 875.25
        }
    }
    """
    data = request.get_json(silent=True)
    if not data or 'prices' not in data:
        return jsonify({'error': 'Request must include "prices" object'}), 400

    prices = data['prices']
    if not isinstance(prices, dict):
        return jsonify({'error': '"prices" must be an object mapping ticker to price'}), 400

    try:
        pm = _get_portfolio_manager()
        updated_count = pm.update_prices(prices)
        _invalidate_cache()

        return jsonify({
            'success': True,
            'updated_count': updated_count,
        })

    except Exception as e:
        current_app.logger.error(f"Portfolio update prices error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to update prices',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/portfolio/snapshot
# ──────────────────────────────────────────────────────────────────────────────

@portfolio_bp.route('/portfolio/snapshot', methods=['POST'])
@log_request
@require_api_key
def portfolio_snapshot():
    """
    Create a daily performance snapshot.
    Should be called at end of trading day.
    """
    try:
        pm = _get_portfolio_manager()
        snapshot = pm.create_daily_snapshot()
        _invalidate_cache()

        return jsonify({
            'success': True,
            'snapshot': json.loads(json.dumps(snapshot, default=_serialize)),
        })

    except Exception as e:
        current_app.logger.error(f"Portfolio snapshot error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to create snapshot',
            'details': error_details(e),
        }), 500


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/portfolio/stop-losses
# ──────────────────────────────────────────────────────────────────────────────

@portfolio_bp.route('/portfolio/stop-losses', methods=['GET'])
@log_request
@require_api_key
def portfolio_stop_losses():
    """
    Check for holdings that have triggered stop-loss.
    """
    try:
        pm = _get_portfolio_manager()
        triggered = pm.check_stop_losses()

        return jsonify({
            'triggered': triggered,
            'count': len(triggered),
        })

    except Exception as e:
        current_app.logger.error(f"Portfolio stop-losses error: {e}")
        return jsonify({
            'error': 'Failed to check stop-losses',
            'details': error_details(e),
        }), 500
