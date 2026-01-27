"""
Dashboard Service
=================
Computes market sentiment, sector sentiment, index/VIX sentiment,
and commodities/crypto data for the frontend dashboard widgets.

Indicator selection per timeframe:
- CCI: all periods
- Stochastic: daily and longer
- TLEV: hourly and faster
"""

import logging
import sys
import os
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

# Add project root so we can import src modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

SECTOR_ETFS = {
    'Technology': 'XLK',
    'Health Care': 'XLV',
    'Financials': 'XLF',
    'Consumer Discretionary': 'XLY',
    'Communication Services': 'XLC',
    'Industrials': 'XLI',
    'Consumer Staples': 'XLP',
    'Energy': 'XLE',
    'Utilities': 'XLU',
    'Real Estate': 'XLRE',
    'Materials': 'XLB',
}

COMMODITY_CRYPTO_ASSETS = [
    {'symbol': 'GC=F', 'name': 'Gold'},
    {'symbol': 'SI=F', 'name': 'Silver'},
    {'symbol': 'ETH-USD', 'name': 'Ethereum'},
    {'symbol': 'BTC-USD', 'name': 'Bitcoin'},
]

INDEX_SYMBOLS = [
    {'symbol': '^GSPC', 'name': 'S&P 500'},
    {'symbol': '^RUT', 'name': 'Russell 2000'},
    {'symbol': 'QQQ', 'name': 'Nasdaq-100'},
]

INVERSE_ETFS = [
    {'symbol': 'SH', 'name': 'Short S&P 500'},
    {'symbol': 'PSQ', 'name': 'Short QQQ'},
    {'symbol': 'DOG', 'name': 'Short Dow 30'},
]


# ──────────────────────────────────────────────────────────────────────────────
# Indicator helpers
# ──────────────────────────────────────────────────────────────────────────────

def _calculate_cci(df, length=20):
    """Compute CCI on a DataFrame with High, Low, Close columns."""
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    sma_tp = tp.rolling(window=length).mean()
    mad = tp.rolling(window=length).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    cci = (tp - sma_tp) / (0.015 * mad)
    return cci


def _calculate_stochastic(df, k_period=14, d_period=3):
    """Compute Stochastic %K and %D."""
    low_min = df['Low'].rolling(window=k_period).min()
    high_max = df['High'].rolling(window=k_period).max()
    stoch_k = 100 * (df['Close'] - low_min) / (high_max - low_min)
    stoch_d = stoch_k.rolling(window=d_period).mean()
    return stoch_k, stoch_d


def _calculate_rsi(df, length=14):
    """Compute RSI."""
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=length).mean()
    avg_loss = loss.rolling(window=length).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _calculate_sma(series, length):
    """Compute SMA on a Series."""
    return series.rolling(window=length).mean()


def _calculate_adx(df, length=14):
    """Compute ADX for market type classification."""
    high = df['High']
    low = df['Low']
    close = df['Close']

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=length).mean()
    plus_di = 100 * (plus_dm.rolling(window=length).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=length).mean() / atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(window=length).mean()
    return adx, plus_di, minus_di


def calculate_tlev(df):
    """
    Traders Lion Enhanced Volume (TLEV) indicator.
    Volume-weighted price momentum: rolling(14).sum() of pct_change * relative_volume.

    Returns Series of TLEV values.
    """
    if 'Volume' not in df.columns or df['Volume'].sum() == 0:
        return pd.Series(np.nan, index=df.index)

    price_change = df['Close'].pct_change()
    vol_sma = df['Volume'].rolling(20).mean()
    vol_sma = vol_sma.replace(0, np.nan)
    rel_volume = df['Volume'] / vol_sma
    tlev_raw = price_change * rel_volume
    tlev = tlev_raw.rolling(14).sum()
    return tlev


def select_indicators_for_timeframe(timeframe):
    """Return indicator names to use for a given timeframe."""
    indicators = ['CCI']
    if timeframe in ('weekly', 'daily'):
        indicators.append('Stochastic')
    if timeframe in ('hourly', '5min', '1min'):
        indicators.append('TLEV')
    return indicators


