"""
Options Pricing Module
=======================
Black-Scholes and Binomial Tree option pricing models.

IMPORTANT: Most US stock options are AMERICAN options (can be exercised anytime),
not European options (exercise only at expiry). Use binomial tree for American options.

Black-Scholes underprices American options, especially:
- Puts when stock price drops significantly
- Calls on dividend-paying stocks

This module contains:
- Black-Scholes pricing for European options (use for indices, some ETFs)
- Binomial tree pricing for American options (use for US stocks - RECOMMENDED)
- Greeks calculation (Delta, Gamma, Theta, Vega, Rho)
- Dynamic risk-free rate from Treasury yields
- Options fair value analysis with trend direction filtering

Usage:
    from src.options_pricing import (
        binomial_tree_american,  # Primary for US stock options
        black_scholes_call,      # European only
        option_analysis,
        get_risk_free_rate
    )

    # For US stock options - use binomial tree (American)
    price = binomial_tree_american(S=150, K=145, r=0.05, t=0.25, sigma=0.3, option_type='call')

    # Get current risk-free rate from market
    rate = get_risk_free_rate(time_to_expiry_years=0.25)

    # Full options analysis
    result = option_analysis('AAPL', '2023-01-01', '2024-01-01', 150, '2024-06-21')

Note: For intra-day swing trading, dividend adjustments are not included.
See dividend_adjustment_guide.txt for long-term holding strategies.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional, Union, List
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')


# ════════════════════════════════════════════════════════════════════════════
# DYNAMIC RISK-FREE RATE
# ════════════════════════════════════════════════════════════════════════════

def get_risk_free_rate(time_to_expiry_years: Optional[float] = None) -> float:
    """
    Retrieve current risk-free rate from Treasury yields (not hardcoded).

    Uses Treasury yields matched to option expiry period:
    - <3 months: 13-week T-bill (^IRX)
    - 3-6 months: 5-year Treasury (^FVX)
    - >6 months: 10-year Treasury (^TNX)

    Args:
        time_to_expiry_years: Time to expiry in years. If None, uses 13-week T-bill.

    Returns:
        Annual risk-free rate as decimal (e.g., 0.045 for 4.5%)

    Example:
        >>> rate = get_risk_free_rate(0.25)  # 3 months to expiry
        >>> print(f"Risk-free rate: {rate:.2%}")
    """
    try:
        # Select appropriate Treasury based on time to expiry
        if time_to_expiry_years is None or time_to_expiry_years < 0.25:
            ticker = "^IRX"  # 13-week T-bill
            name = "13-week T-bill"
        elif time_to_expiry_years < 0.5:
            ticker = "^FVX"  # 5-year Treasury
            name = "5-year Treasury"
        else:
            ticker = "^TNX"  # 10-year Treasury
            name = "10-year Treasury"

        treasury = yf.Ticker(ticker)
        rate_data = treasury.history(period="5d")

        if rate_data.empty:
            print(f"Warning: Could not retrieve {name} rate, using fallback 4.5%")
            return 0.045

        # Treasury yields are in percentage, convert to decimal
        risk_free_rate = rate_data['Close'].iloc[-1] / 100
        return risk_free_rate

    except Exception as e:
        print(f"Error retrieving risk-free rate: {e}. Using fallback 4.5%")
        return 0.045


def get_cboe_sentiment() -> Optional[Dict]:
    """
    Get current CBOE market sentiment from P/C ratios stored in the database.

    Connects to the PostgreSQL database and loads the last 60 trading days
    of CBOE market options stats to compute current sentiment metrics.

    Returns:
        Dict with keys:
            pcr_current: Current total put/call ratio
            pcr_zscore: Z-score of current P/C ratio (60-day)
            pcr_regime: Integer regime (-2 to +2)
            pcr_regime_label: Human-readable regime label
            volume_zscore: Relative volume vs 20-day average
            contrarian_signal: 'bullish', 'bearish', or 'neutral'
              (high P/C -> contrarian bullish, low P/C -> contrarian bearish)
        Returns None if database is unavailable or no data found.
    """
    try:
        import psycopg2
        import os

        db_config = {
            'host': os.environ.get('POSTGRES_HOST', 'localhost'),
            'port': int(os.environ.get('POSTGRES_PORT', 5433)),
            'database': os.environ.get('POSTGRES_DB', 'trading_data'),
            'user': os.environ.get('POSTGRES_USER', 'trading'),
            'password': os.environ.get('POSTGRES_PASSWORD', 'trading123'),
            'sslmode': os.environ.get('POSTGRES_SSLMODE', 'prefer')
        }
        conn = psycopg2.connect(**db_config)

        query = """
            SELECT trade_date, total_call_volume, total_put_volume,
                   equity_put_call_ratio, index_put_call_ratio
            FROM cboe_market_options_stats
            ORDER BY trade_date DESC
            LIMIT 60
        """
        df = pd.read_sql(query, conn)
        conn.close()

        if df.empty or len(df) < 10:
            return None

        df = df.sort_values('trade_date')

        # Calculate total P/C ratio
        df['total_pcr'] = np.where(
            df['total_call_volume'] > 0,
            df['total_put_volume'] / df['total_call_volume'],
            np.nan
        )
        df = df.dropna(subset=['total_pcr'])
        if len(df) < 10:
            return None

        current_pcr = float(df['total_pcr'].iloc[-1])
        pcr_mean = float(df['total_pcr'].mean())
        pcr_std = float(df['total_pcr'].std())

        # Z-score
        pcr_zscore = (current_pcr - pcr_mean) / pcr_std if pcr_std > 0 else 0.0

        # Regime classification
        if pcr_zscore >= 1.5:
            regime, label = 2, 'Very Bearish'
        elif pcr_zscore >= 0.5:
            regime, label = 1, 'Bearish'
        elif pcr_zscore <= -1.5:
            regime, label = -2, 'Very Bullish'
        elif pcr_zscore <= -0.5:
            regime, label = -1, 'Bullish'
        else:
            regime, label = 0, 'Neutral'

        # Volume z-score
        total_vol = df['total_call_volume'].fillna(0) + df['total_put_volume'].fillna(0)
        vol_20d_avg = total_vol.rolling(20, min_periods=10).mean().iloc[-1]
        volume_zscore = float((total_vol.iloc[-1] - vol_20d_avg) / vol_20d_avg) if vol_20d_avg > 0 else 0.0

        # Contrarian signal: high P/C (fear) -> bullish, low P/C (complacency) -> bearish
        if regime >= 1:
            contrarian = 'bullish'
        elif regime <= -1:
            contrarian = 'bearish'
        else:
            contrarian = 'neutral'

        return {
            'pcr_current': current_pcr,
            'pcr_zscore': pcr_zscore,
            'pcr_regime': regime,
            'pcr_regime_label': label,
            'volume_zscore': volume_zscore,
            'contrarian_signal': contrarian
        }

    except Exception as e:
        # Graceful fallback - DB not required for options pricing
        print(f"  Note: CBOE sentiment unavailable ({e})")
        return None


def calculate_time_to_expiry(current_date, expiry_date) -> float:
    """
    Calculate time to expiry in years (as scalar, not Series).

    Args:
        current_date: Current date (str or datetime)
        expiry_date: Option expiry date (str or datetime)

    Returns:
        Time to expiry in years

    Example:
        >>> t = calculate_time_to_expiry('2024-01-15', '2024-06-21')
    """
    if isinstance(current_date, str):
        current_date = datetime.strptime(current_date, '%Y-%m-%d')
    if isinstance(expiry_date, str):
        expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d')

    days_to_expiry = (expiry_date - current_date).days

    if days_to_expiry < 0:
        print("Warning: Expiry date is in the past!")
        return 0

    return days_to_expiry / 365.0


# ════════════════════════════════════════════════════════════════════════════
# BLACK-SCHOLES MODEL (European Options)
# Note: Use binomial tree for American options (most US stock options)
# ════════════════════════════════════════════════════════════════════════════

def black_scholes_call(
    S: float,
    K: float,
    r: float,
    t: float,
    sigma: float
) -> float:
    """
    Calculate Black-Scholes price for a European call option.

    Args:
        S: Current stock price
        K: Strike price
        r: Risk-free interest rate (annual, decimal)
        t: Time to expiration (in years)
        sigma: Volatility (annual, decimal)

    Returns:
        Theoretical call option price

    Example:
        >>> price = black_scholes_call(S=150, K=145, r=0.05, t=0.25, sigma=0.3)
        >>> print(f"Call price: ${price:.2f}")
    """
    if t <= 0:
        return max(0, S - K)

    d1 = (np.log(S / K) + (r + sigma ** 2 / 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)

    call_price = S * norm.cdf(d1) - K * np.exp(-r * t) * norm.cdf(d2)
    return call_price


def black_scholes_put(
    S: float,
    K: float,
    r: float,
    t: float,
    sigma: float
) -> float:
    """
    Calculate Black-Scholes price for a European put option.

    Args:
        S: Current stock price
        K: Strike price
        r: Risk-free interest rate (annual, decimal)
        t: Time to expiration (in years)
        sigma: Volatility (annual, decimal)

    Returns:
        Theoretical put option price

    Example:
        >>> price = black_scholes_put(S=150, K=155, r=0.05, t=0.25, sigma=0.3)
        >>> print(f"Put price: ${price:.2f}")
    """
    if t <= 0:
        return max(0, K - S)

    d1 = (np.log(S / K) + (r + sigma ** 2 / 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)

    put_price = K * np.exp(-r * t) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return put_price


# ════════════════════════════════════════════════════════════════════════════
# GREEKS CALCULATION
# ════════════════════════════════════════════════════════════════════════════

def calculate_greeks(
    S: float,
    K: float,
    r: float,
    t: float,
    sigma: float,
    option_type: str = 'call'
) -> Dict[str, float]:
    """
    Calculate option Greeks.

    Args:
        S: Current stock price
        K: Strike price
        r: Risk-free interest rate (annual, decimal)
        t: Time to expiration (in years)
        sigma: Volatility (annual, decimal)
        option_type: 'call' or 'put'

    Returns:
        Dictionary with Delta, Gamma, Theta, Vega, Rho

    Greeks explanation:
        - Delta: Price change per $1 move in underlying
        - Gamma: Delta change per $1 move in underlying
        - Theta: Price decay per day
        - Vega: Price change per 1% change in volatility
        - Rho: Price change per 1% change in interest rate

    Example:
        >>> greeks = calculate_greeks(S=150, K=145, r=0.05, t=0.25, sigma=0.3)
        >>> print(f"Delta: {greeks['delta']:.4f}")
    """
    if t <= 0:
        return {
            'delta': 1.0 if (option_type == 'call' and S > K) else (-1.0 if option_type == 'put' and S < K else 0.0),
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0
        }

    d1 = (np.log(S / K) + (r + sigma ** 2 / 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)

    # Delta
    if option_type == 'call':
        delta = norm.cdf(d1)
    else:
        delta = norm.cdf(d1) - 1

    # Gamma (same for call and put)
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(t))

    # Theta
    term1 = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(t))
    if option_type == 'call':
        term2 = r * K * np.exp(-r * t) * norm.cdf(d2)
        theta = (term1 - term2) / 365  # Daily theta
    else:
        term2 = r * K * np.exp(-r * t) * norm.cdf(-d2)
        theta = (term1 + term2) / 365  # Daily theta

    # Vega (same for call and put)
    vega = S * np.sqrt(t) * norm.pdf(d1) / 100  # Per 1% change

    # Rho
    if option_type == 'call':
        rho = K * t * np.exp(-r * t) * norm.cdf(d2) / 100  # Per 1% change
    else:
        rho = -K * t * np.exp(-r * t) * norm.cdf(-d2) / 100  # Per 1% change

    return {
        'delta': delta,
        'gamma': gamma,
        'theta': theta,
        'vega': vega,
        'rho': rho
    }


# ════════════════════════════════════════════════════════════════════════════
# BINOMIAL TREE MODEL (American Options)
# ════════════════════════════════════════════════════════════════════════════

def binomial_tree_american(
    S: float,
    K: float,
    r: float,
    t: float,
    sigma: float,
    option_type: str = 'call',
    steps: int = 100
) -> float:
    """
    Calculate American option price using binomial tree.

    American options can be exercised at any time before expiration,
    making binomial tree more appropriate than Black-Scholes.

    Args:
        S: Current stock price
        K: Strike price
        r: Risk-free interest rate (annual, decimal)
        t: Time to expiration (in years)
        sigma: Volatility (annual, decimal)
        option_type: 'call' or 'put'
        steps: Number of time steps in tree (more = more accurate)

    Returns:
        Theoretical American option price

    Example:
        >>> price = binomial_tree_american(S=150, K=145, r=0.05, t=0.25, sigma=0.3, option_type='put')
        >>> print(f"American put price: ${price:.2f}")
    """
    dt = t / steps
    u = np.exp(sigma * np.sqrt(dt))  # Up factor
    d = 1 / u  # Down factor
    p = (np.exp(r * dt) - d) / (u - d)  # Risk-neutral probability

    # Initialize asset prices at maturity
    asset_prices = np.zeros(steps + 1)
    for i in range(steps + 1):
        asset_prices[i] = S * (u ** (steps - i)) * (d ** i)

    # Initialize option values at maturity
    option_values = np.zeros(steps + 1)
    for i in range(steps + 1):
        if option_type == 'call':
            option_values[i] = max(0, asset_prices[i] - K)
        else:
            option_values[i] = max(0, K - asset_prices[i])

    # Work backwards through the tree
    for j in range(steps - 1, -1, -1):
        for i in range(j + 1):
            asset_price = S * (u ** (j - i)) * (d ** i)

            # Continuation value (hold option)
            continuation = np.exp(-r * dt) * (p * option_values[i] + (1 - p) * option_values[i + 1])

            # Early exercise value
            if option_type == 'call':
                exercise = max(0, asset_price - K)
            else:
                exercise = max(0, K - asset_price)

            # American option: take max of hold vs exercise
            option_values[i] = max(continuation, exercise)

    return option_values[0]


# ════════════════════════════════════════════════════════════════════════════
# VOLATILITY CALCULATION
# ════════════════════════════════════════════════════════════════════════════

def calculate_historical_volatility(
    prices: pd.Series,
    window: int = 252
) -> float:
    """
    Calculate annualized historical volatility.

    Args:
        prices: Series of closing prices
        window: Trading days for calculation (default: 252 = 1 year)

    Returns:
        Annualized volatility as decimal

    Example:
        >>> vol = calculate_historical_volatility(data['Close'])
        >>> print(f"Volatility: {vol:.2%}")
    """
    log_returns = np.log(prices / prices.shift(1)).dropna()
    volatility = log_returns.std() * np.sqrt(252)
    return volatility


def calculate_implied_volatility(
    option_price: float,
    S: float,
    K: float,
    r: float,
    t: float,
    option_type: str = 'call',
    precision: float = 0.0001,
    max_iterations: int = 100
) -> float:
    """
    Calculate implied volatility using Newton-Raphson method.

    Args:
        option_price: Market price of option
        S: Current stock price
        K: Strike price
        r: Risk-free interest rate
        t: Time to expiration (years)
        option_type: 'call' or 'put'
        precision: Desired precision
        max_iterations: Max iterations for convergence

    Returns:
        Implied volatility as decimal

    Example:
        >>> iv = calculate_implied_volatility(10.5, 150, 145, 0.05, 0.25, 'call')
        >>> print(f"Implied volatility: {iv:.2%}")
    """
    sigma = 0.3  # Initial guess

    for _ in range(max_iterations):
        if option_type == 'call':
            price = black_scholes_call(S, K, r, t, sigma)
        else:
            price = black_scholes_put(S, K, r, t, sigma)

        vega = calculate_greeks(S, K, r, t, sigma, option_type)['vega'] * 100

        if abs(vega) < 1e-10:
            break

        diff = option_price - price
        if abs(diff) < precision:
            return sigma

        sigma = sigma + diff / vega

        # Keep sigma in reasonable bounds
        sigma = max(0.01, min(sigma, 5.0))

    return sigma


# ════════════════════════════════════════════════════════════════════════════
# OPTIONS DATA FETCHING
# ════════════════════════════════════════════════════════════════════════════

def get_option_prices(
    symbol: str,
    expiry_date: Optional[str] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Get option chain data for a symbol.

    Args:
        symbol: Stock ticker symbol
        expiry_date: Expiration date (if None, uses nearest expiry)

    Returns:
        Tuple of (calls_df, puts_df)

    Example:
        >>> calls, puts = get_option_prices('AAPL', '2024-06-21')
    """
    ticker = yf.Ticker(symbol)

    # Get available expiration dates
    expirations = ticker.options

    if not expirations:
        raise ValueError(f"No options available for {symbol}")

    # Use specified or nearest expiry
    if expiry_date and expiry_date in expirations:
        selected_expiry = expiry_date
    else:
        selected_expiry = expirations[0]

    # Get option chain
    opt = ticker.option_chain(selected_expiry)

    return opt.calls, opt.puts


