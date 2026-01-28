"""
Report Generation Service
=========================
Generates trend break reports by orchestrating:
- Price data fetching (yfinance or DB)
- Trend break feature computation and prediction
- Indicator enrichment (CCI, Stochastic, RSI, ADX, TLEV, SMA)
- Sector mapping and sentiment
- Options pricing (for daily/hourly only)
- Recency alert detection

Used by:
- Airflow DAGs (trend_break_*_report_dag.py)
- Flask API on-demand fallback (routes/reports.py)
"""

import uuid
import logging
import time
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

import pandas as pd
import numpy as np

# Add project root for src imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

PROBABILITY_THRESHOLD = 0.80

RECENCY_WINDOWS = {
    'daily': timedelta(days=3),
    'hourly': timedelta(hours=3),
    '10min': timedelta(hours=1),
}

YFINANCE_PARAMS = {
    'daily': {'period': '3mo', 'interval': '1d'},
    'hourly': {'period': '5d', 'interval': '1h'},
    '10min': {'period': '1d', 'interval': '5m'},
}

TIMEFRAME_MAP = {
    'daily': 'daily',
    'hourly': '1hour',
    '10min': '5min',
}

# S&P 500 top tickers by market cap (subset)
SP500_TOP_50 = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
    'UNH', 'JNJ', 'XOM', 'JPM', 'V', 'PG', 'MA', 'HD', 'CVX', 'MRK',
    'ABBV', 'PEP', 'COST', 'AVGO', 'KO', 'WMT', 'MCD', 'CSCO', 'TMO',
    'ACN', 'ABT', 'DHR', 'LIN', 'VZ', 'ADBE', 'NKE', 'CRM', 'PM',
    'TXN', 'NFLX', 'DIS', 'CMCSA', 'WFC', 'NEE', 'BMY', 'UPS', 'RTX',
    'HON', 'ORCL', 'QCOM', 'INTC', 'IBM',
]

# Sector mapping for common tickers (used when yfinance info is unavailable)
TICKER_SECTOR_MAP = {
    'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Communication Services',
    'AMZN': 'Consumer Discretionary', 'NVDA': 'Technology', 'META': 'Communication Services',
    'TSLA': 'Consumer Discretionary', 'BRK-B': 'Financials', 'UNH': 'Health Care',
    'JNJ': 'Health Care', 'XOM': 'Energy', 'JPM': 'Financials', 'V': 'Financials',
    'PG': 'Consumer Staples', 'MA': 'Financials', 'HD': 'Consumer Discretionary',
    'CVX': 'Energy', 'MRK': 'Health Care', 'ABBV': 'Health Care', 'PEP': 'Consumer Staples',
    'COST': 'Consumer Staples', 'AVGO': 'Technology', 'KO': 'Consumer Staples',
    'WMT': 'Consumer Staples', 'MCD': 'Consumer Discretionary', 'CSCO': 'Technology',
    'TMO': 'Health Care', 'ACN': 'Technology', 'ABT': 'Health Care', 'DHR': 'Health Care',
    'LIN': 'Materials', 'VZ': 'Communication Services', 'ADBE': 'Technology',
    'NKE': 'Consumer Discretionary', 'CRM': 'Technology', 'PM': 'Consumer Staples',
    'TXN': 'Technology', 'NFLX': 'Communication Services', 'DIS': 'Communication Services',
    'CMCSA': 'Communication Services', 'WFC': 'Financials', 'NEE': 'Utilities',
    'BMY': 'Health Care', 'UPS': 'Industrials', 'RTX': 'Industrials',
    'HON': 'Industrials', 'ORCL': 'Technology', 'QCOM': 'Technology',
    'INTC': 'Technology', 'IBM': 'Technology',
}

SECTOR_ETFS = {
    'Technology': 'XLK', 'Health Care': 'XLV', 'Financials': 'XLF',
    'Consumer Discretionary': 'XLY', 'Communication Services': 'XLC',
    'Industrials': 'XLI', 'Consumer Staples': 'XLP', 'Energy': 'XLE',
    'Utilities': 'XLU', 'Real Estate': 'XLRE', 'Materials': 'XLB',
}


# ──────────────────────────────────────────────────────────────────────────────
# Main report generation
# ──────────────────────────────────────────────────────────────────────────────

