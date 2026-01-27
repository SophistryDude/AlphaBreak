"""
META-LEARNING MODEL FOR ADAPTIVE INDICATOR SELECTION

This module creates a meta-learning system that predicts which technical indicators
will be accurate based on current market conditions. The goal is to adaptively
weight indicators before using them in the main time-series prediction model.

Updated to use PostgreSQL/TimescaleDB data sources instead of data_fetcher.

Architecture:
    Stage 1 (This file): Meta-Learning → Which indicators are reliable now?
    Stage 2 (Future): Time-Series Model → Predict stock movements using reliable indicators

The model uses REGRESSION (not classification) to predict continuous accuracy scores
(0.0 to 1.0) for each indicator, preserving full information and natural groupings
that emerge from different market regimes.
"""

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

# Import from src modules
from .trend_analysis import trend_break, trend_line_break_accuracy
from .technical_indicators import TechnicalIndicators, INDICATOR_FUNCTIONS

# ════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ════════════════════════════════════════════════════════════════════════════

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5433')),
    'database': os.getenv('DB_NAME', 'trading_data'),
    'user': os.getenv('DB_USER', 'trading'),
    'password': os.getenv('DB_PASSWORD', 'trading123')
}

def get_db_connection():
    """Get a database connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_stock_data_from_db(
    ticker: str,
    start_date: str,
    end_date: str,
    timeframe: str = 'daily'
) -> pd.DataFrame:
    """
    Fetch stock data from PostgreSQL database.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date 'YYYY-MM-DD'
        end_date: End date 'YYYY-MM-DD'
        timeframe: 'daily', '1hour', '5min', or '1min'

    Returns:
        DataFrame with OHLCV data
    """
    conn = get_db_connection()

    if timeframe == 'daily':
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM stock_prices
            WHERE ticker = %s
            AND timestamp >= %s
            AND timestamp <= %s
            ORDER BY timestamp
        """
    else:
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM stock_prices_intraday
            WHERE ticker = %s
            AND interval_type = %s
            AND timestamp >= %s
            AND timestamp <= %s
            ORDER BY timestamp
        """

    try:
        if timeframe == 'daily':
            df = pd.read_sql(query, conn, params=(ticker, start_date, end_date))
        else:
            df = pd.read_sql(query, conn, params=(ticker, timeframe, start_date, end_date))

        # Rename columns to standard format
        df.columns = ['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)

        return df
    finally:
        conn.close()


def get_trend_breaks_from_db(
    ticker: Optional[str] = None,
    timeframe: str = 'daily',
    limit: int = None,
    start_date: str = None,
    end_date: str = None
) -> pd.DataFrame:
    """
    Fetch trend breaks from the database.

    Args:
        ticker: Optional ticker filter
        timeframe: 'daily', '1hour', '5min', or '1min'
        limit: Maximum number of records to return
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        DataFrame with trend break data
    """
    conn = get_db_connection()

    query = """
        SELECT ticker, timestamp, break_type, direction_before, direction_after,
               price_at_break, magnitude, price_change_pct, volume_ratio,
               periods_since_last_break, trend_strength
        FROM trend_breaks
        WHERE timeframe = %s
    """
    params = [timeframe]

    if ticker:
        query += " AND ticker = %s"
        params.append(ticker)

    if start_date:
        query += " AND timestamp >= %s"
        params.append(start_date)

    if end_date:
        query += " AND timestamp <= %s"
        params.append(end_date)

    query += " ORDER BY timestamp"

    if limit:
        query += f" LIMIT {limit}"

    try:
        df = pd.read_sql(query, conn, params=params)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    finally:
        conn.close()


def get_trend_ranges_from_db(
    ticker: Optional[str] = None,
    timeframe: str = 'daily',
    limit: int = None
) -> pd.DataFrame:
    """
    Fetch trend ranges from the database.
    """
    conn = get_db_connection()

    query = """
        SELECT ticker, start_timestamp, end_timestamp, trend_direction,
               duration_periods, price_change_pct, avg_volume
        FROM trend_ranges
        WHERE timeframe = %s
    """
    params = [timeframe]

    if ticker:
        query += " AND ticker = %s"
        params.append(ticker)

    query += " ORDER BY start_timestamp"

    if limit:
        query += f" LIMIT {limit}"

    try:
        df = pd.read_sql(query, conn, params=params)
        return df
    finally:
        conn.close()


def get_available_tickers(timeframe: str = 'daily') -> List[str]:
    """Get list of tickers with trend breaks."""
    conn = get_db_connection()

    query = """
        SELECT DISTINCT ticker
        FROM trend_breaks
        WHERE timeframe = %s
        ORDER BY ticker
    """

    try:
        df = pd.read_sql(query, conn, params=(timeframe,))
        return df['ticker'].tolist()
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════════
# INDICATOR DESCRIPTIONS
# ════════════════════════════════════════════════════════════════════════════

INDICATOR_DESCRIPTIONS = {
    'RSI': 'Relative Strength Index - momentum oscillator measuring speed/change of price movements (overbought >70, oversold <30)',
    'MACD': 'Moving Average Convergence Divergence - trend-following momentum indicator showing relationship between two EMAs',
    'MACD_signal': 'MACD Signal Line - 9-period EMA of MACD, used for crossover signals',
    'MACD_hist': 'MACD Histogram - difference between MACD and Signal line, shows momentum strength',
    'BB_upper': 'Bollinger Band Upper - 2 std deviations above 20-period SMA, resistance level',
    'BB_middle': 'Bollinger Band Middle - 20-period SMA, baseline trend indicator',
    'BB_lower': 'Bollinger Band Lower - 2 std deviations below 20-period SMA, support level',
    'BB_width': 'Bollinger Band Width - measures volatility as distance between bands',
    'SMA_20': 'Simple Moving Average 20 - average close price over 20 periods, short-term trend',
    'SMA_50': 'Simple Moving Average 50 - average close price over 50 periods, medium-term trend',
    'SMA_200': 'Simple Moving Average 200 - average close price over 200 periods, long-term trend',
    'EMA_12': 'Exponential Moving Average 12 - weighted average favoring recent prices, fast trend',
    'EMA_26': 'Exponential Moving Average 26 - weighted average favoring recent prices, slow trend',
    'ATR': 'Average True Range - measures market volatility using high/low/close range',
    'ADX': 'Average Directional Index - measures trend strength (>25 strong trend, <20 weak/ranging)',
    'CCI': 'Commodity Channel Index - identifies cyclical trends, overbought/oversold levels',
    'MFI': 'Money Flow Index - volume-weighted RSI, measures buying/selling pressure',
    'OBV': 'On Balance Volume - cumulative volume indicator confirming price trends',
    'VWAP': 'Volume Weighted Average Price - average price weighted by volume, institutional benchmark',
    'Stoch_K': 'Stochastic %K - compares close to high-low range over period, momentum oscillator',
    'Stoch_D': 'Stochastic %D - 3-period SMA of %K, generates smoother signals',
    'Williams_R': 'Williams %R - momentum indicator comparing close to high-low range (inverse of Stoch)',
    'ROC': 'Rate of Change - measures percentage change in price over period, momentum indicator',
    'TRIX': 'Triple Exponential Moving Average - trend indicator filtering out noise',
    'Ultimate_Osc': 'Ultimate Oscillator - momentum oscillator using multiple timeframes',
    'DPO': 'Detrended Price Oscillator - removes trend to identify cycles',
    'Aroon_Up': 'Aroon Up - measures time since highest high, identifies uptrend strength',
    'Aroon_Down': 'Aroon Down - measures time since lowest low, identifies downtrend strength',
    'Aroon_Osc': 'Aroon Oscillator - difference between Aroon Up and Down, trend direction',
    'PPO': 'Percentage Price Oscillator - MACD expressed as percentage, normalized momentum',
    'CMF': 'Chaikin Money Flow - measures accumulation/distribution over period',
    'Force_Index': 'Force Index - combines price change and volume for trend strength',
    'Keltner_Upper': 'Keltner Channel Upper - ATR-based band above EMA, dynamic resistance',
    'Keltner_Lower': 'Keltner Channel Lower - ATR-based band below EMA, dynamic support',
    'Donchian_Upper': 'Donchian Channel Upper - highest high over period, breakout level',
    'Donchian_Lower': 'Donchian Channel Lower - lowest low over period, breakdown level',
    'PSAR': 'Parabolic SAR - trailing stop and reversal indicator, identifies trend changes',
    'Ichimoku_Conv': 'Ichimoku Conversion Line (Tenkan-sen) - midpoint of 9-period high/low',
    'Ichimoku_Base': 'Ichimoku Base Line (Kijun-sen) - midpoint of 26-period high/low',
    'Ichimoku_A': 'Ichimoku Span A (Senkou A) - midpoint of conversion and base lines',
    'Ichimoku_B': 'Ichimoku Span B (Senkou B) - midpoint of 52-period high/low',
    'VWMA': 'Volume Weighted Moving Average - MA weighted by volume, confirms price moves',
    'HMA': 'Hull Moving Average - fast MA with reduced lag using weighted calculations',
    'DEMA': 'Double Exponential Moving Average - reduced lag EMA using double smoothing',
    'TEMA': 'Triple Exponential Moving Average - further reduced lag using triple smoothing',
    'Pivot': 'Pivot Point - key support/resistance calculated from prior high/low/close',
    'R1': 'Resistance 1 - first resistance level above pivot',
    'S1': 'Support 1 - first support level below pivot',
    'Fib_0.382': 'Fibonacci 38.2% - key retracement level for pullback support',
    'Fib_0.618': 'Fibonacci 61.8% - golden ratio retracement, major support/resistance',
    'Elder_Bull': 'Elder Ray Bull Power - measures buying pressure relative to EMA',
    'Elder_Bear': 'Elder Ray Bear Power - measures selling pressure relative to EMA',
    'Choppiness': 'Choppiness Index - measures if market is trending or ranging (>61.8 choppy)',
    'Mass_Index': 'Mass Index - identifies trend reversals by measuring range expansion',
    'KST': 'Know Sure Thing - momentum oscillator using multiple ROC timeframes',
    'TSI': 'True Strength Index - double-smoothed momentum showing trend direction',
    'MACD_diff': 'MACD Difference - difference between MACD and Signal, momentum measure',
    # Newly added indicators
    'Keltner': 'Keltner Channels - ATR-based volatility bands showing dynamic support/resistance',
    'Donchian': 'Donchian Channels - breakout indicator using highest high/lowest low over period',
    'AccDist': 'Accumulation/Distribution Line - volume-weighted price momentum, tracks smart money flow',
    'TLEV': 'Traders Lion Enhanced Volume - volume-weighted momentum indicator for trend confirmation',
    'VolPrice': 'Volume at Price - volume-weighted price momentum showing institutional activity zones'
}


# ════════════════════════════════════════════════════════════════════════════
# FEATURE ENGINEERING: MARKET REGIME DETECTION
# ════════════════════════════════════════════════════════════════════════════

def calculate_market_regime_features(data: pd.DataFrame, lookback_window: int = 30) -> Dict[str, float]:
    """
    Calculates market regime features that determine which indicators work best.

    These features capture market conditions like volatility, trend strength,
    and momentum that affect indicator reliability.
    """
    # Get recent data window
    recent = data.tail(lookback_window)

    # Calculate returns
    returns = recent['Close'].pct_change().dropna()

    features = {}

    # 1. Volatility (standard deviation of returns)
    features['volatility'] = returns.std() if len(returns) > 0 else 0

    # 2. Trend Strength (using price momentum)
    ma_short = recent['Close'].rolling(10).mean()
    ma_long = recent['Close'].rolling(20).mean()
    if len(ma_long.dropna()) > 0 and ma_long.iloc[-1] != 0:
        features['trend_strength'] = abs((ma_short.iloc[-1] - ma_long.iloc[-1]) / ma_long.iloc[-1]) * 100
    else:
        features['trend_strength'] = 0

    # 3. Market Regime (trending vs ranging)
    features['market_regime'] = 1 if features['trend_strength'] > 2 else 0

    # 4. Trend Consistency (how many direction changes)
    if len(returns) > 1:
        direction_changes = (returns.shift(1) * returns < 0).sum()
        features['trend_consistency'] = 1 - (direction_changes / len(returns))
    else:
        features['trend_consistency'] = 0.5

    # 5. Volume Trend
    if 'Volume' in recent.columns:
        volume_ma_short = recent['Volume'].rolling(5).mean()
        volume_ma_long = recent['Volume'].rolling(20).mean()
        if len(volume_ma_long.dropna()) > 0 and volume_ma_long.iloc[-1] != 0:
            features['volume_trend'] = (volume_ma_short.iloc[-1] / volume_ma_long.iloc[-1]) - 1
        else:
            features['volume_trend'] = 0
    else:
        features['volume_trend'] = 0

    # 6. Price Momentum
    if len(recent) >= 2 and recent['Close'].iloc[0] != 0:
        features['price_momentum'] = (recent['Close'].iloc[-1] / recent['Close'].iloc[0]) - 1
    else:
        features['price_momentum'] = 0

    # 7. Volatility Regime
    if len(data) > lookback_window * 3:
        historical_vol = data['Close'].pct_change().rolling(lookback_window).std()
        if len(historical_vol.dropna()) > 0:
            current_vol_percentile = (historical_vol.iloc[-1] > historical_vol).sum() / len(historical_vol)
            features['volatility_regime'] = current_vol_percentile
        else:
            features['volatility_regime'] = 0.5
    else:
        features['volatility_regime'] = 0.5

    # 8. Mean Reversion Tendency
    ma = recent['Close'].rolling(20).mean()
    if len(ma.dropna()) > 0:
        distance_from_ma = abs(recent['Close'] - ma) / ma
        features['mean_reversion_tendency'] = 1 - distance_from_ma.mean()
    else:
        features['mean_reversion_tendency'] = 0.5

    # 9. Price Range
    if 'High' in recent.columns and 'Low' in recent.columns:
        daily_range = (recent['High'] - recent['Low']) / recent['Close']
        features['avg_daily_range'] = daily_range.mean()
    else:
        features['avg_daily_range'] = 0

    return features


# ════════════════════════════════════════════════════════════════════════════
# INDICATOR ACCURACY TESTING AGAINST TREND BREAKS
# ════════════════════════════════════════════════════════════════════════════

def calculate_indicator_signals(data: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate all technical indicators with both continuous values and signals.

    For continuous indicators, we track:
    - Raw value
    - Rate of change (momentum of the indicator itself)
    - Divergence from price
    - Extreme zones

    Returns DataFrame with indicator values and signal columns.
    """
    import pandas_ta as ta

    df = data.copy()

    try:
        # ═══════════════════════════════════════════════════════════════════
        # RSI - Relative Strength Index (0-100 scale)
        # ═══════════════════════════════════════════════════════════════════
        df['RSI'] = ta.rsi(df['Close'], length=14)
        # Continuous: normalize to -1 to 1 (50 = neutral)
        df['RSI_continuous'] = (df['RSI'] - 50) / 50
        # Rate of change of RSI (momentum of momentum)
        df['RSI_roc'] = df['RSI'].diff(3) / 3
        # Divergence: RSI direction vs price direction
        price_dir = np.sign(df['Close'].diff(5))
        rsi_dir = np.sign(df['RSI'].diff(5))
        df['RSI_divergence'] = (price_dir != rsi_dir).astype(int)
        # Traditional binary signal
        df['RSI_signal'] = np.where(df['RSI'] < 30, 1, np.where(df['RSI'] > 70, -1, 0))

        # ═══════════════════════════════════════════════════════════════════
        # MACD - Moving Average Convergence Divergence
        # ═══════════════════════════════════════════════════════════════════
        macd = ta.macd(df['Close'])
        if macd is not None and len(macd.columns) >= 3:
            df['MACD'] = macd.iloc[:, 0]
            df['MACD_hist'] = macd.iloc[:, 1]
            df['MACD_signal_line'] = macd.iloc[:, 2]
            # Continuous: histogram normalized by ATR
            atr = ta.atr(df['High'], df['Low'], df['Close'], length=14)
            df['MACD_continuous'] = df['MACD_hist'] / atr.replace(0, np.nan)
            # Rate of change of histogram (acceleration)
            df['MACD_hist_roc'] = df['MACD_hist'].diff(3)
            # Crossover detection (1 = bullish cross, -1 = bearish cross)
            df['MACD_crossover'] = np.where(
                (df['MACD'] > df['MACD_signal_line']) & (df['MACD'].shift(1) <= df['MACD_signal_line'].shift(1)), 1,
                np.where(
                    (df['MACD'] < df['MACD_signal_line']) & (df['MACD'].shift(1) >= df['MACD_signal_line'].shift(1)), -1, 0
                )
            )
            df['MACD_signal'] = np.where(df['MACD'] > df['MACD_signal_line'], 1, -1)

        # ═══════════════════════════════════════════════════════════════════
        # Bollinger Bands - Volatility and mean reversion
        # ═══════════════════════════════════════════════════════════════════
        bb = ta.bbands(df['Close'])
        if bb is not None and len(bb.columns) >= 5:
            df['BB_lower'] = bb.iloc[:, 0]
            df['BB_middle'] = bb.iloc[:, 1]
            df['BB_upper'] = bb.iloc[:, 2]
            df['BB_bandwidth'] = bb.iloc[:, 3] if len(bb.columns) > 3 else (df['BB_upper'] - df['BB_lower']) / df['BB_middle']
            df['BB_pct'] = bb.iloc[:, 4] if len(bb.columns) > 4 else (df['Close'] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])
            # Continuous: %B normalized to -1 to 1 (0.5 = middle band)
            df['BB_continuous'] = (df['BB_pct'] - 0.5) * 2
            # Squeeze detection (low bandwidth = potential breakout)
            df['BB_squeeze'] = df['BB_bandwidth'] < df['BB_bandwidth'].rolling(20).mean() * 0.8
            df['BB_signal'] = np.where(df['Close'] < df['BB_lower'], 1,
                                       np.where(df['Close'] > df['BB_upper'], -1, 0))

        # ═══════════════════════════════════════════════════════════════════
        # Moving Averages - Trend following
        # ═══════════════════════════════════════════════════════════════════
        df['SMA_20'] = ta.sma(df['Close'], length=20)
        df['SMA_50'] = ta.sma(df['Close'], length=50)
        df['SMA_200'] = ta.sma(df['Close'], length=200)
        df['EMA_12'] = ta.ema(df['Close'], length=12)
        df['EMA_26'] = ta.ema(df['Close'], length=26)

        # Continuous: distance from MA as % (positive = above, negative = below)
        df['SMA20_dist'] = (df['Close'] - df['SMA_20']) / df['SMA_20'] * 100
        df['SMA50_dist'] = (df['Close'] - df['SMA_50']) / df['SMA_50'] * 100
        df['EMA_spread'] = (df['EMA_12'] - df['EMA_26']) / df['EMA_26'] * 100

        # MA slope (trend direction strength)
        df['SMA20_slope'] = df['SMA_20'].diff(5) / df['SMA_20'].shift(5) * 100
        df['SMA50_slope'] = df['SMA_50'].diff(5) / df['SMA_50'].shift(5) * 100

        # Golden/Death cross detection
        df['MA_crossover'] = np.where(
            (df['SMA_50'] > df['SMA_200']) & (df['SMA_50'].shift(1) <= df['SMA_200'].shift(1)), 1,
            np.where(
                (df['SMA_50'] < df['SMA_200']) & (df['SMA_50'].shift(1) >= df['SMA_200'].shift(1)), -1, 0
            )
        )

        df['SMA_signal'] = np.where(df['SMA_20'] > df['SMA_50'], 1, -1)
        df['EMA_signal'] = np.where(df['EMA_12'] > df['EMA_26'], 1, -1)

        # ═══════════════════════════════════════════════════════════════════
        # ATR - Average True Range (Volatility)
        # ═══════════════════════════════════════════════════════════════════
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'])
        # Normalized ATR (as % of price)
        df['ATR_pct'] = df['ATR'] / df['Close'] * 100
        # ATR expansion/contraction
        df['ATR_ratio'] = df['ATR'] / df['ATR'].rolling(20).mean()

        # ═══════════════════════════════════════════════════════════════════
        # ADX - Average Directional Index (Trend Strength 0-100)
        # ═══════════════════════════════════════════════════════════════════
        adx = ta.adx(df['High'], df['Low'], df['Close'])
        if adx is not None and len(adx.columns) >= 3:
            df['ADX'] = adx.iloc[:, 0]
            df['DI_plus'] = adx.iloc[:, 1]
            df['DI_minus'] = adx.iloc[:, 2]
            # Continuous: ADX normalized, DI difference for direction
            df['ADX_continuous'] = df['ADX'] / 50 - 1  # -1 to 1 scale
            df['DI_diff'] = (df['DI_plus'] - df['DI_minus']) / 50
            # ADX rising = strengthening trend
            df['ADX_rising'] = (df['ADX'].diff(3) > 0).astype(int)
            df['ADX_signal'] = np.where(df['ADX'] > 25, 1, 0)

        # ═══════════════════════════════════════════════════════════════════
        # CCI - Commodity Channel Index (-200 to +200 typical)
        # ═══════════════════════════════════════════════════════════════════
        df['CCI'] = ta.cci(df['High'], df['Low'], df['Close'])
        # Continuous: normalize to -1 to 1
        df['CCI_continuous'] = np.clip(df['CCI'] / 200, -1, 1)
        # CCI momentum
        df['CCI_roc'] = df['CCI'].diff(3)
        df['CCI_signal'] = np.where(df['CCI'] < -100, 1, np.where(df['CCI'] > 100, -1, 0))

        # ═══════════════════════════════════════════════════════════════════
        # Stochastic Oscillator (0-100)
        # ═══════════════════════════════════════════════════════════════════
        stoch = ta.stoch(df['High'], df['Low'], df['Close'])
        if stoch is not None and len(stoch.columns) >= 2:
            df['Stoch_K'] = stoch.iloc[:, 0]
            df['Stoch_D'] = stoch.iloc[:, 1]
            # Continuous: normalize to -1 to 1
            df['Stoch_continuous'] = (df['Stoch_K'] - 50) / 50
            # K/D crossover
            df['Stoch_crossover'] = np.where(
                (df['Stoch_K'] > df['Stoch_D']) & (df['Stoch_K'].shift(1) <= df['Stoch_D'].shift(1)), 1,
                np.where(
                    (df['Stoch_K'] < df['Stoch_D']) & (df['Stoch_K'].shift(1) >= df['Stoch_D'].shift(1)), -1, 0
                )
            )
            df['Stoch_signal'] = np.where(df['Stoch_K'] < 20, 1, np.where(df['Stoch_K'] > 80, -1, 0))

        # ═══════════════════════════════════════════════════════════════════
        # Williams %R (-100 to 0)
        # ═══════════════════════════════════════════════════════════════════
        df['Williams_R'] = ta.willr(df['High'], df['Low'], df['Close'])
        # Continuous: normalize to -1 to 1
        df['Williams_continuous'] = (df['Williams_R'] + 50) / 50
        df['Williams_signal'] = np.where(df['Williams_R'] < -80, 1, np.where(df['Williams_R'] > -20, -1, 0))

        # ═══════════════════════════════════════════════════════════════════
        # ROC - Rate of Change (momentum)
        # ═══════════════════════════════════════════════════════════════════
        df['ROC'] = ta.roc(df['Close'], length=10)
        df['ROC_5'] = ta.roc(df['Close'], length=5)
        df['ROC_20'] = ta.roc(df['Close'], length=20)
        # Continuous: already in % terms, clip extremes
        df['ROC_continuous'] = np.clip(df['ROC'] / 10, -1, 1)
        # ROC acceleration
        df['ROC_accel'] = df['ROC'].diff(3)
        df['ROC_signal'] = np.where(df['ROC'] > 0, 1, -1)

        # ═══════════════════════════════════════════════════════════════════
        # MFI - Money Flow Index (0-100, volume-weighted RSI)
        # ═══════════════════════════════════════════════════════════════════
        df['MFI'] = ta.mfi(df['High'], df['Low'], df['Close'], df['Volume'])
        df['MFI_continuous'] = (df['MFI'] - 50) / 50
        df['MFI_roc'] = df['MFI'].diff(3) / 3
        df['MFI_signal'] = np.where(df['MFI'] < 20, 1, np.where(df['MFI'] > 80, -1, 0))

        # ═══════════════════════════════════════════════════════════════════
        # OBV - On Balance Volume (cumulative)
        # ═══════════════════════════════════════════════════════════════════
        df['OBV'] = ta.obv(df['Close'], df['Volume'])
        # OBV momentum (rate of change)
        df['OBV_roc'] = df['OBV'].pct_change(5) * 100
        # OBV vs price divergence
        df['OBV_divergence'] = (np.sign(df['Close'].diff(10)) != np.sign(df['OBV'].diff(10))).astype(int)
        df['OBV_signal'] = np.where(df['OBV'].diff() > 0, 1, -1)

        # ═══════════════════════════════════════════════════════════════════
        # CMF - Chaikin Money Flow (-1 to 1)
        # ═══════════════════════════════════════════════════════════════════
        df['CMF'] = ta.cmf(df['High'], df['Low'], df['Close'], df['Volume'])
        df['CMF_continuous'] = df['CMF']  # Already -1 to 1
        df['CMF_roc'] = df['CMF'].diff(3)
        df['CMF_signal'] = np.where(df['CMF'] > 0, 1, -1)

        # ═══════════════════════════════════════════════════════════════════
        # PPO - Percentage Price Oscillator (normalized MACD)
        # ═══════════════════════════════════════════════════════════════════
        ppo = ta.ppo(df['Close'])
        if ppo is not None and len(ppo.columns) >= 2:
            df['PPO'] = ppo.iloc[:, 0]
            df['PPO_signal_line'] = ppo.iloc[:, 1]
            df['PPO_hist'] = ppo.iloc[:, 2] if len(ppo.columns) > 2 else df['PPO'] - df['PPO_signal_line']
            df['PPO_continuous'] = np.clip(df['PPO'] / 5, -1, 1)
            df['PPO_crossover'] = np.where(
                (df['PPO'] > df['PPO_signal_line']) & (df['PPO'].shift(1) <= df['PPO_signal_line'].shift(1)), 1,
                np.where(
                    (df['PPO'] < df['PPO_signal_line']) & (df['PPO'].shift(1) >= df['PPO_signal_line'].shift(1)), -1, 0
                )
            )
            df['PPO_signal'] = np.where(df['PPO'] > df['PPO_signal_line'], 1, -1)

        # ═══════════════════════════════════════════════════════════════════
        # TRIX - Triple Exponential Average (momentum)
        # ═══════════════════════════════════════════════════════════════════
        trix = ta.trix(df['Close'])
        if trix is not None:
            if isinstance(trix, pd.DataFrame):
                df['TRIX'] = trix.iloc[:, 0]
            else:
                df['TRIX'] = trix
            df['TRIX_continuous'] = np.clip(df['TRIX'] * 100, -1, 1)
            df['TRIX_signal'] = np.where(df['TRIX'] > 0, 1, -1)

        # ═══════════════════════════════════════════════════════════════════
        # Aroon - Trend timing (0-100 each)
        # ═══════════════════════════════════════════════════════════════════
        aroon = ta.aroon(df['High'], df['Low'])
        if aroon is not None and len(aroon.columns) >= 2:
            df['Aroon_Down'] = aroon.iloc[:, 0]
            df['Aroon_Up'] = aroon.iloc[:, 1]
            df['Aroon_Osc'] = df['Aroon_Up'] - df['Aroon_Down']
            df['Aroon_continuous'] = df['Aroon_Osc'] / 100
            # Aroon crossover
            df['Aroon_crossover'] = np.where(
                (df['Aroon_Up'] > df['Aroon_Down']) & (df['Aroon_Up'].shift(1) <= df['Aroon_Down'].shift(1)), 1,
                np.where(
                    (df['Aroon_Up'] < df['Aroon_Down']) & (df['Aroon_Up'].shift(1) >= df['Aroon_Down'].shift(1)), -1, 0
                )
            )
            df['Aroon_signal'] = np.where(df['Aroon_Osc'] > 0, 1, -1)

        # ═══════════════════════════════════════════════════════════════════
        # TSI - True Strength Index (double-smoothed momentum)
        # ═══════════════════════════════════════════════════════════════════
        tsi = ta.tsi(df['Close'])
        if tsi is not None and len(tsi.columns) >= 1:
            df['TSI'] = tsi.iloc[:, 0]
            df['TSI_continuous'] = np.clip(df['TSI'] / 50, -1, 1)
            df['TSI_roc'] = df['TSI'].diff(3)
            df['TSI_signal'] = np.where(df['TSI'] > 0, 1, -1)

        # ═══════════════════════════════════════════════════════════════════
        # Ultimate Oscillator (multi-timeframe momentum, 0-100)
        # ═══════════════════════════════════════════════════════════════════
        df['Ultimate_Osc'] = ta.uo(df['High'], df['Low'], df['Close'])
        if 'Ultimate_Osc' in df.columns and df['Ultimate_Osc'] is not None:
            df['Ultimate_continuous'] = (df['Ultimate_Osc'] - 50) / 50
            df['Ultimate_signal'] = np.where(df['Ultimate_Osc'] < 30, 1,
                                             np.where(df['Ultimate_Osc'] > 70, -1, 0))

        # ═══════════════════════════════════════════════════════════════════
        # PSAR - Parabolic SAR (trend reversal)
        # ═══════════════════════════════════════════════════════════════════
        psar = ta.psar(df['High'], df['Low'], df['Close'])
        if psar is not None and len(psar.columns) >= 2:
            df['PSAR_long'] = psar.iloc[:, 0]
            df['PSAR_short'] = psar.iloc[:, 1]
            # Distance from PSAR as continuous signal
            psar_val = df['PSAR_long'].fillna(df['PSAR_short'])
            df['PSAR_dist'] = (df['Close'] - psar_val) / df['Close'] * 100
            df['PSAR_continuous'] = np.clip(df['PSAR_dist'] / 5, -1, 1)
            # PSAR flip detection
            df['PSAR_flip'] = np.where(
                df['PSAR_long'].notna() & df['PSAR_long'].shift(1).isna(), 1,
                np.where(
                    df['PSAR_short'].notna() & df['PSAR_short'].shift(1).isna(), -1, 0
                )
            )
            df['PSAR_signal'] = np.where(df['Close'] > df['PSAR_long'].fillna(0), 1,
                                         np.where(df['Close'] < df['PSAR_short'].fillna(np.inf), -1, 0))

        # ═══════════════════════════════════════════════════════════════════
        # Choppiness Index (trending vs ranging, 0-100)
        # ═══════════════════════════════════════════════════════════════════
        df['Choppiness'] = ta.chop(df['High'], df['Low'], df['Close'])
        if 'Choppiness' in df.columns and df['Choppiness'] is not None:
            # High = choppy/ranging, Low = trending
            df['Choppiness_continuous'] = (df['Choppiness'] - 50) / 50  # Inverted: negative = trending
            df['Choppiness_signal'] = np.where(df['Choppiness'] < 38.2, 1, 0)  # Trending

        # ═══════════════════════════════════════════════════════════════════
        # Keltner Channels (volatility-based trend channels)
        # ═══════════════════════════════════════════════════════════════════
        kc = ta.kc(df['High'], df['Low'], df['Close'])
        if kc is not None and len(kc.columns) >= 3:
            df['KC_lower'] = kc.iloc[:, 0]
            df['KC_mid'] = kc.iloc[:, 1]
            df['KC_upper'] = kc.iloc[:, 2]
            # Position within channel (0 = lower, 1 = upper)
            kc_range = df['KC_upper'] - df['KC_lower']
            df['KC_pct'] = np.where(kc_range > 0,
                                    (df['Close'] - df['KC_lower']) / kc_range, 0.5)
            df['KC_continuous'] = (df['KC_pct'] - 0.5) * 2  # -1 to 1
            # Breakout signals
            df['KC_breakout_up'] = (df['Close'] > df['KC_upper']).astype(int)
            df['KC_breakout_down'] = (df['Close'] < df['KC_lower']).astype(int)
            df['KC_signal'] = df['KC_breakout_up'] - df['KC_breakout_down']
            # Distance from mid-channel
            df['KC_dist'] = np.where(df['KC_mid'] > 0,
                                     (df['Close'] - df['KC_mid']) / df['KC_mid'] * 100, 0)

        # ═══════════════════════════════════════════════════════════════════
        # Donchian Channels (breakout channels based on highs/lows)
        # ═══════════════════════════════════════════════════════════════════
        donchian = ta.donchian(df['High'], df['Low'])
        if donchian is not None and len(donchian.columns) >= 3:
            df['DC_lower'] = donchian.iloc[:, 0]
            df['DC_mid'] = donchian.iloc[:, 1]
            df['DC_upper'] = donchian.iloc[:, 2]
            # Position within channel
            dc_range = df['DC_upper'] - df['DC_lower']
            df['DC_pct'] = np.where(dc_range > 0,
                                    (df['Close'] - df['DC_lower']) / dc_range, 0.5)
            df['DC_continuous'] = (df['DC_pct'] - 0.5) * 2  # -1 to 1
            # Breakout signals (touching upper/lower = potential reversal)
            df['DC_at_upper'] = (df['High'] >= df['DC_upper']).astype(int)
            df['DC_at_lower'] = (df['Low'] <= df['DC_lower']).astype(int)
            df['DC_signal'] = df['DC_at_upper'] - df['DC_at_lower']
            # Channel squeeze detection (narrowing range)
            df['DC_width'] = dc_range / df['Close'] * 100
            df['DC_squeeze'] = (df['DC_width'] < df['DC_width'].rolling(20).mean()).astype(int)

        # ═══════════════════════════════════════════════════════════════════
        # Accumulation/Distribution Line (volume-weighted price momentum)
        # ═══════════════════════════════════════════════════════════════════
        df['AD_line'] = ta.ad(df['High'], df['Low'], df['Close'], df['Volume'])
        if 'AD_line' in df.columns and df['AD_line'] is not None:
            # Rate of change for AD line
            df['AD_roc'] = df['AD_line'].pct_change(5) * 100
            df['AD_roc'] = df['AD_roc'].clip(-100, 100)
            df['AD_continuous'] = np.clip(df['AD_roc'] / 20, -1, 1)
            # AD divergence with price
            price_roc = df['Close'].pct_change(5)
            df['AD_divergence'] = np.where(
                (df['AD_roc'] > 0) & (price_roc < 0), 1,  # Bullish divergence
                np.where((df['AD_roc'] < 0) & (price_roc > 0), -1, 0)  # Bearish divergence
            )
            # AD trend
            ad_sma = df['AD_line'].rolling(20).mean()
            df['AD_signal'] = np.where(df['AD_line'] > ad_sma, 1,
                                       np.where(df['AD_line'] < ad_sma, -1, 0))

        # ═══════════════════════════════════════════════════════════════════
        # TLEV - Traders Lion Enhanced Volume (custom implementation)
        # Combines volume momentum with price action for trend confirmation
        # ═══════════════════════════════════════════════════════════════════
        # TLEV calculation: Volume-weighted price momentum
        # Uses price change weighted by relative volume
        price_change = df['Close'].pct_change()
        vol_sma = df['Volume'].rolling(20).mean()
        rel_volume = df['Volume'] / vol_sma  # Relative volume (>1 = above average)

        # TLEV = cumulative sum of (price change * relative volume)
        df['TLEV_raw'] = price_change * rel_volume
        df['TLEV'] = df['TLEV_raw'].rolling(14).sum()  # 14-period sum

        if 'TLEV' in df.columns and df['TLEV'] is not None:
            # Normalize TLEV for continuous signal (-1 to 1)
            tlev_std = df['TLEV'].rolling(20).std()
            tlev_mean = df['TLEV'].rolling(20).mean()
            df['TLEV_zscore'] = np.where(tlev_std > 0,
                                         (df['TLEV'] - tlev_mean) / tlev_std, 0)
            df['TLEV_continuous'] = np.clip(df['TLEV_zscore'] / 2, -1, 1)
            # TLEV momentum (rate of change)
            df['TLEV_roc'] = df['TLEV'].pct_change(5) * 100
            df['TLEV_roc'] = df['TLEV_roc'].clip(-100, 100)
            # Signal based on TLEV direction
            df['TLEV_signal'] = np.where(df['TLEV'] > df['TLEV'].shift(1), 1,
                                         np.where(df['TLEV'] < df['TLEV'].shift(1), -1, 0))
            # Crossover with moving average of TLEV
            tlev_ma = df['TLEV'].rolling(10).mean()
            df['TLEV_crossover'] = np.where(
                (df['TLEV'] > tlev_ma) & (df['TLEV'].shift(1) <= tlev_ma.shift(1)), 1,
                np.where(
                    (df['TLEV'] < tlev_ma) & (df['TLEV'].shift(1) >= tlev_ma.shift(1)), -1, 0
                )
            )

        # ═══════════════════════════════════════════════════════════════════
        # Volume at Price (VWAP zones and volume concentration)
        # ═══════════════════════════════════════════════════════════════════
        # VWAP already calculated above, add volume profile analysis
        if 'VWAP' in df.columns:
            # Distance from VWAP (already have VWAP_dist)
            # Add volume-weighted momentum
            typical_price = (df['High'] + df['Low'] + df['Close']) / 3
            df['VP_momentum'] = (typical_price - typical_price.shift(1)) * df['Volume']
            df['VP_cumulative'] = df['VP_momentum'].rolling(20).sum()
            df['VP_normalized'] = np.where(
                df['Volume'].rolling(20).sum() > 0,
                df['VP_cumulative'] / df['Volume'].rolling(20).sum(),
                0
            )
            df['VP_continuous'] = np.clip(df['VP_normalized'] / df['Close'].mean() * 100, -1, 1)
            # Volume concentration (high volume at current price = support/resistance)
            df['VP_signal'] = np.where(df['VP_normalized'] > 0, 1,
                                       np.where(df['VP_normalized'] < 0, -1, 0))

        # ═══════════════════════════════════════════════════════════════════
        # Additional Composite Signals
        # ═══════════════════════════════════════════════════════════════════

        # Momentum consensus (average of normalized momentum indicators)
        momentum_cols = ['RSI_continuous', 'MACD_continuous', 'Stoch_continuous', 'ROC_continuous', 'MFI_continuous']
        available_momentum = [col for col in momentum_cols if col in df.columns]
        if available_momentum:
            df['Momentum_consensus'] = df[available_momentum].mean(axis=1)

        # Trend consensus (average of trend indicators)
        trend_cols = ['SMA20_dist', 'EMA_spread', 'Aroon_continuous']
        available_trend = [col for col in trend_cols if col in df.columns]
        if available_trend:
            df['Trend_consensus'] = df[available_trend].mean(axis=1)

        # Volume confirmation
        if 'CMF_continuous' in df.columns and 'OBV_roc' in df.columns:
            df['Volume_confirmation'] = (np.sign(df['CMF_continuous']) == np.sign(df['Close'].pct_change(5))).astype(int)

    except Exception as e:
        print(f"Warning: Error calculating some indicators: {e}")

    return df