def get_all_option_expirations(symbol: str) -> list:
    """
    Get all available option expiration dates for a symbol.

    Args:
        symbol: Stock ticker symbol

    Returns:
        List of expiration dates

    Example:
        >>> expirations = get_all_option_expirations('AAPL')
    """
    ticker = yf.Ticker(symbol)
    return list(ticker.options)


# ════════════════════════════════════════════════════════════════════════════
# FULL OPTIONS ANALYSIS
# ════════════════════════════════════════════════════════════════════════════

def option_analysis(
    ticker: str,
    start_date: str,
    end_date: str,
    strike_price: float,
    expiry_date: str,
    option_type: str = 'call',
    risk_free_rate: float = 0.05
) -> Dict[str, Union[float, Dict]]:
    """
    Perform full options analysis comparing market price to fair value.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date for historical data
        end_date: End date for historical data
        strike_price: Option strike price
        expiry_date: Option expiration date (YYYY-MM-DD)
        option_type: 'call' or 'put'
        risk_free_rate: Risk-free rate (default: 0.05)

    Returns:
        Dictionary with:
            - fair_value: Black-Scholes theoretical price
            - american_value: Binomial tree price
            - greeks: Dictionary of Greeks
            - volatility: Historical volatility used
            - stock_price: Current stock price
            - time_to_expiry: Time to expiration in years

    Example:
        >>> result = option_analysis('AAPL', '2023-01-01', '2024-01-01', 150, '2024-06-21')
        >>> print(f"Fair value: ${result['fair_value']:.2f}")
    """
    # Download historical stock data
    stock_data = yf.download(ticker, start=start_date, end=end_date, progress=False)

    # Handle multi-level columns from yfinance
    if isinstance(stock_data.columns, pd.MultiIndex):
        stock_data.columns = stock_data.columns.get_level_values(0)

    stock_data = stock_data.reset_index()

    # Get close prices as Series
    close_prices = stock_data['Close']
    if isinstance(close_prices, pd.DataFrame):
        close_prices = close_prices.iloc[:, 0]

    # Current stock price
    stock_price = float(close_prices.iloc[-1])

    # Calculate time to expiry
    expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
    current = datetime.strptime(end_date, "%Y-%m-%d")
    time_to_expiry = max((expiry - current).days / 365.0, 0.001)

    # Calculate historical volatility
    volatility = calculate_historical_volatility(close_prices)
    if hasattr(volatility, 'item'):
        volatility = volatility.item()
    elif isinstance(volatility, pd.Series):
        volatility = float(volatility.iloc[0])
    else:
        volatility = float(volatility)

    # Black-Scholes fair value (European)
    if option_type == 'call':
        fair_value = black_scholes_call(stock_price, strike_price, risk_free_rate, time_to_expiry, volatility)
    else:
        fair_value = black_scholes_put(stock_price, strike_price, risk_free_rate, time_to_expiry, volatility)

    # Binomial tree value (American)
    american_value = binomial_tree_american(
        stock_price, strike_price, risk_free_rate, time_to_expiry, volatility, option_type
    )

    # Calculate Greeks
    greeks = calculate_greeks(stock_price, strike_price, risk_free_rate, time_to_expiry, volatility, option_type)

    return {
        'ticker': ticker,
        'stock_price': stock_price,
        'strike_price': strike_price,
        'expiry_date': expiry_date,
        'time_to_expiry': time_to_expiry,
        'volatility': volatility,
        'risk_free_rate': risk_free_rate,
        'option_type': option_type,
        'fair_value_european': fair_value,
        'fair_value_american': american_value,
        'greeks': greeks
    }


