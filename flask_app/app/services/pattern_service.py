"""
Pattern Service
================
Candlestick pattern recognition + seasonality analysis.

Detects common candlestick patterns and scores them with probability
based on historical follow-through in the current regime.

Also computes monthly/weekly seasonality heatmap data.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List

logger = logging.getLogger(__name__)


def detect_patterns(ticker: str, period: str = '6mo') -> Dict:
    """Detect candlestick patterns and compute seasonality."""
    import yfinance as yf

    stock = yf.Ticker(ticker)
    hist = stock.history(period=period, interval='1d')
    if hist.empty or len(hist) < 10:
        return {'ticker': ticker, 'patterns': [], 'seasonality': {}}

    hist = hist.reset_index()
    ts_col = 'Date' if 'Date' in hist.columns else 'Datetime' if 'Datetime' in hist.columns else hist.columns[0]

    df = pd.DataFrame({
        'timestamp': hist[ts_col],
        'open': hist['Open'].astype(float),
        'high': hist['High'].astype(float),
        'low': hist['Low'].astype(float),
        'close': hist['Close'].astype(float),
        'volume': hist['Volume'].astype(float),
    })

    patterns = _detect_candlestick_patterns(df)
    seasonality = _compute_seasonality(ticker)

    return {
        'ticker': ticker,
        'patterns': patterns,
        'seasonality': seasonality,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Candlestick Pattern Detection
# ──────────────────────────────────────────────────────────────────────────────

def _detect_candlestick_patterns(df: pd.DataFrame) -> List[Dict]:
    """
    Detect candlestick patterns in the last 30 bars.
    Returns list of {index, timestamp, pattern, direction, probability, description}.
    """
    patterns = []
    n = len(df)
    start = max(2, n - 30)  # Only scan last 30 bars

    o = df['open'].values
    h = df['high'].values
    l = df['low'].values
    c = df['close'].values
    v = df['volume'].values

    avg_vol = np.mean(v[-30:]) if n >= 30 else np.mean(v)

    for i in range(start, n):
        body = abs(c[i] - o[i])
        full_range = h[i] - l[i]
        if full_range == 0:
            continue

        body_pct = body / full_range
        upper_wick = h[i] - max(o[i], c[i])
        lower_wick = min(o[i], c[i]) - l[i]
        is_bullish = c[i] > o[i]
        vol_ratio = v[i] / avg_vol if avg_vol > 0 else 1.0

        ts = df['timestamp'].iloc[i]
        ts_str = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)

        # ── Doji ──────────────────────────────────────────────────
        if body_pct < 0.1 and full_range > 0:
            patterns.append({
                'index': int(i),
                'timestamp': ts_str,
                'pattern': 'Doji',
                'direction': 'neutral',
                'probability': _score_pattern(df, i, 'neutral', vol_ratio),
                'description': 'Indecision candle. Open and close are nearly equal. Often signals a potential reversal, especially after a strong trend.',
            })

        # ── Hammer / Inverted Hammer ──────────────────────────��───
        if lower_wick >= body * 2 and upper_wick < body * 0.5 and body_pct > 0.1:
            # Check if at a low point (potential reversal)
            if i >= 3 and c[i] < np.mean(c[i-3:i]):
                patterns.append({
                    'index': int(i),
                    'timestamp': ts_str,
                    'pattern': 'Hammer',
                    'direction': 'bullish',
                    'probability': _score_pattern(df, i, 'bullish', vol_ratio),
                    'description': 'Long lower wick, small body at top. Sellers pushed price down but buyers recovered. Bullish reversal signal, especially after a downtrend.',
                })

        if upper_wick >= body * 2 and lower_wick < body * 0.5 and body_pct > 0.1:
            if i >= 3 and c[i] > np.mean(c[i-3:i]):
                patterns.append({
                    'index': int(i),
                    'timestamp': ts_str,
                    'pattern': 'Shooting Star',
                    'direction': 'bearish',
                    'probability': _score_pattern(df, i, 'bearish', vol_ratio),
                    'description': 'Long upper wick, small body at bottom. Buyers pushed price up but sellers rejected it. Bearish reversal signal after an uptrend.',
                })

        # ── Engulfing ─────────────────────────────────────────────
        if i >= 1:
            prev_body = abs(c[i-1] - o[i-1])
            prev_bullish = c[i-1] > o[i-1]

            # Bullish engulfing
            if is_bullish and not prev_bullish and body > prev_body * 1.1:
                if o[i] <= c[i-1] and c[i] >= o[i-1]:
                    patterns.append({
                        'index': int(i),
                        'timestamp': ts_str,
                        'pattern': 'Bullish Engulfing',
                        'direction': 'bullish',
                        'probability': _score_pattern(df, i, 'bullish', vol_ratio),
                        'description': 'Large green candle completely engulfs previous red candle. Strong bullish reversal signal with high reliability.',
                    })

            # Bearish engulfing
            if not is_bullish and prev_bullish and body > prev_body * 1.1:
                if o[i] >= c[i-1] and c[i] <= o[i-1]:
                    patterns.append({
                        'index': int(i),
                        'timestamp': ts_str,
                        'pattern': 'Bearish Engulfing',
                        'direction': 'bearish',
                        'probability': _score_pattern(df, i, 'bearish', vol_ratio),
                        'description': 'Large red candle completely engulfs previous green candle. Strong bearish reversal signal.',
                    })

        # ── Morning/Evening Star ──────────────────────────────────
        if i >= 2:
            first_body = abs(c[i-2] - o[i-2])
            middle_body = abs(c[i-1] - o[i-1])
            first_bearish = c[i-2] < o[i-2]

            # Morning star (bullish)
            if first_bearish and middle_body < first_body * 0.3 and is_bullish and body > first_body * 0.5:
                patterns.append({
                    'index': int(i),
                    'timestamp': ts_str,
                    'pattern': 'Morning Star',
                    'direction': 'bullish',
                    'probability': _score_pattern(df, i, 'bullish', vol_ratio),
                    'description': '3-candle reversal: large red, small indecision, large green. One of the most reliable bullish reversal patterns.',
                })

            # Evening star (bearish)
            first_bullish = c[i-2] > o[i-2]
            if first_bullish and middle_body < first_body * 0.3 and not is_bullish and body > first_body * 0.5:
                patterns.append({
                    'index': int(i),
                    'timestamp': ts_str,
                    'pattern': 'Evening Star',
                    'direction': 'bearish',
                    'probability': _score_pattern(df, i, 'bearish', vol_ratio),
                    'description': '3-candle reversal: large green, small indecision, large red. One of the most reliable bearish reversal patterns.',
                })

        # ── Three White Soldiers / Three Black Crows ──────────────
        if i >= 2:
            three_up = all(c[i-j] > o[i-j] for j in range(3))
            three_down = all(c[i-j] < o[i-j] for j in range(3))
            ascending = c[i] > c[i-1] > c[i-2]
            descending = c[i] < c[i-1] < c[i-2]

            if three_up and ascending:
                patterns.append({
                    'index': int(i),
                    'timestamp': ts_str,
                    'pattern': 'Three White Soldiers',
                    'direction': 'bullish',
                    'probability': _score_pattern(df, i, 'bullish', vol_ratio),
                    'description': 'Three consecutive large green candles with higher closes. Very strong bullish continuation signal.',
                })

            if three_down and descending:
                patterns.append({
                    'index': int(i),
                    'timestamp': ts_str,
                    'pattern': 'Three Black Crows',
                    'direction': 'bearish',
                    'probability': _score_pattern(df, i, 'bearish', vol_ratio),
                    'description': 'Three consecutive large red candles with lower closes. Very strong bearish continuation signal.',
                })

    # Deduplicate — keep highest probability per index
    seen = {}
    for p in patterns:
        key = p['index']
        if key not in seen or p['probability'] > seen[key]['probability']:
            seen[key] = p

    result = sorted(seen.values(), key=lambda x: x['index'], reverse=True)
    return result[:15]  # Max 15 most recent


def _score_pattern(df: pd.DataFrame, idx: int, direction: str,
                   vol_ratio: float) -> float:
    """
    Score a pattern's probability (0-100) based on:
    - Historical follow-through at similar setups
    - Volume confirmation
    - Trend context
    """
    c = df['close'].values
    n = len(c)

    base = 55.0  # Baseline probability

    # Volume boost: high volume = more reliable
    if vol_ratio > 1.5:
        base += 10
    elif vol_ratio > 1.2:
        base += 5
    elif vol_ratio < 0.7:
        base -= 5

    # Trend context: reversal patterns at extremes are stronger
    if idx >= 10:
        recent_trend = (c[idx] - c[idx - 10]) / c[idx - 10] * 100
        if direction == 'bullish' and recent_trend < -5:
            base += 8  # Bullish at bottom of downtrend
        elif direction == 'bearish' and recent_trend > 5:
            base += 8  # Bearish at top of uptrend
        elif direction == 'bullish' and recent_trend > 5:
            base -= 5  # Bullish in already-uptrend (less meaningful)
        elif direction == 'bearish' and recent_trend < -5:
            base -= 5  # Bearish in already-downtrend

    # Historical validation: check if similar patterns led to expected moves
    matches = 0
    agrees = 0
    for j in range(10, n - 5):
        if j == idx:
            continue
        # Simple pattern matching: similar body/wick ratio at this point
        body_j = abs(c[j] - df['open'].values[j])
        body_i = abs(c[idx] - df['open'].values[idx])
        if body_i > 0 and abs(body_j - body_i) / body_i < 0.3:
            matches += 1
            future = c[min(j + 5, n - 1)] - c[j]
            if direction == 'bullish' and future > 0:
                agrees += 1
            elif direction == 'bearish' and future < 0:
                agrees += 1
            elif direction == 'neutral':
                agrees += 1

    if matches >= 5:
        agreement = agrees / matches
        base = base * 0.6 + agreement * 100 * 0.4

    return round(min(95, max(30, base)), 1)


# ──────────────────────────────────────────────────────────────────────────────
# Seasonality
# ──────────────────────────────────────────────────────────────────────────────

def _compute_seasonality(ticker: str) -> Dict:
    """
    Compute monthly return seasonality over 5 years.
    Returns {monthly: [{month, avg_return, win_rate, count}]}.
    """
    import yfinance as yf

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='5y', interval='1mo')
        if hist.empty or len(hist) < 12:
            return {}

        hist = hist.reset_index()
        ts_col = 'Date' if 'Date' in hist.columns else 'Datetime' if 'Datetime' in hist.columns else hist.columns[0]

        hist['month'] = pd.to_datetime(hist[ts_col]).dt.month
        hist['return'] = hist['Close'].pct_change() * 100

        monthly = []
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        for m in range(1, 13):
            month_data = hist[hist['month'] == m]['return'].dropna()
            if len(month_data) == 0:
                monthly.append({
                    'month': m,
                    'name': month_names[m - 1],
                    'avg_return': 0,
                    'win_rate': 0,
                    'count': 0,
                })
                continue

            avg_ret = float(month_data.mean())
            win_rate = float((month_data > 0).sum() / len(month_data) * 100)

            monthly.append({
                'month': m,
                'name': month_names[m - 1],
                'avg_return': round(avg_ret, 2),
                'win_rate': round(win_rate, 1),
                'count': len(month_data),
            })

        return {'monthly': monthly}

    except Exception as e:
        logger.debug(f"Seasonality failed for {ticker}: {e}")
        return {}