# ──────────────────────────────────────────────────────────────────────────────
# Sentiment scoring
# ──────────────────────────────────────────────────────────────────────────────

def _determine_sentiment(cci, stoch_k, stoch_d, sma_short, sma_long, rsi):
    """
    Score multiple indicator signals to determine BULLISH / BEARISH / NEUTRAL.

    Returns (sentiment, confidence, signals_dict).
    """
    bullish = 0
    bearish = 0
    signals = {}

    # CCI
    if not np.isnan(cci):
        if cci > 100:
            bullish += 1
            signals['cci'] = {'value': round(float(cci), 1), 'signal': 'bullish',
                              'description': 'Above +100: strong uptrend'}
        elif cci < -100:
            bearish += 1
            signals['cci'] = {'value': round(float(cci), 1), 'signal': 'bearish',
                              'description': 'Below -100: strong downtrend'}
        else:
            signals['cci'] = {'value': round(float(cci), 1), 'signal': 'neutral',
                              'description': 'Between -100 and +100: no strong trend'}

    # Stochastic
    if not np.isnan(stoch_k) and not np.isnan(stoch_d):
        if stoch_k > stoch_d and stoch_k < 80:
            bullish += 1
            signals['stochastic'] = {'value': round(float(stoch_k), 1), 'signal': 'bullish',
                                     'description': '%K above %D, not overbought'}
        elif stoch_k < stoch_d and stoch_k > 20:
            bearish += 1
            signals['stochastic'] = {'value': round(float(stoch_k), 1), 'signal': 'bearish',
                                     'description': '%K below %D, not oversold'}
        else:
            signals['stochastic'] = {'value': round(float(stoch_k), 1), 'signal': 'neutral',
                                     'description': 'No clear stochastic signal'}

    # SMA crossover
    if not np.isnan(sma_short) and not np.isnan(sma_long):
        if sma_short > sma_long:
            bullish += 1
            signals['sma_crossover'] = {'value': round(float(sma_short), 2), 'signal': 'bullish',
                                        'description': '20-period above 50-period'}
        else:
            bearish += 1
            signals['sma_crossover'] = {'value': round(float(sma_short), 2), 'signal': 'bearish',
                                        'description': '20-period below 50-period'}

    # RSI
    if not np.isnan(rsi):
        if rsi > 50:
            bullish += 1
            signals['rsi'] = {'value': round(float(rsi), 1), 'signal': 'bullish',
                              'description': f'RSI {rsi:.0f} above 50'}
        else:
            bearish += 1
            signals['rsi'] = {'value': round(float(rsi), 1), 'signal': 'bearish',
                              'description': f'RSI {rsi:.0f} below 50'}

    total = bullish + bearish
    if total == 0:
        return 'NEUTRAL', 0.5, signals

    if bullish >= 3:
        sentiment = 'BULLISH'
    elif bearish >= 3:
        sentiment = 'BEARISH'
    else:
        sentiment = 'NEUTRAL'

    confidence = abs(bullish - bearish) / total
    return sentiment, round(confidence, 2), signals


def interpret_vix(vix_level):
    """Interpret VIX level into fear label and description."""
    if vix_level < 12:
        return 'Very Low (Complacent)', 'VIX below 12 indicates extreme complacency; potential for volatility spike'
    elif vix_level < 15:
        return 'Low Fear', 'VIX between 12-15 indicates low market fear'
    elif vix_level < 25:
        return 'Normal', 'VIX between 15-25 indicates normal market conditions'
    elif vix_level < 35:
        return 'Elevated Fear', 'VIX between 25-35 indicates elevated market fear'
    else:
        return 'Extreme Fear', 'VIX above 35 indicates extreme fear and market stress'