def analyze_option_chain(
    ticker: str,
    expiry_date: str,
    risk_free_rate: float = 0.05
) -> pd.DataFrame:
    """
    Analyze entire option chain, comparing market prices to fair values.

    Args:
        ticker: Stock ticker symbol
        expiry_date: Option expiration date
        risk_free_rate: Risk-free rate

    Returns:
        DataFrame with market prices, fair values, and analysis

    Example:
        >>> analysis = analyze_option_chain('AAPL', '2024-06-21')
        >>> undervalued = analysis[analysis['pct_diff'] < -5]
    """
    # Get current stock price
    stock = yf.Ticker(ticker)
    hist_1d = stock.history(period='1d')
    close_1d = hist_1d['Close']
    if isinstance(close_1d, pd.DataFrame):
        close_1d = close_1d.iloc[:, 0]
    stock_price = float(close_1d.iloc[-1])

    # Get option chain
    calls, puts = get_option_prices(ticker, expiry_date)

    # Calculate time to expiry
    expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
    time_to_expiry = max((expiry - datetime.now()).days / 365.0, 0.001)

    # Get historical volatility
    hist = stock.history(period='1y')
    close_prices = hist['Close']
    if isinstance(close_prices, pd.DataFrame):
        close_prices = close_prices.iloc[:, 0]
    volatility = calculate_historical_volatility(close_prices)
    if hasattr(volatility, 'item'):
        volatility = volatility.item()
    elif isinstance(volatility, pd.Series):
        volatility = float(volatility.iloc[0])
    else:
        volatility = float(volatility)

    results = []

    # Analyze calls
    for _, row in calls.iterrows():
        strike = row['strike']
        market_price = row['lastPrice']

        fair_value = black_scholes_call(stock_price, strike, risk_free_rate, time_to_expiry, volatility)
        greeks = calculate_greeks(stock_price, strike, risk_free_rate, time_to_expiry, volatility, 'call')

        pct_diff = ((market_price - fair_value) / fair_value * 100) if fair_value > 0 else 0

        results.append({
            'type': 'call',
            'strike': strike,
            'market_price': market_price,
            'fair_value': fair_value,
            'pct_diff': pct_diff,
            'delta': greeks['delta'],
            'gamma': greeks['gamma'],
            'theta': greeks['theta'],
            'vega': greeks['vega'],
            'volume': row.get('volume', 0),
            'open_interest': row.get('openInterest', 0),
            'implied_vol': row.get('impliedVolatility', 0)
        })

    # Analyze puts
    for _, row in puts.iterrows():
        strike = row['strike']
        market_price = row['lastPrice']

        fair_value = black_scholes_put(stock_price, strike, risk_free_rate, time_to_expiry, volatility)
        greeks = calculate_greeks(stock_price, strike, risk_free_rate, time_to_expiry, volatility, 'put')

        pct_diff = ((market_price - fair_value) / fair_value * 100) if fair_value > 0 else 0

        results.append({
            'type': 'put',
            'strike': strike,
            'market_price': market_price,
            'fair_value': fair_value,
            'pct_diff': pct_diff,
            'delta': greeks['delta'],
            'gamma': greeks['gamma'],
            'theta': greeks['theta'],
            'vega': greeks['vega'],
            'volume': row.get('volume', 0),
            'open_interest': row.get('openInterest', 0),
            'implied_vol': row.get('impliedVolatility', 0)
        })

    return pd.DataFrame(results)


