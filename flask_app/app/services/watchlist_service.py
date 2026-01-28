"""
Watchlist Service
=================
Aggregates real-time data for user-watchlisted tickers:

- Current price + daily change
- Trend break probability (from latest report or on-demand)
- Sector identification + sentiment
- Key indicators (CCI, Stochastic, RSI, ADX, SMA)
- Options summary (ATM call/put, IV)

Used by:
- flask_app/app/routes/watchlist.py
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def fetch_watchlist_data(
    tickers: List[str],
    db_manager=None,
) -> Dict:
    """
    Batch-fetch data for a list of watchlisted tickers.

    Returns:
        {
            'securities': [...],
            'errors': [{'ticker': 'BAD', 'error': '...'}],
            'fetched_at': 'ISO timestamp',
        }
    """
    securities = []
    errors = []

    for ticker in tickers:
        try:
            data = fetch_single_ticker_data(ticker, db_manager)
            securities.append(data)
        except Exception as e:
            logger.warning(f"Watchlist fetch failed for {ticker}: {e}")
            errors.append({'ticker': ticker, 'error': str(e)})
        time.sleep(0.15)  # Rate limit yfinance

    return {
        'securities': securities,
        'errors': errors,
        'fetched_at': datetime.utcnow().isoformat(),
    }


def fetch_single_ticker_data(
    ticker: str,
    db_manager=None,
) -> Dict:
    """
    Fetch all watchlist data for a single ticker.

    Returns dict with price, trend_break, sector, indicators, options.
    """
    import yfinance as yf
    from app.services.dashboard_service import (
        _calculate_cci, _calculate_stochastic, _calculate_rsi,
        _calculate_sma, _calculate_adx, calculate_tlev,
        _determine_sentiment,
    )
    from app.services.report_service import (
        TICKER_SECTOR_MAP, SECTOR_ETFS, _predict_rule_based,
    )

    result = {
        'ticker': ticker,
        'fetched_at': datetime.utcnow().isoformat(),
    }

    # 1. Price data (3-month daily for indicators)
    stock = yf.Ticker(ticker)
    df = stock.history(period='3mo', interval='1d')

    if df.empty or len(df) < 5:
        raise ValueError(f"Insufficient price data for {ticker}")

    df = df.reset_index()
    if 'Date' in df.columns:
        df = df.rename(columns={'Date': 'date'})

    # Current price + daily change
    current_price = float(df['Close'].iloc[-1])
    prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price
    price_change = current_price - prev_close
    price_change_pct = (price_change / prev_close * 100) if prev_close != 0 else 0.0

    result['price'] = {
        'current': round(current_price, 4),
        'previous_close': round(prev_close, 4),
        'change': round(price_change, 4),
        'change_pct': round(price_change_pct, 4),
    }

    # 2. Trend break probability
    trend_break = _get_trend_break_data(ticker, df, db_manager)
    result['trend_break'] = trend_break

    # 3. Sector + sentiment
    sector_name = TICKER_SECTOR_MAP.get(ticker)
    if not sector_name:
        try:
            info = stock.info
            sector_name = info.get('sector')
        except Exception:
            pass

    sector_etf = SECTOR_ETFS.get(sector_name) if sector_name else None

    sector_sentiment = {'sentiment': 'NEUTRAL', 'confidence': 0}
    if sector_name and sector_etf:
        sector_sentiment = _compute_sector_sentiment_cached(sector_name, sector_etf)

    result['sector'] = {
        'name': sector_name,
        'etf': sector_etf,
        'sentiment': sector_sentiment.get('sentiment', 'NEUTRAL'),
        'confidence': sector_sentiment.get('confidence', 0),
    }

    # 4. Indicators
    indicators = {}
    if len(df) >= 20:
        try:
            cci = _calculate_cci(df)
            indicators['cci'] = _safe_float(cci.iloc[-1], 2)

            stoch_k, stoch_d = _calculate_stochastic(df)
            indicators['stochastic_k'] = _safe_float(stoch_k.iloc[-1], 2)
            indicators['stochastic_d'] = _safe_float(stoch_d.iloc[-1], 2)

            rsi = _calculate_rsi(df)
            indicators['rsi'] = _safe_float(rsi.iloc[-1], 2)

            sma_20 = _calculate_sma(df['Close'], 20)
            indicators['sma_20'] = _safe_float(sma_20.iloc[-1], 4)

            if len(df) >= 50:
                sma_50 = _calculate_sma(df['Close'], 50)
                indicators['sma_50'] = _safe_float(sma_50.iloc[-1], 4)

            adx, _, _ = _calculate_adx(df)
            indicators['adx'] = _safe_float(adx.iloc[-1], 2)

        except Exception as e:
            logger.warning(f"Indicator calc failed for {ticker}: {e}")

    result['indicators'] = indicators

    # 5. Options summary
    result['options'] = _get_options_summary(stock, current_price)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

_sector_cache = {}
_SECTOR_CACHE_TTL = 600  # 10 minutes


def _compute_sector_sentiment_cached(sector_name: str, sector_etf: str) -> Dict:
    """Compute sector sentiment with caching."""
    now = time.time()
    cache_key = f'sector_{sector_name}'

    if cache_key in _sector_cache:
        data, expiry = _sector_cache[cache_key]
        if now < expiry:
            return data

    from app.services.dashboard_service import (
        _fetch_yfinance_data, _calculate_cci, _calculate_stochastic,
        _calculate_rsi, _calculate_sma, _determine_sentiment,
    )

    try:
        df = _fetch_yfinance_data(sector_etf, period='1y', interval='1wk')
        if df.empty or len(df) < 20:
            return {'sentiment': 'NEUTRAL', 'confidence': 0}

        cci = _calculate_cci(df)
        stoch_k, stoch_d = _calculate_stochastic(df)
        rsi = _calculate_rsi(df)
        sma_20 = _calculate_sma(df['Close'], 20)
        sma_50 = _calculate_sma(df['Close'], 50)

        latest = len(df) - 1
        sentiment, confidence, _ = _determine_sentiment(
            _safe_float(cci.iloc[latest]) or 0,
            _safe_float(stoch_k.iloc[latest]) or 50,
            _safe_float(stoch_d.iloc[latest]) or 50,
            _safe_float(sma_20.iloc[latest]) or 0,
            _safe_float(sma_50.iloc[latest]) or 0,
            _safe_float(rsi.iloc[latest]) or 50,
        )

        result = {'sentiment': sentiment, 'confidence': confidence}
        _sector_cache[cache_key] = (result, now + _SECTOR_CACHE_TTL)
        return result

    except Exception as e:
        logger.warning(f"Sector sentiment failed for {sector_name}: {e}")
        return {'sentiment': 'NEUTRAL', 'confidence': 0}


def _get_trend_break_data(ticker: str, df: pd.DataFrame, db_manager) -> Dict:
    """Get trend break probability from DB or compute on-demand."""
    # Try DB first
    if db_manager:
        try:
            query = """
                SELECT break_probability, break_direction, confidence,
                       is_recent_alert, report_generated_at
                FROM trend_break_reports
                WHERE ticker = %s
                ORDER BY report_generated_at DESC
                LIMIT 1
            """
            rows = db_manager.execute_query(query, (ticker,))
            if rows:
                row = rows[0]
                return {
                    'probability': float(row[0]) if row[0] else None,
                    'direction': row[1],
                    'confidence': float(row[2]) if row[2] else None,
                    'is_recent_alert': row[3] or False,
                    'last_report_at': row[4].isoformat() if row[4] and hasattr(row[4], 'isoformat') else str(row[4]) if row[4] else None,
                    'source': 'database',
                }
        except Exception as e:
            logger.debug(f"DB trend break lookup failed for {ticker}: {e}")

    # Compute on-demand via rule-based model
    try:
        from app.services.report_service import _predict_rule_based
        prediction = _predict_rule_based(df, 'daily')
        return {
            'probability': prediction['probability'],
            'direction': prediction['direction'],
            'confidence': prediction['confidence'],
            'is_recent_alert': False,
            'last_report_at': None,
            'source': 'on-demand',
        }
    except Exception as e:
        logger.warning(f"On-demand prediction failed for {ticker}: {e}")
        return {
            'probability': None,
            'direction': None,
            'confidence': None,
            'is_recent_alert': False,
            'last_report_at': None,
            'source': 'unavailable',
        }


def _get_options_summary(stock, current_price: float) -> Dict:
    """Get ATM options summary for a ticker."""
    try:
        expirations = stock.options
        if not expirations:
            return {'available': False}

        nearest_exp = expirations[0]
        chain = stock.option_chain(nearest_exp)

        result = {
            'available': True,
            'nearest_expiry': nearest_exp,
        }

        # Nearest ATM call
        if not chain.calls.empty:
            calls = chain.calls
            calls_diff = (calls['strike'] - current_price).abs()
            atm_call = calls.loc[calls_diff.idxmin()]
            result['nearest_call_strike'] = float(atm_call['strike'])
            result['nearest_call_price'] = float(atm_call['lastPrice'])
            result['call_iv'] = float(atm_call['impliedVolatility']) if 'impliedVolatility' in atm_call else None

        # Nearest ATM put
        if not chain.puts.empty:
            puts = chain.puts
            puts_diff = (puts['strike'] - current_price).abs()
            atm_put = puts.loc[puts_diff.idxmin()]
            result['nearest_put_strike'] = float(atm_put['strike'])
            result['nearest_put_price'] = float(atm_put['lastPrice'])
            result['put_iv'] = float(atm_put['impliedVolatility']) if 'impliedVolatility' in atm_put else None

        # Average IV
        call_iv = result.get('call_iv') or 0
        put_iv = result.get('put_iv') or 0
        result['implied_volatility'] = round((call_iv + put_iv) / 2, 4) if (call_iv or put_iv) else None

        return result

    except Exception as e:
        logger.debug(f"Options fetch failed: {e}")
        return {'available': False}


def fetch_chart_data(ticker: str, interval: str = '1h') -> Dict:
    """
    Fetch OHLC chart data for a ticker at a given interval.

    Args:
        ticker: Stock ticker symbol
        interval: '1d', '1h', or '5m'

    Returns:
        {data: [{timestamp, open, high, low, close, volume}], peaks: [...], troughs: [...]}
    """
    import yfinance as yf

    INTERVAL_PARAMS = {
        '1d': {'period': '3mo', 'interval': '1d'},
        '1h': {'period': '5d', 'interval': '1h'},
        '5m': {'period': '1d', 'interval': '5m'},
    }

    params = INTERVAL_PARAMS.get(interval, INTERVAL_PARAMS['1h'])
    stock = yf.Ticker(ticker)
    hist = stock.history(period=params['period'], interval=params['interval'])

    if hist.empty:
        return {'data': [], 'peaks': [], 'troughs': []}

    hist = hist.reset_index()

    # Determine timestamp column
    ts_col = 'Date' if 'Date' in hist.columns else 'Datetime' if 'Datetime' in hist.columns else hist.columns[0]

    # Serialize OHLCV
    chart_data = []
    for _, row in hist.iterrows():
        ts = row[ts_col]
        chart_data.append({
            'timestamp': ts.isoformat() if hasattr(ts, 'isoformat') else str(ts),
            'open': round(float(row['Open']), 4),
            'high': round(float(row['High']), 4),
            'low': round(float(row['Low']), 4),
            'close': round(float(row['Close']), 4),
            'volume': int(row['Volume']),
        })

    # Detect peaks and troughs from close values
    closes = [d['close'] for d in chart_data]
    peaks = _detect_peaks(closes, chart_data)
    troughs = _detect_troughs(closes, chart_data)

    return {
        'data': chart_data,
        'peaks': peaks,
        'troughs': troughs,
    }


def _detect_peaks(closes, chart_data, window=5):
    """Detect local maxima (resistance levels)."""
    peaks = []
    for i in range(window, len(closes) - window):
        if all(closes[i] >= closes[i - j] for j in range(1, window + 1)) and \
           all(closes[i] >= closes[i + j] for j in range(1, window + 1)):
            peaks.append({
                'timestamp': chart_data[i]['timestamp'],
                'price': closes[i],
                'index': i,
            })
    return peaks


def _detect_troughs(closes, chart_data, window=5):
    """Detect local minima (support levels)."""
    troughs = []
    for i in range(window, len(closes) - window):
        if all(closes[i] <= closes[i - j] for j in range(1, window + 1)) and \
           all(closes[i] <= closes[i + j] for j in range(1, window + 1)):
            troughs.append({
                'timestamp': chart_data[i]['timestamp'],
                'price': closes[i],
                'index': i,
            })
    return troughs


def _safe_float(val, decimals=None):
    """Convert to float safely, returning None for NaN."""
    try:
        f = float(val)
        if np.isnan(f):
            return None
        return round(f, decimals) if decimals is not None else f
    except (TypeError, ValueError):
        return None
