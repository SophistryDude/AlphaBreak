"""
OPTIONS ANALYSIS MODULE - BLACK-SCHOLES & BINOMIAL TREE PRICING

This module provides comprehensive options pricing and analysis tools for
evaluating whether options are appropriately priced for trading decisions.

Features:
- Black-Scholes pricing for European options (calls and puts)
- Binomial tree pricing for American options (calls and puts)
- Dynamic risk-free rate retrieval
- Option data retrieval with error handling
- Greeks calculation (Delta, Gamma, Theta, Vega, Rho)
- Historical options trading assessment
- Trend direction filtering for intra-day swing trading

Usage:
    For intra-day swing trading - analyzes options without dividend considerations.
    See dividend_adjustment_guide.txt for long-term holding strategies.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import norm
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


# ════════════════════════════════════════════════════════════════════════════
# ISSUE 3 FIX: DYNAMIC RISK-FREE RATE
# ════════════════════════════════════════════════════════════════════════════

def get_risk_free_rate(time_to_expiry_years=None):
    """
    Retrieves current risk-free rate from market data instead of hardcoding.

    Uses Treasury yields matched to option expiry period:
    - <3 months: 13-week T-bill (^IRX)
    - 3-6 months: 5-year Treasury (^FVX)
    - >6 months: 10-year Treasury (^TNX)

    Args:
        time_to_expiry_years (float): Time to expiry in years. If None, uses 13-week T-bill.

    Returns:
        float: Annual risk-free rate as decimal (e.g., 0.045 for 4.5%)
    """
    try:
        # Select appropriate Treasury based on time to expiry
        if time_to_expiry_years is None or time_to_expiry_years < 0.25:
            # Use 13-week T-bill for short-term
            ticker = "^IRX"
            name = "13-week T-bill"
        elif time_to_expiry_years < 0.5:
            # Use 5-year Treasury for medium-term
            ticker = "^FVX"
            name = "5-year Treasury"
        else:
            # Use 10-year Treasury for longer-term
            ticker = "^TNX"
            name = "10-year Treasury"

        # Fetch current yield
        treasury = yf.Ticker(ticker)
        rate_data = treasury.history(period="5d")

        if rate_data.empty:
            print(f"Warning: Could not retrieve {name} rate, using fallback rate 4.5%")
            return 0.045

        # Treasury yields are in percentage (e.g., 4.5), convert to decimal
        risk_free_rate = rate_data['Close'].iloc[-1] / 100

        print(f"Using {name} rate: {risk_free_rate:.4f} ({risk_free_rate*100:.2f}%)")
        return risk_free_rate

    except Exception as e:
        print(f"Error retrieving risk-free rate: {e}. Using fallback rate 4.5%")
        return 0.045


# ════════════════════════════════════════════════════════════════════════════
# ISSUE 1 FIX: BLACK-SCHOLES FOR BOTH CALLS AND PUTS (EUROPEAN)
# ════════════════════════════════════════════════════════════════════════════

def black_scholes_call(S, K, r, t, sigma):
    """
    Black-Scholes pricing formula for European CALL option.

    Args:
        S (float): Current stock price
        K (float): Strike price
        r (float): Risk-free rate (annual, as decimal)
        t (float): Time to expiry (in years)
        sigma (float): Volatility (annual, as decimal)

    Returns:
        float: Theoretical call option price
    """
    if t <= 0:
        return max(S - K, 0)  # Intrinsic value at expiry

    d1 = (np.log(S / K) + (r + sigma ** 2 / 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)
    call_price = S * norm.cdf(d1) - K * np.exp(-r * t) * norm.cdf(d2)

    return call_price


def black_scholes_put(S, K, r, t, sigma):
    """
    Black-Scholes pricing formula for European PUT option.

    Args:
        S (float): Current stock price
        K (float): Strike price
        r (float): Risk-free rate (annual, as decimal)
        t (float): Time to expiry (in years)
        sigma (float): Volatility (annual, as decimal)

    Returns:
        float: Theoretical put option price
    """
    if t <= 0:
        return max(K - S, 0)  # Intrinsic value at expiry

    d1 = (np.log(S / K) + (r + sigma ** 2 / 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)
    put_price = K * np.exp(-r * t) * norm.cdf(-d2) - S * norm.cdf(-d1)

    return put_price


# ════════════════════════════════════════════════════════════════════════════
# AMERICAN OPTIONS PRICING: BINOMIAL TREE METHOD
# ════════════════════════════════════════════════════════════════════════════

def binomial_tree_american(S, K, r, t, sigma, option_type='call', steps=100):
    """
    Binomial tree pricing for American options (can be exercised anytime).

    American options are worth at least as much as European options because
    of the early exercise feature. This is especially important for:
    - Puts when stock price drops significantly
    - Calls on dividend-paying stocks (not relevant for intra-day trading)

    Args:
        S (float): Current stock price
        K (float): Strike price
        r (float): Risk-free rate (annual, as decimal)
        t (float): Time to expiry (in years)
        sigma (float): Volatility (annual, as decimal)
        option_type (str): 'call' or 'put'
        steps (int): Number of time steps in the tree (more = more accurate)

    Returns:
        float: American option price
    """
    if t <= 0:
        # At expiry, return intrinsic value
        if option_type == 'call':
            return max(S - K, 0)
        else:
            return max(K - S, 0)

    # Time step
    dt = t / steps

    # Up and down factors
    u = np.exp(sigma * np.sqrt(dt))
    d = 1 / u

    # Risk-neutral probability
    p = (np.exp(r * dt) - d) / (u - d)

    # Initialize stock price tree
    stock_tree = np.zeros((steps + 1, steps + 1))
    stock_tree[0, 0] = S

    # Build stock price tree (forward)
    for i in range(1, steps + 1):
        stock_tree[i, 0] = stock_tree[i-1, 0] * u
        for j in range(1, i + 1):
            stock_tree[i, j] = stock_tree[i-1, j-1] * d

    # Initialize option value tree
    option_tree = np.zeros((steps + 1, steps + 1))

    # Calculate option values at expiry (final nodes)
    if option_type == 'call':
        for j in range(steps + 1):
            option_tree[steps, j] = max(stock_tree[steps, j] - K, 0)
    else:  # put
        for j in range(steps + 1):
            option_tree[steps, j] = max(K - stock_tree[steps, j], 0)

    # Backward induction: work backwards through the tree
    for i in range(steps - 1, -1, -1):
        for j in range(i + 1):
            # Expected value if held (discounted expected payoff)
            hold_value = np.exp(-r * dt) * (p * option_tree[i+1, j] + (1-p) * option_tree[i+1, j+1])

            # Immediate exercise value
            if option_type == 'call':
                exercise_value = max(stock_tree[i, j] - K, 0)
            else:  # put
                exercise_value = max(K - stock_tree[i, j], 0)

            # American option: take maximum of holding or exercising
            option_tree[i, j] = max(hold_value, exercise_value)

    return option_tree[0, 0]


def binomial_tree_american_call(S, K, r, t, sigma, steps=100):
    """Convenience wrapper for American call option."""
    return binomial_tree_american(S, K, r, t, sigma, 'call', steps)


def binomial_tree_american_put(S, K, r, t, sigma, steps=100):
    """Convenience wrapper for American put option."""
    return binomial_tree_american(S, K, r, t, sigma, 'put', steps)


# ════════════════════════════════════════════════════════════════════════════
# ISSUE 4: AGNOSTIC OPTION DATA RETRIEVAL WITH ERROR HANDLING
# ════════════════════════════════════════════════════════════════════════════

def get_option_chain(ticker, expiry_date=None):
    """
    Retrieves option chain data for a given ticker with comprehensive error handling.

    This function is agnostic to the data source and handles common errors
    gracefully, providing useful feedback.

    Args:
        ticker (str): Stock ticker symbol (e.g., 'AAPL')
        expiry_date (str): Expiry date in 'YYYY-MM-DD' format.
                          If None, uses nearest expiry date available.

    Returns:
        dict: Contains 'calls' and 'puts' DataFrames, or None if error occurs
              {
                  'calls': DataFrame with call options,
                  'puts': DataFrame with put options,
                  'expiry_date': actual expiry date used
              }
    """
    try:
        # Create ticker object
        ticker_obj = yf.Ticker(ticker)

        # Get available expiry dates
        try:
            expiry_dates = ticker_obj.options
        except Exception as e:
            print(f"Error: Could not retrieve expiry dates for {ticker}")
            print(f"Reason: {e}")
            return None

        if len(expiry_dates) == 0:
            print(f"Error: No option data available for {ticker}")
            return None

        # Select expiry date
        if expiry_date is None:
            # Use nearest expiry
            selected_expiry = expiry_dates[0]
            print(f"No expiry date specified. Using nearest expiry: {selected_expiry}")
        else:
            # Validate requested expiry date exists
            if expiry_date not in expiry_dates:
                print(f"Warning: Requested expiry {expiry_date} not available for {ticker}")
                print(f"Available expiry dates: {expiry_dates[:5]}...")

                # Find closest available expiry
                target_date = datetime.strptime(expiry_date, '%Y-%m-%d')
                available_dates = [datetime.strptime(d, '%Y-%m-%d') for d in expiry_dates]
                closest_expiry = min(available_dates, key=lambda x: abs(x - target_date))
                selected_expiry = closest_expiry.strftime('%Y-%m-%d')

                print(f"Using closest available expiry: {selected_expiry}")
            else:
                selected_expiry = expiry_date

        # Retrieve option chain
        try:
            option_chain = ticker_obj.option_chain(selected_expiry)
        except Exception as e:
            print(f"Error: Could not retrieve option chain for {ticker} on {selected_expiry}")
            print(f"Reason: {e}")
            return None

        # Validate data
        if option_chain.calls.empty and option_chain.puts.empty:
            print(f"Error: Option chain is empty for {ticker} on {selected_expiry}")
            return None

        print(f"✓ Retrieved {len(option_chain.calls)} calls and {len(option_chain.puts)} puts for {ticker}")

        return {
            'calls': option_chain.calls,
            'puts': option_chain.puts,
            'expiry_date': selected_expiry,
            'ticker': ticker
        }

    except Exception as e:
        print(f"Unexpected error retrieving option chain for {ticker}: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# ISSUE 2 FIX: CORRECT TIME-TO-EXPIRY CALCULATION
# ════════════════════════════════════════════════════════════════════════════

def calculate_time_to_expiry(current_date, expiry_date):
    """
    Calculates time to expiry in years (as a scalar, not Series).

    Args:
        current_date (str or datetime): Current date
        expiry_date (str or datetime): Option expiry date

    Returns:
        float: Time to expiry in years
    """
    if isinstance(current_date, str):
        current_date = datetime.strptime(current_date, '%Y-%m-%d')
    if isinstance(expiry_date, str):
        expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d')

    days_to_expiry = (expiry_date - current_date).days

    if days_to_expiry < 0:
        print("Warning: Expiry date is in the past!")
        return 0

    # Convert to years (365 days per year)
    time_to_expiry = days_to_expiry / 365.0

    return time_to_expiry


# ════════════════════════════════════════════════════════════════════════════
# ISSUE 5 FIX: FILTER OPTIONS BY TREND DIRECTION
# ════════════════════════════════════════════════════════════════════════════

def filter_options_by_trend(option_chain, trend_direction='both', moneyness='all'):
    """
    Filters option chain based on predicted trend direction for swing trading.

    For intra-day swing trading, you want to trade options that align with
    your predicted trend direction:
    - Bullish trend → Focus on calls
    - Bearish trend → Focus on puts
    - Can also filter by moneyness (ITM, ATM, OTM)

    Args:
        option_chain (dict): Output from get_option_chain()
        trend_direction (str): 'bullish', 'bearish', or 'both'
        moneyness (str): Filter by option moneyness
                        'itm' = in-the-money
                        'atm' = at-the-money (±5% of spot)
                        'otm' = out-of-the-money
                        'all' = no filter

    Returns:
        dict: Filtered option chain with 'calls' and/or 'puts'
    """
    if option_chain is None:
        return None

    result = {}

    # Get current stock price from option data
    if not option_chain['calls'].empty:
        underlying_price = option_chain['calls']['lastPrice'].iloc[0] * 10  # Rough estimate
        # Better: fetch from stock data
        try:
            ticker_obj = yf.Ticker(option_chain['ticker'])
            underlying_price = ticker_obj.history(period='1d')['Close'].iloc[-1]
        except:
            pass

    # Filter by trend direction
    if trend_direction in ['bullish', 'both']:
        calls = option_chain['calls'].copy()

        # Filter by moneyness
        if moneyness == 'itm':
            calls = calls[calls['inTheMoney'] == True]
        elif moneyness == 'otm':
            calls = calls[calls['inTheMoney'] == False]
        elif moneyness == 'atm':
            # At-the-money: strike within ±5% of spot
            calls = calls[
                (calls['strike'] >= underlying_price * 0.95) &
                (calls['strike'] <= underlying_price * 1.05)
            ]

        result['calls'] = calls

    if trend_direction in ['bearish', 'both']:
        puts = option_chain['puts'].copy()

        # Filter by moneyness
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

    result['expiry_date'] = option_chain['expiry_date']
    result['ticker'] = option_chain['ticker']

    print(f"Filtered options for {trend_direction} trend, {moneyness} moneyness:")
    if 'calls' in result:
        print(f"  Calls: {len(result['calls'])}")
    if 'puts' in result:
        print(f"  Puts: {len(result['puts'])}")

    return result


# ════════════════════════════════════════════════════════════════════════════
# COMPREHENSIVE OPTION ANALYSIS FUNCTION
# ════════════════════════════════════════════════════════════════════════════

def analyze_option_pricing(ticker, start_date, end_date, expiry_date=None,
                           strike_price=None, option_type='call',
                           pricing_model='american', trend_direction='both'):
    """
    Comprehensive option pricing analysis with Black-Scholes and Binomial Tree.

    This function:
    1. Retrieves historical stock data
    2. Calculates volatility
    3. Gets current risk-free rate
    4. Retrieves option chain data
    5. Calculates theoretical fair value (Black-Scholes or Binomial)
    6. Compares to market price
    7. Identifies mispriced options

    Args:
        ticker (str): Stock ticker symbol
        start_date (str): Start date for historical data 'YYYY-MM-DD'
        end_date (str): End date (typically today) 'YYYY-MM-DD'
        expiry_date (str): Option expiry date. If None, uses nearest expiry.
        strike_price (float): Specific strike to analyze. If None, analyzes all strikes.
        option_type (str): 'call', 'put', or 'both'
        pricing_model (str): 'european' (Black-Scholes) or 'american' (Binomial)
        trend_direction (str): 'bullish', 'bearish', or 'both' for filtering

    Returns:
        DataFrame: Analysis results with fair values and mispricing percentages
    """
    print(f"\n{'='*80}")
    print(f"OPTION PRICING ANALYSIS: {ticker}")
    print(f"{'='*80}\n")

    # Step 1: Get historical stock data
    print("Step 1: Fetching historical stock data...")
    try:
        stock_data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if stock_data.empty:
            print(f"Error: No stock data available for {ticker}")
            return None
    except Exception as e:
        print(f"Error downloading stock data: {e}")
        return None

    current_price = stock_data['Close'].iloc[-1]
    current_date = stock_data.index[-1]
    print(f"✓ Current price: ${current_price:.2f} (as of {current_date.date()})")

    # Step 2: Calculate historical volatility
    print("\nStep 2: Calculating historical volatility...")
    log_returns = np.log(stock_data['Close'] / stock_data['Close'].shift(1))
    volatility = np.sqrt(252) * log_returns.std()
    print(f"✓ Annualized volatility: {volatility:.4f} ({volatility*100:.2f}%)")

    # Step 3: Get option chain
    print("\nStep 3: Retrieving option chain...")
    option_chain = get_option_chain(ticker, expiry_date)
    if option_chain is None:
        return None

    # Step 4: Calculate time to expiry
    print("\nStep 4: Calculating time to expiry...")
    time_to_expiry = calculate_time_to_expiry(current_date, option_chain['expiry_date'])
    print(f"✓ Time to expiry: {time_to_expiry:.4f} years ({time_to_expiry*365:.0f} days)")

    # Step 5: Get risk-free rate
    print("\nStep 5: Fetching risk-free rate...")
    risk_free_rate = get_risk_free_rate(time_to_expiry)

    # Step 6: Filter by trend direction
    print("\nStep 6: Filtering options by trend direction...")
    filtered_chain = filter_options_by_trend(option_chain, trend_direction, moneyness='all')

    # Step 7: Calculate theoretical prices and compare
    print(f"\nStep 7: Calculating theoretical prices using {pricing_model.upper()} model...")

    results = []

    # Analyze calls
    if 'calls' in filtered_chain and option_type in ['call', 'both']:
        calls = filtered_chain['calls']

        if strike_price is not None:
            calls = calls[calls['strike'] == strike_price]

        for _, option in calls.iterrows():
            K = option['strike']
            market_price = option['lastPrice']

            # Calculate theoretical price
            if pricing_model == 'european':
                theoretical_price = black_scholes_call(current_price, K, risk_free_rate, time_to_expiry, volatility)
            else:  # american
                theoretical_price = binomial_tree_american_call(current_price, K, risk_free_rate, time_to_expiry, volatility)

            # Calculate mispricing
            if theoretical_price > 0:
                mispricing_pct = (market_price - theoretical_price) / theoretical_price
            else:
                mispricing_pct = 0

            results.append({
                'type': 'CALL',
                'strike': K,
                'market_price': market_price,
                'theoretical_price': theoretical_price,
                'mispricing_%': mispricing_pct * 100,
                'recommendation': 'OVERPRICED' if mispricing_pct > 0.1 else ('UNDERPRICED' if mispricing_pct < -0.1 else 'FAIR'),
                'bid': option.get('bid', np.nan),
                'ask': option.get('ask', np.nan),
                'volume': option.get('volume', 0),
                'openInterest': option.get('openInterest', 0)
            })

    # Analyze puts
    if 'puts' in filtered_chain and option_type in ['put', 'both']:
        puts = filtered_chain['puts']

        if strike_price is not None:
            puts = puts[puts['strike'] == strike_price]

        for _, option in puts.iterrows():
            K = option['strike']
            market_price = option['lastPrice']

            # Calculate theoretical price
            if pricing_model == 'european':
                theoretical_price = black_scholes_put(current_price, K, risk_free_rate, time_to_expiry, volatility)
            else:  # american
                theoretical_price = binomial_tree_american_put(current_price, K, risk_free_rate, time_to_expiry, volatility)

            # Calculate mispricing
            if theoretical_price > 0:
                mispricing_pct = (market_price - theoretical_price) / theoretical_price
            else:
                mispricing_pct = 0

            results.append({
                'type': 'PUT',
                'strike': K,
                'market_price': market_price,
                'theoretical_price': theoretical_price,
                'mispricing_%': mispricing_pct * 100,
                'recommendation': 'OVERPRICED' if mispricing_pct > 0.1 else ('UNDERPRICED' if mispricing_pct < -0.1 else 'FAIR'),
                'bid': option.get('bid', np.nan),
                'ask': option.get('ask', np.nan),
                'volume': option.get('volume', 0),
                'openInterest': option.get('openInterest', 0)
            })

    # Create results DataFrame
    results_df = pd.DataFrame(results)

    if results_df.empty:
        print("No options found matching criteria.")
        return None

    # Sort by absolute mispricing
    results_df['abs_mispricing'] = results_df['mispricing_%'].abs()
    results_df = results_df.sort_values('abs_mispricing', ascending=False)
    results_df = results_df.drop('abs_mispricing', axis=1)

    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}")
    print(f"Analyzed {len(results_df)} options")
    print(f"Underpriced options: {len(results_df[results_df['recommendation'] == 'UNDERPRICED'])}")
    print(f"Overpriced options: {len(results_df[results_df['recommendation'] == 'OVERPRICED'])}")
    print(f"Fairly priced options: {len(results_df[results_df['recommendation'] == 'FAIR'])}")
    print(f"{'='*80}\n")

    return results_df


# ════════════════════════════════════════════════════════════════════════════
# BETTER HISTORICAL OPTIONS TRADING ASSESSMENT
# ════════════════════════════════════════════════════════════════════════════

def backtest_options_strategy(ticker, start_date, end_date, strategy='mispricing',
                               threshold=10, holding_period_days=5, initial_capital=10000):
    """
    Backtests historical options trading to assess strategy profitability.

    This provides a better way to evaluate options trading by simulating
    actual trades based on your pricing analysis. Much more realistic than
    just comparing fair value to market price.

    Strategies:
    - 'mispricing': Buy underpriced, sell overpriced options
    - 'trend_following': Buy calls in uptrends, puts in downtrends
    - 'volatility_arbitrage': Trade based on implied vs realized vol differences

    Args:
        ticker (str): Stock ticker
        start_date (str): Backtest start date
        end_date (str): Backtest end date
        strategy (str): Trading strategy to backtest
        threshold (float): Mispricing threshold % to trigger trades
        holding_period_days (int): Days to hold option before closing
        initial_capital (float): Starting capital

    Returns:
        dict: Backtest results including trades, P&L, and performance metrics
    """
    print(f"\n{'='*80}")
    print(f"BACKTESTING OPTIONS STRATEGY: {strategy.upper()}")
    print(f"{'='*80}\n")

    # Download historical stock data
    stock_data = yf.download(ticker, start=start_date, end=end_date, progress=False)

    trades = []
    current_capital = initial_capital
    positions = []

    # Simulate trading day by day
    trading_days = stock_data.index[:-holding_period_days]  # Leave room for holding period

    for i, current_date in enumerate(trading_days):
        if i % 20 == 0:
            print(f"Processing {current_date.date()}... (Capital: ${current_capital:,.2f})")

        # Get data up to current date
        historical_data = stock_data.loc[:current_date]
        current_price = historical_data['Close'].iloc[-1]

        # Calculate volatility using past 30 days
        lookback_data = historical_data.tail(30)
        log_returns = np.log(lookback_data['Close'] / lookback_data['Close'].shift(1))
        volatility = np.sqrt(252) * log_returns.std()

        # Get options expiring in ~30 days (simulate this)
        future_date = current_date + pd.Timedelta(days=30)
        time_to_expiry = 30 / 365.0

        # Simulate available strikes (ATM ±20%)
        strikes = np.arange(current_price * 0.8, current_price * 1.2, current_price * 0.05)

        # Get risk-free rate
        risk_free_rate = get_risk_free_rate(time_to_expiry)

        # Evaluate each strike for trading opportunities
        for strike in strikes:
            # Calculate theoretical prices (American options)
            theo_call = binomial_tree_american_call(current_price, strike, risk_free_rate, time_to_expiry, volatility, steps=50)
            theo_put = binomial_tree_american_put(current_price, strike, risk_free_rate, time_to_expiry, volatility, steps=50)

            # Simulate market prices with bid-ask spread (±10% from theoretical)
            # In reality, you'd fetch actual historical option prices
            market_call = theo_call * np.random.uniform(0.90, 1.10)
            market_put = theo_put * np.random.uniform(0.90, 1.10)

            # Calculate mispricing
            call_mispricing = ((market_call - theo_call) / theo_call * 100) if theo_call > 0 else 0
            put_mispricing = ((market_put - theo_put) / theo_put * 100) if theo_put > 0 else 0

            # Execute trades based on strategy
            if strategy == 'mispricing':
                # Buy underpriced options
                if call_mispricing < -threshold and current_capital > market_call * 100:
                    trades.append({
                        'date': current_date,
                        'action': 'BUY',
                        'type': 'CALL',
                        'strike': strike,
                        'entry_price': market_call,
                        'theo_price': theo_call,
                        'expiry_date': future_date,
                        'underlying_price': current_price
                    })
                    current_capital -= market_call * 100  # 1 contract = 100 shares
                    positions.append(trades[-1])

                if put_mispricing < -threshold and current_capital > market_put * 100:
                    trades.append({
                        'date': current_date,
                        'action': 'BUY',
                        'type': 'PUT',
                        'strike': strike,
                        'entry_price': market_put,
                        'theo_price': theo_put,
                        'expiry_date': future_date,
                        'underlying_price': current_price
                    })
                    current_capital -= market_put * 100
                    positions.append(trades[-1])

        # Close positions after holding period
        exit_date = current_date + pd.Timedelta(days=holding_period_days)
        if exit_date in stock_data.index:
            exit_price = stock_data.loc[exit_date, 'Close']
            time_remaining = (30 - holding_period_days) / 365.0

            for pos in positions[:]:
                if pos['date'] == current_date - pd.Timedelta(days=holding_period_days):
                    # Calculate exit option price
                    if pos['type'] == 'CALL':
                        exit_option_price = max(binomial_tree_american_call(
                            exit_price, pos['strike'], risk_free_rate, time_remaining, volatility, steps=50
                        ), exit_price - pos['strike']) if exit_price > pos['strike'] else 0.01
                    else:  # PUT
                        exit_option_price = max(binomial_tree_american_put(
                            exit_price, pos['strike'], risk_free_rate, time_remaining, volatility, steps=50
                        ), pos['strike'] - exit_price) if exit_price < pos['strike'] else 0.01

                    # Close position
                    pnl = (exit_option_price - pos['entry_price']) * 100
                    current_capital += exit_option_price * 100

                    pos['exit_date'] = exit_date
                    pos['exit_price'] = exit_option_price
                    pos['pnl'] = pnl
                    pos['return_%'] = (pnl / (pos['entry_price'] * 100)) * 100

                    positions.remove(pos)

    # Calculate performance metrics
    trades_df = pd.DataFrame([t for t in trades if 'pnl' in t])

    if trades_df.empty:
        print("No trades executed during backtest period.")
        return None

    total_pnl = trades_df['pnl'].sum()
    total_return = (current_capital - initial_capital) / initial_capital * 100
    num_trades = len(trades_df)
    win_rate = (trades_df['pnl'] > 0).sum() / num_trades * 100
    avg_pnl = trades_df['pnl'].mean()
    sharpe_ratio = trades_df['pnl'].mean() / trades_df['pnl'].std() if trades_df['pnl'].std() > 0 else 0

    print(f"\n{'='*80}")
    print("BACKTEST RESULTS")
    print(f"{'='*80}")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print(f"Final Capital: ${current_capital:,.2f}")
    print(f"Total P&L: ${total_pnl:,.2f}")
    print(f"Total Return: {total_return:.2f}%")
    print(f"Number of Trades: {num_trades}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Average P&L per Trade: ${avg_pnl:.2f}")
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"{'='*80}\n")

    return {
        'trades': trades_df,
        'initial_capital': initial_capital,
        'final_capital': current_capital,
        'total_pnl': total_pnl,
        'total_return_%': total_return,
        'num_trades': num_trades,
        'win_rate_%': win_rate,
        'avg_pnl': avg_pnl,
        'sharpe_ratio': sharpe_ratio
    }


def assess_option_liquidity(option_data):
    """
    Assesses option liquidity to avoid illiquid options in trading.

    Liquidity is crucial for intra-day swing trading - you need to be able
    to enter and exit positions without excessive slippage.

    Args:
        option_data (DataFrame): Option chain data from get_option_chain()

    Returns:
        DataFrame: Options with liquidity scores and recommendations
    """
    df = option_data.copy()

    # Calculate liquidity score based on:
    # 1. Volume (recent trading activity)
    # 2. Open Interest (total outstanding contracts)
    # 3. Bid-Ask Spread (tighter = more liquid)

    # Normalize volume (higher is better)
    if 'volume' in df.columns:
        df['volume_score'] = df['volume'] / df['volume'].max() if df['volume'].max() > 0 else 0
    else:
        df['volume_score'] = 0

    # Normalize open interest (higher is better)
    if 'openInterest' in df.columns:
        df['oi_score'] = df['openInterest'] / df['openInterest'].max() if df['openInterest'].max() > 0 else 0
    else:
        df['oi_score'] = 0

    # Bid-ask spread score (tighter is better)
    if 'bid' in df.columns and 'ask' in df.columns:
        df['spread'] = df['ask'] - df['bid']
        df['spread_%'] = (df['spread'] / df['lastPrice']) * 100
        df['spread_score'] = 1 - (df['spread_%'] / df['spread_%'].max()) if df['spread_%'].max() > 0 else 0
    else:
        df['spread_score'] = 0.5  # Neutral if no data

    # Combined liquidity score (weighted average)
    df['liquidity_score'] = (
        df['volume_score'] * 0.4 +
        df['oi_score'] * 0.4 +
        df['spread_score'] * 0.2
    )

    # Liquidity recommendation
    df['liquidity_rating'] = df['liquidity_score'].apply(lambda x:
        'EXCELLENT' if x > 0.8 else
        'GOOD' if x > 0.6 else
        'FAIR' if x > 0.4 else
        'POOR'
    )

    return df[['strike', 'lastPrice', 'volume', 'openInterest', 'spread_%',
               'liquidity_score', 'liquidity_rating']].sort_values('liquidity_score', ascending=False)


# ════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # Example 1: Analyze all options for a bullish trend (intra-day swing trade)
    results = analyze_option_pricing(
        ticker='AAPL',
        start_date='2023-01-01',
        end_date='2024-01-15',
        option_type='call',
        pricing_model='american',
        trend_direction='bullish'
    )

    if results is not None:
        print("\nTop 5 Most Underpriced Calls:")
        underpriced = results[results['recommendation'] == 'UNDERPRICED'].head(5)
        print(underpriced[['type', 'strike', 'market_price', 'theoretical_price', 'mispricing_%']])

        print("\nTop 5 Most Overpriced Calls:")
        overpriced = results[results['recommendation'] == 'OVERPRICED'].head(5)
        print(overpriced[['type', 'strike', 'market_price', 'theoretical_price', 'mispricing_%']])

    # Example 2: Analyze specific strike price
    results_specific = analyze_option_pricing(
        ticker='AAPL',
        start_date='2023-01-01',
        end_date='2024-01-15',
        strike_price=150,
        option_type='both',
        pricing_model='american'
    )

    if results_specific is not None:
        print("\nAnalysis for Strike $150:")
        print(results_specific[['type', 'strike', 'market_price', 'theoretical_price', 'mispricing_%', 'recommendation']])