def test_indicator_accuracy_at_breaks(
    ticker: str,
    trend_breaks: pd.DataFrame,
    lookback_periods: List[int] = [1, 2, 3, 5, 8, 13],
    timeframe: str = 'daily',
    market_indicator_data: Optional[Dict[str, pd.DataFrame]] = None,
    darkpool_context: Optional[pd.DataFrame] = None,
    cboe_context: Optional[pd.DataFrame] = None
) -> Dict[str, Dict]:
    """
    Test how accurately each indicator predicted trend breaks at various lookback periods.

    Tests both stock-level indicators AND (optionally) market instrument indicators
    (e.g., SP500_RSI, VIX_BB, FUTURES_MACD) against this stock's trend breaks.

    Uses multiple accuracy metrics:
    1. Binary signal accuracy (traditional)
    2. Continuous indicator direction (was indicator moving in anticipation of break?)
    3. Extreme value detection (was indicator at an extreme before reversal?)
    4. Divergence detection (did indicator diverge from price before break?)
    5. Crossover timing (did a crossover occur before break?)

    Args:
        ticker: Stock ticker
        trend_breaks: DataFrame of trend breaks for this ticker
        lookback_periods: List of periods to look back from break
        timeframe: 'daily', '1hour', '5min'

    Returns:
        Dict with accuracy metrics for each indicator at each lookback period
    """
    if len(trend_breaks) == 0:
        return {}

    # Get date range for price data
    min_date = trend_breaks['timestamp'].min() - timedelta(days=60)
    max_date = trend_breaks['timestamp'].max() + timedelta(days=1)

    # Fetch price data
    try:
        price_data = get_stock_data_from_db(
            ticker,
            min_date.strftime('%Y-%m-%d'),
            max_date.strftime('%Y-%m-%d'),
            timeframe
        )
    except Exception as e:
        print(f"  Error fetching data for {ticker}: {e}")
        return {}

    if len(price_data) < 50:
        return {}

    # Calculate indicators
    indicator_data = calculate_indicator_signals(price_data)

    # Define indicator groups for different accuracy tests
    continuous_indicators = {
        'RSI': {'continuous': 'RSI_continuous', 'roc': 'RSI_roc', 'divergence': 'RSI_divergence', 'extreme_high': 70, 'extreme_low': 30, 'raw': 'RSI'},
        'MACD': {'continuous': 'MACD_continuous', 'roc': 'MACD_hist_roc', 'crossover': 'MACD_crossover', 'raw': 'MACD_hist'},
        'Stoch': {'continuous': 'Stoch_continuous', 'crossover': 'Stoch_crossover', 'extreme_high': 80, 'extreme_low': 20, 'raw': 'Stoch_K'},
        'CCI': {'continuous': 'CCI_continuous', 'roc': 'CCI_roc', 'extreme_high': 100, 'extreme_low': -100, 'raw': 'CCI'},
        'MFI': {'continuous': 'MFI_continuous', 'roc': 'MFI_roc', 'extreme_high': 80, 'extreme_low': 20, 'raw': 'MFI'},
        'Williams': {'continuous': 'Williams_continuous', 'extreme_high': -20, 'extreme_low': -80, 'raw': 'Williams_R'},
        'ROC': {'continuous': 'ROC_continuous', 'roc': 'ROC_accel', 'raw': 'ROC'},
        'CMF': {'continuous': 'CMF_continuous', 'roc': 'CMF_roc', 'raw': 'CMF'},
        'OBV': {'roc': 'OBV_roc', 'divergence': 'OBV_divergence'},
        'PPO': {'continuous': 'PPO_continuous', 'crossover': 'PPO_crossover', 'raw': 'PPO'},
        'Aroon': {'continuous': 'Aroon_continuous', 'crossover': 'Aroon_crossover', 'raw': 'Aroon_Osc'},
        'TSI': {'continuous': 'TSI_continuous', 'roc': 'TSI_roc', 'raw': 'TSI'},
        'PSAR': {'continuous': 'PSAR_continuous', 'flip': 'PSAR_flip', 'raw': 'PSAR_dist'},
        'ADX': {'continuous': 'ADX_continuous', 'raw': 'ADX', 'di_diff': 'DI_diff'},
        'BB': {'continuous': 'BB_continuous', 'squeeze': 'BB_squeeze', 'raw': 'BB_pct'},
        'SMA': {'dist': 'SMA20_dist', 'slope': 'SMA20_slope', 'crossover': 'MA_crossover'},
        'EMA': {'spread': 'EMA_spread'},
        'Ultimate': {'continuous': 'Ultimate_continuous', 'extreme_high': 70, 'extreme_low': 30, 'raw': 'Ultimate_Osc'},
        'Choppiness': {'continuous': 'Choppiness_continuous', 'raw': 'Choppiness'},
        # Newly added indicators
        'Keltner': {'continuous': 'KC_continuous', 'raw': 'KC_pct', 'dist': 'KC_dist'},
        'Donchian': {'continuous': 'DC_continuous', 'squeeze': 'DC_squeeze', 'raw': 'DC_pct'},
        'AccDist': {'continuous': 'AD_continuous', 'roc': 'AD_roc', 'divergence': 'AD_divergence', 'raw': 'AD_line'},
        'TLEV': {'continuous': 'TLEV_continuous', 'roc': 'TLEV_roc', 'crossover': 'TLEV_crossover', 'raw': 'TLEV'},
        'VolPrice': {'continuous': 'VP_continuous', 'raw': 'VP_normalized'},
    }

    results = {}

    for indicator_name, cols in continuous_indicators.items():
        results[indicator_name] = {
            'total_breaks': 0,
            # Binary signal accuracy
            'binary_correct': {period: 0 for period in lookback_periods},
            # Continuous direction accuracy (was indicator moving toward reversal)
            'direction_correct': {period: 0 for period in lookback_periods},
            # Extreme value detection
            'extreme_detected': {period: 0 for period in lookback_periods},
            # Divergence detected
            'divergence_detected': {period: 0 for period in lookback_periods},
            # Crossover detected
            'crossover_detected': {period: 0 for period in lookback_periods},
            # Composite scores
            'accuracy_by_lookback': {period: 0.0 for period in lookback_periods}
        }

    # For each trend break, check indicators
    for _, break_row in trend_breaks.iterrows():
        break_time = break_row['timestamp']
        break_type = break_row['break_type']  # 'peak' or 'trough'

        # Expected direction before break:
        # - Before a 'peak' (price will drop): indicators should be showing bearish divergence/extreme
        # - Before a 'trough' (price will rise): indicators should be showing bullish divergence/extreme
        expected_direction = -1 if break_type == 'peak' else 1

        # Find the break time in indicator data
        try:
            if break_time in indicator_data.index:
                break_idx = indicator_data.index.get_loc(break_time)
            else:
                time_diffs = abs(indicator_data.index - break_time)
                nearest_idx = time_diffs.argmin()
                if time_diffs[nearest_idx] > timedelta(days=2):
                    continue
                break_idx = nearest_idx
        except:
            continue

        for indicator_name, cols in continuous_indicators.items():
            results[indicator_name]['total_breaks'] += 1

            for lookback in lookback_periods:
                check_idx = break_idx - lookback
                if check_idx < 0 or check_idx >= len(indicator_data):
                    continue

                # 1. Binary signal check
                signal_col = f'{indicator_name}_signal'
                if signal_col in indicator_data.columns:
                    signal_val = indicator_data[signal_col].iloc[check_idx]
                    if not pd.isna(signal_val) and signal_val == expected_direction:
                        results[indicator_name]['binary_correct'][lookback] += 1

                # 2. Continuous direction check (is indicator moving in anticipation?)
                if 'continuous' in cols and cols['continuous'] in indicator_data.columns:
                    cont_val = indicator_data[cols['continuous']].iloc[check_idx]
                    # For peak (expected_direction=-1), we want continuous to be positive (overbought)
                    # For trough (expected_direction=1), we want continuous to be negative (oversold)
                    if not pd.isna(cont_val):
                        if (expected_direction == -1 and cont_val > 0.3) or \
                           (expected_direction == 1 and cont_val < -0.3):
                            results[indicator_name]['direction_correct'][lookback] += 1

                # 3. Rate of change check (is indicator momentum anticipating reversal?)
                if 'roc' in cols and cols['roc'] in indicator_data.columns:
                    roc_val = indicator_data[cols['roc']].iloc[check_idx]
                    # Before peak, RSI should be declining; before trough, rising
                    if not pd.isna(roc_val):
                        if (expected_direction == -1 and roc_val < 0) or \
                           (expected_direction == 1 and roc_val > 0):
                            results[indicator_name]['direction_correct'][lookback] += 1

                # 4. Extreme value detection
                if 'raw' in cols and cols['raw'] in indicator_data.columns:
                    raw_val = indicator_data[cols['raw']].iloc[check_idx]
                    if not pd.isna(raw_val):
                        if 'extreme_high' in cols and 'extreme_low' in cols:
                            # Before peak, indicator should be at extreme high
                            # Before trough, indicator should be at extreme low
                            if (expected_direction == -1 and raw_val > cols['extreme_high']) or \
                               (expected_direction == 1 and raw_val < cols['extreme_low']):
                                results[indicator_name]['extreme_detected'][lookback] += 1

                # 5. Divergence detection
                if 'divergence' in cols and cols['divergence'] in indicator_data.columns:
                    div_val = indicator_data[cols['divergence']].iloc[check_idx]
                    if not pd.isna(div_val) and div_val == 1:
                        results[indicator_name]['divergence_detected'][lookback] += 1

                # 6. Crossover detection
                crossover_col = cols.get('crossover') or cols.get('flip')
                if crossover_col and crossover_col in indicator_data.columns:
                    # Check if crossover happened in lookback window
                    for j in range(max(0, check_idx - lookback), check_idx + 1):
                        cross_val = indicator_data[crossover_col].iloc[j]
                        if not pd.isna(cross_val) and cross_val == expected_direction:
                            results[indicator_name]['crossover_detected'][lookback] += 1
                            break

    # ═══════════════════════════════════════════════════════════════════
    # TEST MARKET INSTRUMENT INDICATORS (Layer B)
    # ═══════════════════════════════════════════════════════════════════
    if market_indicator_data:
        # Define which market instrument indicators to test and their properties
        # These mirror the stock-level indicator definitions but are prefixed
        market_indicator_defs = {}
        for prefix in ['SP500', 'VIX', 'FUTURES']:
            if prefix not in market_indicator_data:
                continue
            mkt_df = market_indicator_data[prefix]
            available_cols = set(mkt_df.columns)

            # Build indicator definitions from available columns
            for base_indicator in ['RSI', 'MACD', 'Stoch', 'CCI', 'MFI', 'BB', 'ADX', 'OBV', 'CMF']:
                indicator_name = f'{prefix}_{base_indicator}'
                cols = {}

                # Map column names with prefix
                cont_col = f'{prefix}_{base_indicator}_continuous'
                roc_col = f'{prefix}_{base_indicator}_roc'
                div_col = f'{prefix}_{base_indicator}_divergence'
                cross_col = f'{prefix}_{base_indicator}_crossover'
                flip_col = f'{prefix}_{base_indicator}_flip'
                raw_col = f'{prefix}_{base_indicator}'

                if cont_col in available_cols:
                    cols['continuous'] = cont_col
                if roc_col in available_cols:
                    cols['roc'] = roc_col
                if div_col in available_cols:
                    cols['divergence'] = div_col
                if cross_col in available_cols:
                    cols['crossover'] = cross_col
                if flip_col in available_cols:
                    cols['flip'] = flip_col
                if raw_col in available_cols:
                    cols['raw'] = raw_col

                # Set extreme thresholds for oscillators
                if base_indicator == 'RSI':
                    cols['extreme_high'] = 70
                    cols['extreme_low'] = 30
                elif base_indicator == 'Stoch':
                    cols['extreme_high'] = 80
                    cols['extreme_low'] = 20
                elif base_indicator == 'CCI':
                    cols['extreme_high'] = 100
                    cols['extreme_low'] = -100
                elif base_indicator == 'MFI':
                    cols['extreme_high'] = 80
                    cols['extreme_low'] = 20

                if cols:  # Only add if we found at least one column
                    market_indicator_defs[indicator_name] = cols

        # Initialize results for market indicators
        for indicator_name, cols in market_indicator_defs.items():
            results[indicator_name] = {
                'total_breaks': 0,
                'binary_correct': {period: 0 for period in lookback_periods},
                'direction_correct': {period: 0 for period in lookback_periods},
                'extreme_detected': {period: 0 for period in lookback_periods},
                'divergence_detected': {period: 0 for period in lookback_periods},
                'crossover_detected': {period: 0 for period in lookback_periods},
                'accuracy_by_lookback': {period: 0.0 for period in lookback_periods},
                'is_market_indicator': True
            }

        # Test market indicators against each trend break
        for _, break_row in trend_breaks.iterrows():
            break_time = break_row['timestamp']
            break_type = break_row['break_type']
            expected_direction = -1 if break_type == 'peak' else 1

            for indicator_name, cols in market_indicator_defs.items():
                # Determine which market DataFrame contains this indicator
                prefix = indicator_name.split('_')[0]
                if prefix not in market_indicator_data:
                    continue
                mkt_df = market_indicator_data[prefix]

                # Find the break time in market data
                try:
                    # Normalize break_time for date matching
                    break_date = pd.Timestamp(break_time).normalize()
                    if break_date in mkt_df.index:
                        break_idx = mkt_df.index.get_loc(break_date)
                    else:
                        time_diffs = abs(mkt_df.index - break_date)
                        nearest_idx = time_diffs.argmin()
                        if time_diffs[nearest_idx] > timedelta(days=5):
                            continue
                        break_idx = nearest_idx
                except:
                    continue

                results[indicator_name]['total_breaks'] += 1

                for lookback in lookback_periods:
                    check_idx = break_idx - lookback
                    if check_idx < 0 or check_idx >= len(mkt_df):
                        continue

                    # 1. Continuous direction check
                    if 'continuous' in cols and cols['continuous'] in mkt_df.columns:
                        cont_val = mkt_df[cols['continuous']].iloc[check_idx]
                        if not pd.isna(cont_val):
                            if (expected_direction == -1 and cont_val > 0.3) or \
                               (expected_direction == 1 and cont_val < -0.3):
                                results[indicator_name]['direction_correct'][lookback] += 1

                    # 2. Rate of change check
                    if 'roc' in cols and cols['roc'] in mkt_df.columns:
                        roc_val = mkt_df[cols['roc']].iloc[check_idx]
                        if not pd.isna(roc_val):
                            if (expected_direction == -1 and roc_val < 0) or \
                               (expected_direction == 1 and roc_val > 0):
                                results[indicator_name]['direction_correct'][lookback] += 1

                    # 3. Extreme value detection
                    if 'raw' in cols and cols['raw'] in mkt_df.columns:
                        raw_val = mkt_df[cols['raw']].iloc[check_idx]
                        if not pd.isna(raw_val):
                            if 'extreme_high' in cols and 'extreme_low' in cols:
                                if (expected_direction == -1 and raw_val > cols['extreme_high']) or \
                                   (expected_direction == 1 and raw_val < cols['extreme_low']):
                                    results[indicator_name]['extreme_detected'][lookback] += 1

                    # 4. Divergence detection
                    if 'divergence' in cols and cols['divergence'] in mkt_df.columns:
                        div_val = mkt_df[cols['divergence']].iloc[check_idx]
                        if not pd.isna(div_val) and div_val == 1:
                            results[indicator_name]['divergence_detected'][lookback] += 1

                    # 5. Crossover detection
                    crossover_col = cols.get('crossover') or cols.get('flip')
                    if crossover_col and crossover_col in mkt_df.columns:
                        for j in range(max(0, check_idx - lookback), check_idx + 1):
                            cross_val = mkt_df[crossover_col].iloc[j]
                            if not pd.isna(cross_val) and cross_val == expected_direction:
                                results[indicator_name]['crossover_detected'][lookback] += 1
                                break

    # Calculate composite accuracy scores
    for indicator_name, data in results.items():
        total = data['total_breaks']
        if total > 0:
            for lookback in lookback_periods:
                # Weight different accuracy types
                binary_acc = data['binary_correct'][lookback] / total
                direction_acc = data['direction_correct'][lookback] / total
                extreme_acc = data['extreme_detected'][lookback] / total
                divergence_acc = data['divergence_detected'][lookback] / total
                crossover_acc = data['crossover_detected'][lookback] / total

                # Composite: weighted average (direction and extremes are most predictive)
                composite = (
                    binary_acc * 0.15 +
                    direction_acc * 0.30 +
                    extreme_acc * 0.25 +
                    divergence_acc * 0.15 +
                    crossover_acc * 0.15
                )
                data['accuracy_by_lookback'][lookback] = composite

                # Store individual scores for analysis
                data[f'binary_{lookback}'] = binary_acc
                data[f'direction_{lookback}'] = direction_acc
                data[f'extreme_{lookback}'] = extreme_acc
                data[f'divergence_{lookback}'] = divergence_acc
                data[f'crossover_{lookback}'] = crossover_acc

    # ─── DARK POOL AMPLIFICATION ───
    # High dark pool volume (z>0) amplifies composite accuracy scores.
    # Rationale: analysis showed DP high volume (z>1) amplifies post-break returns
    # by +1.29pp (3.22% vs 1.93%). Amplification is multiplicative on composite score.
    if darkpool_context is not None and len(darkpool_context) > 0:
        ticker_dp = darkpool_context[darkpool_context['ticker'] == ticker]
        if len(ticker_dp) > 0:
            # Match each break to nearest dark pool week (within 14 days)
            breaks_sorted = trend_breaks.sort_values('timestamp').copy()
            breaks_sorted['timestamp'] = pd.to_datetime(breaks_sorted['timestamp']).dt.tz_localize(None)
            ticker_dp_sorted = ticker_dp.sort_values('week_start_date')

            matched_dp = pd.merge_asof(
                breaks_sorted[['timestamp']],
                ticker_dp_sorted[['week_start_date', 'dp_volume_zscore', 'dp_shares_change',
                                   'concentration_ratio']],
                left_on='timestamp',
                right_on='week_start_date',
                direction='backward',
                tolerance=pd.Timedelta('14 days')
            )

            # Compute average amplification factor for this ticker
            valid_dp = matched_dp.dropna(subset=['dp_volume_zscore'])
            if len(valid_dp) > 0:
                avg_zscore = valid_dp['dp_volume_zscore'].mean()
                avg_concentration = valid_dp['concentration_ratio'].mean()
                # Amplification: 1.0 + max(0, z) * 0.15
                # z=0 -> 1.0x, z=1 -> 1.15x, z=2 -> 1.30x
                amplification = 1.0 + max(0.0, avg_zscore) * 0.15

                for indicator_name, data in results.items():
                    # Apply amplification to composite scores
                    for lookback in lookback_periods:
                        if lookback in data['accuracy_by_lookback']:
                            data['accuracy_by_lookback'][lookback] *= amplification
                    # Store dark pool context on each indicator result
                    data['dp_amplification'] = amplification
                    data['dp_volume_zscore'] = avg_zscore
                    data['dp_concentration'] = avg_concentration

    # ─── CBOE P/C RATIO CONTEXT ───
    # Store CBOE sentiment context on each indicator result for segmented analysis.
    # Not used as an amplifier (P/C is directional/contrarian, not magnitude).
    if cboe_context is not None and len(cboe_context) > 0:
        breaks_sorted = trend_breaks.sort_values('timestamp').copy()
        breaks_sorted['timestamp'] = pd.to_datetime(breaks_sorted['timestamp']).dt.tz_localize(None)
        cboe_sorted = cboe_context.reset_index().sort_values('trade_date')

        matched_cboe = pd.merge_asof(
            breaks_sorted[['timestamp']],
            cboe_sorted[['trade_date', 'pcr_zscore', 'pcr_regime', 'volume_zscore', 'total_pcr']],
            left_on='timestamp',
            right_on='trade_date',
            direction='backward',
            tolerance=pd.Timedelta('5 days')
        )

        valid_cboe = matched_cboe.dropna(subset=['pcr_zscore'])
        if len(valid_cboe) > 0:
            avg_pcr_zscore = valid_cboe['pcr_zscore'].mean()
            avg_pcr_regime = int(round(valid_cboe['pcr_regime'].mean()))
            avg_vol_zscore = valid_cboe['volume_zscore'].mean()
            avg_total_pcr = valid_cboe['total_pcr'].mean()

            for indicator_name, data in results.items():
                data['cboe_pcr_zscore'] = avg_pcr_zscore
                data['cboe_pcr_regime'] = avg_pcr_regime
                data['cboe_volume_zscore'] = avg_vol_zscore
                data['cboe_total_pcr'] = avg_total_pcr

    return results