def find_undervalued_options(
    ticker: str,
    expiry_date: str,
    threshold: float = -10.0,
    min_volume: int = 10,
    include_sentiment: bool = True
) -> pd.DataFrame:
    """
    Find potentially undervalued options.

    When include_sentiment=True, adds CBOE P/C ratio sentiment columns:
    - market_sentiment: Current regime label
    - contrarian_signal: 'bullish', 'bearish', or 'neutral'
    - sentiment_enhanced: True if option aligns with contrarian signal

    Args:
        ticker: Stock ticker symbol
        expiry_date: Option expiration date
        threshold: Percentage below fair value to consider undervalued (default: -10%)
        min_volume: Minimum trading volume
        include_sentiment: If True, enrich with CBOE sentiment context

    Returns:
        DataFrame of undervalued options sorted by discount

    Example:
        >>> undervalued = find_undervalued_options('AAPL', '2024-06-21', threshold=-15)
    """
    analysis = analyze_option_chain(ticker, expiry_date)

    undervalued = analysis[
        (analysis['pct_diff'] < threshold) &
        (analysis['volume'] >= min_volume)
    ].sort_values('pct_diff').copy()

    if include_sentiment and len(undervalued) > 0:
        sentiment = get_cboe_sentiment()
        if sentiment:
            undervalued['market_sentiment'] = sentiment['pcr_regime_label']
            undervalued['contrarian_signal'] = sentiment['contrarian_signal']
            # Flag calls as sentiment-enhanced when market is fearful (contrarian bullish)
            # Flag puts as sentiment-enhanced when market is complacent (contrarian bearish)
            undervalued['sentiment_enhanced'] = False
            if 'type' in undervalued.columns:
                call_mask = undervalued['type'] == 'call'
                put_mask = undervalued['type'] == 'put'
                if sentiment['contrarian_signal'] == 'bullish':
                    undervalued.loc[call_mask, 'sentiment_enhanced'] = True
                elif sentiment['contrarian_signal'] == 'bearish':
                    undervalued.loc[put_mask, 'sentiment_enhanced'] = True

    return undervalued


