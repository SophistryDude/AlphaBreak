"""
Technical Indicators Module
============================
Calculate technical indicators using the 'ta' library.

This module uses the 'ta' (Technical Analysis) library which provides
130+ technical indicators with a simple, consistent API.

Indicator Categories:
- Momentum: RSI, Stochastic, ROC, MFI
- Trend: ADX, MACD, Supertrend, Parabolic SAR
- Volatility: Bollinger Bands, Keltner Channel, Donchian Channel, ATR
- Volume: OBV, VWAP, CMF, A/D Line, VPT, Ease of Movement
- Moving Averages: SMA, EMA, WMA, HMA

Usage:
    from src.technical_indicators import calculate_all_indicators, TechnicalIndicators
    from src.data_fetcher import get_stock_data

    data = get_stock_data('AAPL', '2020-01-01', '2024-01-01')
    data = calculate_all_indicators(data)

    # Or use the class interface
    ti = TechnicalIndicators(data)
    ti.add_all()
    result = ti.get_data()
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict, List

# ta library is the primary library
try:
    import ta as ta_lib
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    print("Warning: ta not installed. Run: pip install ta")

# Alias for backward compatibility
PANDAS_TA_AVAILABLE = TA_AVAILABLE


# ════════════════════════════════════════════════════════════════════════════
# INDICATOR MAPPING - Maps short names to pandas_ta functions
# ════════════════════════════════════════════════════════════════════════════

INDICATOR_FUNCTIONS = {
    # Trend Indicators
    'MACD': 'macd',
    'ADX': 'adx',
    'Supertrend': 'supertrend',
    'Parabolic_SAR': 'psar',
    'Aroon': 'aroon',
    'CCI': 'cci',

    # Momentum Indicators
    'RSI': 'rsi',
    'Stochastic': 'stoch',
    'ROC': 'roc',
    'MOM': 'mom',
    'Williams_R': 'willr',
    'Ultimate_Osc': 'uo',

    # Volume Indicators
    'OBV': 'obv',
    'VWAP': 'vwap',
    'CMF': 'cmf',
    'MFI': 'mfi',
    'AD': 'ad',
    'VPT': 'pvt',  # Note: pandas_ta uses 'pvt' for Price Volume Trend
    'EOM': 'eom',

    # Volatility Indicators
    'BBands': 'bbands',
    'Keltner': 'kc',
    'Donchian': 'donchian',
    'ATR': 'atr',

    # Moving Averages
    'SMA': 'sma',
    'EMA': 'ema',
    'WMA': 'wma',
    'HMA': 'hma',
    'DEMA': 'dema',
    'TEMA': 'tema',
}


# ════════════════════════════════════════════════════════════════════════════
# MOMENTUM INDICATORS (using ta library)
# ════════════════════════════════════════════════════════════════════════════

def calculate_rsi(data: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """
    Calculate Relative Strength Index (RSI) using ta library.

    Args:
        data: DataFrame with 'Close' column
        length: RSI period (default: 14)

    Returns:
        DataFrame with RSI column added

    Interpretation:
        - RSI > 70: Overbought
        - RSI < 30: Oversold

    Example:
        >>> data = calculate_rsi(data, length=14)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required. Run: pip install ta")

    data = data.copy()
    data['RSI'] = ta_lib.momentum.RSIIndicator(data['Close'], window=length).rsi()
    return data


