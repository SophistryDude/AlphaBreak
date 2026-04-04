"""
Trendline Service
=================
Auto-detected trendlines with regime-aware confidence scoring.

Algorithm:
1. Detect pivot highs/lows using configurable lookback window
2. Fit trendlines through pivot combinations (minimum 2 touches)
3. Score each line: touches, recency, volume at touches, slope consistency
4. Classify market regime: BULL, BEAR, RANGE, HIGH_VOL
5. Match against historical analogs in similar regimes
6. Return scored, ranked trendlines with projection data

Used by:
- flask_app/app/routes/analyze.py  (GET /api/analyze/<ticker>/trendlines)
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from itertools import combinations

logger = logging.getLogger(__name__)


def detect_trendlines(ticker: str, period: str = '6mo', interval: str = '1d',
                      db_manager=None) -> Dict:
    """
    Detect and score trendlines for a ticker.

    Returns:
        {
            ticker, period, interval, regime, regime_confidence,
            trendlines: [{type, start, end, slope, touches, confidence,
                          analog_score, color, projected_price, ...}],
            support_levels: [...],
            resistance_levels: [...],
        }
    """
    import yfinance as yf

    stock = yf.Ticker(ticker)

    # Fetch enough history for analog matching
    # Use a longer period for regime detection
    PERIOD_MAP = {
        '1mo': ('3mo', '1d'),
        '3mo': ('6mo', '1d'),
        '6mo': ('1y', '1d'),
        '1y': ('2y', '1d'),
    }
    fetch_period, fetch_interval = PERIOD_MAP.get(period, ('1y', interval))

    hist = stock.history(period=fetch_period, interval=fetch_interval)
    if hist.empty or len(hist) < 20:
        return {'ticker': ticker, 'error': 'Insufficient data', 'trendlines': []}

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

    # ── Step 1: Detect pivots ─────────────────────────────────────────────
    window = max(3, len(df) // 20)  # Adaptive window
    pivot_highs = _detect_pivot_highs(df, window)
    pivot_lows = _detect_pivot_lows(df, window)

    # ── Step 2: Classify regime ───────────────────────────────────────────
    regime, regime_confidence = _classify_regime(df)

    # ── Step 3: Fit trendlines ────────────────────────────────────────────
    resistance_lines = _fit_trendlines(df, pivot_highs, 'resistance')
    support_lines = _fit_trendlines(df, pivot_lows, 'support')

    # ── Step 4: Score each trendline ──────────────────────────────────────
    all_lines = []
    for line in resistance_lines + support_lines:
        scored = _score_trendline(line, df, regime)
        if scored['confidence'] >= 30:  # Filter low-confidence noise
            all_lines.append(scored)

    # ── Step 5: Historical analog matching ────────────────────────────────
    for line in all_lines:
        line['analog_score'] = _compute_analog_score(line, df, regime, db_manager)

    # ── Step 6: Sort by confidence ────────────────────────────────────────
    all_lines.sort(key=lambda x: x['confidence'], reverse=True)

    # ── Step 7: Compute projections ───────────────────────────────────────
    for line in all_lines:
        _add_projection(line, df)

    # ── Step 8: Compute horizontal support/resistance levels ──────────────
    support_levels = _compute_horizontal_levels(pivot_lows, df, 'support')
    resistance_levels = _compute_horizontal_levels(pivot_highs, df, 'resistance')

    # Assign colors based on confidence
    for line in all_lines:
        line['color'] = _confidence_to_color(line['confidence'], line['type'])

    return {
        'ticker': ticker,
        'period': period,
        'interval': interval,
        'regime': regime,
        'regime_confidence': regime_confidence,
        'current_price': float(df['close'].iloc[-1]),
        'trendlines': all_lines[:10],  # Top 10
        'support_levels': support_levels[:5],
        'resistance_levels': resistance_levels[:5],
        'pivot_highs': [{'index': int(i), 'price': float(df['high'].iloc[i]),
                         'timestamp': df['timestamp'].iloc[i].isoformat()
                         if hasattr(df['timestamp'].iloc[i], 'isoformat')
                         else str(df['timestamp'].iloc[i])}
                        for i in pivot_highs],
        'pivot_lows': [{'index': int(i), 'price': float(df['low'].iloc[i]),
                        'timestamp': df['timestamp'].iloc[i].isoformat()
                        if hasattr(df['timestamp'].iloc[i], 'isoformat')
                        else str(df['timestamp'].iloc[i])}
                       for i in pivot_lows],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Pivot Detection
# ──────────────────────────────────────────────────────────────────────────────

def _detect_pivot_highs(df: pd.DataFrame, window: int) -> List[int]:
    """Detect local maxima in high prices."""
    highs = df['high'].values
    pivots = []
    for i in range(window, len(highs) - window):
        if all(highs[i] >= highs[i - j] for j in range(1, window + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, window + 1)):
            pivots.append(i)
    return pivots


def _detect_pivot_lows(df: pd.DataFrame, window: int) -> List[int]:
    """Detect local minima in low prices."""
    lows = df['low'].values
    pivots = []
    for i in range(window, len(lows) - window):
        if all(lows[i] <= lows[i - j] for j in range(1, window + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, window + 1)):
            pivots.append(i)
    return pivots


# ──────────────────────────────────────────────────────────────────────────────
# Regime Classification
# ──────────────────────────────────────────────────────────────────────────────

def _classify_regime(df: pd.DataFrame) -> Tuple[str, float]:
    """
    Classify market regime using price action + volatility.

    Returns (regime, confidence):
        regime: BULL, BEAR, RANGE, HIGH_VOL
        confidence: 0-100
    """
    closes = df['close'].values
    n = len(closes)

    if n < 20:
        return 'RANGE', 50.0

    # Recent vs older price comparison
    recent_half = closes[n // 2:]
    older_half = closes[:n // 2]
    trend_pct = (np.mean(recent_half) / np.mean(older_half) - 1) * 100

    # Slope of linear regression on closes
    x = np.arange(n)
    slope = np.polyfit(x, closes, 1)[0]
    slope_pct = (slope * n) / closes[0] * 100  # Total % change implied by slope

    # Volatility (annualized)
    returns = np.diff(closes) / closes[:-1]
    vol = np.std(returns) * np.sqrt(252) * 100

    # ADX-like trend strength
    highs = df['high'].values
    lows = df['low'].values
    atr = np.mean(highs[-20:] - lows[-20:])
    atr_pct = (atr / closes[-1]) * 100

    # SMA crossover
    sma20 = np.mean(closes[-20:])
    sma50 = np.mean(closes[-50:]) if n >= 50 else sma20

    # Decision logic
    if vol > 35:
        return 'HIGH_VOL', min(95, 50 + vol)

    if slope_pct > 8 and sma20 > sma50:
        confidence = min(95, 50 + abs(slope_pct) * 2)
        return 'BULL', confidence

    if slope_pct < -8 and sma20 < sma50:
        confidence = min(95, 50 + abs(slope_pct) * 2)
        return 'BEAR', confidence

    if abs(slope_pct) < 5 and atr_pct < 3:
        return 'RANGE', min(90, 60 + (5 - abs(slope_pct)) * 6)

    # Weak trend
    if slope_pct > 0:
        return 'BULL', max(40, 50 + slope_pct)
    else:
        return 'BEAR', max(40, 50 + abs(slope_pct))


# ──────────────────────────────────────────────────────────────────────────────
# Trendline Fitting
# ──────────────────────────────────────────────────────────────────────────────

def _fit_trendlines(df: pd.DataFrame, pivots: List[int],
                    line_type: str) -> List[Dict]:
    """
    Fit trendlines through combinations of pivot points.
    Returns list of trendline dicts with start/end indices, slope, touches.
    """
    if len(pivots) < 2:
        return []

    prices = df['high'].values if line_type == 'resistance' else df['low'].values
    n = len(df)
    lines = []

    # Try all pairs of pivots (limit to most recent 8 for performance)
    recent_pivots = pivots[-8:]

    for i, j in combinations(range(len(recent_pivots)), 2):
        idx1, idx2 = recent_pivots[i], recent_pivots[j]
        if idx2 - idx1 < 3:  # Too close together
            continue

        p1 = prices[idx1]
        p2 = prices[idx2]
        slope = (p2 - p1) / (idx2 - idx1)

        # Count how many other pivots "touch" this line (within tolerance)
        touches = []
        current_price = df['close'].iloc[-1]
        tolerance = current_price * 0.015  # 1.5% tolerance

        for k in range(n):
            expected = p1 + slope * (k - idx1)
            actual = prices[k]
            if abs(actual - expected) <= tolerance:
                touches.append(k)

        if len(touches) >= 2:
            # Calculate where the line is at the last bar
            end_price = p1 + slope * (n - 1 - idx1)

            lines.append({
                'type': line_type,
                'start_index': int(idx1),
                'end_index': int(idx2),
                'start_price': float(p1),
                'end_price': float(p2),
                'current_line_price': float(end_price),
                'slope': float(slope),
                'slope_per_bar': float(slope),
                'touches': [int(t) for t in touches],
                'touch_count': len(touches),
                'start_timestamp': _ts(df, idx1),
                'end_timestamp': _ts(df, idx2),
            })

    # Deduplicate similar lines (within 2% slope and 3% price)
    return _deduplicate_lines(lines)


def _deduplicate_lines(lines: List[Dict]) -> List[Dict]:
    """Remove near-duplicate trendlines, keeping the one with more touches."""
    if not lines:
        return []

    lines.sort(key=lambda x: x['touch_count'], reverse=True)
    unique = []

    for line in lines:
        is_dup = False
        for existing in unique:
            slope_sim = abs(line['slope'] - existing['slope']) / (abs(existing['slope']) + 1e-10) < 0.20
            price_sim = abs(line['start_price'] - existing['start_price']) / existing['start_price'] < 0.03
            if slope_sim and price_sim:
                is_dup = True
                break
        if not is_dup:
            unique.append(line)

    return unique


# ──────────────────────────────────────────────────────────────────────────────
# Scoring
# ──────────────────────────────────────────────���───────────────────────────────

def _score_trendline(line: Dict, df: pd.DataFrame, regime: str) -> Dict:
    """
    Score a trendline 0-100 based on multiple factors.

    Factors:
    - Touch count (more touches = more valid)
    - Recency of touches (recent touches matter more)
    - Volume at touch points (high volume = stronger)
    - Proximity to current price (closer = more relevant)
    - Slope consistency with regime (bullish support in bull market = higher)
    - Span (longer trendlines = more significant)
    """
    n = len(df)
    current_price = float(df['close'].iloc[-1])
    scores = {}

    # 1. Touch count: 2=base, 3=good, 4+=excellent (0-25 points)
    tc = line['touch_count']
    scores['touches'] = min(25, (tc - 1) * 8)

    # 2. Recency: are touches near the end of the data? (0-20 points)
    touches = line['touches']
    if touches:
        most_recent = max(touches)
        recency_pct = most_recent / n
        scores['recency'] = recency_pct * 20
    else:
        scores['recency'] = 0

    # 3. Volume at touches (0-15 points)
    volumes = df['volume'].values
    avg_vol = np.mean(volumes)
    if avg_vol > 0 and touches:
        touch_vols = [volumes[t] for t in touches if t < len(volumes)]
        vol_ratio = np.mean(touch_vols) / avg_vol if touch_vols else 1.0
        scores['volume'] = min(15, vol_ratio * 7.5)
    else:
        scores['volume'] = 7.5

    # 4. Proximity to current price (0-20 points)
    line_price = line['current_line_price']
    distance_pct = abs(current_price - line_price) / current_price * 100
    if distance_pct < 1:
        scores['proximity'] = 20  # Very close — about to test
    elif distance_pct < 3:
        scores['proximity'] = 15
    elif distance_pct < 5:
        scores['proximity'] = 10
    elif distance_pct < 10:
        scores['proximity'] = 5
    else:
        scores['proximity'] = 0

    # 5. Regime alignment (0-10 points)
    is_support = line['type'] == 'support'
    is_rising = line['slope'] > 0

    if regime == 'BULL' and is_support and is_rising:
        scores['regime'] = 10  # Rising support in bull = strong
    elif regime == 'BEAR' and not is_support and not is_rising:
        scores['regime'] = 10  # Falling resistance in bear = strong
    elif regime == 'RANGE':
        scores['regime'] = 8 if abs(line['slope']) < 0.1 else 4
    else:
        scores['regime'] = 5

    # 6. Span (0-10 points)
    span = line['end_index'] - line['start_index']
    span_pct = span / n
    scores['span'] = min(10, span_pct * 20)

    total = sum(scores.values())
    line['confidence'] = round(min(100, total), 1)
    line['score_breakdown'] = {k: round(v, 1) for k, v in scores.items()}

    return line


# ──────────────────────────────────────────────────────────────────────────────
# Historical Analog Matching
# ──────────────────────────────────────────────────────────────────────────────

def _compute_analog_score(line: Dict, df: pd.DataFrame, regime: str,
                          db_manager=None) -> float:
    """
    Score how well this trendline setup matches historical analogs.

    Uses price pattern similarity in similar regime conditions.
    Returns 0-100 score.
    """
    closes = df['close'].values
    n = len(closes)

    if n < 40:
        return 50.0  # Not enough data for analogs

    # Extract the recent pattern (last 20 bars normalized)
    recent = closes[-20:]
    recent_norm = (recent - recent[0]) / recent[0] * 100  # % change from start

    # Slide a 20-bar window across history and find similar patterns
    match_scores = []
    for start in range(0, n - 40, 5):  # Step by 5 for performance
        window = closes[start:start + 20]
        window_norm = (window - window[0]) / window[0] * 100

        # Cosine similarity
        dot = np.dot(recent_norm, window_norm)
        norm_a = np.linalg.norm(recent_norm)
        norm_b = np.linalg.norm(window_norm)
        if norm_a > 0 and norm_b > 0:
            similarity = dot / (norm_a * norm_b)
        else:
            similarity = 0

        # What happened after this historical window?
        if start + 30 < n:
            future_return = (closes[start + 30] - closes[start + 20]) / closes[start + 20] * 100
        else:
            future_return = 0

        if similarity > 0.7:  # Only count strong matches
            match_scores.append({
                'similarity': similarity,
                'future_return': future_return,
                'start': start,
            })

    if not match_scores:
        return 50.0

    # Score based on how many analogs agree with the trendline direction
    is_support = line['type'] == 'support'
    agreeing = 0
    total = len(match_scores)

    for m in match_scores:
        if is_support and m['future_return'] > 0:
            agreeing += 1  # Support held, price went up
        elif not is_support and m['future_return'] < 0:
            agreeing += 1  # Resistance held, price went down

    agreement_pct = (agreeing / total * 100) if total > 0 else 50
    avg_similarity = np.mean([m['similarity'] for m in match_scores]) * 100

    # Weighted: 60% agreement, 40% similarity strength
    score = agreement_pct * 0.6 + avg_similarity * 0.4
    return round(min(100, max(0, score)), 1)


# ──────────────────────────────────────────────────────────────────────────────
# Projection
# ──────────────────────────────────────────────────────────────────────────────

def _add_projection(line: Dict, df: pd.DataFrame):
    """Add forward projection of where the trendline will be in 5/10/20 bars."""
    n = len(df)
    start_idx = line['start_index']
    p1 = line['start_price']
    slope = line['slope']

    projections = {}
    for bars_ahead in [5, 10, 20]:
        future_idx = n - 1 + bars_ahead
        projected = p1 + slope * (future_idx - start_idx)
        projections[f'bars_{bars_ahead}'] = round(float(projected), 4)

    line['projections'] = projections

    # Distance from current price to trendline
    current = float(df['close'].iloc[-1])
    line_at_current = line['current_line_price']
    line['distance_pct'] = round((current - line_at_current) / current * 100, 2)
    line['distance_abs'] = round(current - line_at_current, 2)


# ──────────────────────────────────────────────────────────────────────────────
# Horizontal Support/Resistance Levels
# ──────────────────────────────────────────────────────────────────────────────

def _compute_horizontal_levels(pivots: List[int], df: pd.DataFrame,
                               level_type: str) -> List[Dict]:
    """Cluster pivot prices into horizontal support/resistance zones."""
    if not pivots:
        return []

    prices = df['high'].values if level_type == 'resistance' else df['low'].values
    pivot_prices = [float(prices[i]) for i in pivots]
    current = float(df['close'].iloc[-1])

    # Cluster nearby prices (within 2%)
    pivot_prices.sort()
    clusters = []
    current_cluster = [pivot_prices[0]]

    for p in pivot_prices[1:]:
        if abs(p - current_cluster[-1]) / current_cluster[-1] < 0.02:
            current_cluster.append(p)
        else:
            clusters.append(current_cluster)
            current_cluster = [p]
    clusters.append(current_cluster)

    levels = []
    for cluster in clusters:
        avg_price = np.mean(cluster)
        strength = len(cluster)  # More touches = stronger
        distance_pct = (current - avg_price) / current * 100

        levels.append({
            'price': round(avg_price, 2),
            'strength': strength,
            'touches': len(cluster),
            'distance_pct': round(distance_pct, 2),
            'type': level_type,
        })

    # Sort by strength (most touches first)
    levels.sort(key=lambda x: x['strength'], reverse=True)
    return levels


# ──────────────────────────────────────────────────────────────────────────────
# Color & Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _confidence_to_color(confidence: float, line_type: str) -> Dict:
    """
    Map confidence to RGBA color with gradient.
    Support = green spectrum, Resistance = red spectrum.
    Higher confidence = more opaque + more saturated.
    """
    alpha = max(0.3, min(0.95, confidence / 100))

    if line_type == 'support':
        # Green spectrum: low confidence = muted, high = bright
        if confidence >= 80:
            return {'r': 38, 'g': 166, 'b': 154, 'a': alpha, 'hex': '#26a69a'}
        elif confidence >= 60:
            return {'r': 76, 'g': 175, 'b': 160, 'a': alpha, 'hex': '#4cafa0'}
        else:
            return {'r': 120, 'g': 160, 'b': 155, 'a': alpha * 0.7, 'hex': '#78a09b'}
    else:
        # Red spectrum
        if confidence >= 80:
            return {'r': 239, 'g': 83, 'b': 80, 'a': alpha, 'hex': '#ef5350'}
        elif confidence >= 60:
            return {'r': 229, 'g': 115, 'b': 115, 'a': alpha, 'hex': '#e57373'}
        else:
            return {'r': 200, 'g': 140, 'b': 140, 'a': alpha * 0.7, 'hex': '#c88c8c'}


def _ts(df: pd.DataFrame, idx: int) -> str:
    """Get ISO timestamp string for an index."""
    ts = df['timestamp'].iloc[idx]
    return ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