# ════════════════════════════════════════════════════════════════════════════
# TREND DIRECTION FILTERING (for swing trading)
# ════════════════════════════════════════════════════════════════════════════

def filter_options_by_trend(
    option_chain: Dict,
    trend_direction: str = 'both',
    moneyness: str = 'all'
) -> Dict:
    """
    Filter option chain based on predicted trend direction for swing trading.

    For intra-day swing trading, trade options aligned with predicted trend:
    - Bullish trend → Focus on calls
    - Bearish trend → Focus on puts

    Args:
        option_chain: Dict with 'calls' and 'puts' DataFrames
        trend_direction: 'bullish', 'bearish', or 'both'
        moneyness: Filter by option moneyness
                  'itm' = in-the-money
                  'atm' = at-the-money (±5% of spot)
                  'otm' = out-of-the-money
                  'all' = no filter

    Returns:
        Filtered option chain dict

    Example:
        >>> calls, puts = get_option_prices('AAPL', '2024-06-21')
        >>> chain = {'calls': calls, 'puts': puts, 'ticker': 'AAPL'}
        >>> filtered = filter_options_by_trend(chain, 'bullish', 'atm')
    """
    if option_chain is None:
        return None

    result = {}

    # Get underlying price
    try:
        ticker = option_chain.get('ticker', 'AAPL')
        ticker_obj = yf.Ticker(ticker)
        underlying_price = ticker_obj.history(period='1d')['Close'].iloc[-1]
    except:
        underlying_price = 100  # Fallback

    # Filter by trend direction
    if trend_direction in ['bullish', 'both'] and 'calls' in option_chain:
        calls = option_chain['calls'].copy()

        if moneyness == 'itm':
            calls = calls[calls['inTheMoney'] == True]
        elif moneyness == 'otm':
            calls = calls[calls['inTheMoney'] == False]
        elif moneyness == 'atm':
            calls = calls[
                (calls['strike'] >= underlying_price * 0.95) &
                (calls['strike'] <= underlying_price * 1.05)
            ]

        result['calls'] = calls

    if trend_direction in ['bearish', 'both'] and 'puts' in option_chain:
        puts = option_chain['puts'].copy()

        if moneyness == 'itm':
            puts = puts[puts['inTheMoney'] == True]
        elif moneyness == 'otm':
            puts = puts[puts['inTheMoney'] == False]
        elif moneyness == 'atm':
            puts = puts[
                (puts['strike'] >= underlying_price * 0.95) &
                (puts['strike'] <= underlying_price * 1.05)
            ]

        result['puts'] = puts

    result['ticker'] = option_chain.get('ticker')
    result['expiry_date'] = option_chain.get('expiry_date')

    return result


