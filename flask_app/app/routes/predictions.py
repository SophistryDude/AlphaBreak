"""
Predictions API Routes
=======================
Endpoints for trend break predictions and indicator analysis.

Endpoints:
- POST /api/predict - Get trend break prediction for a ticker
- POST /api/analyze - Analyze indicator accuracy
- GET  /api/indicators/<ticker> - Get current indicator values
"""

from flask import Blueprint, request, jsonify, current_app
from app.models import model_manager
from app.utils.validation import validate_request, PREDICTION_SCHEMA, INDICATOR_ANALYSIS_SCHEMA
from app.utils.auth import require_api_key, log_request
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

predictions_bp = Blueprint('predictions', __name__)


@predictions_bp.route('/predict', methods=['POST'])
@log_request
@require_api_key
@validate_request(PREDICTION_SCHEMA)
def predict():
    """
    Get trend break prediction for a ticker.

    Request body:
        {
            "ticker": "AAPL",           # Required
            "start_date": "2023-01-01", # Optional, defaults to 1 year ago
            "end_date": "2024-01-01",   # Optional, defaults to today
            "model_type": "xgboost"     # Optional: xgboost, lightgbm, lstm, meta
        }

    Response:
        {
            "ticker": "AAPL",
            "prediction": {
                "trend_break_probability": 0.75,
                "predicted_direction": "bullish",
                "confidence": 0.82,
                "timeframe": "1-5 days"
            },
            "indicators": {
                "RSI": 65.2,
                "MACD": 1.23,
                ...
            },
            "model_used": "xgboost",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    data = request.validated_data
    ticker = data['ticker'].upper()
    model_type = data.get('model_type', 'xgboost')

    try:
        # Import src modules
        from src.data_fetcher import get_stock_data
        from src.technical_indicators import calculate_all_indicators
        from src.trend_analysis import trend_break

        # Get date range
        from datetime import datetime, timedelta
        end_date = data.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        start_date = data.get('start_date', (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))

        # Fetch data and calculate indicators
        current_app.logger.info(f"Fetching data for {ticker}")
        stock_data = get_stock_data(ticker, start_date, end_date)

        if stock_data.empty:
            return jsonify({
                'error': f'No data found for ticker {ticker}',
                'code': 'NO_DATA'
            }), 404

        # Calculate indicators
        current_app.logger.info(f"Calculating indicators for {ticker}")
        data_with_indicators = calculate_all_indicators(stock_data)

        # Get latest indicator values
        latest = data_with_indicators.iloc[-1]
        indicators = {}
        indicator_cols = ['RSI', 'MACD', 'MACD_signal', 'MACD_hist', '%K', '%D',
                         'ADX', 'OBV', 'CMF', 'MFI', 'BB_upper', 'BB_middle', 'BB_lower']

        for col in indicator_cols:
            if col in data_with_indicators.columns:
                val = latest[col]
                indicators[col] = float(val) if not (val != val) else None  # Handle NaN

        # Get trend model prediction
        trend_model = model_manager.get_trend_model()

        if trend_model is not None:
            # Prepare features for prediction
            feature_cols = [col for col in indicator_cols if col in data_with_indicators.columns]
            X = data_with_indicators[feature_cols].iloc[-1:].fillna(0)

            try:
                prob = trend_model.predict_proba(X)[0]
                prediction = {
                    'trend_break_probability': float(max(prob)),
                    'predicted_direction': 'bullish' if prob[1] > prob[0] else 'bearish',
                    'confidence': float(max(prob)),
                    'timeframe': '1-5 days'
                }
            except Exception as e:
                current_app.logger.warning(f"Model prediction failed: {e}")
                prediction = {
                    'trend_break_probability': None,
                    'predicted_direction': 'unknown',
                    'confidence': None,
                    'timeframe': '1-5 days',
                    'note': 'Model prediction unavailable, showing indicators only'
                }
        else:
            # No model loaded - return indicator-based analysis
            current_app.logger.warning("No trend model loaded")

            # Simple rule-based prediction from indicators
            rsi = indicators.get('RSI', 50)
            macd_hist = indicators.get('MACD_hist', 0)

            if rsi and macd_hist:
                if rsi > 70 and macd_hist < 0:
                    direction = 'bearish'
                    confidence = 0.6
                elif rsi < 30 and macd_hist > 0:
                    direction = 'bullish'
                    confidence = 0.6
                elif macd_hist > 0:
                    direction = 'bullish'
                    confidence = 0.5
                else:
                    direction = 'bearish'
                    confidence = 0.5
            else:
                direction = 'unknown'
                confidence = 0.0

            prediction = {
                'trend_break_probability': confidence,
                'predicted_direction': direction,
                'confidence': confidence,
                'timeframe': '1-5 days',
                'note': 'Rule-based prediction (no ML model loaded)'
            }

        # Detect recent trend breaks
        breaks = trend_break(data_with_indicators, 'Close')
        recent_breaks = breaks[-5:] if breaks else []

        return jsonify({
            'ticker': ticker,
            'prediction': prediction,
            'indicators': indicators,
            'recent_trend_breaks': [
                {'date': str(date), 'direction': direction}
                for date, direction in recent_breaks
            ],
            'current_price': float(latest['Close']),
            'model_used': model_type if trend_model else 'rule-based',
            'timestamp': datetime.now().isoformat()
        })

    except ImportError as e:
        current_app.logger.error(f"Import error: {e}")
        return jsonify({
            'error': 'Server configuration error - src modules not found',
            'code': 'IMPORT_ERROR',
            'details': str(e)
        }), 500

    except Exception as e:
        current_app.logger.error(f"Prediction error for {ticker}: {e}")
        return jsonify({
            'error': 'Failed to generate prediction',
            'code': 'PREDICTION_ERROR',
            'details': str(e)
        }), 500


@predictions_bp.route('/analyze', methods=['POST'])
@log_request
@require_api_key
@validate_request(INDICATOR_ANALYSIS_SCHEMA)
def analyze_indicators():
    """
    Analyze indicator accuracy for a ticker.

    Request body:
        {
            "ticker": "AAPL",
            "start_date": "2020-01-01",
            "end_date": "2024-01-01",
            "indicators": ["RSI", "MACD", "ADX"]  # Optional, defaults to all
        }

    Response:
        {
            "ticker": "AAPL",
            "analysis": {
                "RSI": {"accuracy": 0.72, "rank": 1},
                "MACD": {"accuracy": 0.68, "rank": 2},
                ...
            },
            "best_indicator": "RSI",
            "trend_breaks_found": 45,
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    data = request.validated_data
    ticker = data['ticker'].upper()
    start_date = data['start_date']
    end_date = data['end_date']
    requested_indicators = data.get('indicators')

    try:
        from src.trend_analysis import analyze_indicator_accuracy
        from datetime import datetime

        current_app.logger.info(f"Analyzing indicators for {ticker}")

        results = analyze_indicator_accuracy(ticker, start_date, end_date)

        if results is None:
            return jsonify({
                'error': f'Analysis failed for {ticker}',
                'code': 'ANALYSIS_FAILED'
            }), 500

        # Format results
        accuracy_data = results['accuracy_data']
        accuracy_df = results['accuracy_df']
        summary = results['summary_stats']

        # Filter to requested indicators if specified
        if requested_indicators:
            accuracy_data = {k: v for k, v in accuracy_data.items()
                          if k in requested_indicators}

        # Build response
        analysis = {}
        for indicator, accuracy in accuracy_data.items():
            rank = int(accuracy_df.loc[indicator, 'rank']) if indicator in accuracy_df.index else None
            analysis[indicator] = {
                'accuracy': round(accuracy, 4),
                'rank': rank,
                'above_mean': accuracy > summary['mean_accuracy']
            }

        return jsonify({
            'ticker': ticker,
            'date_range': {
                'start': start_date,
                'end': end_date
            },
            'analysis': analysis,
            'summary': {
                'best_indicator': summary['best_indicator'],
                'best_accuracy': round(summary['best_accuracy'], 4),
                'mean_accuracy': round(summary['mean_accuracy'], 4),
                'median_accuracy': round(summary['median_accuracy'], 4),
                'total_indicators': summary['total_indicators'],
                'trend_breaks_found': summary['trend_breaks_detected']
            },
            'timestamp': datetime.now().isoformat()
        })

    except ImportError as e:
        current_app.logger.error(f"Import error: {e}")
        return jsonify({
            'error': 'Server configuration error',
            'code': 'IMPORT_ERROR'
        }), 500

    except Exception as e:
        current_app.logger.error(f"Analysis error: {e}")
        return jsonify({
            'error': 'Failed to analyze indicators',
            'code': 'ANALYSIS_ERROR',
            'details': str(e)
        }), 500


@predictions_bp.route('/indicators/<ticker>', methods=['GET'])
@log_request
@require_api_key
def get_indicators(ticker: str):
    """
    Get current indicator values for a ticker.

    Path parameters:
        ticker: Stock ticker symbol

    Query parameters:
        period: Data period (default: 3mo)

    Response:
        {
            "ticker": "AAPL",
            "current_price": 185.50,
            "indicators": {
                "RSI": 65.2,
                "MACD": 1.23,
                ...
            },
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    ticker = ticker.upper()
    period = request.args.get('period', '3mo')

    try:
        from src.data_fetcher import get_stock_data
        from src.technical_indicators import calculate_all_indicators
        from datetime import datetime, timedelta

        # Calculate date range from period
        end_date = datetime.now()
        period_days = {
            '1mo': 30, '3mo': 90, '6mo': 180, '1y': 365
        }
        days = period_days.get(period, 90)
        start_date = end_date - timedelta(days=days)

        # Fetch and calculate
        stock_data = get_stock_data(
            ticker,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        if stock_data.empty:
            return jsonify({
                'error': f'No data found for {ticker}',
                'code': 'NO_DATA'
            }), 404

        data_with_indicators = calculate_all_indicators(stock_data)
        latest = data_with_indicators.iloc[-1]

        # Extract indicators
        indicators = {}
        for col in data_with_indicators.columns:
            if col not in ['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']:
                val = latest[col]
                if val == val:  # Not NaN
                    indicators[col] = round(float(val), 4)

        return jsonify({
            'ticker': ticker,
            'current_price': round(float(latest['Close']), 2),
            'indicators': indicators,
            'data_points': len(data_with_indicators),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error getting indicators for {ticker}: {e}")
        return jsonify({
            'error': 'Failed to get indicators',
            'code': 'INDICATOR_ERROR',
            'details': str(e)
        }), 500


@predictions_bp.route('/data/<ticker>', methods=['GET'])
@log_request
@require_api_key
def get_stock_data(ticker: str):
    """
    Get historical stock data from database.

    Path parameters:
        ticker: Stock ticker symbol

    Query parameters:
        start_date: Start date (YYYY-MM-DD, default: 1 year ago)
        end_date: End date (YYYY-MM-DD, default: today)
        source: Data source ('database' or 'live', default: 'database')

    Response:
        {
            "ticker": "AAPL",
            "data": [
                {"date": "2024-01-02", "open": 185.5, "high": 186.0, ...},
                ...
            ],
            "record_count": 252,
            "source": "database",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    ticker = ticker.upper()
    from datetime import datetime, timedelta

    # Parse query parameters
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date = request.args.get(
        'start_date',
        (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    )
    source = request.args.get('source', 'database')

    try:
        if source == 'database':
            # Try to get data from database first
            try:
                from app.utils.database import get_stock_data_as_dataframe, check_data_availability

                # Check data availability
                availability = check_data_availability(ticker, start_date, end_date)

                if availability['available']:
                    df = get_stock_data_as_dataframe(ticker, start_date, end_date)

                    if not df.empty:
                        data = []
                        for _, row in df.iterrows():
                            data.append({
                                'date': row['Date'].strftime('%Y-%m-%d') if hasattr(row['Date'], 'strftime') else str(row['Date']),
                                'open': round(float(row['Open']), 2) if row['Open'] else None,
                                'high': round(float(row['High']), 2) if row['High'] else None,
                                'low': round(float(row['Low']), 2) if row['Low'] else None,
                                'close': round(float(row['Close']), 2) if row['Close'] else None,
                                'volume': int(row['Volume']) if row['Volume'] else None,
                                'adjusted_close': round(float(row['Adj Close']), 2) if row['Adj Close'] else None
                            })

                        return jsonify({
                            'ticker': ticker,
                            'data': data,
                            'record_count': len(data),
                            'date_range': {
                                'start': start_date,
                                'end': end_date,
                                'first_available': availability['first_date'],
                                'last_available': availability['last_date']
                            },
                            'source': 'database',
                            'timestamp': datetime.now().isoformat()
                        })

                # No data in database, fall through to live fetch
                current_app.logger.info(f"No database data for {ticker}, fetching live")

            except ImportError:
                current_app.logger.warning("Database module not available, using live data")
            except Exception as e:
                current_app.logger.warning(f"Database error, falling back to live: {e}")

        # Fetch live data
        from src.data_fetcher import get_stock_data as fetch_live_data
        df = fetch_live_data(ticker, start_date, end_date)

        if df.empty:
            return jsonify({
                'error': f'No data found for ticker {ticker}',
                'code': 'NO_DATA'
            }), 404

        data = []
        for _, row in df.iterrows():
            data.append({
                'date': row['Date'].strftime('%Y-%m-%d') if hasattr(row['Date'], 'strftime') else str(row['Date']),
                'open': round(float(row['Open']), 2) if row['Open'] else None,
                'high': round(float(row['High']), 2) if row['High'] else None,
                'low': round(float(row['Low']), 2) if row['Low'] else None,
                'close': round(float(row['Close']), 2) if row['Close'] else None,
                'volume': int(row['Volume']) if row['Volume'] else None,
                'adjusted_close': round(float(row['Adj Close']), 2) if row.get('Adj Close') else None
            })

        return jsonify({
            'ticker': ticker,
            'data': data,
            'record_count': len(data),
            'date_range': {
                'start': start_date,
                'end': end_date
            },
            'source': 'live',
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error getting data for {ticker}: {e}")
        return jsonify({
            'error': 'Failed to get stock data',
            'code': 'DATA_ERROR',
            'details': str(e)
        }), 500


@predictions_bp.route('/tickers', methods=['GET'])
@log_request
@require_api_key
def list_available_tickers():
    """
    List all tickers available in the database.

    Response:
        {
            "tickers": [
                {"ticker": "AAPL", "record_count": 1014, "first_date": "2022-01-03", "last_date": "2024-01-16"},
                ...
            ],
            "count": 10,
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    from datetime import datetime

    try:
        from app.utils.database import get_ticker_summary

        tickers = get_ticker_summary()

        return jsonify({
            'tickers': tickers,
            'count': len(tickers),
            'timestamp': datetime.now().isoformat()
        })

    except ImportError:
        return jsonify({
            'error': 'Database not configured',
            'code': 'DATABASE_NOT_CONFIGURED'
        }), 503

    except Exception as e:
        current_app.logger.error(f"Error listing tickers: {e}")
        return jsonify({
            'error': 'Failed to list tickers',
            'code': 'DATABASE_ERROR',
            'details': str(e)
        }), 500