# ──────────────────────────────────────────────────────────────────────────────
# Data fetching helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_yfinance_data(symbol, period='1y', interval='1wk'):
    """Fetch data via yfinance. Returns DataFrame with Open/High/Low/Close/Volume."""
    import yfinance as yf
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        return pd.DataFrame()
    df = df.reset_index()
    # Normalize column names
    if 'Date' in df.columns:
        df = df.rename(columns={'Date': 'date'})
    elif 'Datetime' in df.columns:
        df = df.rename(columns={'Datetime': 'date'})
    return df


def _fetch_market_index_from_db(db_manager, symbol, days=210):
    """Fetch market index daily data from database."""
    try:
        query = """
            SELECT timestamp, open, high, low, close, volume, adjusted_close
            FROM market_indices
            WHERE symbol = %s
              AND timestamp >= %s::date
            ORDER BY timestamp ASC
        """
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        rows = db_manager.execute_query(query, (symbol, start_date))
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=['date', 'Open', 'High', 'Low', 'Close', 'Volume', 'AdjClose'])
        df['date'] = pd.to_datetime(df['date'])
        for col in ['Open', 'High', 'Low', 'Close', 'AdjClose']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce').fillna(0).astype(int)
        return df
    except Exception as e:
        logger.warning(f"DB fetch failed for {symbol}: {e}")
        return pd.DataFrame()


def _get_cboe_context():
    """Load latest CBOE P/C ratio context. Returns dict or None."""
    try:
        from src.darkpool_options_analysis import batch_load_cboe_context
        cboe_df = batch_load_cboe_context()
        if cboe_df is None or cboe_df.empty:
            return None

        latest = cboe_df.iloc[-1]
        regime_val = int(latest.get('pcr_regime', 0))
        regime_labels = {-2: 'Very Bullish', -1: 'Bullish', 0: 'Neutral',
                         1: 'Bearish', 2: 'Very Bearish'}
        return {
            'pcr_regime': regime_labels.get(regime_val, 'Neutral'),
            'pcr_regime_value': regime_val,
            'total_pcr': round(float(latest.get('total_pcr', 0)), 2),
            'pcr_zscore': round(float(latest.get('pcr_zscore', 0)), 2),
        }
    except Exception as e:
        logger.warning(f"CBOE context unavailable: {e}")
        return None


def _resample_to_weekly(df):
    """Resample daily OHLCV to weekly."""
    if df.empty:
        return df
    df = df.set_index('date')
    weekly = df.resample('W').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum',
    }).dropna()
    weekly = weekly.reset_index()
    return weekly


# ──────────────────────────────────────────────────────────────────────────────
# Widget 1: Market Sentiment
# ──────────────────────────────────────────────────────────────────────────────