# ════════════════════════════════════════════════════════════════════════════
# TRAINING AND VALIDATION DATASET CREATION
# ════════════════════════════════════════════════════════════════════════════

def create_training_validation_datasets(
    timeframe: str = 'daily',
    train_ratio: float = 0.8,
    max_samples: int = 100000,
    target_accuracy: float = 0.85,
    lookback_periods: List[int] = [1, 2, 3, 5, 8, 13],
    include_market_data: bool = True,
    include_darkpool: bool = True,
    include_cboe: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict, Optional[pd.DataFrame]]:
    """
    Create training and validation datasets from trend breaks.

    For each trend break, we calculate:
    - Features: Market regime features at the time of break
    - Labels: Which indicators correctly predicted the break (at various lookbacks)

    When include_market_data=True, also:
    - Loads market instruments (S&P 500, VIX, futures, inverse ETFs) in batch
    - Calculates technical indicators on market instruments
    - Tests market indicators against stock trend breaks
    - Tags each break with market regime (VIX regime, S&P trend)

    When include_darkpool=True:
    - Loads dark pool context (volume z-scores, concentration) per ticker
    - Applies multiplicative amplification to composite scores for high DP volume

    When include_cboe=True:
    - Loads CBOE put/call ratio context (z-scores, regimes)
    - Stores sentiment context on each indicator for segmented analysis

    Args:
        timeframe: 'daily', '1hour', '5min'
        train_ratio: Fraction for training (rest is validation)
        max_samples: Maximum number of trend breaks to use
        target_accuracy: Target accuracy threshold for reporting
        lookback_periods: Periods to check before break
        include_market_data: If True, incorporate market instruments into analysis

    Returns:
        Tuple of (training_df, validation_df, indicator_results, market_regime_df)
        market_regime_df is None if include_market_data=False
    """
    print(f"\n{'='*60}")
    print(f"CREATING TRAINING/VALIDATION DATASETS")
    print(f"{'='*60}")
    print(f"Timeframe: {timeframe}")
    print(f"Max samples: {max_samples:,}")
    print(f"Train/Val split: {train_ratio:.0%}/{1-train_ratio:.0%}")
    print(f"Target accuracy threshold: {target_accuracy:.0%}")
    print(f"Lookback periods: {lookback_periods}")
    print(f"Include market data: {include_market_data}")
    print(f"Include dark pool: {include_darkpool}")
    print(f"Include CBOE: {include_cboe}")

    # Get all tickers
    tickers = get_available_tickers(timeframe)
    print(f"\nFound {len(tickers)} tickers with trend breaks")

    # Get trend breaks
    date_filter = ""
    if start_date:
        date_filter += f" from {start_date}"
    if end_date:
        date_filter += f" to {end_date}"
    print(f"\nFetching trend breaks (limit: {max_samples:,}{date_filter})...")
    all_breaks = get_trend_breaks_from_db(
        timeframe=timeframe, limit=max_samples,
        start_date=start_date, end_date=end_date
    )
    print(f"Retrieved {len(all_breaks):,} trend breaks")

    # Split by time for train/val
    all_breaks = all_breaks.sort_values('timestamp')
    split_idx = int(len(all_breaks) * train_ratio)
    train_breaks = all_breaks.iloc[:split_idx]
    val_breaks = all_breaks.iloc[split_idx:]

    print(f"\nTraining set: {len(train_breaks):,} breaks")
    print(f"Validation set: {len(val_breaks):,} breaks")

    # ═══════════════════════════════════════════════════════════════════
    # LOAD MARKET DATA (Layer A + B)
    # ═══════════════════════════════════════════════════════════════════
    market_indicator_data = None
    market_regime_df = None

    if include_market_data:
        from .populate_market_indices import (
            batch_load_market_data,
            calculate_market_features_batch,
            calculate_market_instrument_indicators
        )

        # Determine date range from breaks (with buffer for lookback)
        min_date = (all_breaks['timestamp'].min() - timedelta(days=90)).strftime('%Y-%m-%d')
        max_date = (all_breaks['timestamp'].max() + timedelta(days=1)).strftime('%Y-%m-%d')

        print(f"\nLoading market data from {min_date} to {max_date}...")
        market_data = batch_load_market_data(min_date, max_date)

        if market_data:
            # Layer A: Calculate market regime features for all break timestamps
            print("\nCalculating market regime features for all breaks...")
            market_regime_df = calculate_market_features_batch(
                market_data, all_breaks['timestamp']
            )
            print(f"  Computed {len(market_regime_df)} regime feature rows")
            print(f"  Features: {list(market_regime_df.columns)}")

            # Tag breaks with regime info for segmented analysis
            breaks_with_regime = all_breaks.copy()
            breaks_with_regime['timestamp_normalized'] = pd.to_datetime(
                breaks_with_regime['timestamp']
            ).dt.normalize()

            regime_cols = ['vix_regime', 'sp500_trend', 'futures_premium']
            available_regime_cols = [c for c in regime_cols if c in market_regime_df.columns]

            if available_regime_cols:
                regime_lookup = market_regime_df[available_regime_cols].copy()
                regime_lookup.index = pd.to_datetime(regime_lookup.index).normalize()
                regime_lookup = regime_lookup[~regime_lookup.index.duplicated(keep='last')]

                for col in available_regime_cols:
                    breaks_with_regime[col] = breaks_with_regime['timestamp_normalized'].map(
                        regime_lookup[col]
                    )

                # Update train/val with regime tags
                train_breaks = breaks_with_regime.iloc[:split_idx]
                val_breaks = breaks_with_regime.iloc[split_idx:]

                # Print regime distribution
                print("\nMarket regime distribution in training breaks:")
                if 'vix_regime' in available_regime_cols:
                    vix_counts = train_breaks['vix_regime'].value_counts()
                    vix_labels = {1: 'High VIX (>25)', 0: 'Normal VIX (15-25)', -1: 'Low VIX (<15)'}
                    for val, count in vix_counts.items():
                        label = vix_labels.get(val, f'Unknown ({val})')
                        print(f"  {label}: {count:,} breaks ({count/len(train_breaks):.1%})")

                if 'sp500_trend' in available_regime_cols:
                    sp_counts = train_breaks['sp500_trend'].value_counts()
                    sp_labels = {1: 'S&P Uptrend', -1: 'S&P Downtrend'}
                    for val, count in sp_counts.items():
                        label = sp_labels.get(val, f'Unknown ({val})')
                        print(f"  {label}: {count:,} breaks ({count/len(train_breaks):.1%})")

            # Layer B: Calculate indicators on market instruments
            print("\nCalculating indicators on market instruments...")
            market_indicator_data = calculate_market_instrument_indicators(market_data)
        else:
            print("\nWarning: No market data available. Proceeding without market features.")

    # ═══════════════════════════════════════════════════════════════════
    # LOAD DARK POOL & CBOE CONTEXT
    # ═══════════════════════════════════════════════════════════════════
    dp_context = None
    cboe_ctx = None

    if include_darkpool:
        try:
            from .darkpool_options_analysis import batch_load_darkpool_context
            print("\nLoading dark pool context...")
            dp_context = batch_load_darkpool_context()
            if dp_context is not None:
                # Compute overlap with training breaks
                dp_tickers = set(dp_context['ticker'].unique())
                train_tickers_set = set(train_breaks['ticker'].unique())
                overlap = dp_tickers & train_tickers_set
                print(f"  Dark pool tickers overlapping with training: {len(overlap)}/{len(train_tickers_set)}")
        except Exception as e:
            print(f"\nWarning: Could not load dark pool context: {e}")

    if include_cboe:
        try:
            from .darkpool_options_analysis import batch_load_cboe_context
            print("\nLoading CBOE P/C ratio context...")
            cboe_ctx = batch_load_cboe_context()
            if cboe_ctx is not None:
                # Compute date overlap with training breaks
                # Normalize timestamps to tz-naive for comparison
                break_ts = pd.to_datetime(all_breaks['timestamp']).dt.tz_localize(None)
                break_min = break_ts.min()
                break_max = break_ts.max()
                cboe_min = cboe_ctx.index.min()
                cboe_max = cboe_ctx.index.max()
                overlap_start = max(break_min, cboe_min)
                overlap_end = min(break_max, cboe_max)
                if overlap_start < overlap_end:
                    breaks_in_range = len(all_breaks[
                        (break_ts >= overlap_start) &
                        (break_ts <= overlap_end)
                    ])
                    print(f"  CBOE date overlap: {overlap_start.date()} to {overlap_end.date()}")
                    print(f"  Breaks in CBOE range: {breaks_in_range:,}/{len(all_breaks):,}")
                else:
                    print(f"  Warning: No date overlap between CBOE ({cboe_min.date()}-{cboe_max.date()}) "
                          f"and breaks ({break_min.date()}-{break_max.date()})")
        except Exception as e:
            print(f"\nWarning: Could not load CBOE context: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # TEST INDICATOR ACCURACY
    # ═══════════════════════════════════════════════════════════════════

    # Aggregate indicator accuracy across all tickers
    aggregate_results = {}
    processed_tickers = 0

    # Get unique tickers in training set
    train_tickers = train_breaks['ticker'].unique()
    print(f"\nProcessing {len(train_tickers)} tickers for indicator accuracy...")

    for ticker in train_tickers:
        ticker_breaks = train_breaks[train_breaks['ticker'] == ticker]

        if len(ticker_breaks) < 10:
            continue

        results = test_indicator_accuracy_at_breaks(
            ticker, ticker_breaks, lookback_periods, timeframe,
            market_indicator_data=market_indicator_data,
            darkpool_context=dp_context,
            cboe_context=cboe_ctx
        )

        # Aggregate results - handles both stock and market indicator structures
        for indicator, data in results.items():
            if indicator not in aggregate_results:
                aggregate_results[indicator] = {
                    'total_breaks': 0,
                    'binary_correct': {p: 0 for p in lookback_periods},
                    'direction_correct': {p: 0 for p in lookback_periods},
                    'extreme_detected': {p: 0 for p in lookback_periods},
                    'divergence_detected': {p: 0 for p in lookback_periods},
                    'crossover_detected': {p: 0 for p in lookback_periods},
                    'accuracy_by_lookback': {p: 0.0 for p in lookback_periods}
                }
                # Preserve market indicator flag
                if data.get('is_market_indicator'):
                    aggregate_results[indicator]['is_market_indicator'] = True

            aggregate_results[indicator]['total_breaks'] += data['total_breaks']
            for p in lookback_periods:
                aggregate_results[indicator]['binary_correct'][p] += data.get('binary_correct', {}).get(p, 0)
                aggregate_results[indicator]['direction_correct'][p] += data.get('direction_correct', {}).get(p, 0)
                aggregate_results[indicator]['extreme_detected'][p] += data.get('extreme_detected', {}).get(p, 0)
                aggregate_results[indicator]['divergence_detected'][p] += data.get('divergence_detected', {}).get(p, 0)
                aggregate_results[indicator]['crossover_detected'][p] += data.get('crossover_detected', {}).get(p, 0)

            # Accumulate dark pool and CBOE context values for averaging later
            if 'dp_amplification' in data:
                if '_dp_values' not in aggregate_results[indicator]:
                    aggregate_results[indicator]['_dp_values'] = []
                aggregate_results[indicator]['_dp_values'].append({
                    'amp': data['dp_amplification'],
                    'zscore': data['dp_volume_zscore'],
                    'conc': data['dp_concentration'],
                    'n': data['total_breaks']
                })
            if 'cboe_pcr_zscore' in data:
                if '_cboe_values' not in aggregate_results[indicator]:
                    aggregate_results[indicator]['_cboe_values'] = []
                aggregate_results[indicator]['_cboe_values'].append({
                    'pcr_z': data['cboe_pcr_zscore'],
                    'regime': data['cboe_pcr_regime'],
                    'vol_z': data['cboe_volume_zscore'],
                    'pcr': data['cboe_total_pcr'],
                    'n': data['total_breaks']
                })

        processed_tickers += 1
        if processed_tickers % 50 == 0:
            print(f"  Processed {processed_tickers}/{len(train_tickers)} tickers")

    # ═══════════════════════════════════════════════════════════════════
    # REGIME-SEGMENTED ACCURACY (Layer A analysis)
    # ═══════════════════════════════════════════════════════════════════
    if include_market_data and market_indicator_data and 'vix_regime' in train_breaks.columns:
        print("\nCalculating regime-segmented accuracy...")

        # Test accuracy separately for each VIX regime
        for regime_val, regime_label in [(1, 'High VIX'), (0, 'Normal VIX'), (-1, 'Low VIX')]:
            regime_breaks = train_breaks[train_breaks['vix_regime'] == regime_val]
            if len(regime_breaks) < 100:
                continue

            regime_tickers = regime_breaks['ticker'].unique()
            regime_results = {}

            for ticker in regime_tickers:
                ticker_regime_breaks = regime_breaks[regime_breaks['ticker'] == ticker]
                if len(ticker_regime_breaks) < 5:
                    continue

                results = test_indicator_accuracy_at_breaks(
                    ticker, ticker_regime_breaks, lookback_periods, timeframe,
                    market_indicator_data=market_indicator_data,
                    darkpool_context=dp_context,
                    cboe_context=cboe_ctx
                )

                for indicator, data in results.items():
                    if indicator not in regime_results:
                        regime_results[indicator] = {
                            'total_breaks': 0,
                            'direction_correct': {p: 0 for p in lookback_periods},
                            'extreme_detected': {p: 0 for p in lookback_periods},
                        }
                    regime_results[indicator]['total_breaks'] += data['total_breaks']
                    for p in lookback_periods:
                        regime_results[indicator]['direction_correct'][p] += data.get('direction_correct', {}).get(p, 0)
                        regime_results[indicator]['extreme_detected'][p] += data.get('extreme_detected', {}).get(p, 0)

            # Store regime results in aggregate
            for indicator, data in regime_results.items():
                total = data['total_breaks']
                if total > 0 and indicator in aggregate_results:
                    best_dir = max(data['direction_correct'][p] / total for p in lookback_periods)
                    best_ext = max(data['extreme_detected'][p] / total for p in lookback_periods)
                    aggregate_results[indicator][f'regime_{regime_label}_direction'] = best_dir
                    aggregate_results[indicator][f'regime_{regime_label}_extreme'] = best_ext
                    aggregate_results[indicator][f'regime_{regime_label}_breaks'] = total

    # ═══════════════════════════════════════════════════════════════════
    # CBOE P/C REGIME-SEGMENTED ACCURACY
    # ═══════════════════════════════════════════════════════════════════
    if include_cboe and cboe_ctx is not None:
        print("\nCalculating CBOE P/C regime-segmented accuracy...")

        # Tag each break with its nearest CBOE regime
        breaks_for_pcr = train_breaks.copy()
        breaks_for_pcr['timestamp_dt'] = pd.to_datetime(breaks_for_pcr['timestamp']).dt.tz_localize(None)
        cboe_regimes = cboe_ctx[['pcr_regime']].copy()
        cboe_regimes.index = pd.to_datetime(cboe_regimes.index)

        merged_pcr = pd.merge_asof(
            breaks_for_pcr.sort_values('timestamp_dt'),
            cboe_regimes.reset_index().rename(columns={'trade_date': 'cboe_date'}),
            left_on='timestamp_dt',
            right_on='cboe_date',
            direction='backward',
            tolerance=pd.Timedelta('5 days')
        )

        pcr_regime_labels = {-2: 'Very Bullish PCR', -1: 'Bullish PCR', 0: 'Neutral PCR',
                             1: 'Bearish PCR', 2: 'Very Bearish PCR'}

        for regime_val, regime_label in pcr_regime_labels.items():
            regime_breaks = merged_pcr[merged_pcr['pcr_regime'] == regime_val]
            if len(regime_breaks) < 100:
                continue

            regime_tickers = regime_breaks['ticker'].unique()
            regime_results = {}

            for ticker in regime_tickers:
                ticker_regime_breaks = regime_breaks[regime_breaks['ticker'] == ticker]
                if len(ticker_regime_breaks) < 5:
                    continue

                results = test_indicator_accuracy_at_breaks(
                    ticker, ticker_regime_breaks, lookback_periods, timeframe,
                    market_indicator_data=market_indicator_data,
                    darkpool_context=dp_context,
                    cboe_context=cboe_ctx
                )

                for indicator, data in results.items():
                    if indicator not in regime_results:
                        regime_results[indicator] = {
                            'total_breaks': 0,
                            'direction_correct': {p: 0 for p in lookback_periods},
                            'extreme_detected': {p: 0 for p in lookback_periods},
                        }
                    regime_results[indicator]['total_breaks'] += data['total_breaks']
                    for p in lookback_periods:
                        regime_results[indicator]['direction_correct'][p] += data.get('direction_correct', {}).get(p, 0)
                        regime_results[indicator]['extreme_detected'][p] += data.get('extreme_detected', {}).get(p, 0)

            # Store PCR regime results in aggregate
            for indicator, data in regime_results.items():
                total = data['total_breaks']
                if total > 0 and indicator in aggregate_results:
                    best_dir = max(data['direction_correct'][p] / total for p in lookback_periods)
                    best_ext = max(data['extreme_detected'][p] / total for p in lookback_periods)
                    aggregate_results[indicator][f'regime_{regime_label}_direction'] = best_dir
                    aggregate_results[indicator][f'regime_{regime_label}_extreme'] = best_ext
                    aggregate_results[indicator][f'regime_{regime_label}_breaks'] = total

            print(f"  {regime_label}: {len(regime_breaks):,} breaks processed")

    # ═══════════════════════════════════════════════════════════════════
    # AGGREGATE DARK POOL & CBOE CONTEXT VALUES
    # ═══════════════════════════════════════════════════════════════════
    for indicator, data in aggregate_results.items():
        # Weighted average of dark pool values across tickers
        if '_dp_values' in data:
            dp_vals = data['_dp_values']
            total_n = sum(v['n'] for v in dp_vals)
            if total_n > 0:
                data['dp_amplification'] = sum(v['amp'] * v['n'] for v in dp_vals) / total_n
                data['dp_volume_zscore'] = sum(v['zscore'] * v['n'] for v in dp_vals) / total_n
                data['dp_concentration'] = sum(v['conc'] * v['n'] for v in dp_vals) / total_n
            del data['_dp_values']

        # Weighted average of CBOE values across tickers
        if '_cboe_values' in data:
            cb_vals = data['_cboe_values']
            total_n = sum(v['n'] for v in cb_vals)
            if total_n > 0:
                data['cboe_pcr_zscore'] = sum(v['pcr_z'] * v['n'] for v in cb_vals) / total_n
                data['cboe_pcr_regime'] = int(round(sum(v['regime'] * v['n'] for v in cb_vals) / total_n))
                data['cboe_volume_zscore'] = sum(v['vol_z'] * v['n'] for v in cb_vals) / total_n
                data['cboe_total_pcr'] = sum(v['pcr'] * v['n'] for v in cb_vals) / total_n
            del data['_cboe_values']

    # Calculate final accuracy percentages with composite score
    for indicator, data in aggregate_results.items():
        total = data['total_breaks']
        if total > 0:
            for p in lookback_periods:
                binary_acc = data['binary_correct'][p] / total
                direction_acc = data['direction_correct'][p] / total
                extreme_acc = data['extreme_detected'][p] / total
                divergence_acc = data['divergence_detected'][p] / total
                crossover_acc = data['crossover_detected'][p] / total

                # Composite score (weighted)
                composite = (
                    binary_acc * 0.15 +
                    direction_acc * 0.30 +
                    extreme_acc * 0.25 +
                    divergence_acc * 0.15 +
                    crossover_acc * 0.15
                )
                data['accuracy_by_lookback'][p] = composite

                # Store individual scores
                data[f'binary_{p}'] = binary_acc
                data[f'direction_{p}'] = direction_acc
                data[f'extreme_{p}'] = extreme_acc
                data[f'divergence_{p}'] = divergence_acc
                data[f'crossover_{p}'] = crossover_acc

    return train_breaks, val_breaks, aggregate_results, market_regime_df


def analyze_indicator_accuracy(
    results: Dict,
    target_accuracy: float = 0.85,
    lookback_periods: List[int] = [1, 2, 3, 5, 8, 13]
) -> pd.DataFrame:
    """
    Analyze indicator accuracy results and create a summary report.

    Shows breakdown by accuracy type:
    - Binary: Traditional signal accuracy
    - Direction: Continuous indicator was in correct zone
    - Extreme: Indicator at extreme before reversal
    - Divergence: Indicator diverged from price
    - Crossover: Crossover occurred before break

    Also includes regime-segmented accuracy (High/Normal/Low VIX) and
    flags market instrument indicators separately from stock indicators.

    Args:
        results: Output from create_training_validation_datasets
        target_accuracy: Target accuracy to highlight
        lookback_periods: Lookback periods to analyze

    Returns:
        DataFrame with indicator accuracy summary
    """
    rows = []

    for indicator, data in results.items():
        if data['total_breaks'] < 100:
            continue

        # Determine indicator source type
        is_market = data.get('is_market_indicator', False)
        if is_market:
            desc = f"Market instrument indicator ({indicator.split('_')[0]})"
        else:
            desc = INDICATOR_DESCRIPTIONS.get(indicator, 'Technical indicator')

        row = {
            'indicator': indicator,
            'total_breaks': data['total_breaks'],
            'description': desc,
            'indicator_type': 'market' if is_market else 'stock'
        }

        # Add composite accuracy for each lookback period
        for p in lookback_periods:
            row[f'composite_{p}p'] = data['accuracy_by_lookback'][p]

        # Add breakdown by accuracy type (use best lookback for display)
        best_lookback = None
        best_accuracy = 0
        for p in lookback_periods:
            acc = data['accuracy_by_lookback'][p]
            if acc > best_accuracy:
                best_accuracy = acc
                best_lookback = p

        row['best_lookback'] = best_lookback if best_lookback else lookback_periods[0]
        row['best_accuracy'] = best_accuracy

        # Get component scores at best lookback
        if best_lookback:
            row['binary_acc'] = data.get(f'binary_{best_lookback}', 0)
            row['direction_acc'] = data.get(f'direction_{best_lookback}', 0)
            row['extreme_acc'] = data.get(f'extreme_{best_lookback}', 0)
            row['divergence_acc'] = data.get(f'divergence_{best_lookback}', 0)
            row['crossover_acc'] = data.get(f'crossover_{best_lookback}', 0)

        row['meets_target'] = best_accuracy >= target_accuracy

        # Add regime-segmented accuracy if available
        for regime_label in ['High VIX', 'Normal VIX', 'Low VIX']:
            dir_key = f'regime_{regime_label}_direction'
            ext_key = f'regime_{regime_label}_extreme'
            breaks_key = f'regime_{regime_label}_breaks'
            if dir_key in data:
                row[f'{regime_label}_direction'] = data[dir_key]
                row[f'{regime_label}_extreme'] = data[ext_key]
                row[f'{regime_label}_breaks'] = data[breaks_key]

        # Add CBOE P/C regime-segmented accuracy if available
        for regime_label in ['Very Bullish PCR', 'Bullish PCR', 'Neutral PCR', 'Bearish PCR', 'Very Bearish PCR']:
            dir_key = f'regime_{regime_label}_direction'
            ext_key = f'regime_{regime_label}_extreme'
            breaks_key = f'regime_{regime_label}_breaks'
            if dir_key in data:
                row[f'{regime_label}_direction'] = data[dir_key]
                row[f'{regime_label}_extreme'] = data[ext_key]
                row[f'{regime_label}_breaks'] = data[breaks_key]

        # Add dark pool context if available
        if 'dp_amplification' in data:
            row['dp_amplification'] = data['dp_amplification']
            row['dp_volume_zscore'] = data['dp_volume_zscore']
        # Add CBOE context if available
        if 'cboe_pcr_zscore' in data:
            row['cboe_pcr_zscore'] = data['cboe_pcr_zscore']
            row['cboe_pcr_regime'] = data['cboe_pcr_regime']
            row['cboe_volume_zscore'] = data['cboe_volume_zscore']

        rows.append(row)

    df = pd.DataFrame(rows)
    if len(df) > 0:
        df = df.sort_values('best_accuracy', ascending=False)

    return df


# ════════════════════════════════════════════════════════════════════════════
# MODEL TRAINING
# ════════════════════════════════════════════════════════════════════════════

def train_on_trend_breaks(
    n_samples: int = 100000,
    timeframe: str = 'daily',
    target_accuracy: float = 0.85,
    include_market_data: bool = True,
    include_darkpool: bool = True,
    include_cboe: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Train and evaluate indicator accuracy on trend breaks.

    This is the main entry point for training on N trend break samples.

    When include_market_data=True, also tests market instrument indicators
    (S&P 500, VIX, futures) and produces regime-segmented accuracy reports.

    When include_darkpool=True, applies dark pool volume amplification to
    composite accuracy scores for tickers with elevated DP activity.

    When include_cboe=True, stores CBOE P/C ratio sentiment context and
    produces regime-segmented accuracy by P/C ratio regime.

    Args:
        n_samples: Number of trend break samples to use
        timeframe: 'daily', '1hour', '5min'
        target_accuracy: Target accuracy threshold (default 85%)
        include_market_data: If True, incorporate market instruments into analysis
        include_darkpool: If True, apply dark pool volume amplification
        include_cboe: If True, integrate CBOE P/C ratio sentiment

    Returns:
        Dict containing results, accuracy summary, and recommendations
    """
    print("\n" + "="*80)
    print(f"TRAINING ON {n_samples:,} TREND BREAKS ({timeframe.upper()})")
    if include_market_data:
        print("WITH MARKET INSTRUMENTS (S&P 500, VIX, Futures, Inverse ETFs)")
    if include_darkpool:
        print("WITH DARK POOL AMPLIFICATION")
    if include_cboe:
        print("WITH CBOE P/C RATIO SENTIMENT")
    print("="*80)

    # Create datasets
    train_df, val_df, indicator_results, market_regime_df = create_training_validation_datasets(
        timeframe=timeframe,
        train_ratio=0.8,
        max_samples=n_samples,
        target_accuracy=target_accuracy,
        include_market_data=include_market_data,
        include_darkpool=include_darkpool,
        include_cboe=include_cboe,
        start_date=start_date,
        end_date=end_date
    )

    # Analyze results
    summary_df = analyze_indicator_accuracy(
        indicator_results,
        target_accuracy=target_accuracy
    )

    # Print results
    print("\n" + "="*80)
    print("INDICATOR ACCURACY RESULTS (Ordered by Best Composite Score)")
    print("="*80)

    # Separate stock and market indicators
    stock_indicators = summary_df[summary_df['indicator_type'] == 'stock'] if 'indicator_type' in summary_df.columns else summary_df
    market_indicators = summary_df[summary_df['indicator_type'] == 'market'] if 'indicator_type' in summary_df.columns else pd.DataFrame()

    print(f"\nTotal indicators analyzed: {len(summary_df)}")
    print(f"  Stock indicators: {len(stock_indicators)}")
    print(f"  Market instrument indicators: {len(market_indicators)}")
    print(f"Indicators meeting {target_accuracy:.0%} target: {summary_df['meets_target'].sum()}")

    # ─── TOP STOCK INDICATORS ───
    print("\n" + "-"*80)
    print("TOP STOCK INDICATORS BY ACCURACY:")
    print("-"*80)
    print("\nComposite score = weighted average of:")
    print("  - Direction (30%): Continuous indicator in correct zone before break")
    print("  - Extreme (25%): Indicator at extreme value before reversal")
    print("  - Binary (15%): Traditional signal accuracy")
    print("  - Divergence (15%): Indicator diverged from price")
    print("  - Crossover (15%): Signal crossover before break")

    for idx, row in stock_indicators.head(20).iterrows():
        print(f"\n{row['indicator']}")
        print(f"  Composite Score: {row['best_accuracy']:.1%}")
        print(f"  Best lookback: {row['best_lookback']} periods before break")
        print(f"  Breakdown: Binary={row.get('binary_acc', 0):.1%} | Direction={row.get('direction_acc', 0):.1%} | "
              f"Extreme={row.get('extreme_acc', 0):.1%} | Divergence={row.get('divergence_acc', 0):.1%} | "
              f"Crossover={row.get('crossover_acc', 0):.1%}")
        print(f"  Total breaks tested: {row['total_breaks']:,}")
        desc = row.get('description', 'Technical indicator')
        print(f"  {desc[:100] if isinstance(desc, str) else 'Technical indicator'}")

    # ─── MARKET INSTRUMENT INDICATORS ───
    if len(market_indicators) > 0:
        print("\n" + "="*80)
        print("MARKET INSTRUMENT INDICATOR ACCURACY")
        print("="*80)
        print("\nThese indicators are calculated on market instruments (S&P 500, VIX, Futures)")
        print("and tested for their ability to predict individual stock trend breaks.\n")

        for idx, row in market_indicators.iterrows():
            print(f"{row['indicator']}")
            print(f"  Composite Score: {row['best_accuracy']:.1%}")
            print(f"  Best lookback: {row['best_lookback']} periods before break")
            print(f"  Breakdown: Direction={row.get('direction_acc', 0):.1%} | "
                  f"Extreme={row.get('extreme_acc', 0):.1%} | "
                  f"Divergence={row.get('divergence_acc', 0):.1%} | "
                  f"Crossover={row.get('crossover_acc', 0):.1%}")
            print(f"  Total breaks tested: {row['total_breaks']:,}")
            print()

    # Show composite accuracy by lookback period for top indicators
    print("\n" + "-"*80)
    print("COMPOSITE ACCURACY BY LOOKBACK PERIOD (Top 10 Indicators):")
    print("-"*80)

    lookback_cols = [col for col in summary_df.columns if col.startswith('composite_')]
    display_cols = ['indicator', 'indicator_type'] + lookback_cols + ['best_accuracy', 'meets_target']

    available_cols = [c for c in display_cols if c in summary_df.columns]
    if available_cols:
        print(summary_df.head(10)[available_cols].to_string(index=False))

    # Show which accuracy type works best for each indicator
    print("\n" + "-"*80)
    print("BEST ACCURACY TYPE PER INDICATOR:")
    print("-"*80)

    for idx, row in summary_df.head(10).iterrows():
        acc_types = {
            'Binary': row.get('binary_acc', 0),
            'Direction': row.get('direction_acc', 0),
            'Extreme': row.get('extreme_acc', 0),
            'Divergence': row.get('divergence_acc', 0),
            'Crossover': row.get('crossover_acc', 0)
        }
        best_type = max(acc_types, key=acc_types.get)
        best_val = acc_types[best_type]
        indicator_type = f" [{row.get('indicator_type', 'stock')}]" if row.get('indicator_type') == 'market' else ''
        print(f"  {row['indicator']}{indicator_type}: {best_type} ({best_val:.1%})")

    # ─── REGIME-SEGMENTED ACCURACY ───
    regime_cols = [c for c in summary_df.columns if 'VIX' in c and ('direction' in c or 'extreme' in c)]
    if regime_cols:
        print("\n" + "="*80)
        print("INDICATOR ACCURACY BY MARKET REGIME (VIX)")
        print("="*80)
        print("\nShows how indicator accuracy varies under different volatility environments.")
        print("Direction = continuous indicator in correct zone | Extreme = at extreme before reversal\n")

        regime_display = ['indicator', 'indicator_type']
        for regime in ['High VIX', 'Normal VIX', 'Low VIX']:
            dir_col = f'{regime}_direction'
            ext_col = f'{regime}_extreme'
            brk_col = f'{regime}_breaks'
            if dir_col in summary_df.columns:
                regime_display.extend([dir_col, ext_col, brk_col])

        available_regime = [c for c in regime_display if c in summary_df.columns]
        if available_regime:
            # Only show indicators that have regime data
            regime_data = summary_df.dropna(subset=[c for c in available_regime if c != 'indicator' and c != 'indicator_type'], how='all')
            if len(regime_data) > 0:
                print(regime_data.head(15)[available_regime].to_string(index=False, float_format='%.1%%'))

        # Best indicators per regime
        for regime in ['High VIX', 'Normal VIX', 'Low VIX']:
            dir_col = f'{regime}_direction'
            if dir_col in summary_df.columns:
                regime_sorted = summary_df.dropna(subset=[dir_col]).sort_values(dir_col, ascending=False)
                if len(regime_sorted) > 0:
                    print(f"\n  Best indicators during {regime}:")
                    for _, row in regime_sorted.head(5).iterrows():
                        itype = ' [market]' if row.get('indicator_type') == 'market' else ''
                        print(f"    {row['indicator']}{itype}: Direction={row[dir_col]:.1%}")

    # Show indicators meeting target
    target_indicators = summary_df[summary_df['meets_target']]
    print(f"\n" + "-"*80)
    print(f"INDICATORS MEETING {target_accuracy:.0%} TARGET ACCURACY:")
    print("-"*80)

    if len(target_indicators) > 0:
        for _, row in target_indicators.iterrows():
            itype = ' [market]' if row.get('indicator_type') == 'market' else ''
            print(f"  {row['indicator']}{itype}: {row['best_accuracy']:.1%} at {row['best_lookback']} periods")
    else:
        print("  No indicators currently meet the target threshold with composite score.")
        print("\n  Individual component scores may be higher - check breakdown above.")
        print("  Consider:")
        print("    - Using 'Extreme' detection for oscillators (RSI, Stoch, MFI)")
        print("    - Using 'Direction' for trend indicators (MACD, EMA)")
        print("    - Using 'Divergence' for volume indicators (OBV)")
        print("    - Combining multiple indicators (ensemble approach)")
        if include_market_data:
            print("    - Using market regime to select different indicators for different conditions")

    # ─── DARK POOL AMPLIFICATION EFFECT ───
    if include_darkpool and 'dp_amplification' in summary_df.columns:
        dp_data = summary_df.dropna(subset=['dp_amplification'])
        if len(dp_data) > 0:
            print("\n" + "="*80)
            print("DARK POOL AMPLIFICATION EFFECT")
            print("="*80)
            print("\nDark pool volume z-score amplifies composite accuracy scores.")
            print("Formula: amplification = 1.0 + max(0, z-score) * 0.15")
            print(f"\nAvg amplification factor: {dp_data['dp_amplification'].mean():.3f}")
            print(f"Avg dark pool volume z-score: {dp_data['dp_volume_zscore'].mean():.3f}")
            print(f"Indicators with DP context: {len(dp_data)}")

            # Show most amplified indicators
            amplified = dp_data[dp_data['dp_amplification'] > 1.0].sort_values('dp_amplification', ascending=False)
            if len(amplified) > 0:
                print(f"\nIndicators most boosted by dark pool activity:")
                for _, row in amplified.head(10).iterrows():
                    print(f"  {row['indicator']}: {row['dp_amplification']:.3f}x amplification "
                          f"(DP z-score: {row['dp_volume_zscore']:.2f})")

    # ─── CBOE P/C RATIO SENTIMENT CONTEXT ───
    if include_cboe and 'cboe_pcr_zscore' in summary_df.columns:
        cboe_data = summary_df.dropna(subset=['cboe_pcr_zscore'])
        if len(cboe_data) > 0:
            print("\n" + "="*80)
            print("CBOE P/C RATIO SENTIMENT CONTEXT")
            print("="*80)
            regime_labels = {-2: 'Very Bullish', -1: 'Bullish', 0: 'Neutral', 1: 'Bearish', 2: 'Very Bearish'}
            avg_regime = int(round(cboe_data['cboe_pcr_regime'].mean()))
            print(f"\nAvg P/C z-score: {cboe_data['cboe_pcr_zscore'].mean():.3f}")
            print(f"Avg P/C regime: {regime_labels.get(avg_regime, 'Unknown')} ({avg_regime})")
            print(f"Avg CBOE volume z-score: {cboe_data['cboe_volume_zscore'].mean():.3f}")

            # Show CBOE regime-segmented accuracy
            pcr_regime_cols = [c for c in summary_df.columns if 'PCR' in c and ('direction' in c or 'extreme' in c)]
            if pcr_regime_cols:
                print("\nIndicator accuracy by CBOE P/C regime:")
                for regime_label in ['Very Bearish PCR', 'Bearish PCR', 'Neutral PCR', 'Bullish PCR', 'Very Bullish PCR']:
                    dir_col = f'{regime_label}_direction'
                    if dir_col in summary_df.columns:
                        regime_sorted = summary_df.dropna(subset=[dir_col]).sort_values(dir_col, ascending=False)
                        if len(regime_sorted) > 0:
                            print(f"\n  Best indicators during {regime_label}:")
                            for _, row in regime_sorted.head(5).iterrows():
                                itype = ' [market]' if row.get('indicator_type') == 'market' else ''
                                brk_col = f'{regime_label}_breaks'
                                n_brk = int(row.get(brk_col, 0)) if brk_col in row else 0
                                print(f"    {row['indicator']}{itype}: Direction={row[dir_col]:.1%} ({n_brk:,} breaks)")

    return {
        'train_df': train_df,
        'val_df': val_df,
        'indicator_results': indicator_results,
        'summary_df': summary_df,
        'market_regime_df': market_regime_df,
        'target_accuracy': target_accuracy,
        'n_samples': n_samples,
        'include_market_data': include_market_data,
        'include_darkpool': include_darkpool,
        'include_cboe': include_cboe
    }


# ════════════════════════════════════════════════════════════════════════════
# LEGACY COMPATIBILITY: Original Functions with DB Backend
# ════════════════════════════════════════════════════════════════════════════

def create_accuracy_features_dataset(
    ticker: str,
    start_date: str,
    end_date: str,
    indicators_to_test: Optional[List[str]] = None,
    lookback_window: int = 30,
    lookahead_window: int = 30,
    step_size: int = 7,
    trend_col: str = 'Close'
) -> pd.DataFrame:
    """
    Creates the dataset for training a meta-learning model (legacy interface).
    Now uses PostgreSQL database instead of data_fetcher.
    """
    from .technical_indicators import calculate_all_indicators

    print(f"Creating accuracy features dataset for {ticker}")
    print(f"Period: {start_date} to {end_date}")

    # Get stock data from database
    data = get_stock_data_from_db(ticker, start_date, end_date)
    all_data = calculate_all_indicators(data)

    if indicators_to_test is None:
        indicators_to_test = list(INDICATOR_FUNCTIONS.keys())

    rows = []
    total_periods = (len(all_data) - lookback_window - lookahead_window) // step_size

    for period_idx, i in enumerate(range(lookback_window, len(all_data) - lookahead_window, step_size)):
        current_date = all_data.index[i]
        past_data = all_data.iloc[i-lookback_window:i]
        future_data = all_data.iloc[i:i+lookahead_window]

        try:
            features = calculate_market_regime_features(past_data, lookback_window)
            features['date'] = current_date

            future_trend_breaks = trend_break(future_data, trend_col, 'trend_direction')

            if len(future_trend_breaks) < 2:
                continue

            for indicator_name in indicators_to_test:
                try:
                    indicator_func = INDICATOR_FUNCTIONS.get(indicator_name)
                    if indicator_func is None:
                        continue

                    import pandas_ta as ta
                    indicator_data = getattr(future_data.ta, indicator_func)()

                    if isinstance(future_trend_breaks, list) and len(future_trend_breaks) >= 2:
                        breaks_df = pd.DataFrame({
                            'start_date': [future_trend_breaks[i][0] for i in range(len(future_trend_breaks)-1)],
                            'end_date': [future_trend_breaks[i+1][0] for i in range(len(future_trend_breaks)-1)],
                            'trend_direction': [future_trend_breaks[i][1] for i in range(len(future_trend_breaks)-1)]
                        })

                        accuracy_result = trend_line_break_accuracy(
                            future_data, breaks_df,
                            f"{indicator_name}_signal" if f"{indicator_name}_signal" in future_data.columns else 'Close',
                            f"{indicator_name}_hist" if f"{indicator_name}_hist" in future_data.columns else 'Close'
                        )

                        if len(accuracy_result) > 0:
                            features[f'{indicator_name}_accuracy'] = accuracy_result['accuracy'].mean()
                        else:
                            features[f'{indicator_name}_accuracy'] = None

                except Exception:
                    features[f'{indicator_name}_accuracy'] = None

            rows.append(features)

            if (period_idx + 1) % 10 == 0:
                print(f"Processed {period_idx + 1}/{total_periods} periods")

        except Exception as e:
            continue

    df = pd.DataFrame(rows)
    if len(df) > 0:
        df = df.dropna(thresh=len(df.columns) * 0.7)

    return df


def train_indicator_reliability_model(
    dataset_path: str = 'accuracy_features.csv',
    test_split_date: Optional[str] = None,
    epochs: int = 50,
    batch_size: int = 32
) -> Dict[str, Any]:
    """
    Trains a Keras neural network to predict indicator reliability (legacy interface).
    """
    try:
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import Dense, Dropout
        from tensorflow.keras.optimizers import Adam
    except ImportError:
        from keras.models import Sequential
        from keras.layers import Dense, Dropout
        from keras.optimizers import Adam

    import warnings
    warnings.filterwarnings('ignore')

    print(f"Loading dataset from {dataset_path}...")
    data = pd.read_csv(dataset_path)

    if 'date' in data.columns:
        data['date'] = pd.to_datetime(data['date'])
        data = data.sort_values('date')

    feature_cols = [col for col in data.columns if not col.endswith('_accuracy') and col != 'date']
    target_cols = [col for col in data.columns if col.endswith('_accuracy')]

    X = data[feature_cols].values
    y = data[target_cols].values
    y = np.nan_to_num(y, nan=0.5)

    if test_split_date:
        split_idx = data[data['date'] >= test_split_date].index[0]
    else:
        split_idx = int(len(X) * 0.8)

    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    model = Sequential()
    model.add(Dense(64, input_dim=X_train.shape[1], activation='relu'))
    model.add(Dropout(0.2))
    model.add(Dense(32, activation='relu'))
    model.add(Dropout(0.2))
    model.add(Dense(y_train.shape[1], activation='sigmoid'))

    model.compile(loss='mse', optimizer=Adam(learning_rate=0.001), metrics=['mae'])

    history = model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=epochs,
        batch_size=batch_size,
        verbose=1
    )

    loss, mae = model.evaluate(X_test, y_test, verbose=0)
    y_pred = model.predict(X_test, verbose=0)

    return {
        'model': model,
        'feature_cols': feature_cols,
        'target_cols': target_cols,
        'history': history,
        'test_loss': loss,
        'test_mae': mae,
        'X_test': X_test,
        'y_test': y_test,
        'y_pred': y_pred
    }


def predict_indicator_reliability(
    model,
    ticker: str,
    current_date: str,
    feature_cols: List[str],
    target_cols: List[str],
    lookback_window: int = 30
) -> Dict[str, float]:
    """
    Predicts which indicators will be reliable (legacy interface).
    Now uses PostgreSQL database.
    """
    from .technical_indicators import calculate_all_indicators

    if current_date == 'latest':
        end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
    else:
        end_date = current_date

    start_date = (pd.to_datetime(end_date) - pd.Timedelta(days=lookback_window*2)).strftime('%Y-%m-%d')

    # Use database instead of data_fetcher
    data = get_stock_data_from_db(ticker, start_date, end_date)
    all_data = calculate_all_indicators(data)

    features = calculate_market_regime_features(all_data, lookback_window)
    X = np.array([[features.get(col, 0) for col in feature_cols]])

    predictions = model.predict(X, verbose=0)[0]

    results = {}
    for i, target_col in enumerate(target_cols):
        indicator_name = target_col.replace('_accuracy', '')
        results[indicator_name] = float(predictions[i])

    return results


# ════════════════════════════════════════════════════════════════════════════
# TIMEFRAME COMPARISON ANALYSIS
# ════════════════════════════════════════════════════════════════════════════

def compare_indicators_across_timeframes(
    samples_per_timeframe: int = 100000,
    target_accuracy: float = 0.85,
    output_file: str = 'timeframe_comparison_results.csv'
) -> Dict[str, Any]:
    """
    Compare indicator performance across daily, 1hour, and 5min timeframes.

    This function trains on trend breaks from each timeframe and identifies:
    - Which indicators work best for short-term trades (5min, 1hour)
    - Which indicators work best for daily/swing trades
    - Optimal lookback periods for each timeframe

    Args:
        samples_per_timeframe: Number of samples to use per timeframe
        target_accuracy: Target accuracy threshold
        output_file: Output file for comparative results

    Returns:
        Dict with results for each timeframe and comparative analysis
    """
    timeframes = ['5min', '1hour', 'daily']
    all_results = {}

    print("\n" + "="*80)
    print("COMPREHENSIVE TIMEFRAME COMPARISON ANALYSIS")
    print("="*80)
    print(f"\nAnalyzing {samples_per_timeframe:,} trend breaks per timeframe")
    print(f"Timeframes: {', '.join(timeframes)}")
    print(f"Target accuracy: {target_accuracy:.0%}")

    for tf in timeframes:
        print(f"\n{'='*80}")
        print(f"PROCESSING TIMEFRAME: {tf.upper()}")
        print('='*80)

        try:
            results = train_on_trend_breaks(
                n_samples=samples_per_timeframe,
                timeframe=tf,
                target_accuracy=target_accuracy
            )
            all_results[tf] = results
        except Exception as e:
            print(f"Error processing {tf}: {e}")
            all_results[tf] = None

    # Generate comparative analysis
    print("\n" + "="*80)
    print("COMPARATIVE ANALYSIS - INDICATOR PERFORMANCE BY TIMEFRAME")
    print("="*80)

    # Collect all indicators
    all_indicators = set()
    for tf, result in all_results.items():
        if result and 'summary_df' in result:
            all_indicators.update(result['summary_df']['indicator'].tolist())

    # Build comparison table
    comparison_rows = []
    for indicator in sorted(all_indicators):
        row = {'indicator': indicator}

        for tf in timeframes:
            if all_results[tf] and 'summary_df' in all_results[tf]:
                df = all_results[tf]['summary_df']
                ind_row = df[df['indicator'] == indicator]
                if len(ind_row) > 0:
                    row[f'{tf}_composite'] = ind_row['best_accuracy'].values[0]
                    row[f'{tf}_direction'] = ind_row.get('direction_acc', pd.Series([0])).values[0]
                    row[f'{tf}_crossover'] = ind_row.get('crossover_acc', pd.Series([0])).values[0]
                    row[f'{tf}_lookback'] = ind_row['best_lookback'].values[0]
                else:
                    row[f'{tf}_composite'] = 0
                    row[f'{tf}_direction'] = 0
                    row[f'{tf}_crossover'] = 0
                    row[f'{tf}_lookback'] = 0

        # Calculate which timeframe this indicator works best for
        composites = {tf: row.get(f'{tf}_composite', 0) for tf in timeframes}
        row['best_timeframe'] = max(composites, key=composites.get)
        row['best_score'] = max(composites.values())

        # Classify as short-term or long-term indicator
        short_term_avg = (row.get('5min_composite', 0) + row.get('1hour_composite', 0)) / 2
        long_term_avg = row.get('daily_composite', 0)

        if short_term_avg > long_term_avg * 1.1:
            row['optimal_horizon'] = 'SHORT-TERM'
        elif long_term_avg > short_term_avg * 1.1:
            row['optimal_horizon'] = 'LONG-TERM'
        else:
            row['optimal_horizon'] = 'UNIVERSAL'

        comparison_rows.append(row)

    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df = comparison_df.sort_values('best_score', ascending=False)

    # Print results
    print("\n" + "-"*80)
    print("INDICATORS BEST FOR SHORT-TERM TRADING (5min, 1hour)")
    print("-"*80)
    short_term = comparison_df[comparison_df['optimal_horizon'] == 'SHORT-TERM'].head(10)
    for _, row in short_term.iterrows():
        print(f"\n{row['indicator']}")
        print(f"  5min: {row.get('5min_composite', 0):.1%} | "
              f"1hour: {row.get('1hour_composite', 0):.1%} | "
              f"Daily: {row.get('daily_composite', 0):.1%}")
        print(f"  Best: {row['best_timeframe']} ({row['best_score']:.1%})")

    print("\n" + "-"*80)
    print("INDICATORS BEST FOR DAILY/SWING TRADING")
    print("-"*80)
    long_term = comparison_df[comparison_df['optimal_horizon'] == 'LONG-TERM'].head(10)
    for _, row in long_term.iterrows():
        print(f"\n{row['indicator']}")
        print(f"  5min: {row.get('5min_composite', 0):.1%} | "
              f"1hour: {row.get('1hour_composite', 0):.1%} | "
              f"Daily: {row.get('daily_composite', 0):.1%}")
        print(f"  Best: {row['best_timeframe']} ({row['best_score']:.1%})")

    print("\n" + "-"*80)
    print("UNIVERSAL INDICATORS (Work well across all timeframes)")
    print("-"*80)
    universal = comparison_df[comparison_df['optimal_horizon'] == 'UNIVERSAL'].head(10)
    for _, row in universal.iterrows():
        print(f"\n{row['indicator']}")
        print(f"  5min: {row.get('5min_composite', 0):.1%} | "
              f"1hour: {row.get('1hour_composite', 0):.1%} | "
              f"Daily: {row.get('daily_composite', 0):.1%}")
        print(f"  Best: {row['best_timeframe']} ({row['best_score']:.1%})")

    # Print specific accuracy type analysis
    print("\n" + "-"*80)
    print("DIRECTION ACCURACY BY TIMEFRAME (Top 5)")
    print("-"*80)
    for tf in timeframes:
        print(f"\n{tf.upper()}:")
        col = f'{tf}_direction'
        if col in comparison_df.columns:
            top5 = comparison_df.nlargest(5, col)[['indicator', col]]
            for _, row in top5.iterrows():
                print(f"  {row['indicator']}: {row[col]:.1%}")

    print("\n" + "-"*80)
    print("CROSSOVER ACCURACY BY TIMEFRAME (Top 5)")
    print("-"*80)
    for tf in timeframes:
        print(f"\n{tf.upper()}:")
        col = f'{tf}_crossover'
        if col in comparison_df.columns:
            top5 = comparison_df.nlargest(5, col)[['indicator', col]]
            for _, row in top5.iterrows():
                print(f"  {row['indicator']}: {row[col]:.1%}")

    # Save results
    comparison_df.to_csv(output_file, index=False)
    print(f"\n\nComparative results saved to: {output_file}")

    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)

    for tf in timeframes:
        if all_results[tf] and 'summary_df' in all_results[tf]:
            df = all_results[tf]['summary_df']
            print(f"\n{tf.upper()}:")
            print(f"  Total indicators analyzed: {len(df)}")
            print(f"  Indicators >= 85% target: {(df['best_accuracy'] >= 0.85).sum()}")
            print(f"  Indicators >= 70%: {(df['best_accuracy'] >= 0.70).sum()}")
            print(f"  Average composite score: {df['best_accuracy'].mean():.1%}")
            if 'direction_acc' in df.columns:
                print(f"  Average direction accuracy: {df['direction_acc'].mean():.1%}")
            print(f"  Best indicator: {df.iloc[0]['indicator']} ({df.iloc[0]['best_accuracy']:.1%})")

    return {
        'all_results': all_results,
        'comparison_df': comparison_df,
        'timeframes': timeframes
    }


# ════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Meta-Learning Model for Indicator Selection')
    parser.add_argument('--action', choices=['train', 'test', 'full', 'compare'],
                        default='train', help='Action to perform')
    parser.add_argument('--samples', type=int, default=100000, help='Number of trend breaks to train on')
    parser.add_argument('--timeframe', default='daily', choices=['daily', '1hour', '5min'],
                        help='Timeframe for trend breaks')
    parser.add_argument('--target-accuracy', type=float, default=0.85,
                        help='Target accuracy threshold (0.0-1.0)')
    parser.add_argument('--output', default='indicator_accuracy_results.csv',
                        help='Output CSV file for results')

    args = parser.parse_args()

    if args.action == 'compare':
        # Compare indicators across all timeframes
        results = compare_indicators_across_timeframes(
            samples_per_timeframe=args.samples,
            target_accuracy=args.target_accuracy,
            output_file=args.output
        )
    elif args.action in ['train', 'full']:
        # Train on trend breaks for a single timeframe
        results = train_on_trend_breaks(
            n_samples=args.samples,
            timeframe=args.timeframe,
            target_accuracy=args.target_accuracy
        )

        # Save results
        results['summary_df'].to_csv(args.output, index=False)
        print(f"\nResults saved to {args.output}")

    print("\n" + "="*80)
    print("COMPLETE!")
    print("="*80)