def calculate_stochastic(
    data: pd.DataFrame,
    k: int = 14,
    d: int = 3,
    smooth_k: int = 3
) -> pd.DataFrame:
    """
    Calculate Stochastic Oscillator using ta library.

    Args:
        data: DataFrame with High, Low, Close columns
        k: %K period (default: 14)
        d: %D period (default: 3)
        smooth_k: %K smoothing (default: 3)

    Returns:
        DataFrame with STOCHk and STOCHd columns added

    Example:
        >>> data = calculate_stochastic(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    stoch = ta_lib.momentum.StochasticOscillator(
        data['High'], data['Low'], data['Close'],
        window=k, smooth_window=d
    )
    data['STOCHk'] = stoch.stoch()
    data['STOCHd'] = stoch.stoch_signal()
    return data


def calculate_roc(data: pd.DataFrame, length: int = 12) -> pd.DataFrame:
    """
    Calculate Rate of Change (ROC) using ta library.

    Args:
        data: DataFrame with 'Close' column
        length: ROC period (default: 12)

    Returns:
        DataFrame with ROC column added

    Example:
        >>> data = calculate_roc(data, length=12)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data['ROC'] = ta_lib.momentum.ROCIndicator(data['Close'], window=length).roc()
    return data


def calculate_mfi(data: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """
    Calculate Money Flow Index (MFI) using ta library.

    MFI is a volume-weighted RSI.

    Args:
        data: DataFrame with High, Low, Close, Volume columns
        length: MFI period (default: 14)

    Returns:
        DataFrame with MFI column added

    Interpretation:
        - MFI > 80: Overbought
        - MFI < 20: Oversold

    Example:
        >>> data = calculate_mfi(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data['MFI'] = ta_lib.volume.MFIIndicator(
        data['High'], data['Low'], data['Close'], data['Volume'],
        window=length
    ).money_flow_index()
    return data


def calculate_williams_r(data: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """
    Calculate Williams %R using ta library.

    Args:
        data: DataFrame with High, Low, Close columns
        length: Period (default: 14)

    Returns:
        DataFrame with WILLR column added

    Example:
        >>> data = calculate_williams_r(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data['WILLR'] = ta_lib.momentum.WilliamsRIndicator(
        data['High'], data['Low'], data['Close'], lbp=length
    ).williams_r()
    return data


def calculate_cci(data: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """
    Calculate Commodity Channel Index (CCI) using ta library.

    Args:
        data: DataFrame with High, Low, Close columns
        length: Period (default: 20)

    Returns:
        DataFrame with CCI column added

    Example:
        >>> data = calculate_cci(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data['CCI'] = ta_lib.trend.CCIIndicator(
        data['High'], data['Low'], data['Close'], window=length
    ).cci()
    return data


# ════════════════════════════════════════════════════════════════════════════
# TREND INDICATORS (using ta library)
# ════════════════════════════════════════════════════════════════════════════

def calculate_adx(data: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """
    Calculate Average Directional Index (ADX) using ta library.

    Args:
        data: DataFrame with High, Low, Close columns
        length: ADX period (default: 14)

    Returns:
        DataFrame with ADX, PDI (Plus DI), NDI (Minus DI) columns added

    Interpretation:
        - ADX > 25: Strong trend
        - ADX < 20: Weak trend
        - PDI > NDI: Uptrend
        - NDI > PDI: Downtrend

    Example:
        >>> data = calculate_adx(data, length=14)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    adx_indicator = ta_lib.trend.ADXIndicator(
        data['High'], data['Low'], data['Close'], window=length
    )
    data['ADX'] = adx_indicator.adx()
    data['PDI'] = adx_indicator.adx_pos()
    data['NDI'] = adx_indicator.adx_neg()

    return data


def calculate_macd(
    data: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> pd.DataFrame:
    """
    Calculate MACD using ta library.

    Args:
        data: DataFrame with 'Close' column
        fast: Fast EMA period (default: 12)
        slow: Slow EMA period (default: 26)
        signal: Signal line period (default: 9)

    Returns:
        DataFrame with MACD, Signal_Line, Histogram columns added

    Example:
        >>> data = calculate_macd(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    macd_indicator = ta_lib.trend.MACD(
        data['Close'], window_slow=slow, window_fast=fast, window_sign=signal
    )
    data['MACD'] = macd_indicator.macd()
    data['Signal_Line'] = macd_indicator.macd_signal()
    data['Histogram'] = macd_indicator.macd_diff()

    return data


def calculate_supertrend(
    data: pd.DataFrame,
    length: int = 7,
    multiplier: float = 3.0
) -> pd.DataFrame:
    """
    Calculate Supertrend indicator.

    Note: ta library doesn't have Supertrend, so we implement it manually.

    Args:
        data: DataFrame with High, Low, Close columns
        length: ATR period (default: 7)
        multiplier: ATR multiplier (default: 3.0)

    Returns:
        DataFrame with Supertrend and Supertrend_Direction columns

    Example:
        >>> data = calculate_supertrend(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()

    # Calculate ATR
    atr = ta_lib.volatility.AverageTrueRange(
        data['High'], data['Low'], data['Close'], window=length
    ).average_true_range()

    # Calculate basic upper and lower bands
    hl2 = (data['High'] + data['Low']) / 2
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    # Initialize Supertrend
    supertrend = pd.Series(index=data.index, dtype=float)
    direction = pd.Series(index=data.index, dtype=int)

    for i in range(length, len(data)):
        if data['Close'].iloc[i] > upper_band.iloc[i-1]:
            supertrend.iloc[i] = lower_band.iloc[i]
            direction.iloc[i] = 1
        elif data['Close'].iloc[i] < lower_band.iloc[i-1]:
            supertrend.iloc[i] = upper_band.iloc[i]
            direction.iloc[i] = -1
        else:
            if direction.iloc[i-1] == 1:
                supertrend.iloc[i] = max(lower_band.iloc[i], supertrend.iloc[i-1])
                direction.iloc[i] = 1
            else:
                supertrend.iloc[i] = min(upper_band.iloc[i], supertrend.iloc[i-1])
                direction.iloc[i] = -1

    data['Supertrend'] = supertrend
    data['Supertrend_Direction'] = direction
    return data


def calculate_psar(data: pd.DataFrame, af0: float = 0.02, af: float = 0.02, max_af: float = 0.2) -> pd.DataFrame:
    """
    Calculate Parabolic SAR using ta library.

    Args:
        data: DataFrame with High, Low, Close columns
        af0: Initial acceleration factor (default: 0.02)
        af: Acceleration factor increment (default: 0.02)
        max_af: Maximum acceleration factor (default: 0.2)

    Returns:
        DataFrame with PSAR column

    Example:
        >>> data = calculate_psar(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    psar_indicator = ta_lib.trend.PSARIndicator(
        data['High'], data['Low'], data['Close'],
        step=af, max_step=max_af
    )
    data['PSAR'] = psar_indicator.psar()
    data['PSAR_Up'] = psar_indicator.psar_up()
    data['PSAR_Down'] = psar_indicator.psar_down()
    return data


def calculate_aroon(data: pd.DataFrame, length: int = 25) -> pd.DataFrame:
    """
    Calculate Aroon indicator using ta library.

    Args:
        data: DataFrame with High, Low columns
        length: Period (default: 25)

    Returns:
        DataFrame with Aroon_Up, Aroon_Down, Aroon_Indicator columns

    Example:
        >>> data = calculate_aroon(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    aroon_indicator = ta_lib.trend.AroonIndicator(data['Close'], window=length)
    data['Aroon_Up'] = aroon_indicator.aroon_up()
    data['Aroon_Down'] = aroon_indicator.aroon_down()
    data['Aroon_Indicator'] = aroon_indicator.aroon_indicator()
    return data


# ════════════════════════════════════════════════════════════════════════════
# VOLUME INDICATORS (using ta library)
# ════════════════════════════════════════════════════════════════════════════

def calculate_obv(data: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate On-Balance Volume (OBV) using ta library.

    Args:
        data: DataFrame with Close, Volume columns

    Returns:
        DataFrame with OBV column added

    Example:
        >>> data = calculate_obv(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data['OBV'] = ta_lib.volume.OnBalanceVolumeIndicator(
        data['Close'], data['Volume']
    ).on_balance_volume()
    return data


def calculate_vwap(data: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Volume Weighted Average Price (VWAP) using ta library.

    Args:
        data: DataFrame with High, Low, Close, Volume columns

    Returns:
        DataFrame with VWAP column added

    Example:
        >>> data = calculate_vwap(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data['VWAP'] = ta_lib.volume.VolumeWeightedAveragePrice(
        data['High'], data['Low'], data['Close'], data['Volume']
    ).volume_weighted_average_price()
    return data


def calculate_cmf(data: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """
    Calculate Chaikin Money Flow (CMF) using ta library.

    Args:
        data: DataFrame with High, Low, Close, Volume columns
        length: Period (default: 20)

    Returns:
        DataFrame with CMF column added

    Example:
        >>> data = calculate_cmf(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data['CMF'] = ta_lib.volume.ChaikinMoneyFlowIndicator(
        data['High'], data['Low'], data['Close'], data['Volume'], window=length
    ).chaikin_money_flow()
    return data


def calculate_ad(data: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Accumulation/Distribution Line using ta library.

    Args:
        data: DataFrame with High, Low, Close, Volume columns

    Returns:
        DataFrame with AD column added

    Example:
        >>> data = calculate_ad(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data['AD'] = ta_lib.volume.AccDistIndexIndicator(
        data['High'], data['Low'], data['Close'], data['Volume']
    ).acc_dist_index()
    return data


def calculate_vpt(data: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Volume Price Trend (VPT) using manual calculation.

    Args:
        data: DataFrame with Close, Volume columns

    Returns:
        DataFrame with VPT column added

    Example:
        >>> data = calculate_vpt(data)
    """
    data = data.copy()
    # VPT = Previous VPT + Volume * ((Close - Previous Close) / Previous Close)
    pct_change = data['Close'].pct_change()
    data['VPT'] = (data['Volume'] * pct_change).cumsum()
    return data


def calculate_eom(data: pd.DataFrame, length: int = 14, divisor: int = 100000000) -> pd.DataFrame:
    """
    Calculate Ease of Movement (EOM) using ta library.

    Args:
        data: DataFrame with High, Low, Volume columns
        length: Period (default: 14)
        divisor: Divisor for calculation

    Returns:
        DataFrame with EOM column added

    Example:
        >>> data = calculate_eom(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data['EOM'] = ta_lib.volume.EaseOfMovementIndicator(
        data['High'], data['Low'], data['Volume'], window=length
    ).ease_of_movement()
    return data


# ════════════════════════════════════════════════════════════════════════════
# VOLATILITY INDICATORS (using ta library)
# ════════════════════════════════════════════════════════════════════════════

def calculate_bbands(data: pd.DataFrame, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    """
    Calculate Bollinger Bands using ta library.

    Args:
        data: DataFrame with 'Close' column
        length: MA period (default: 20)
        std: Standard deviation multiplier (default: 2.0)

    Returns:
        DataFrame with BB_Lower, BB_Middle, BB_Upper columns

    Example:
        >>> data = calculate_bbands(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    bb_indicator = ta_lib.volatility.BollingerBands(
        data['Close'], window=length, window_dev=int(std)
    )
    data['BB_Lower'] = bb_indicator.bollinger_lband()
    data['BB_Middle'] = bb_indicator.bollinger_mavg()
    data['BB_Upper'] = bb_indicator.bollinger_hband()
    data['BB_Width'] = bb_indicator.bollinger_wband()
    data['BB_Pct'] = bb_indicator.bollinger_pband()

    return data


def calculate_keltner(data: pd.DataFrame, length: int = 20, scalar: float = 2.0) -> pd.DataFrame:
    """
    Calculate Keltner Channel using ta library.

    Args:
        data: DataFrame with High, Low, Close columns
        length: EMA period (default: 20)
        scalar: ATR multiplier (default: 2.0)

    Returns:
        DataFrame with KC_Lower, KC_Middle, KC_Upper columns

    Example:
        >>> data = calculate_keltner(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    kc_indicator = ta_lib.volatility.KeltnerChannel(
        data['High'], data['Low'], data['Close'], window=length, window_atr=length
    )
    data['KC_Lower'] = kc_indicator.keltner_channel_lband()
    data['KC_Middle'] = kc_indicator.keltner_channel_mband()
    data['KC_Upper'] = kc_indicator.keltner_channel_hband()
    return data


def calculate_donchian(data: pd.DataFrame, lower_length: int = 20, upper_length: int = 20) -> pd.DataFrame:
    """
    Calculate Donchian Channel using ta library.

    Args:
        data: DataFrame with High, Low columns
        lower_length: Lower band period (default: 20)
        upper_length: Upper band period (default: 20)

    Returns:
        DataFrame with DC_Lower, DC_Middle, DC_Upper columns

    Example:
        >>> data = calculate_donchian(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    dc_indicator = ta_lib.volatility.DonchianChannel(
        data['High'], data['Low'], data['Close'], window=upper_length
    )
    data['DC_Lower'] = dc_indicator.donchian_channel_lband()
    data['DC_Middle'] = dc_indicator.donchian_channel_mband()
    data['DC_Upper'] = dc_indicator.donchian_channel_hband()
    return data


def calculate_atr(data: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """
    Calculate Average True Range (ATR) using ta library.

    Args:
        data: DataFrame with High, Low, Close columns
        length: ATR period (default: 14)

    Returns:
        DataFrame with ATR column added

    Example:
        >>> data = calculate_atr(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data['ATR'] = ta_lib.volatility.AverageTrueRange(
        data['High'], data['Low'], data['Close'], window=length
    ).average_true_range()
    return data


# ════════════════════════════════════════════════════════════════════════════
# MOVING AVERAGES (using ta library)
# ════════════════════════════════════════════════════════════════════════════

def calculate_sma(data: pd.DataFrame, length: int = 20, column: str = 'Close') -> pd.DataFrame:
    """
    Calculate Simple Moving Average using ta library.

    Args:
        data: DataFrame with specified column
        length: SMA period (default: 20)
        column: Column to calculate SMA on (default: 'Close')

    Returns:
        DataFrame with SMA column added

    Example:
        >>> data = calculate_sma(data, length=50)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data[f'SMA_{length}'] = ta_lib.trend.SMAIndicator(
        data[column], window=length
    ).sma_indicator()
    return data


def calculate_ema(data: pd.DataFrame, length: int = 20, column: str = 'Close') -> pd.DataFrame:
    """
    Calculate Exponential Moving Average using ta library.

    Args:
        data: DataFrame with specified column
        length: EMA period (default: 20)
        column: Column to calculate EMA on (default: 'Close')

    Returns:
        DataFrame with EMA column added

    Example:
        >>> data = calculate_ema(data, length=50)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data[f'EMA_{length}'] = ta_lib.trend.EMAIndicator(
        data[column], window=length
    ).ema_indicator()
    return data


def calculate_wma(data: pd.DataFrame, length: int = 20, column: str = 'Close') -> pd.DataFrame:
    """
    Calculate Weighted Moving Average using ta library.
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()
    data[f'WMA_{length}'] = ta_lib.trend.WMAIndicator(
        data[column], window=length
    ).wma()
    return data


def calculate_hma(data: pd.DataFrame, length: int = 20, column: str = 'Close') -> pd.DataFrame:
    """
    Calculate Hull Moving Average.

    Note: ta library doesn't have HMA, so we calculate manually.
    HMA = WMA(2*WMA(n/2) - WMA(n)), sqrt(n))
    """
    data = data.copy()

    half_length = int(length / 2)
    sqrt_length = int(np.sqrt(length))

    # Calculate WMA components
    wma_half = data[column].rolling(window=half_length).apply(
        lambda x: np.sum(np.arange(1, half_length + 1) * x) / np.sum(np.arange(1, half_length + 1))
    )
    wma_full = data[column].rolling(window=length).apply(
        lambda x: np.sum(np.arange(1, length + 1) * x) / np.sum(np.arange(1, length + 1))
    )

    raw_hma = 2 * wma_half - wma_full
    data[f'HMA_{length}'] = raw_hma.rolling(window=sqrt_length).apply(
        lambda x: np.sum(np.arange(1, sqrt_length + 1) * x) / np.sum(np.arange(1, sqrt_length + 1))
    )
    return data


# ════════════════════════════════════════════════════════════════════════════
# ALL-IN-ONE FUNCTION
# ════════════════════════════════════════════════════════════════════════════

def calculate_all_indicators(data: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
    """
    Calculate all technical indicators using ta library.

    Args:
        data: DataFrame with Date, Open, High, Low, Close, Volume columns
        verbose: Print progress

    Returns:
        DataFrame with all indicators added

    Example:
        >>> data = calculate_all_indicators(data)
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required. Run: pip install ta")

    data = data.copy()

    indicators_to_add = [
        # Momentum
        ('RSI', lambda d: calculate_rsi(d)),
        ('Stochastic', lambda d: calculate_stochastic(d)),
        ('ROC', lambda d: calculate_roc(d)),
        ('MFI', lambda d: calculate_mfi(d)),
        ('Williams %R', lambda d: calculate_williams_r(d)),
        ('CCI', lambda d: calculate_cci(d)),

        # Trend
        ('ADX', lambda d: calculate_adx(d)),
        ('MACD', lambda d: calculate_macd(d)),
        ('Supertrend', lambda d: calculate_supertrend(d)),
        ('Parabolic SAR', lambda d: calculate_psar(d)),
        ('Aroon', lambda d: calculate_aroon(d)),

        # Volume
        ('OBV', lambda d: calculate_obv(d)),
        ('VWAP', lambda d: calculate_vwap(d)),
        ('CMF', lambda d: calculate_cmf(d)),
        ('A/D', lambda d: calculate_ad(d)),
        ('VPT', lambda d: calculate_vpt(d)),
        ('EOM', lambda d: calculate_eom(d)),

        # Volatility
        ('Bollinger Bands', lambda d: calculate_bbands(d)),
        ('Keltner Channel', lambda d: calculate_keltner(d)),
        ('Donchian Channel', lambda d: calculate_donchian(d)),
        ('ATR', lambda d: calculate_atr(d)),

        # Moving Averages
        ('SMA 20', lambda d: calculate_sma(d, 20)),
        ('SMA 50', lambda d: calculate_sma(d, 50)),
        ('SMA 200', lambda d: calculate_sma(d, 200)),
        ('EMA 12', lambda d: calculate_ema(d, 12)),
        ('EMA 26', lambda d: calculate_ema(d, 26)),
    ]

    for name, func in indicators_to_add:
        try:
            data = func(data)
            if verbose:
                print(f"  ✓ {name}")
        except Exception as e:
            if verbose:
                print(f"  ✗ {name}: {e}")

    return data


def calculate_indicators_by_category(data: pd.DataFrame, category: str = 'all') -> pd.DataFrame:
    """
    Calculate indicators by category using ta library.

    Args:
        data: DataFrame with OHLCV columns
        category: Category name - 'all', 'momentum', 'trend', 'volatility', 'volume'

    Returns:
        DataFrame with indicators added

    Example:
        >>> data = calculate_indicators_by_category(data, category='momentum')
    """
    if not TA_AVAILABLE:
        raise ImportError("ta required")

    data = data.copy()

    if category == 'all' or category == 'momentum':
        data = ta_lib.add_momentum_ta(data, high='High', low='Low', close='Close', volume='Volume')

    if category == 'all' or category == 'trend':
        data = ta_lib.add_trend_ta(data, high='High', low='Low', close='Close')

    if category == 'all' or category == 'volatility':
        data = ta_lib.add_volatility_ta(data, high='High', low='Low', close='Close')

    if category == 'all' or category == 'volume':
        data = ta_lib.add_volume_ta(data, high='High', low='Low', close='Close', volume='Volume')

    return data


# ════════════════════════════════════════════════════════════════════════════
# TECHNICAL INDICATORS CLASS
# ════════════════════════════════════════════════════════════════════════════

class TechnicalIndicators:
    """
    Class interface for technical indicators using pandas_ta.

    Example:
        >>> from src.data_fetcher import get_stock_data
        >>> data = get_stock_data('AAPL', '2020-01-01', '2024-01-01')
        >>> ti = TechnicalIndicators(data)
        >>> ti.add_all()
        >>> result = ti.get_data()
    """

    # Class-level mapping for external access
    INDICATOR_FUNCTIONS = INDICATOR_FUNCTIONS

    def __init__(self, data: pd.DataFrame):
        """Initialize with DataFrame containing OHLCV data."""
        self.data = data.copy()

    def add_rsi(self, length: int = 14):
        """Add RSI indicator."""
        self.data = calculate_rsi(self.data, length)
        return self

    def add_macd(self, fast: int = 12, slow: int = 26, signal: int = 9):
        """Add MACD indicator."""
        self.data = calculate_macd(self.data, fast, slow, signal)
        return self

    def add_adx(self, length: int = 14):
        """Add ADX indicator."""
        self.data = calculate_adx(self.data, length)
        return self

    def add_stochastic(self, k: int = 14, d: int = 3):
        """Add Stochastic oscillator."""
        self.data = calculate_stochastic(self.data, k, d)
        return self

    def add_bbands(self, length: int = 20, std: float = 2.0):
        """Add Bollinger Bands."""
        self.data = calculate_bbands(self.data, length, std)
        return self

    def add_supertrend(self, length: int = 7, multiplier: float = 3.0):
        """Add Supertrend indicator."""
        self.data = calculate_supertrend(self.data, length, multiplier)
        return self

    def add_psar(self):
        """Add Parabolic SAR."""
        self.data = calculate_psar(self.data)
        return self

    def add_obv(self):
        """Add On-Balance Volume."""
        self.data = calculate_obv(self.data)
        return self

    def add_vwap(self):
        """Add VWAP."""
        self.data = calculate_vwap(self.data)
        return self

    def add_cmf(self, length: int = 20):
        """Add Chaikin Money Flow."""
        self.data = calculate_cmf(self.data, length)
        return self

    def add_mfi(self, length: int = 14):
        """Add Money Flow Index."""
        self.data = calculate_mfi(self.data, length)
        return self

    def add_atr(self, length: int = 14):
        """Add Average True Range."""
        self.data = calculate_atr(self.data, length)
        return self

    def add_sma(self, length: int = 20):
        """Add Simple Moving Average."""
        self.data = calculate_sma(self.data, length)
        return self

    def add_ema(self, length: int = 20):
        """Add Exponential Moving Average."""
        self.data = calculate_ema(self.data, length)
        return self

    def add_all(self, verbose: bool = False):
        """Add all indicators."""
        self.data = calculate_all_indicators(self.data, verbose)
        return self

    def get_data(self) -> pd.DataFrame:
        """Return the DataFrame with indicators."""
        return self.data

    def get_all_indicators(self) -> pd.DataFrame:
        """Calculate and return all indicators (backward compatibility)."""
        return calculate_all_indicators(self.data)

    def get_indicator_columns(self) -> List[str]:
        """Return list of indicator column names."""
        ohlcv_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
        return [col for col in self.data.columns if col not in ohlcv_cols]


# ════════════════════════════════════════════════════════════════════════════
# LEGACY COMPATIBILITY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

# These maintain backward compatibility with the original SP_historical_data.py

def bollinger_bands(data: pd.DataFrame, window: int = 20) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Legacy function for backward compatibility."""
    result = calculate_bbands(data, length=window)
    return result['BB_Upper'], result['BB_Middle'], result['BB_Lower']


def on_balance_volume(data: pd.DataFrame) -> pd.Series:
    """Legacy function for backward compatibility."""
    result = calculate_obv(data)
    return result['OBV']


def chaikin_money_flow(data: pd.DataFrame, window: int = 20) -> pd.Series:
    """Legacy function for backward compatibility."""
    result = calculate_cmf(data, length=window)
    return result['CMF']


def money_flow_index(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Legacy function for backward compatibility."""
    result = calculate_mfi(data, length=period)
    return result['MFI']


def stochastic_oscillator(data: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    """Legacy function for backward compatibility."""
    return calculate_stochastic(data, k=n)


def moving_averages(
    data: pd.DataFrame,
    short: int = 7,
    long: int = 14
) -> Tuple[pd.Series, pd.Series]:
    """Legacy function for backward compatibility."""
    if TA_AVAILABLE:
        short_ma = ta_lib.trend.SMAIndicator(data['Close'], window=short).sma_indicator()
        long_ma = ta_lib.trend.SMAIndicator(data['Close'], window=long).sma_indicator()
    else:
        short_ma = data['Close'].rolling(short).mean()
        long_ma = data['Close'].rolling(long).mean()
    return short_ma, long_ma


def trend_line(data: pd.DataFrame) -> np.ndarray:
    """Calculate linear trend line for closing prices."""
    x = np.arange(len(data))
    z = np.polyfit(x, data['Close'], 1)
    p = np.poly1d(z)
    return p(x)


def volume_weighted_average_price(data: pd.DataFrame) -> pd.Series:
    """Legacy function for backward compatibility."""
    result = calculate_vwap(data)
    return result['VWAP']


def accumulation_distribution_line(data: pd.DataFrame) -> pd.Series:
    """Legacy function for backward compatibility."""
    result = calculate_ad(data)
    return result['AD']


def percent_number_of_stocks_above_moving_average(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate percentage above moving averages."""
    data = data.copy()
    if TA_AVAILABLE:
        data['MA50'] = ta_lib.trend.SMAIndicator(data['Close'], window=50).sma_indicator()
        data['MA200'] = ta_lib.trend.SMAIndicator(data['Close'], window=200).sma_indicator()
    else:
        data['MA50'] = data['Close'].rolling(50).mean()
        data['MA200'] = data['Close'].rolling(200).mean()
    data['%MA50'] = (data['Close'] / data['MA50'] - 1) * 100
    data['%MA200'] = (data['Close'] / data['MA200'] - 1) * 100
    return data[['Date', '%MA50', '%MA200']].dropna()


def periodic_high_and_lows(data: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """Calculate periodic highs and lows."""
    data = data.copy()
    data['PeriodHigh'] = data['High'].rolling(window=window, min_periods=1).max()
    data['PeriodLow'] = data['Low'].rolling(window=window, min_periods=1).min()
    data['%PeriodHigh'] = (data['Close'] / data['PeriodHigh'] - 1) * 100
    data['%PeriodLow'] = (data['Close'] / data['PeriodLow'] - 1) * 100
    return data[['Date', '%PeriodHigh', '%PeriodLow']].dropna()


def advance_decline(data: pd.DataFrame, window: int = 30) -> pd.DataFrame:
    """Calculate Advance/Decline ratio."""
    data = data.copy()
    data['Advances'] = (data['Close'] > data['Close'].shift(1)).rolling(window=window, min_periods=1).sum()
    data['Declines'] = (data['Close'] < data['Close'].shift(1)).rolling(window=window, min_periods=1).sum()
    data['%A/D'] = data['Advances'] / (data['Advances'] + data['Declines']) * 100
    return data[['Date', '%A/D']].dropna()
