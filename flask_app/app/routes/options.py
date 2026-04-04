"""
Options Analysis API Routes
============================
Endpoints for options pricing and analysis.

Endpoints:
- POST /api/options/analyze - Analyze option pricing and find mispriced options
- POST /api/options/price - Calculate theoretical option price
- GET  /api/options/chain/<ticker> - Get option chain for a ticker
- GET  /api/options/expirations/<ticker> - Get available expiration dates
"""

from flask import Blueprint, request, jsonify, current_app
from app.utils import error_details
from app.utils.validation import validate_request, OPTIONS_SCHEMA
from app.utils.auth import require_api_key, log_request
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

options_bp = Blueprint('options', __name__)


@options_bp.route('/options/analyze', methods=['POST'])
@log_request
@require_api_key
@validate_request(OPTIONS_SCHEMA)
def analyze_options():
    """
    Analyze option pricing and find mispriced options.

    Request body:
        {
            "ticker": "AAPL",                    # Required
            "expiry_date": "2024-06-21",         # Optional, defaults to nearest
            "strike_price": 150.0,               # Optional, analyze specific strike
            "option_type": "call",               # Optional: call, put, both (default)
            "pricing_model": "american",         # Optional: american (default), european
            "trend_direction": "bullish"         # Optional: bullish, bearish, both (default)
        }

    Response:
        {
            "ticker": "AAPL",
            "current_price": 185.50,
            "expiry_date": "2024-06-21",
            "options": [
                {
                    "type": "CALL",
                    "strike": 180.0,
                    "market_price": 12.50,
                    "theoretical_price": 14.20,
                    "mispricing_pct": -11.97,
                    "recommendation": "UNDERPRICED",
                    "greeks": {...}
                },
                ...
            ],
            "summary": {
                "underpriced": 5,
                "overpriced": 3,
                "fair": 12
            },
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    data = request.validated_data
    ticker = data['ticker'].upper()
    expiry_date = data.get('expiry_date')
    strike_price = data.get('strike_price')
    option_type = data.get('option_type', 'both')
    pricing_model = data.get('pricing_model', 'american')
    trend_direction = data.get('trend_direction', 'both')

    try:
        from src.options_pricing import (
            analyze_option_pricing,
            get_risk_free_rate,
            calculate_greeks,
            calculate_historical_volatility
        )
        from datetime import datetime, timedelta
        import yfinance as yf

        current_app.logger.info(f"Analyzing options for {ticker}")

        # Get date range for historical data
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        # Run analysis
        results_df = analyze_option_pricing(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            expiry_date=expiry_date,
            strike_price=strike_price,
            option_type=option_type,
            pricing_model=pricing_model,
            trend_direction=trend_direction
        )

        if results_df is None or results_df.empty:
            return jsonify({
                'error': f'No options data found for {ticker}',
                'code': 'NO_OPTIONS_DATA'
            }), 404

        # Get current stock price
        stock = yf.Ticker(ticker)
        current_price = stock.history(period='1d')['Close'].iloc[-1]

        # Get actual expiry date used
        if expiry_date is None:
            expiry_date = stock.options[0] if stock.options else None

        # Format results
        import math
        options = []
        for _, row in results_df.iterrows():
            # Helper to safely convert to int, handling NaN
            def safe_int(val, default=0):
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return default
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return default

            # Helper to safely convert to float, handling NaN
            def safe_float(val, default=None):
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return default
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return default

            options.append({
                'type': row['type'],
                'strike': safe_float(row['strike'], 0.0),
                'market_price': safe_float(row['market_price'], 0.0),
                'theoretical_price': round(safe_float(row['theoretical_price'], 0.0), 2),
                'mispricing_pct': round(safe_float(row['mispricing_%'], 0.0), 2),
                'recommendation': row['recommendation'],
                'bid': safe_float(row['bid']),
                'ask': safe_float(row['ask']),
                'volume': safe_int(row['volume']),
                'open_interest': safe_int(row['open_interest'])
            })

        # Calculate summary
        summary = {
            'underpriced': len(results_df[results_df['recommendation'] == 'UNDERPRICED']),
            'overpriced': len(results_df[results_df['recommendation'] == 'OVERPRICED']),
            'fair': len(results_df[results_df['recommendation'] == 'FAIR']),
            'total_analyzed': len(results_df)
        }

        return jsonify({
            'ticker': ticker,
            'current_price': round(float(current_price), 2),
            'expiry_date': expiry_date,
            'pricing_model': pricing_model,
            'trend_filter': trend_direction,
            'options': options,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        })

    except ImportError as e:
        current_app.logger.error(f"Import error: {e}")
        return jsonify({
            'error': 'Server configuration error',
            'code': 'IMPORT_ERROR',
            'details': error_details(e)
        }), 500

    except Exception as e:
        current_app.logger.error(f"Options analysis error: {e}")
        return jsonify({
            'error': 'Failed to analyze options',
            'code': 'OPTIONS_ERROR',
            'details': error_details(e)
        }), 500


@options_bp.route('/options/price', methods=['POST'])
@log_request
@require_api_key
def calculate_option_price():
    """
    Calculate theoretical option price.

    Request body:
        {
            "stock_price": 185.50,       # Required
            "strike_price": 180.0,       # Required
            "expiry_date": "2024-06-21", # Required
            "volatility": 0.25,          # Optional, calculated if not provided
            "option_type": "call",       # Optional: call (default), put
            "pricing_model": "american"  # Optional: american (default), european
        }

    Response:
        {
            "theoretical_price": 14.20,
            "greeks": {
                "delta": 0.65,
                "gamma": 0.02,
                "theta": -0.05,
                "vega": 0.35,
                "rho": 0.12
            },
            "inputs": {...},
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    data = request.get_json()

    # Validate required fields
    required = ['stock_price', 'strike_price', 'expiry_date']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({
            'error': f"Missing required fields: {', '.join(missing)}",
            'code': 'VALIDATION_ERROR'
        }), 400

    try:
        from src.options_pricing import (
            binomial_tree_american,
            black_scholes_call,
            black_scholes_put,
            calculate_greeks,
            get_risk_free_rate,
            calculate_time_to_expiry
        )
        from datetime import datetime

        stock_price = float(data['stock_price'])
        strike_price = float(data['strike_price'])
        expiry_date = data['expiry_date']
        volatility = float(data.get('volatility', 0.25))
        option_type = data.get('option_type', 'call').lower()
        pricing_model = data.get('pricing_model', 'american').lower()

        # Calculate time to expiry
        current_date = datetime.now().strftime('%Y-%m-%d')
        time_to_expiry = calculate_time_to_expiry(current_date, expiry_date)

        if time_to_expiry <= 0:
            return jsonify({
                'error': 'Expiry date must be in the future',
                'code': 'INVALID_EXPIRY'
            }), 400

        # Get risk-free rate
        risk_free_rate = get_risk_free_rate(time_to_expiry)

        # Calculate theoretical price
        if pricing_model == 'american':
            price = binomial_tree_american(
                S=stock_price,
                K=strike_price,
                r=risk_free_rate,
                t=time_to_expiry,
                sigma=volatility,
                option_type=option_type
            )
        else:
            if option_type == 'call':
                price = black_scholes_call(stock_price, strike_price, risk_free_rate, time_to_expiry, volatility)
            else:
                price = black_scholes_put(stock_price, strike_price, risk_free_rate, time_to_expiry, volatility)

        # Calculate Greeks
        greeks = calculate_greeks(
            S=stock_price,
            K=strike_price,
            r=risk_free_rate,
            t=time_to_expiry,
            sigma=volatility,
            option_type=option_type
        )

        return jsonify({
            'theoretical_price': round(price, 2),
            'greeks': {
                'delta': round(greeks['delta'], 4),
                'gamma': round(greeks['gamma'], 4),
                'theta': round(greeks['theta'], 4),
                'vega': round(greeks['vega'], 4),
                'rho': round(greeks['rho'], 4)
            },
            'inputs': {
                'stock_price': stock_price,
                'strike_price': strike_price,
                'expiry_date': expiry_date,
                'time_to_expiry_years': round(time_to_expiry, 4),
                'volatility': volatility,
                'risk_free_rate': round(risk_free_rate, 4),
                'option_type': option_type,
                'pricing_model': pricing_model
            },
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Option pricing error: {e}")
        return jsonify({
            'error': 'Failed to calculate option price',
            'code': 'PRICING_ERROR',
            'details': error_details(e)
        }), 500


@options_bp.route('/options/chain/<ticker>', methods=['GET'])
@log_request
@require_api_key
def get_option_chain(ticker: str):
    """
    Get option chain for a ticker.

    Path parameters:
        ticker: Stock ticker symbol

    Query parameters:
        expiry: Expiration date (optional, defaults to nearest)

    Response:
        {
            "ticker": "AAPL",
            "expiry_date": "2024-06-21",
            "current_price": 185.50,
            "calls": [...],
            "puts": [...],
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    ticker = ticker.upper()
    expiry_date = request.args.get('expiry')

    try:
        from src.options_pricing import get_option_prices
        from datetime import datetime
        import yfinance as yf

        # Get option chain
        calls, puts = get_option_prices(ticker, expiry_date)

        # Get current stock price
        stock = yf.Ticker(ticker)
        current_price = stock.history(period='1d')['Close'].iloc[-1]

        # Get actual expiry used
        if expiry_date is None:
            expiry_date = stock.options[0] if stock.options else None

        # Helper functions for safe type conversion
        import math

        def safe_int(val, default=0):
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        def safe_float(val, default=None):
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        # Format calls
        calls_data = []
        for _, row in calls.iterrows():
            calls_data.append({
                'strike': safe_float(row['strike'], 0.0),
                'lastPrice': safe_float(row['lastPrice'], 0.0),
                'bid': safe_float(row['bid']),
                'ask': safe_float(row['ask']),
                'volume': safe_int(row['volume']),
                'openInterest': safe_int(row['openInterest']),
                'impliedVolatility': round(safe_float(row['impliedVolatility'], 0.0), 4) if safe_float(row['impliedVolatility']) else None,
                'inTheMoney': bool(row['inTheMoney'])
            })

        # Format puts
        puts_data = []
        for _, row in puts.iterrows():
            puts_data.append({
                'strike': safe_float(row['strike'], 0.0),
                'lastPrice': safe_float(row['lastPrice'], 0.0),
                'bid': safe_float(row['bid']),
                'ask': safe_float(row['ask']),
                'volume': safe_int(row['volume']),
                'openInterest': safe_int(row['openInterest']),
                'impliedVolatility': round(safe_float(row['impliedVolatility'], 0.0), 4) if safe_float(row['impliedVolatility']) else None,
                'inTheMoney': bool(row['inTheMoney'])
            })

        return jsonify({
            'ticker': ticker,
            'expiry_date': expiry_date,
            'current_price': round(float(current_price), 2),
            'calls': calls_data,
            'puts': puts_data,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error getting option chain for {ticker}: {e}")
        return jsonify({
            'error': 'Failed to get option chain',
            'code': 'CHAIN_ERROR',
            'details': error_details(e)
        }), 500


@options_bp.route('/options/expirations/<ticker>', methods=['GET'])
@log_request
@require_api_key
def get_expirations(ticker: str):
    """
    Get available option expiration dates for a ticker.

    Path parameters:
        ticker: Stock ticker symbol

    Response:
        {
            "ticker": "AAPL",
            "expirations": ["2024-01-19", "2024-01-26", ...],
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    ticker = ticker.upper()

    try:
        from src.options_pricing import get_all_option_expirations
        from datetime import datetime

        expirations = get_all_option_expirations(ticker)

        return jsonify({
            'ticker': ticker,
            'expirations': expirations,
            'count': len(expirations),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error getting expirations for {ticker}: {e}")
        return jsonify({
            'error': 'Failed to get expiration dates',
            'code': 'EXPIRATIONS_ERROR',
            'details': error_details(e)
        }), 500