def generate_report(
    frequency: str,
    tickers: Optional[List[str]] = None,
    db_manager=None,
    include_options: bool = True,
) -> Dict:
    """
    Generate a complete trend break report.

    Args:
        frequency: 'daily', 'hourly', or '10min'
        tickers: List of tickers to scan. Defaults to SP500 subset.
        db_manager: Optional database manager for DB queries.
        include_options: Whether to include options data (slow; skip for 10min).

    Returns:
        Dict with report_id, frequency, generated_at, securities list.
    """
    report_id = str(uuid.uuid4())
    generated_at = datetime.utcnow()

    if tickers is None:
        tickers = get_default_tickers(frequency)

    logger.info(f"Generating {frequency} report for {len(tickers)} tickers (report_id={report_id[:8]})")

    # 1. Fetch price data
    price_data = _fetch_all_prices(tickers, frequency)
    logger.info(f"Fetched price data for {len(price_data)} tickers")

    # 2. Compute predictions
    predictions = _compute_predictions(price_data, frequency)
    logger.info(f"Computed predictions: {len(predictions)} tickers scored")

    # 3. Filter to >= 80%
    flagged = {t: p for t, p in predictions.items() if p['probability'] >= PROBABILITY_THRESHOLD}
    logger.info(f"Flagged {len(flagged)} tickers above {PROBABILITY_THRESHOLD*100}% threshold")

    # 4. Enrich flagged tickers
    securities = []
    sector_sentiments_cache = {}
    for ticker, pred in flagged.items():
        entry = _enrich_security(
            ticker, pred, price_data.get(ticker),
            frequency, include_options, sector_sentiments_cache
        )
        securities.append(entry)

    # 5. Sort by probability descending
    securities.sort(key=lambda s: s.get('break_probability', 0), reverse=True)

    # 6. Detect recency alerts
    alerts_count = _detect_recency_alerts(securities, frequency, db_manager)

    return {
        'report_id': report_id,
        'frequency': frequency,
        'generated_at': generated_at.isoformat(),
        'securities_count': len(securities),
        'alerts_count': alerts_count,
        'securities': securities,
    }


def get_default_tickers(frequency: str) -> List[str]:
    """Get default ticker list based on frequency."""
    if frequency == 'daily':
        return SP500_TOP_50[:50]
    elif frequency == 'hourly':
        return SP500_TOP_50[:30]
    else:  # 10min
        return SP500_TOP_50[:20]


# ──────────────────────────────────────────────────────────────────────────────
# Price fetching
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_all_prices(tickers: List[str], frequency: str) -> Dict[str, pd.DataFrame]:
    """Fetch OHLCV data for all tickers via yfinance."""
    import yfinance as yf

    params = YFINANCE_PARAMS.get(frequency, YFINANCE_PARAMS['daily'])
    result = {}

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=params['period'], interval=params['interval'])
            if not df.empty and len(df) >= 20:
                df = df.reset_index()
                # Normalize column names
                if 'Date' in df.columns:
                    df = df.rename(columns={'Date': 'date'})
                elif 'Datetime' in df.columns:
                    df = df.rename(columns={'Datetime': 'date'})
                result[ticker] = df
            time.sleep(0.2)
        except Exception as e:
            logger.warning(f"Failed to fetch {ticker}: {e}")

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Prediction computation
# ──────────────────────────────────────────────────────────────────────────────

def _compute_predictions(
    price_data: Dict[str, pd.DataFrame],
    frequency: str,
) -> Dict[str, Dict]:
    """
    Compute trend break predictions for all tickers.

    Tries to load XGBoost model; falls back to rule-based scoring.
    Returns {ticker: {probability, direction, confidence}}.
    """
    predictions = {}

    # Try to load trained model
    model = _try_load_model()

    for ticker, df in price_data.items():
        try:
            if model is not None:
                pred = _predict_with_model(model, df)
            else:
                pred = _predict_rule_based(df, frequency)
            predictions[ticker] = pred
        except Exception as e:
            logger.warning(f"Prediction failed for {ticker}: {e}")

    return predictions