# ════════════════════════════════════════════════════════════════════════════
# COMPREHENSIVE OPTION ANALYSIS (American options as default)
# ════════════════════════════════════════════════════════════════════════════

def analyze_option_pricing(
    ticker: str,
    start_date: str,
    end_date: str,
    expiry_date: Optional[str] = None,
    strike_price: Optional[float] = None,
    option_type: str = 'both',
    pricing_model: str = 'american',
    trend_direction: str = 'both',
    include_sentiment: bool = True
) -> Optional[pd.DataFrame]:
    """
    Comprehensive option pricing analysis with Black-Scholes and Binomial Tree.

    IMPORTANT: Most US stock options are American options. Use pricing_model='american'
    (binomial tree) for accurate pricing. Black-Scholes is for European options only.

    This function:
    1. Retrieves historical stock data
    2. Calculates volatility
    3. Gets current risk-free rate dynamically
    4. Retrieves option chain data
    5. Calculates theoretical fair value
    6. Compares to market price
    7. Identifies mispriced options

    Args:
        ticker: Stock ticker symbol
        start_date: Start date for historical data 'YYYY-MM-DD'
        end_date: End date (typically today) 'YYYY-MM-DD'
        expiry_date: Option expiry date. If None, uses nearest expiry.
        strike_price: Specific strike to analyze. If None, analyzes all strikes.
        option_type: 'call', 'put', or 'both'
        pricing_model: 'american' (Binomial - RECOMMENDED) or 'european' (Black-Scholes)
        trend_direction: 'bullish', 'bearish', or 'both' for filtering

    Returns:
        DataFrame with fair values, mispricing percentages, and recommendations

    Example:
        >>> results = analyze_option_pricing(
        ...     'AAPL', '2023-01-01', '2024-01-15',
        ...     option_type='call', pricing_model='american', trend_direction='bullish'
        ... )
        >>> underpriced = results[results['recommendation'] == 'UNDERPRICED']
    """
    print(f"\n{'='*70}")
    print(f"OPTION PRICING ANALYSIS: {ticker}")
    print(f"Model: {pricing_model.upper()} ({'Binomial Tree' if pricing_model == 'american' else 'Black-Scholes'})")
    print(f"{'='*70}\n")

    # Step 1: Get historical stock data
    print("Step 1: Fetching historical stock data...")
    try:
        stock_data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if stock_data.empty:
            print(f"Error: No stock data for {ticker}")
            return None
    except Exception as e:
        print(f"Error downloading stock data: {e}")
        return None

    # Handle multi-level columns from yfinance
    if isinstance(stock_data.columns, pd.MultiIndex):
        stock_data.columns = stock_data.columns.get_level_values(0)

    close_prices = stock_data['Close']
    # Ensure we have a Series, not a DataFrame
    if isinstance(close_prices, pd.DataFrame):
        close_prices = close_prices.iloc[:, 0]

    current_price = float(close_prices.iloc[-1])
    print(f"Current price: ${current_price:.2f}")

    # Step 2: Calculate historical volatility
    print("\nStep 2: Calculating historical volatility...")
    volatility = calculate_historical_volatility(close_prices)
    # Ensure volatility is a scalar
    if hasattr(volatility, 'item'):
        volatility = volatility.item()
    elif isinstance(volatility, pd.Series):
        volatility = float(volatility.iloc[0])
    else:
        volatility = float(volatility)
    print(f"Annualized volatility: {volatility:.2%}")

    # Step 3: Get option chain
    print("\nStep 3: Retrieving option chain...")
    try:
        calls, puts = get_option_prices(ticker, expiry_date)
        if expiry_date is None:
            stock = yf.Ticker(ticker)
            expiry_date = stock.options[0]
    except Exception as e:
        print(f"Error getting option chain: {e}")
        return None

    # Step 4: Calculate time to expiry
    print("\nStep 4: Calculating time to expiry...")
    time_to_expiry = calculate_time_to_expiry(end_date, expiry_date)
    print(f"Time to expiry: {time_to_expiry:.4f} years ({time_to_expiry*365:.0f} days)")

    # Step 5: Get dynamic risk-free rate
    print("\nStep 5: Fetching risk-free rate...")
    risk_free_rate = get_risk_free_rate(time_to_expiry)
    print(f"Risk-free rate: {risk_free_rate:.2%}")

    # Step 5b: Get CBOE sentiment context
    sentiment = None
    if include_sentiment:
        print("\nStep 5b: Fetching CBOE market sentiment...")
        sentiment = get_cboe_sentiment()
        if sentiment:
            print(f"  P/C Ratio: {sentiment['pcr_current']:.3f} (z={sentiment['pcr_zscore']:+.2f})")
            print(f"  Regime: {sentiment['pcr_regime_label']} (contrarian signal: {sentiment['contrarian_signal']})")
        else:
            print("  CBOE sentiment data not available (proceeding without)")

    # Step 6: Filter by trend direction
    option_chain = {'calls': calls, 'puts': puts, 'ticker': ticker, 'expiry_date': expiry_date}
    filtered_chain = filter_options_by_trend(option_chain, trend_direction)

    # Step 7: Calculate theoretical prices
    print(f"\nStep 7: Calculating theoretical prices...")

    results = []

    # Analyze calls
    if option_type in ['call', 'both'] and 'calls' in filtered_chain:
        calls_df = filtered_chain['calls']
        if strike_price is not None:
            calls_df = calls_df[calls_df['strike'] == strike_price]

        for _, opt in calls_df.iterrows():
            K = opt['strike']
            market_price = opt['lastPrice']

            if pricing_model == 'american':
                theoretical = binomial_tree_american(current_price, K, risk_free_rate, time_to_expiry, volatility, 'call')
            else:
                theoretical = black_scholes_call(current_price, K, risk_free_rate, time_to_expiry, volatility)

            mispricing = ((market_price - theoretical) / theoretical * 100) if theoretical > 0 else 0

            row = {
                'type': 'CALL',
                'strike': K,
                'market_price': market_price,
                'theoretical_price': theoretical,
                'mispricing_%': mispricing,
                'recommendation': 'OVERPRICED' if mispricing > 10 else ('UNDERPRICED' if mispricing < -10 else 'FAIR'),
                'bid': opt.get('bid', np.nan),
                'ask': opt.get('ask', np.nan),
                'volume': opt.get('volume', 0),
                'open_interest': opt.get('openInterest', 0)
            }
            if sentiment:
                row['market_sentiment'] = sentiment['pcr_regime_label']
                row['contrarian_signal'] = sentiment['contrarian_signal']
                # Flag: calls underpriced while market is fearful = strong buy signal
                if mispricing < -10 and sentiment['contrarian_signal'] == 'bullish':
                    row['sentiment_note'] = 'STRONG BUY: Call underpriced + market fearful (contrarian bullish)'
                elif mispricing < -10:
                    row['sentiment_note'] = 'Underpriced call'
                else:
                    row['sentiment_note'] = ''
            results.append(row)

    # Analyze puts
    if option_type in ['put', 'both'] and 'puts' in filtered_chain:
        puts_df = filtered_chain['puts']
        if strike_price is not None:
            puts_df = puts_df[puts_df['strike'] == strike_price]

        for _, opt in puts_df.iterrows():
            K = opt['strike']
            market_price = opt['lastPrice']

            if pricing_model == 'american':
                theoretical = binomial_tree_american(current_price, K, risk_free_rate, time_to_expiry, volatility, 'put')
            else:
                theoretical = black_scholes_put(current_price, K, risk_free_rate, time_to_expiry, volatility)

            mispricing = ((market_price - theoretical) / theoretical * 100) if theoretical > 0 else 0

            row = {
                'type': 'PUT',
                'strike': K,
                'market_price': market_price,
                'theoretical_price': theoretical,
                'mispricing_%': mispricing,
                'recommendation': 'OVERPRICED' if mispricing > 10 else ('UNDERPRICED' if mispricing < -10 else 'FAIR'),
                'bid': opt.get('bid', np.nan),
                'ask': opt.get('ask', np.nan),
                'volume': opt.get('volume', 0),
                'open_interest': opt.get('openInterest', 0)
            }
            if sentiment:
                row['market_sentiment'] = sentiment['pcr_regime_label']
                row['contrarian_signal'] = sentiment['contrarian_signal']
                # Flag: puts underpriced while market is complacent = strong buy signal
                if mispricing < -10 and sentiment['contrarian_signal'] == 'bearish':
                    row['sentiment_note'] = 'STRONG BUY: Put underpriced + market complacent (contrarian bearish)'
                elif mispricing < -10:
                    row['sentiment_note'] = 'Underpriced put'
                else:
                    row['sentiment_note'] = ''
            results.append(row)

    if not results:
        print("No options found matching criteria.")
        return None

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('mispricing_%')

    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")
    print(f"Analyzed {len(results_df)} options")
    print(f"Underpriced: {len(results_df[results_df['recommendation'] == 'UNDERPRICED'])}")
    print(f"Overpriced: {len(results_df[results_df['recommendation'] == 'OVERPRICED'])}")
    print(f"Fair: {len(results_df[results_df['recommendation'] == 'FAIR'])}")

    # Sentiment summary
    if sentiment and 'sentiment_note' in results_df.columns:
        strong_signals = results_df[results_df['sentiment_note'].str.startswith('STRONG', na=False)]
        if len(strong_signals) > 0:
            print(f"\n{'='*70}")
            print("SENTIMENT-ENHANCED SIGNALS")
            print(f"{'='*70}")
            print(f"Market sentiment: {sentiment['pcr_regime_label']} (P/C ratio z={sentiment['pcr_zscore']:+.2f})")
            print(f"Contrarian signal: {sentiment['contrarian_signal'].upper()}")
            print(f"\nStrong sentiment-aligned opportunities: {len(strong_signals)}")
            for _, row in strong_signals.head(5).iterrows():
                print(f"  {row['type']} ${row['strike']:.0f}: {row['sentiment_note']}")

    return results_df