def compute_market_sentiment(db_manager=None):
    """
    Compute overall market sentiment from S&P 500 weekly data.
    Uses CCI + Stochastic (weekly timeframe) + SMA crossover + RSI.
    """
    # Fetch S&P 500 data
    df = pd.DataFrame()
    if db_manager:
        df = _fetch_market_index_from_db(db_manager, '^GSPC', days=210)

    if df.empty:
        df = _fetch_yfinance_data('^GSPC', period='1y', interval='1d')
        if df.empty:
            return {'sentiment': 'NEUTRAL', 'confidence': 0, 'indicators': {},
                    'market_type': 'unknown', 'cboe_context': None,
                    'weekly_chart_data': [], 'last_updated': datetime.now().isoformat()}

    # Resample to weekly
    weekly = _resample_to_weekly(df)
    if len(weekly) < 20:
        return {'sentiment': 'NEUTRAL', 'confidence': 0, 'indicators': {},
                'market_type': 'unknown', 'cboe_context': None,
                'weekly_chart_data': [], 'last_updated': datetime.now().isoformat()}

    # Calculate indicators
    cci = _calculate_cci(weekly, length=20)
    stoch_k, stoch_d = _calculate_stochastic(weekly)
    rsi = _calculate_rsi(weekly)
    sma_20 = _calculate_sma(weekly['Close'], 20)
    sma_50 = _calculate_sma(weekly['Close'], 50) if len(weekly) >= 50 else pd.Series(np.nan, index=weekly.index)

    # Get latest values
    latest_cci = float(cci.iloc[-1]) if not np.isnan(cci.iloc[-1]) else 0.0
    latest_k = float(stoch_k.iloc[-1]) if not np.isnan(stoch_k.iloc[-1]) else 50.0
    latest_d = float(stoch_d.iloc[-1]) if not np.isnan(stoch_d.iloc[-1]) else 50.0
    latest_rsi = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0
    latest_sma20 = float(sma_20.iloc[-1]) if not np.isnan(sma_20.iloc[-1]) else 0.0
    latest_sma50 = float(sma_50.iloc[-1]) if not np.isnan(sma_50.iloc[-1]) else 0.0

    sentiment, confidence, signals = _determine_sentiment(
        latest_cci, latest_k, latest_d, latest_sma20, latest_sma50, latest_rsi
    )

    # Market type via ADX on daily data
    market_type = 'unknown'
    if len(df) >= 30:
        adx, plus_di, minus_di = _calculate_adx(df)
        adx_val = float(adx.iloc[-1]) if not np.isnan(adx.iloc[-1]) else 20
        plus_val = float(plus_di.iloc[-1]) if not np.isnan(plus_di.iloc[-1]) else 0
        minus_val = float(minus_di.iloc[-1]) if not np.isnan(minus_di.iloc[-1]) else 0
        if adx_val > 25:
            market_type = 'trending_up' if plus_val > minus_val else 'trending_down'
        elif adx_val < 20:
            market_type = 'ranging'
        else:
            market_type = 'transitioning'

    # CBOE context
    cboe_context = _get_cboe_context()

    # Chart data (last 26 weeks)
    chart_weeks = weekly.tail(26)
    chart_data = []
    for _, row in chart_weeks.iterrows():
        idx = chart_weeks.index[chart_weeks['date'] == row['date']]
        sma_val = float(sma_20.iloc[idx[0]]) if len(idx) > 0 and not np.isnan(sma_20.iloc[idx[0]]) else None
        chart_data.append({
            'date': row['date'].strftime('%Y-%m-%d'),
            'close': round(float(row['Close']), 2),
            'sma_20': round(sma_val, 2) if sma_val is not None else None,
        })

    return {
        'sentiment': sentiment,
        'confidence': confidence,
        'indicators': signals,
        'market_type': market_type,
        'cboe_context': cboe_context,
        'weekly_chart_data': chart_data,
        'last_updated': datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Widget 2: Sector Sentiment
# ──────────────────────────────────────────────────────────────────────────────

def compute_sector_sentiments():
    """
    Compute sentiment for each GICS sector via sector ETFs.
    Uses CCI + Stochastic on weekly data.
    """
    import time
    sectors = []

    for sector_name, etf_symbol in SECTOR_ETFS.items():
        try:
            df = _fetch_yfinance_data(etf_symbol, period='1y', interval='1wk')
            if df.empty or len(df) < 20:
                sectors.append({
                    'name': sector_name,
                    'sentiment': 'NEUTRAL',
                    'confidence': 0,
                    'proxy_etf': etf_symbol,
                    'cci_value': None,
                    'stochastic_k': None,
                    'weekly_change_pct': 0,
                    'weekly_chart_data': [],
                })
                continue

            # Calculate indicators
            cci = _calculate_cci(df, length=20)
            stoch_k, stoch_d = _calculate_stochastic(df)
            rsi = _calculate_rsi(df)
            sma_20 = _calculate_sma(df['Close'], 20)
            sma_50 = _calculate_sma(df['Close'], 50) if len(df) >= 50 else pd.Series(np.nan, index=df.index)

            latest_cci = float(cci.iloc[-1]) if not np.isnan(cci.iloc[-1]) else 0.0
            latest_k = float(stoch_k.iloc[-1]) if not np.isnan(stoch_k.iloc[-1]) else 50.0
            latest_d = float(stoch_d.iloc[-1]) if not np.isnan(stoch_d.iloc[-1]) else 50.0
            latest_rsi = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0
            latest_sma20 = float(sma_20.iloc[-1]) if not np.isnan(sma_20.iloc[-1]) else 0.0
            latest_sma50 = float(sma_50.iloc[-1]) if not np.isnan(sma_50.iloc[-1]) else 0.0

            sentiment, confidence, _ = _determine_sentiment(
                latest_cci, latest_k, latest_d, latest_sma20, latest_sma50, latest_rsi
            )

            # Weekly change
            if len(df) >= 2:
                prev_close = float(df['Close'].iloc[-2])
                curr_close = float(df['Close'].iloc[-1])
                weekly_change = ((curr_close - prev_close) / prev_close * 100) if prev_close else 0
            else:
                weekly_change = 0

            # Chart data (last 12 weeks)
            chart_df = df.tail(12)
            chart_data = [{
                'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])[:10],
                'close': round(float(row['Close']), 2),
            } for _, row in chart_df.iterrows()]

            sectors.append({
                'name': sector_name,
                'sentiment': sentiment,
                'confidence': confidence,
                'proxy_etf': etf_symbol,
                'cci_value': round(latest_cci, 1),
                'stochastic_k': round(latest_k, 1),
                'weekly_change_pct': round(weekly_change, 1),
                'weekly_chart_data': chart_data,
            })

            time.sleep(0.3)  # Rate limit protection

        except Exception as e:
            logger.warning(f"Sector {sector_name} ({etf_symbol}) failed: {e}")
            sectors.append({
                'name': sector_name,
                'sentiment': 'NEUTRAL',
                'confidence': 0,
                'proxy_etf': etf_symbol,
                'cci_value': None,
                'stochastic_k': None,
                'weekly_change_pct': 0,
                'weekly_chart_data': [],
            })

    return {
        'sectors': sectors,
        'last_updated': datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Widget 3: VIX & Index Sentiment
# ──────────────────────────────────────────────────────────────────────────────

def compute_index_sentiment(db_manager=None):
    """
    Compute VIX interpretation, S&P/RUT/QQQ sentiment, and inverse ETF signal.
    """
    result = {
        'vix': None,
        'indices': [],
        'inverse_etfs': None,
        'last_updated': datetime.now().isoformat(),
    }

    # ── VIX ──
    try:
        vix_df = pd.DataFrame()
        if db_manager:
            vix_df = _fetch_market_index_from_db(db_manager, '^VIX', days=10)
        if vix_df.empty:
            vix_df = _fetch_yfinance_data('^VIX', period='1mo', interval='1d')

        if not vix_df.empty:
            latest_vix = float(vix_df['Close'].iloc[-1])
            fear_level, description = interpret_vix(latest_vix)

            change_1d = 0
            change_5d = 0
            if len(vix_df) >= 2:
                change_1d = float(vix_df['Close'].iloc[-1] - vix_df['Close'].iloc[-2])
            if len(vix_df) >= 6:
                change_5d = float(vix_df['Close'].iloc[-1] - vix_df['Close'].iloc[-6])

            result['vix'] = {
                'value': round(latest_vix, 1),
                'fear_level': fear_level,
                'description': description,
                'change_1d': round(change_1d, 1),
                'change_5d': round(change_5d, 1),
            }
    except Exception as e:
        logger.warning(f"VIX fetch failed: {e}")

    # ── Indices (S&P 500, RUT, QQQ) ──
    import time
    for idx_info in INDEX_SYMBOLS:
        try:
            df = pd.DataFrame()
            if db_manager:
                df = _fetch_market_index_from_db(db_manager, idx_info['symbol'], days=210)
            if df.empty:
                df = _fetch_yfinance_data(idx_info['symbol'], period='1y', interval='1d')

            if df.empty or len(df) < 20:
                result['indices'].append({
                    'symbol': idx_info['symbol'], 'name': idx_info['name'],
                    'sentiment': 'NEUTRAL', 'cci_value': None, 'stochastic_k': None,
                    'current_price': None, 'weekly_change_pct': 0,
                })
                continue

            weekly = _resample_to_weekly(df)
            if len(weekly) < 20:
                result['indices'].append({
                    'symbol': idx_info['symbol'], 'name': idx_info['name'],
                    'sentiment': 'NEUTRAL', 'cci_value': None, 'stochastic_k': None,
                    'current_price': round(float(df['Close'].iloc[-1]), 2), 'weekly_change_pct': 0,
                })
                continue

            cci = _calculate_cci(weekly, length=20)
            stoch_k, stoch_d = _calculate_stochastic(weekly)
            rsi = _calculate_rsi(weekly)
            sma_20 = _calculate_sma(weekly['Close'], 20)
            sma_50 = _calculate_sma(weekly['Close'], 50) if len(weekly) >= 50 else pd.Series(np.nan, index=weekly.index)

            latest_cci = float(cci.iloc[-1]) if not np.isnan(cci.iloc[-1]) else 0.0
            latest_k = float(stoch_k.iloc[-1]) if not np.isnan(stoch_k.iloc[-1]) else 50.0
            latest_d = float(stoch_d.iloc[-1]) if not np.isnan(stoch_d.iloc[-1]) else 50.0
            latest_rsi = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0
            latest_sma20 = float(sma_20.iloc[-1]) if not np.isnan(sma_20.iloc[-1]) else 0.0
            latest_sma50 = float(sma_50.iloc[-1]) if not np.isnan(sma_50.iloc[-1]) else 0.0

            sentiment, confidence, _ = _determine_sentiment(
                latest_cci, latest_k, latest_d, latest_sma20, latest_sma50, latest_rsi
            )

            current_price = float(df['Close'].iloc[-1])
            weekly_change = 0
            if len(weekly) >= 2:
                prev = float(weekly['Close'].iloc[-2])
                if prev:
                    weekly_change = (float(weekly['Close'].iloc[-1]) - prev) / prev * 100

            result['indices'].append({
                'symbol': idx_info['symbol'],
                'name': idx_info['name'],
                'sentiment': sentiment,
                'cci_value': round(latest_cci, 1),
                'stochastic_k': round(latest_k, 1),
                'current_price': round(current_price, 2),
                'weekly_change_pct': round(weekly_change, 1),
            })

            time.sleep(0.2)

        except Exception as e:
            logger.warning(f"Index {idx_info['symbol']} failed: {e}")
            result['indices'].append({
                'symbol': idx_info['symbol'], 'name': idx_info['name'],
                'sentiment': 'NEUTRAL', 'cci_value': None, 'stochastic_k': None,
                'current_price': None, 'weekly_change_pct': 0,
            })

    # ── Inverse ETFs ──
    try:
        changes = []
        for etf_info in INVERSE_ETFS:
            df = _fetch_yfinance_data(etf_info['symbol'], period='1mo', interval='1wk')
            if not df.empty and len(df) >= 2:
                prev = float(df['Close'].iloc[-2])
                curr = float(df['Close'].iloc[-1])
                chg = ((curr - prev) / prev * 100) if prev else 0
                changes.append({
                    'symbol': etf_info['symbol'],
                    'name': etf_info['name'],
                    'weekly_change_pct': round(chg, 1),
                })
            else:
                changes.append({
                    'symbol': etf_info['symbol'],
                    'name': etf_info['name'],
                    'weekly_change_pct': 0,
                })
            time.sleep(0.2)

        avg_change = np.mean([c['weekly_change_pct'] for c in changes])

        # Inverse ETFs going UP = bearish positioning, DOWN = bullish
        if avg_change > 1.0:
            inv_sentiment = 'BEARISH'
            inv_desc = 'Rising inverse ETFs suggest increasing bearish positioning'
        elif avg_change < -1.0:
            inv_sentiment = 'BULLISH'
            inv_desc = 'Falling inverse ETFs suggest low bearish positioning'
        else:
            inv_sentiment = 'NEUTRAL'
            inv_desc = 'Inverse ETF activity near neutral'

        result['inverse_etfs'] = {
            'sentiment': inv_sentiment,
            'description': inv_desc,
            'average_weekly_change_pct': round(float(avg_change), 1),
            'details': changes,
        }
    except Exception as e:
        logger.warning(f"Inverse ETF analysis failed: {e}")
        result['inverse_etfs'] = {
            'sentiment': 'NEUTRAL',
            'description': 'Inverse ETF data unavailable',
            'average_weekly_change_pct': 0,
            'details': [],
        }

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Widget 4: Commodities & Crypto
# ──────────────────────────────────────────────────────────────────────────────

def compute_commodities_crypto():
    """
    Fetch hourly data for Gold, Silver, Ethereum, Bitcoin.
    Uses CCI (all periods) + TLEV (hourly timeframe) as indicators.
    """
    import time
    assets = []

    for asset_info in COMMODITY_CRYPTO_ASSETS:
        try:
            df = _fetch_yfinance_data(asset_info['symbol'], period='5d', interval='1h')
            if df.empty:
                assets.append({
                    'symbol': asset_info['symbol'], 'name': asset_info['name'],
                    'current_price': None, 'change_24h_pct': 0, 'change_7d_pct': 0,
                    'tlev_signal': 'neutral', 'tlev_value': 0, 'cci_value': None,
                    'hourly_chart_data': [],
                })
                continue

            current_price = float(df['Close'].iloc[-1])

            # 24h change
            bars_24h = min(24, len(df) - 1)
            if bars_24h > 0:
                price_24h_ago = float(df['Close'].iloc[-(bars_24h + 1)])
                change_24h = ((current_price - price_24h_ago) / price_24h_ago * 100) if price_24h_ago else 0
            else:
                change_24h = 0

            # 7d change (use all available data as proxy, max 5 trading days)
            price_start = float(df['Close'].iloc[0])
            change_7d = ((current_price - price_start) / price_start * 100) if price_start else 0

            # TLEV on hourly
            tlev = calculate_tlev(df)
            tlev_value = float(tlev.iloc[-1]) if not np.isnan(tlev.iloc[-1]) else 0.0
            tlev_prev = float(tlev.iloc[-2]) if len(tlev) >= 2 and not np.isnan(tlev.iloc[-2]) else 0.0

            if tlev_value > 0 and tlev_value > tlev_prev:
                tlev_signal = 'bullish'
            elif tlev_value < 0 and tlev_value < tlev_prev:
                tlev_signal = 'bearish'
            else:
                tlev_signal = 'neutral'

            # CCI on hourly
            cci = _calculate_cci(df, length=20)
            cci_value = float(cci.iloc[-1]) if not np.isnan(cci.iloc[-1]) else None

            # Hourly chart data (last 72 bars)
            chart_df = df.tail(72)
            chart_data = []
            for _, row in chart_df.iterrows():
                ts = row['date']
                if hasattr(ts, 'isoformat'):
                    ts_str = ts.isoformat()
                else:
                    ts_str = str(ts)
                chart_data.append({
                    'timestamp': ts_str,
                    'open': round(float(row['Open']), 2),
                    'high': round(float(row['High']), 2),
                    'low': round(float(row['Low']), 2),
                    'close': round(float(row['Close']), 2),
                })

            assets.append({
                'symbol': asset_info['symbol'],
                'name': asset_info['name'],
                'current_price': round(current_price, 2),
                'change_24h_pct': round(change_24h, 1),
                'change_7d_pct': round(change_7d, 1),
                'tlev_signal': tlev_signal,
                'tlev_value': round(tlev_value, 4),
                'cci_value': round(cci_value, 1) if cci_value is not None else None,
                'hourly_chart_data': chart_data,
            })

            time.sleep(0.3)

        except Exception as e:
            logger.warning(f"Asset {asset_info['symbol']} failed: {e}")
            assets.append({
                'symbol': asset_info['symbol'], 'name': asset_info['name'],
                'current_price': None, 'change_24h_pct': 0, 'change_7d_pct': 0,
                'tlev_signal': 'neutral', 'tlev_value': 0, 'cci_value': None,
                'hourly_chart_data': [],
            })

    return {
        'assets': assets,
        'last_updated': datetime.now().isoformat(),
    }