def _try_load_model():
    """Try to load the XGBoost trend break model."""
    try:
        import joblib
        model_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'trend_break_model.pkl'),
            '/app/models/trend_break_model.pkl',
        ]
        for path in model_paths:
            if os.path.exists(path):
                return joblib.load(path)
    except Exception as e:
        logger.debug(f"Model not available: {e}")
    return None


def _predict_with_model(model, df: pd.DataFrame) -> Dict:
    """Use trained model for prediction."""
    features = _compute_ml_features(df)
    if features is None:
        return _predict_rule_based(df, 'daily')

    prob = model.predict_proba(features.reshape(1, -1))[0]
    probability = float(max(prob))
    direction = 'bullish' if prob[1] > prob[0] else 'bearish'

    return {
        'probability': probability,
        'direction': direction,
        'confidence': probability,
    }


def _compute_ml_features(df: pd.DataFrame) -> Optional[np.ndarray]:
    """Compute ML feature vector from price DataFrame."""
    try:
        from app.services.dashboard_service import (
            _calculate_cci, _calculate_rsi, _calculate_stochastic, _calculate_sma
        )

        if len(df) < 50:
            return None

        cci = _calculate_cci(df)
        rsi = _calculate_rsi(df)
        stoch_k, stoch_d = _calculate_stochastic(df)
        sma_20 = _calculate_sma(df['Close'], 20)
        sma_50 = _calculate_sma(df['Close'], 50)

        # MACD
        ema_12 = df['Close'].ewm(span=12).mean()
        ema_26 = df['Close'].ewm(span=26).mean()
        macd = ema_12 - ema_26
        macd_signal = macd.ewm(span=9).mean()
        macd_hist = macd - macd_signal

        # Bollinger Bands
        bb_mid = sma_20
        bb_std = df['Close'].rolling(20).std()
        bb_upper = bb_mid + (2 * bb_std)
        bb_lower = bb_mid - (2 * bb_std)

        # OBV
        obv = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()

        latest = len(df) - 1
        features = np.array([
            float(rsi.iloc[latest]) if not np.isnan(rsi.iloc[latest]) else 50.0,
            float(macd.iloc[latest]) if not np.isnan(macd.iloc[latest]) else 0.0,
            float(macd_signal.iloc[latest]) if not np.isnan(macd_signal.iloc[latest]) else 0.0,
            float(macd_hist.iloc[latest]) if not np.isnan(macd_hist.iloc[latest]) else 0.0,
            float(bb_upper.iloc[latest]) if not np.isnan(bb_upper.iloc[latest]) else 0.0,
            float(bb_mid.iloc[latest]) if not np.isnan(bb_mid.iloc[latest]) else 0.0,
            float(bb_lower.iloc[latest]) if not np.isnan(bb_lower.iloc[latest]) else 0.0,
            float(stoch_k.iloc[latest]) if not np.isnan(stoch_k.iloc[latest]) else 50.0,
            float(stoch_d.iloc[latest]) if not np.isnan(stoch_d.iloc[latest]) else 50.0,
            float(cci.iloc[latest]) if not np.isnan(cci.iloc[latest]) else 0.0,
            float(obv.iloc[latest]) if not np.isnan(obv.iloc[latest]) else 0.0,
        ])

        return features
    except Exception as e:
        logger.debug(f"ML feature computation failed: {e}")
        return None


def _predict_rule_based(df: pd.DataFrame, frequency: str) -> Dict:
    """
    Rule-based trend break prediction when ML model is unavailable.

    Combines multiple signals:
    - RSI extremes (>70 or <30)
    - MACD histogram divergence
    - CCI extremes (>100 or <-100)
    - Price near Bollinger Band edges
    - Stochastic crossovers
    """
    from app.services.dashboard_service import (
        _calculate_cci, _calculate_rsi, _calculate_stochastic,
        _calculate_sma, calculate_tlev
    )

    if len(df) < 20:
        return {'probability': 0.0, 'direction': 'neutral', 'confidence': 0.0}

    latest = len(df) - 1
    signals_bullish = 0
    signals_bearish = 0
    total_signals = 0

    # RSI
    rsi = _calculate_rsi(df)
    rsi_val = float(rsi.iloc[latest]) if not np.isnan(rsi.iloc[latest]) else 50.0
    if rsi_val > 70:
        signals_bearish += 2  # Strong overbought signal
        total_signals += 2
    elif rsi_val < 30:
        signals_bullish += 2  # Strong oversold signal
        total_signals += 2
    elif rsi_val > 60:
        signals_bearish += 1
        total_signals += 1
    elif rsi_val < 40:
        signals_bullish += 1
        total_signals += 1

    # CCI
    cci = _calculate_cci(df)
    cci_val = float(cci.iloc[latest]) if not np.isnan(cci.iloc[latest]) else 0.0
    if cci_val > 200:
        signals_bearish += 2  # Extreme overbought
        total_signals += 2
    elif cci_val > 100:
        signals_bearish += 1
        total_signals += 1
    elif cci_val < -200:
        signals_bullish += 2  # Extreme oversold
        total_signals += 2
    elif cci_val < -100:
        signals_bullish += 1
        total_signals += 1

    # Stochastic
    stoch_k, stoch_d = _calculate_stochastic(df)
    k_val = float(stoch_k.iloc[latest]) if not np.isnan(stoch_k.iloc[latest]) else 50.0
    d_val = float(stoch_d.iloc[latest]) if not np.isnan(stoch_d.iloc[latest]) else 50.0
    if k_val > 80 and k_val < d_val:
        signals_bearish += 1  # Overbought + bearish crossover
        total_signals += 1
    elif k_val < 20 and k_val > d_val:
        signals_bullish += 1  # Oversold + bullish crossover
        total_signals += 1

    # MACD histogram
    ema_12 = df['Close'].ewm(span=12).mean()
    ema_26 = df['Close'].ewm(span=26).mean()
    macd_hist = (ema_12 - ema_26) - (ema_12 - ema_26).ewm(span=9).mean()
    hist_val = float(macd_hist.iloc[latest]) if not np.isnan(macd_hist.iloc[latest]) else 0.0
    hist_prev = float(macd_hist.iloc[latest-1]) if latest > 0 and not np.isnan(macd_hist.iloc[latest-1]) else 0.0

    if hist_val < 0 and hist_prev > 0:
        signals_bearish += 2  # Bearish MACD crossover
        total_signals += 2
    elif hist_val > 0 and hist_prev < 0:
        signals_bullish += 2  # Bullish MACD crossover
        total_signals += 2

    # Bollinger Band proximity
    sma_20 = _calculate_sma(df['Close'], 20)
    bb_std = df['Close'].rolling(20).std()
    bb_upper = sma_20 + (2 * bb_std)
    bb_lower = sma_20 - (2 * bb_std)
    price = float(df['Close'].iloc[latest])
    upper = float(bb_upper.iloc[latest]) if not np.isnan(bb_upper.iloc[latest]) else price
    lower = float(bb_lower.iloc[latest]) if not np.isnan(bb_lower.iloc[latest]) else price

    if price > upper:
        signals_bearish += 1
        total_signals += 1
    elif price < lower:
        signals_bullish += 1
        total_signals += 1

    # TLEV for intraday
    if frequency in ('hourly', '10min'):
        tlev = calculate_tlev(df)
        tlev_val = float(tlev.iloc[latest]) if not np.isnan(tlev.iloc[latest]) else 0.0
        if tlev_val > 0.05:
            signals_bullish += 1
            total_signals += 1
        elif tlev_val < -0.05:
            signals_bearish += 1
            total_signals += 1

    # Calculate probability from signal strength
    if total_signals == 0:
        return {'probability': 0.3, 'direction': 'neutral', 'confidence': 0.3}

    max_signals = max(signals_bullish, signals_bearish)
    # Scale: 0 signals = 0.30, max signals (10+) = 0.95
    raw_prob = 0.30 + (max_signals / total_signals) * 0.50 + min(max_signals / 8.0, 0.15)
    probability = min(round(raw_prob, 4), 0.98)

    if signals_bullish > signals_bearish:
        direction = 'bullish'
    elif signals_bearish > signals_bullish:
        direction = 'bearish'
    else:
        direction = 'neutral'

    return {
        'probability': probability,
        'direction': direction,
        'confidence': round(abs(signals_bullish - signals_bearish) / max(total_signals, 1), 4),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Enrichment
# ──────────────────────────────────────────────────────────────────────────────

def _enrich_security(
    ticker: str,
    prediction: Dict,
    price_df: Optional[pd.DataFrame],
    frequency: str,
    include_options: bool,
    sector_cache: Dict,
) -> Dict:
    """Add indicators, sector, and options to a flagged security."""
    from app.services.dashboard_service import (
        _calculate_cci, _calculate_stochastic, _calculate_rsi,
        _calculate_sma, _calculate_adx, calculate_tlev,
    )

    entry = {
        'ticker': ticker,
        'break_probability': prediction['probability'],
        'break_direction': prediction['direction'],
        'confidence': prediction.get('confidence', 0),
        'is_recent_alert': False,
        'first_crossed_at': None,
        'consecutive_reports': 1,
    }

    # Price
    if price_df is not None and len(price_df) > 0:
        entry['current_price'] = round(float(price_df['Close'].iloc[-1]), 4)
        if len(price_df) > 1:
            prev = float(price_df['Close'].iloc[-2])
            if prev != 0:
                entry['price_change_pct'] = round(
                    (entry['current_price'] - prev) / prev * 100, 4
                )
            else:
                entry['price_change_pct'] = 0.0
        else:
            entry['price_change_pct'] = 0.0
    else:
        entry['current_price'] = None
        entry['price_change_pct'] = None

    # Indicators
    indicators = {}
    if price_df is not None and len(price_df) >= 20:
        try:
            cci = _calculate_cci(price_df)
            indicators['cci'] = round(float(cci.iloc[-1]), 2) if not np.isnan(cci.iloc[-1]) else None

            stoch_k, stoch_d = _calculate_stochastic(price_df)
            indicators['stochastic_k'] = round(float(stoch_k.iloc[-1]), 2) if not np.isnan(stoch_k.iloc[-1]) else None
            indicators['stochastic_d'] = round(float(stoch_d.iloc[-1]), 2) if not np.isnan(stoch_d.iloc[-1]) else None

            rsi = _calculate_rsi(price_df)
            indicators['rsi'] = round(float(rsi.iloc[-1]), 2) if not np.isnan(rsi.iloc[-1]) else None

            sma_20 = _calculate_sma(price_df['Close'], 20)
            sma_50 = _calculate_sma(price_df['Close'], 50)
            indicators['sma_20'] = round(float(sma_20.iloc[-1]), 4) if not np.isnan(sma_20.iloc[-1]) else None
            indicators['sma_50'] = round(float(sma_50.iloc[-1]), 4) if len(price_df) >= 50 and not np.isnan(sma_50.iloc[-1]) else None

            adx, _, _ = _calculate_adx(price_df)
            indicators['adx'] = round(float(adx.iloc[-1]), 2) if not np.isnan(adx.iloc[-1]) else None

            if frequency in ('hourly', '10min'):
                tlev = calculate_tlev(price_df)
                indicators['tlev'] = round(float(tlev.iloc[-1]), 4) if not np.isnan(tlev.iloc[-1]) else None
        except Exception as e:
            logger.warning(f"Indicator calc failed for {ticker}: {e}")

    entry['indicators'] = indicators

    # Sector
    sector_name = _get_ticker_sector(ticker)
    sector_etf = SECTOR_ETFS.get(sector_name)
    entry['sector'] = sector_name
    entry['sector_etf'] = sector_etf

    # Sector sentiment (cached to avoid redundant computation)
    if sector_name and sector_name not in sector_cache:
        sector_cache[sector_name] = _compute_sector_sentiment(sector_name)
    sector_sent = sector_cache.get(sector_name, {})
    entry['sector_sentiment'] = {
        'name': sector_name,
        'sentiment': sector_sent.get('sentiment', 'NEUTRAL'),
        'confidence': sector_sent.get('confidence', 0),
    }

    # Options
    if include_options and frequency != '10min':
        entry['options_summary'] = _get_options_summary(ticker)
    else:
        entry['options_summary'] = {'available': False}

    return entry


def _get_ticker_sector(ticker: str) -> Optional[str]:
    """Look up sector for a ticker."""
    # First try hardcoded map
    if ticker in TICKER_SECTOR_MAP:
        return TICKER_SECTOR_MAP[ticker]

    # Try yfinance
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return info.get('sector')
    except Exception:
        return None


def _compute_sector_sentiment(sector_name: str) -> Dict:
    """Compute sentiment for a sector using its ETF proxy."""
    from app.services.dashboard_service import (
        _fetch_yfinance_data, _calculate_cci, _calculate_stochastic,
        _calculate_rsi, _calculate_sma, _determine_sentiment,
    )

    etf = SECTOR_ETFS.get(sector_name)
    if not etf:
        return {'sentiment': 'NEUTRAL', 'confidence': 0}

    try:
        df = _fetch_yfinance_data(etf, period='1y', interval='1wk')
        if df.empty or len(df) < 20:
            return {'sentiment': 'NEUTRAL', 'confidence': 0}

        cci = _calculate_cci(df)
        stoch_k, stoch_d = _calculate_stochastic(df)
        rsi = _calculate_rsi(df)
        sma_20 = _calculate_sma(df['Close'], 20)
        sma_50 = _calculate_sma(df['Close'], 50)

        latest = len(df) - 1
        sentiment, confidence, _ = _determine_sentiment(
            float(cci.iloc[latest]) if not np.isnan(cci.iloc[latest]) else 0,
            float(stoch_k.iloc[latest]) if not np.isnan(stoch_k.iloc[latest]) else 50,
            float(stoch_d.iloc[latest]) if not np.isnan(stoch_d.iloc[latest]) else 50,
            float(sma_20.iloc[latest]) if not np.isnan(sma_20.iloc[latest]) else 0,
            float(sma_50.iloc[latest]) if not np.isnan(sma_50.iloc[latest]) else 0,
            float(rsi.iloc[latest]) if not np.isnan(rsi.iloc[latest]) else 50,
        )

        return {'sentiment': sentiment, 'confidence': confidence}
    except Exception as e:
        logger.warning(f"Sector sentiment failed for {sector_name}: {e}")
        return {'sentiment': 'NEUTRAL', 'confidence': 0}


def _get_options_summary(ticker: str) -> Dict:
    """Get ATM options summary for a ticker."""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if not expirations:
            return {'available': False}

        # Use nearest expiration
        nearest_exp = expirations[0]
        chain = stock.option_chain(nearest_exp)

        current_price = stock.info.get('currentPrice') or stock.info.get('regularMarketPrice', 0)
        if not current_price:
            hist = stock.history(period='1d')
            current_price = float(hist['Close'].iloc[-1]) if not hist.empty else 0

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
            result['nearest_call_fair_value'] = float(atm_call['lastPrice'])
            result['call_iv'] = float(atm_call['impliedVolatility']) if 'impliedVolatility' in atm_call else None

        # Nearest ATM put
        if not chain.puts.empty:
            puts = chain.puts
            puts_diff = (puts['strike'] - current_price).abs()
            atm_put = puts.loc[puts_diff.idxmin()]
            result['nearest_put_strike'] = float(atm_put['strike'])
            result['nearest_put_fair_value'] = float(atm_put['lastPrice'])
            result['put_iv'] = float(atm_put['impliedVolatility']) if 'impliedVolatility' in atm_put else None

        # Average IV
        call_iv = result.get('call_iv', 0) or 0
        put_iv = result.get('put_iv', 0) or 0
        result['implied_volatility'] = round((call_iv + put_iv) / 2, 4) if (call_iv or put_iv) else None

        return result
    except Exception as e:
        logger.debug(f"Options fetch failed for {ticker}: {e}")
        return {'available': False}


# ──────────────────────────────────────────────────────────────────────────────
# Recency alerts
# ──────────────────────────────────────────────────────────────────────────────

def _detect_recency_alerts(
    securities: List[Dict],
    frequency: str,
    db_manager=None,
) -> int:
    """
    Mark securities that recently crossed the 80% threshold.

    Without DB, uses a simple heuristic: if multiple strong signals are
    present, mark as alert (for development without Airflow/DB).

    Returns the count of alerts detected.
    """
    alerts_count = 0
    window = RECENCY_WINDOWS[frequency]

    if db_manager:
        # DB-backed: check historical reports
        cutoff = (datetime.utcnow() - window).isoformat()
        for sec in securities:
            try:
                query = """
                    SELECT MIN(report_generated_at), COUNT(*)
                    FROM trend_break_reports
                    WHERE ticker = %s
                      AND report_frequency = %s
                      AND break_probability >= %s
                      AND report_generated_at >= %s
                """
                rows = db_manager.execute_query(
                    query, (sec['ticker'], frequency, PROBABILITY_THRESHOLD, cutoff)
                )
                if rows and rows[0][0]:
                    first_seen = rows[0][0]
                    count = rows[0][1]
                    sec['is_recent_alert'] = True
                    sec['first_crossed_at'] = first_seen.isoformat() if hasattr(first_seen, 'isoformat') else str(first_seen)
                    sec['consecutive_reports'] = count
                    alerts_count += 1
            except Exception as e:
                logger.warning(f"Recency check failed for {sec['ticker']}: {e}")
    else:
        # No DB: heuristic — mark as alert if probability >= 85% and
        # strong directional signal (high CCI or extreme RSI)
        for sec in securities:
            prob = sec.get('break_probability', 0)
            indicators = sec.get('indicators', {})
            cci = abs(indicators.get('cci', 0) or 0)
            rsi = indicators.get('rsi', 50) or 50

            is_extreme = (cci > 150) or (rsi > 70 or rsi < 30)
            if prob >= 0.85 and is_extreme:
                sec['is_recent_alert'] = True
                sec['first_crossed_at'] = datetime.utcnow().isoformat()
                sec['consecutive_reports'] = 1
                alerts_count += 1

    return alerts_count


# ──────────────────────────────────────────────────────────────────────────────
# DB storage (used by Airflow DAGs)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_report_chart_data(ticker: str, interval: str = '5m') -> Dict:
    """
    Fetch OHLC chart data for a report ticker at a given interval.

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

    params = INTERVAL_PARAMS.get(interval, INTERVAL_PARAMS['5m'])
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
    peaks = _detect_chart_peaks(closes, chart_data)
    troughs = _detect_chart_troughs(closes, chart_data)

    return {
        'data': chart_data,
        'peaks': peaks,
        'troughs': troughs,
    }


def _detect_chart_peaks(closes, chart_data, window=5):
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


def _detect_chart_troughs(closes, chart_data, window=5):
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


def store_report(report: Dict, db_manager) -> bool:
    """Store report entries in the database. Returns True on success."""
    try:
        securities = report.get('securities', [])
        if not securities:
            return True

        query = """
            INSERT INTO trend_break_reports (
                report_id, report_frequency, report_generated_at,
                ticker, sector, sector_etf,
                break_probability, break_direction, confidence,
                is_recent_alert, first_crossed_at, consecutive_reports,
                current_price, price_change_pct,
                cci_value, stochastic_k, stochastic_d, rsi_value,
                adx_value, tlev_value, sma_20, sma_50,
                sector_sentiment, sector_confidence,
                options_available, nearest_call_strike, nearest_call_fair_value,
                nearest_put_strike, nearest_put_fair_value, implied_volatility,
                model_version
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
        """

        with db_manager.get_cursor(commit=True) as cursor:
            for sec in securities:
                ind = sec.get('indicators', {})
                opts = sec.get('options_summary', {})
                sect = sec.get('sector_sentiment', {})
                cursor.execute(query, (
                    report['report_id'], report['frequency'], report['generated_at'],
                    sec['ticker'], sec.get('sector'), sec.get('sector_etf'),
                    sec['break_probability'], sec['break_direction'], sec.get('confidence'),
                    sec.get('is_recent_alert', False), sec.get('first_crossed_at'),
                    sec.get('consecutive_reports', 1),
                    sec.get('current_price'), sec.get('price_change_pct'),
                    ind.get('cci'), ind.get('stochastic_k'), ind.get('stochastic_d'),
                    ind.get('rsi'), ind.get('adx'), ind.get('tlev'),
                    ind.get('sma_20'), ind.get('sma_50'),
                    sect.get('sentiment'), sect.get('confidence'),
                    opts.get('available', False), opts.get('nearest_call_strike'),
                    opts.get('nearest_call_fair_value'), opts.get('nearest_put_strike'),
                    opts.get('nearest_put_fair_value'), opts.get('implied_volatility'),
                    'rule-based-v1',
                ))

        logger.info(f"Stored {len(securities)} report entries for report {report['report_id'][:8]}")
        return True
    except Exception as e:
        logger.error(f"Failed to store report: {e}")
        return False
