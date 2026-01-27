import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_finance import candlestick_ohlc
import talib
import pandas_ta as ta


# When you run 
all_data = yf.download("all", start=start_date, end=end_date)
# yfinance downloads the historical price and volume data for all stocks on all major exchanges that are available through Yahoo Finance. This includes not just stocks on the NYSE, but also stocks on the NASDAQ, AMEX, and other exchanges.

# The downloaded data includes the following columns:

    # Open: The opening price of the stock on the specified date
    # High: The highest price of the stock on the specified date
    # Low: The lowest price of the stock on the specified date
    # Close: The closing price of the stock on the specified date
    # Adj Close: The closing price of the stock on the specified date, adjusted for any dividends, splits, or other corporate actions that occurred after that date
    # Volume: The trading volume of the stock on the specified date
# The data is returned as a pandas DataFrame, with each row representing the historical data for a single stock on a single day. The DataFrame includes a column called "Ticker" that specifies the stock's ticker symbol.


# Bollinger Bands are a type of technical analysis tool used to measure and track market volatility. 
# They consist of three lines: 
#   the middle band- which is a simple moving average of a specific time period; 
#   an upper band- which is calculated by adding two standard deviations to the middle band; 
#   a lower band- which is calculated by subtracting two standard deviations from the middle band.

# The upper and lower bands are plotted on a chart alongside the middle band, creating a channel that can be used to identify possible trend reversals, breakouts, or other potential 
# trading opportunities. The width of the bands can also be used to indicate changes in market volatility, with wider bands indicating higher volatility and narrower bands 
# indicating lower volatility. 

# Traders and investors use Bollinger Bands in various ways, such as to identify price trends, detect overbought or oversold conditions, and spot potential buy or sell signals.

# There are a number of stock market indicators that rely on volume, which is a measure of the number of shares of a particular security that are traded over a given period of time. 
# Some of the most commonly used volume-based indicators include:
    # On-Balance Volume (OBV) - This indicator takes a running total of volume and then adds or subtracts it based on whether the price of the security is up or down for the day. 
        # The resulting line can be used to identify potential changes in trend.
    # Chaikin Money Flow (CMF) - This indicator uses a combination of price and volume data to identify buying and selling pressure in a security. It measures the accumulation or 
        # distribution of a security by calculating the volume-weighted average price over a specific period.
    # Volume Weighted Average Price (VWAP) - This indicator calculates the average price of a security over a specific period, weighted by the volume traded at each price level. 
        # It is commonly used by institutional traders to assess their performance relative to the broader market.
    # Accumulation/Distribution Line (A/D Line) - This indicator uses volume to confirm trends in a security. It calculates the difference between the total volume on up days 
        # and the total volume on down days, and then adds this value to a running total. A rising A/D line indicates that the security is being accumulated by buyers, while a 
        # falling A/D line indicates distribution.
    # Money Flow Index (MFI) - This indicator combines price and volume data to identify buying and selling pressure in a security. It uses both the typical price for the period 
        # and the volume to calculate a money flow ratio, which is then used to generate an overbought/oversold signal.

#The Relative Strength Index (RSI) is a technical analysis indicator that measures the strength of a security by comparing its upward movements to its downward movements over 
# a specified period of time. It is calculated using a mathematical formula that produces a value between 0 and 100. A value above 70 is typically considered overbought, 
# indicating that the security may be due for a price correction, while a value below 30 is typically considered oversold, indicating that the security may be due for a price 
# rebound. The RSI is commonly used in conjunction with other technical indicators to help identify potential buy and sell signals.

#The Average Directional Index (ADX) is a technical analysis indicator that helps determine the strength of a trend. The ADX is usually plotted along with two other indicators: 
# the Positive Directional Indicator (+DI) and the Negative Directional Indicator (-DI). The ADX is calculated by taking the difference between the +DI and -DI, and dividing it 
# by the sum of the +DI and -DI over a given period of time. The resulting value is then smoothed with an exponential moving average. The ADX is usually measured on a scale 
# of 0 to 100, with readings above 25 indicating a strong trend, and readings below 20 indicating a weak trend.

#The rate of change, or ROC, is a technical indicator that measures the percentage change in price between the current price and the price a certain number of periods ago. 
# It is used to help identify the strength of a trend, as well as potential turning points in the market. The ROC can be calculated using the following formula:
    #ROC = ((Close - Close n periods ago) / Close n periods ago) x 100
#where "Close" is the current closing price and "Close n periods ago" is the closing price n periods ago. The result is expressed as a percentage.

#Stochastic is a momentum oscillator that compares the price of a security to its price range over a certain period of time. It is used to identify potential overbought or 
# oversold conditions in a security. The Stochastic oscillator consists of two lines, the %K line and the %D line. The %K line represents the current price relative to the range 
# over a certain period, while the %D line is a moving average of the %K line.
# Traders use the Stochastic oscillator to identify potential entry and exit points in a security. When the %K line crosses above the %D line, it is considered a buy signal, 
# while a crossover below the %D line is considered a sell signal. In addition, when the %K line moves above the 80 level, the security is considered overbought, 
# while a move below the 20 level is considered oversold.
# It's important to note that Stochastic oscillators are just one tool among many that traders use to make investment decisions. They should not be relied on solely for making 
# trading decisions, but instead should be used in conjunction with other technical and fundamental analysis tools.

#Supertrend is a technical analysis indicator used to identify trend direction and possible trend reversals in the stock market. The Supertrend indicator is calculated using 
# a combination of Average True Range (ATR) and the stock's closing prices. It places a line above and below the stock prices to indicate support and resistance levels. When 
# the price of the stock crosses above the upper line, it is considered a buy signal, and when it crosses below the lower line, it is considered a sell signal.



#Pull data for specific ticker
def get_stock_data(ticker, start_date, end_date):
    data = yf.download(ticker, start=start_date, end=end_date)
    data = data.reset_index()
    data = data[['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]
    return data

#Index
def calculate_rsi(data, n=14):
    """Calculate the Relative Strength Index (RSI) for a given DataFrame of stock prices."""
    # Get the differences between consecutive prices
    delta = data.diff().dropna()

    # Calculate the gains and losses
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # Calculate the smoothed average gains and losses
    avg_gain = gain.rolling(n).mean()
    avg_loss = loss.rolling(n).mean()

    # Calculate the Relative Strength (RS) and RSI
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Return the RSI as a Pandas DataFrame
    return pd.DataFrame(rsi, columns=['RSI'])


# Define function to calculate ADX, +DI, and -DI
def calculate_adx(ticker, start_date, end_date):
    # Get stock data
    data = get_stock_data(ticker, start_date, end_date)

    # Calculate ADX, +DI, and -DI
    data['ADX'] = talib.ADX(data['High'], data['Low'], data['Close'], timeperiod=14)
    data['PDI'] = talib.PLUS_DI(data['High'], data['Low'], data['Close'], timeperiod=14)
    data['NDI'] = talib.MINUS_DI(data['High'], data['Low'], data['Close'], timeperiod=14)

    # Return the calculated data
    return data


def calculate_roc(n=12):
    data = get_stock_data(ticker, start_date, end_date)
    roc = pd.Series((data['Close'].diff(n) / data['Close'].shift(n)) * 100, name='ROC_' + str(n))
    data = data.join(roc)
    return data

def calculate_supertrend(ticker, start_date, end_date, period=7, multiplier=3):
    data = get_stock_data(ticker, start_date, end_date)
    data['HLC'] = (data['High'] + data['Low'] + data['Close']) / 3
    data['ATR'] = data['HLC'].diff().abs()
    data['ATR'] = data['ATR'].rolling(window=period).mean()
    data['Upper Band'] = (data['HLC'] + multiplier * data['ATR'])
    data['Lower Band'] = (data['HLC'] - multiplier * data['ATR'])
    data['SMA'] = data['HLC'].rolling(window=period).mean()
    data['Signal'] = np.nan
    data['Supertrend'] = np.nan
    
    for i in range(period, len(data)):
        previous_supertrend = data['Supertrend'][i-1]
        previous_close = data['Close'][i-1]
        previous_signal = data['Signal'][i-1]
        current_high = data['High'][i]
        current_low = data['Low'][i]
        current_close = data['Close'][i]
        current_sma = data['SMA'][i]
        previous_upper_band = data['Upper Band'][i-1]
        previous_lower_band = data['Lower Band'][i-1]
        previous_atr = data['ATR'][i-1]
        
        if previous_supertrend == previous_upper_band and current_close <= previous_upper_band:
            current_supertrend = previous_upper_band
            current_signal = current_supertrend - (multiplier * previous_atr)
        elif previous_supertrend == previous_upper_band and current_close > previous_upper_band:
            current_supertrend = previous_lower_band
            current_signal = current_supertrend + (multiplier * previous_atr)
        elif previous_supertrend == previous_lower_band and current_close >= previous_lower_band:
            current_supertrend = previous_lower_band
            current_signal = current_supertrend + (multiplier * previous_atr)
        elif previous_supertrend == previous_lower_band and current_close < previous_lower_band:
            current_supertrend = previous_upper_band
            current_signal = current_supertrend - (multiplier * previous_atr)
        
        data['Supertrend'][i] = current_supertrend
        data['Signal'][i] = current_signal
    
    return data

def calculate_vpt(ticker, start_date, end_date):
    data = get_stock_data(ticker, start_date, end_date)
    data.ta.vpt(inplace=True)
    return data




#charts
def on_balance_volume(data):
    prev_obv = 0
    obv = []
    for i in range(len(data)):
        if i == 0:
            obv.append(data['Volume'][i])
        else:
            if data['Close'][i] > data['Close'][i-1]:
                current_obv = prev_obv + data['Volume'][i]
            elif data['Close'][i] < data['Close'][i-1]:
                current_obv = prev_obv - data['Volume'][i]
            else:
                current_obv = prev_obv
            obv.append(current_obv)
            prev_obv = current_obv
    return obv

def chaikin_money_flow(data):
    mfm = ((data['Close'] - data['Low']) - (data['High'] - data['Close'])) / (data['High'] - data['Low'])
    mfv = mfm * data['Volume']
    cmf = pd.Series(mfv.rolling(window=20).sum()) / pd.Series(data['Volume'].rolling(window=20).sum())
    return cmf

def volume_weighted_average_price(data):
    vwap = (data['Volume'] * (data['High'] + data['Low'] + data['Close'])) / (3 * data['Volume'])
    return vwap

def accumulation_distribution_line(data):
    adl = ((data['Close'] - data['Low']) - (data['High'] - data['Close'])) / (data['High'] - data['Low']) * data['Volume']
    adl = adl.cumsum()
    return adl

def money_flow_index(data):
    typical_price = (data['High'] + data['Low'] + data['Close']) / 3
    money_flow = typical_price * data['Volume']
    money_ratio = (money_flow * (typical_price.diff(1) > 0)).rolling(window=14).sum() / \
                  (money_flow * (typical_price.diff(1) < 0)).rolling(window=14).sum()
    money_flow_index = 100 - (100 / (1 + money_ratio))
    return money_flow_index

def bollinger_bands(data, window=20):
    sma = data['Close'].rolling(window=window).mean()
    std = data['Close'].rolling(window=window).std()
    upper = sma + (2 * std)
    lower = sma - (2 * std)
    return upper, lower

def trend_line(data):
    x = np.arange(len(data))
    z = np.polyfit(x, data['Close'], 1)
    p = np.poly1d(z)
    trend_line = p(x)
    return trend_line

def moving_averages(data, short=7, long=14, short_smoothing=1, long_smoothing=2):
    short_ma = data['Close'].rolling(window=short).mean().ewm(span=short_smoothing, adjust=False).mean()
    long_ma = data['Close'].rolling(window=long).mean().ewm(span=long_smoothing, adjust=False).mean()
    return short_ma, long_ma

def calculate_macd(df, fast_period=12, slow_period=26, signal_period=9):
    # Calculate the Exponential Moving Averages
    ema_fast = df['Close'].ewm(span=fast_period, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=slow_period, adjust=False).mean()

    # Calculate the MACD Line
    macd = ema_fast - ema_slow

    # Calculate the Signal Line
    signal = macd.ewm(span=signal_period, adjust=False).mean()

    # Calculate the MACD Histogram
    histogram = macd - signal

    # Add the MACD Line, Signal Line, and Histogram to the data frame
    df['MACD'] = macd
    df['Signal Line'] = signal
    df['Histogram'] = histogram

    return df

def stochastic_oscillator(data, n=14):
    # calculate the lowest low and highest high in the last n periods
    data['low_min'] = data['Low'].rolling(n).min()
    data['high_max'] = data['High'].rolling(n).max()

    # calculate %K and %D
    data['%K'] = 100 * (data['Close'] - data['low_min']) / (data['high_max'] - data['low_min'])
    data['%D'] = data['%K'].rolling(3).mean()

    return data

class TechnicalIndicators:
      
    def get_hist_data(self, hist_data):
        return pd.cut(hist_data, bins=50).value_counts().to_dict().items()

def percent_number_of_stocks_above_moving_average(df, moving_avg_col, threshold):
    """
    Calculates the percentage of stocks in the dataframe that are above a moving average threshold.
    
    Args:
        df (pd.DataFrame): The input dataframe containing the stock data.
        moving_avg_col (str): The name of the column containing the moving average values.
        threshold (float): The threshold value to compare the stock data to.
    
    Returns:
        float: The percentage of stocks above the threshold.
    """
    return (df[moving_avg_col] > threshold).mean() * 100

def periodic_high_and_lows(df, window):
    """
    Calculates the periodic high and low values of the stock data over a rolling window.
    
    Args:
        df (pd.DataFrame): The input dataframe containing the stock data.
        window (int): The size of the rolling window.
    
    Returns:
        pd.DataFrame: The periodic high and low values.
    """
    high = df['High'].rolling(window).max()
    low = df['Low'].rolling(window).min()
    return pd.DataFrame({'Periodic High': high, 'Periodic Low': low})

def advance_decline(df, volume_col):
    """
    Calculates the advance-decline line using the volume data.
    
    Args:
        df (pd.DataFrame): The input dataframe containing the stock data.
        volume_col (str): The name of the column containing the volume values.
    
    Returns:
        pd.Series: The advance-decline line values.
    """
    advances = df[df['Close'] > df['Open']][volume_col].sum()
    declines = df[df['Close'] < df['Open']][volume_col].sum()
    return pd.Series(advances - declines, index=df['Date'])


from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volume import OnBalanceVolumeIndicator
from ta.utils import dropna

def percent_number_of_stocks_above_moving_average(data):
    data['MA50'] = data['Close'].rolling(window=50).mean()
    data['MA200'] = data['Close'].rolling(window=200).mean()
    data['%MA50'] = (data['Close']/data['MA50'] - 1) * 100
    data['%MA200'] = (data['Close']/data['MA200'] - 1) * 100
    return data[['Date', '%MA50', '%MA200']].dropna()
    
def periodic_high_and_lows(data):
    data['52WHigh'] = data['High'].rolling(window=252, min_periods=1).max()
    data['52WLow'] = data['Low'].rolling(window=252, min_periods=1).min()
    data['%52WHigh'] = (data['Close']/data['52WHigh'] - 1) * 100
    data['%52WLow'] = (data['Close']/data['52WLow'] - 1) * 100
    return data[['Date', '%52WHigh', '%52WLow']].dropna()

def advance_decline(data):
    data['Advances'] = (data['Close'] > data['Close'].shift(1)).rolling(window=30, min_periods=1).sum()
    data['Declines'] = (data['Close'] < data['Close'].shift(1)).rolling(window=30, min_periods=1).sum()
    data['%A/D'] = data['Advances'] / (data['Advances'] + data['Declines']) * 100
    return data[['Date', '%A/D']].dropna()


#Functions to analyze above indicators
def trend_break(df, trend_col, direction_col):
    """
    This function identifies the time when a trend line is broken.
    Args:
        df (pd.DataFrame): Dataframe containing historical data of a security.
        trend_col (str): Name of the column containing the trend line values.
        direction_col (str): Name of the column to store the direction of the trend (increasing or decreasing).

    Returns:
        A list of tuples containing the date and direction of the trend (increasing or decreasing) when the trend line was broken.
    """
    trend = df[trend_col]
    prev_trend = trend[0]
    direction = ""
    trend_breaks = []
    for i in range(1, len(df)):
        if trend[i] > prev_trend:
            if direction != "increasing":
                direction = "increasing"
        elif trend[i] < prev_trend:
            if direction != "decreasing":
                direction = "decreasing"
        else:
            continue

        if (trend[i] > trend[i-1] and trend[i] > trend[i+1]) or (trend[i] < trend[i-1] and trend[i] < trend[i+1]):
            trend_breaks.append((df.iloc[i]['Date'], direction))
        prev_trend = trend[i]
    return trend_breaks

#we can make this function dynamic and apply it to any previously created indicator. We can create a new function that takes the data for the indicator, as well as the trend 
# line breakpoints and the column names for the signal line and histogram, and returns a DataFrame with information on each trend line break.
def trend_line_break_accuracy(data, trend_breaks, signal_col, hist_col):
    """
    Calculate the accuracy of the given indicator at each trend line break.

    Args:
        data (pd.DataFrame): DataFrame containing the indicator data
        trend_breaks (pd.DataFrame): DataFrame containing trend line breaks
        signal_col (str): Name of the column containing the signal line data
        hist_col (str): Name of the column containing the histogram data

    Returns:
        pd.DataFrame: DataFrame containing information on each trend line break
    """
    results = []
    for i, row in trend_breaks.iterrows():
        start_date = row['start_date']
        end_date = row['end_date']
        trend_direction = row['trend_direction']
        signal_start = data.loc[data['Date'] == start_date, signal_col].values[0]
        signal_end = data.loc[data['Date'] == end_date, signal_col].values[0]
        hist_start = data.loc[data['Date'] == start_date, hist_col].values[0]
        hist_end = data.loc[data['Date'] == end_date, hist_col].values[0]
        if trend_direction == 'upward':
            if signal_end > signal_start and hist_end > hist_start:
                accuracy = 1
            elif signal_end > signal_start or hist_end > hist_start:
                accuracy = 0.5
            else:
                accuracy = 0
        else:
            if signal_end < signal_start and hist_end < hist_start:
                accuracy = 1
            elif signal_end < signal_start or hist_end < hist_start:
                accuracy = 0.5
            else:
                accuracy = 0
        results.append({
            'start_date': start_date,
            'end_date': end_date,
            'trend_direction': trend_direction,
            'accuracy': accuracy
        })
    return pd.DataFrame(results)
#To use this function, we can call it with the data for the indicator, the DataFrame of trend line breaks, and the names of the columns containing the signal line and histogram 
# data. Here's an example:
macd_data = ti.moving_average_convergence_divergence()
macd_breaks = ti.trend_line_breaks(moving_average_convergence_divergence, 'MACD')
macd_accuracy = trend_line_break_accuracy(macd_data, macd_breaks, 'MACD_signal', 'MACD_hist')
#This will generate a DataFrame with information on each trend line break for the MACD indicator, including the start and end dates, the trend direction, and the accuracy of the 
# MACD indicator at the time of the break.


def feature_engineering(df):
    # Add a column that measures the length of the trend
    df['trend_length'] = (pd.to_datetime(df['end_date']) - pd.to_datetime(df['start_date'])).dt.days
    
    # Add a column that measures the distance between the start and end price of the trend
    df['price_distance'] = df['end_price'] - df['start_price']
    
    # Add a column that measures the difference in the signal line values between the start and end of the trend
    df['signal_difference'] = df['end_signal'] - df['start_signal']
    
    # Add a column that measures the difference in the histogram values between the start and end of the trend
    df['hist_difference'] = df['end_hist'] - df['start_hist']
    
    # Add a column that measures the accuracy of the trend line break as a percentage
    df['accuracy_percentage'] = df['accuracy'] * 100
    
    # Add a column that measures the strength of the trend, which is the product of trend length and price distance
    df['trend_strength'] = df['trend_length'] * df['price_distance']
    
    return df
#This function takes in a dataframe that contains the output of trend_line_break_accuracy. It adds several new columns to the dataframe, including columns that measure the length of 
# the trend, the distance between the start and end price of the trend, the difference in the signal line values between the start and end of the trend, the difference in the 
# histogram values between the start and end of the trend, the accuracy of the trend line break as a percentage, and the strength of the trend.

#Here's an example script that would do feature engineering on the accuracy of each indicator when analyzed with trend_line_break_accuracy:

from docs.code_snippets.SP_historical_data import trend_break, trend_line_break_accuracy, feature_engineering


def analyze_indicator_accuracy(ticker, start_date, end_date, trend_col='Close', direction_col='trend_direction'):
    """
    Analyzes all technical indicators for a given stock and calculates their accuracy
    in predicting trend breaks.

    Args:
        ticker (str): Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')
        start_date (str): Start date in format 'YYYY-MM-DD'
        end_date (str): End date in format 'YYYY-MM-DD'
        trend_col (str): Column name to use for trend analysis (default: 'Close')
        direction_col (str): Column name to store trend direction (default: 'trend_direction')

    Returns:
        dict: Dictionary containing:
            - 'ti_object': TechnicalIndicators object (for further analysis)
            - 'all_data': DataFrame with all indicator data
            - 'trend_breaks': List of trend break tuples
            - 'accuracy_data': Dictionary of accuracy scores per indicator
            - 'accuracy_df': DataFrame with accuracy metrics and rankings
            - 'summary_stats': Dictionary with summary statistics

    Example:
        >>> results = analyze_indicator_accuracy('AAPL', '2010-01-01', '2021-12-31')
        >>> print(results['accuracy_df'])
        >>> print(f"Best indicator: {results['summary_stats']['best_indicator']}")
    """
    from TechnicalIndicators import TechnicalIndicators

    # Initialize TechnicalIndicators object
    print(f"Initializing analysis for {ticker} from {start_date} to {end_date}...")
    ti = TechnicalIndicators(ticker, start_date, end_date)

    # Get all indicator data
    print("Calculating all technical indicators...")
    all_data = ti.get_all_indicators()

    # Get trend line breaks
    print(f"Detecting trend breaks using '{trend_col}' column...")
    trend_breaks = trend_break(all_data, trend_col, direction_col)
    print(f"Found {len(trend_breaks)} trend breaks")

    # Dictionary to store accuracy data
    accuracy_data = {}

    # Loop through each indicator and calculate accuracy data
    print("Analyzing accuracy for each indicator...")
    for k, v in TechnicalIndicators.INDICATOR_FUNCTIONS.items():
        try:
            indicator_data = getattr(ti.data.ta, v)()
            trend_line_data = trend_line_break_accuracy(
                indicator_data,
                trend_breaks,
                f"{k}_signal",
                f"{k}_hist"
            )
            accuracy_data[k] = trend_line_data['accuracy'].mean()
            print(f"  ✓ {k}: {accuracy_data[k]:.2%}")
        except Exception as e:
            print(f"  ✗ {k}: Error - {str(e)}")
            accuracy_data[k] = None

    # Convert accuracy data to a DataFrame
    accuracy_df = pd.DataFrame.from_dict(
        accuracy_data,
        orient='index',
        columns=['accuracy']
    )

    # Remove None values (failed indicators)
    accuracy_df = accuracy_df.dropna()

    # Feature engineering on accuracy scores
    accuracy_df['above_mean'] = accuracy_df['accuracy'] > accuracy_df['accuracy'].mean()
    accuracy_df['rank'] = accuracy_df['accuracy'].rank(ascending=False)
    accuracy_df['percentile'] = accuracy_df['accuracy'].rank(pct=True) * 100
    accuracy_df = accuracy_df.sort_values('rank')

    # Calculate summary statistics
    summary_stats = {
        'ticker': ticker,
        'date_range': f"{start_date} to {end_date}",
        'total_indicators': len(accuracy_df),
        'trend_breaks_detected': len(trend_breaks),
        'mean_accuracy': accuracy_df['accuracy'].mean(),
        'median_accuracy': accuracy_df['accuracy'].median(),
        'std_accuracy': accuracy_df['accuracy'].std(),
        'best_indicator': accuracy_df.index[0],
        'best_accuracy': accuracy_df['accuracy'].iloc[0],
        'worst_indicator': accuracy_df.index[-1],
        'worst_accuracy': accuracy_df['accuracy'].iloc[-1],
        'indicators_above_mean': accuracy_df['above_mean'].sum()
    }

    # Print summary
    print("\n" + "="*60)
    print("ANALYSIS SUMMARY")
    print("="*60)
    print(f"Ticker: {ticker}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Trend Breaks: {len(trend_breaks)}")
    print(f"Indicators Analyzed: {len(accuracy_df)}")
    print(f"Mean Accuracy: {summary_stats['mean_accuracy']:.2%}")
    print(f"Best Indicator: {summary_stats['best_indicator']} ({summary_stats['best_accuracy']:.2%})")
    print(f"Worst Indicator: {summary_stats['worst_indicator']} ({summary_stats['worst_accuracy']:.2%})")
    print("="*60 + "\n")

    # Return comprehensive results
    return {
        'ti_object': ti,
        'all_data': all_data,
        'trend_breaks': trend_breaks,
        'accuracy_data': accuracy_data,
        'accuracy_df': accuracy_df,
        'summary_stats': summary_stats
    }


def compare_multiple_stocks(tickers, start_date, end_date, trend_col='Close'):
    """
    Analyzes indicator accuracy across multiple stocks for comparison.

    Args:
        tickers (list): List of ticker symbols
        start_date (str): Start date in format 'YYYY-MM-DD'
        end_date (str): End date in format 'YYYY-MM-DD'
        trend_col (str): Column name for trend analysis (default: 'Close')

    Returns:
        dict: Dictionary with ticker symbols as keys, analysis results as values

    Example:
        >>> results = compare_multiple_stocks(['AAPL', 'MSFT', 'GOOGL'], '2020-01-01', '2023-12-31')
        >>> for ticker, result in results.items():
        >>>     print(f"{ticker}: Best = {result['summary_stats']['best_indicator']}")
    """
    results = {}

    for ticker in tickers:
        print(f"\n{'='*60}")
        print(f"Analyzing {ticker}...")
        print(f"{'='*60}")

        try:
            results[ticker] = analyze_indicator_accuracy(ticker, start_date, end_date, trend_col)
        except Exception as e:
            print(f"Error analyzing {ticker}: {str(e)}")
            results[ticker] = None

    return results


def export_results(results, output_dir='.'):
    """
    Exports analysis results to CSV files.

    Args:
        results (dict): Results from analyze_indicator_accuracy()
        output_dir (str): Directory to save output files

    Returns:
        dict: Paths to exported files
    """
    import os

    ticker = results['summary_stats']['ticker']
    timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')

    # Export accuracy DataFrame
    accuracy_file = os.path.join(output_dir, f"{ticker}_indicator_accuracy_{timestamp}.csv")
    results['accuracy_df'].to_csv(accuracy_file)

    # Export summary stats
    summary_file = os.path.join(output_dir, f"{ticker}_summary_{timestamp}.txt")
    with open(summary_file, 'w') as f:
        for key, value in results['summary_stats'].items():
            f.write(f"{key}: {value}\n")

    print(f"\nExported results:")
    print(f"  - Accuracy data: {accuracy_file}")
    print(f"  - Summary stats: {summary_file}")

    return {
        'accuracy_file': accuracy_file,
        'summary_file': summary_file
    }


# ════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE - Ready to use variable
# ════════════════════════════════════════════════════════════════════════════

# Original example from your code, now as a function call
aapl_results = analyze_indicator_accuracy('AAPL', '2010-01-01', '2021-12-31')

# Access the results
ti = aapl_results['ti_object']              # TechnicalIndicators object
all_data = aapl_results['all_data']         # All indicator data
trend_breaks = aapl_results['trend_breaks'] # Trend break points
accuracy_data = aapl_results['accuracy_data'] # Raw accuracy dictionary
accuracy_df = aapl_results['accuracy_df']   # Formatted accuracy DataFrame (same as your original)
summary_stats = aapl_results['summary_stats'] # Summary statistics

# Print the accuracy DataFrame (equivalent to your original line 487)
print(accuracy_df)


# ════════════════════════════════════════════════════════════════════════════
# ADDITIONAL EXAMPLES
# ════════════════════════════════════════════════════════════════════════════

"""
# Example 1: Analyze a different stock
msft_results = analyze_indicator_accuracy('MSFT', '2015-01-01', '2023-12-31')
print(msft_results['accuracy_df'])

# Example 2: Compare multiple stocks
stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
multi_results = compare_multiple_stocks(stocks, '2020-01-01', '2023-12-31')

# Find best indicator across all stocks
for ticker, result in multi_results.items():
    if result:
        best = result['summary_stats']['best_indicator']
        accuracy = result['summary_stats']['best_accuracy']
        print(f"{ticker}: {best} ({accuracy:.2%})")

# Example 3: Export results
export_results(aapl_results, output_dir='./analysis_results')

# Example 4: Access specific data for further analysis
# Get the top 5 indicators
top_5 = aapl_results['accuracy_df'].head(5)
print("Top 5 Indicators:")
print(top_5)

# Get indicators above mean
above_mean = aapl_results['accuracy_df'][aapl_results['accuracy_df']['above_mean']]
print(f"\n{len(above_mean)} indicators above mean accuracy")

# Example 5: Use the TechnicalIndicators object for more analysis
ti_object = aapl_results['ti_object']
# Now you can call other methods on ti_object if needed
"""

#In this script, we first initialize a TechnicalIndicators object to get all indicator data. We then calculate trend line breaks using the trend_break function and store the 
# results in a DataFrame. Next, we loop through each indicator and calculate accuracy data using the trend_line_break_accuracy function. We store the accuracy data in a dictionary.

#We then convert the accuracy data to a DataFrame and perform feature engineering on the accuracy scores. In this example, we add two features: above_mean, which indicates whether 
# an indicator's accuracy is above the mean accuracy score across all indicators, and rank, which ranks the indicators by accuracy score.

#Finally, we sort the DataFrame by the rank column and print the accuracy data with features.


def filter_best_indicators(results, min_accuracy=0.80, max_accuracy=0.90):
    """
    Filters indicators based on accuracy thresholds to avoid overtraining.

    Args:
        results (dict): Results from analyze_indicator_accuracy()
        min_accuracy (float): Minimum accuracy threshold (default: 0.80 or 80%)
        max_accuracy (float): Maximum accuracy threshold (default: 0.90 or 90%)

    Returns:
        dict: Dictionary containing:
            - 'best_indicators_df': DataFrame with filtered indicators
            - 'indicator_names': List of indicator names that meet criteria
            - 'count': Number of indicators that meet criteria
            - 'mean_accuracy': Mean accuracy of filtered indicators

    Example:
        >>> results = analyze_indicator_accuracy('AAPL', '2010-01-01', '2021-12-31')
        >>> best = filter_best_indicators(results, min_accuracy=0.80, max_accuracy=0.90)
        >>> print(f"Found {best['count']} indicators in the 80-90% range")
        >>> print(best['indicator_names'])
    """
    accuracy_df = results['accuracy_df']

    # Filter indicators within the accuracy range
    filtered_df = accuracy_df[
        (accuracy_df['accuracy'] >= min_accuracy) &
        (accuracy_df['accuracy'] <= max_accuracy)
    ].copy()

    # Get list of indicator names
    indicator_names = filtered_df.index.tolist()

    # Calculate statistics
    count = len(filtered_df)
    mean_acc = filtered_df['accuracy'].mean() if count > 0 else 0

    print(f"\n{'='*60}")
    print(f"INDICATOR FILTERING RESULTS")
    print(f"{'='*60}")
    print(f"Accuracy Range: {min_accuracy:.0%} - {max_accuracy:.0%}")
    print(f"Indicators Found: {count}")
    print(f"Mean Accuracy: {mean_acc:.2%}")
    print(f"\nFiltered Indicators:")
    for idx, (name, row) in enumerate(filtered_df.iterrows(), 1):
        print(f"  {idx}. {name}: {row['accuracy']:.2%} (Rank: {int(row['rank'])})")
    print(f"{'='*60}\n")

    return {
        'best_indicators_df': filtered_df,
        'indicator_names': indicator_names,
        'count': count,
        'mean_accuracy': mean_acc,
        'accuracy_range': (min_accuracy, max_accuracy)
    }


def export_best_indicators(results, best_indicators, output_dir='.'):
    """
    Exports the best indicators and their data for use in future models.

    Args:
        results (dict): Results from analyze_indicator_accuracy()
        best_indicators (dict): Results from filter_best_indicators()
        output_dir (str): Directory to save output files

    Returns:
        dict: Paths to exported files
    """
    import os

    ticker = results['summary_stats']['ticker']
    timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')

    # Export filtered indicators
    best_file = os.path.join(output_dir, f"{ticker}_best_indicators_{timestamp}.csv")
    best_indicators['best_indicators_df'].to_csv(best_file)

    # Export indicator names as a text file for easy reference
    names_file = os.path.join(output_dir, f"{ticker}_indicator_names_{timestamp}.txt")
    with open(names_file, 'w') as f:
        f.write(f"Best Indicators for {ticker}\n")
        f.write(f"Accuracy Range: {best_indicators['accuracy_range'][0]:.0%} - {best_indicators['accuracy_range'][1]:.0%}\n")
        f.write(f"Total Indicators: {best_indicators['count']}\n")
        f.write(f"Mean Accuracy: {best_indicators['mean_accuracy']:.2%}\n\n")
        f.write("Indicator Names:\n")
        for name in best_indicators['indicator_names']:
            f.write(f"  - {name}\n")

    # Export the actual indicator data columns from all_data
    indicator_data = results['all_data'][best_indicators['indicator_names']]
    data_file = os.path.join(output_dir, f"{ticker}_indicator_data_{timestamp}.csv")
    indicator_data.to_csv(data_file)

    print(f"\nExported best indicators:")
    print(f"  - Best indicators summary: {best_file}")
    print(f"  - Indicator names list: {names_file}")
    print(f"  - Indicator data: {data_file}")

    return {
        'best_indicators_file': best_file,
        'names_file': names_file,
        'data_file': data_file
    }

#Keras Model

from sklearn.model_selection import train_test_split
from keras.models import Sequential
from keras.layers import Dense, Dropout
from keras.optimizers import Adam

# Load data
data = pd.read_csv('accuracy_features.csv')

# Split data into train and test sets
train_data, test_data = train_test_split(data, test_size=0.2)

# Separate features and target
X_train = train_data.drop(['accuracy'], axis=1).values
y_train = train_data['accuracy'].values
X_test = test_data.drop(['accuracy'], axis=1).values
y_test = test_data['accuracy'].values

# Define the neural network model
model = Sequential()
model.add(Dense(64, input_dim=X_train.shape[1], activation='relu'))
model.add(Dropout(0.2))
model.add(Dense(32, activation='relu'))
model.add(Dropout(0.2))
model.add(Dense(1, activation='sigmoid'))

# Compile the model
model.compile(loss='binary_crossentropy', optimizer=Adam(lr=0.001), metrics=['accuracy'])

# Train the model
model.fit(X_train, y_train, validation_data=(X_test, y_test), epochs=50, batch_size=32)

# Evaluate the model on test data
loss, accuracy = model.evaluate(X_test, y_test)
print(f'Test loss: {loss}')
print(f'Test accuracy: {accuracy}')

#This code first loads the feature engineered data from a CSV file, then splits it into train and test sets. It then defines a neural network model with two hidden layers and 
# one output layer. The model is trained on the train data and evaluated on the test data. The final accuracy of the model is printed.


#Stock Options pricing-
# To generate stock option prices for a stock for x years, you would need access to an options data source, such as an options exchange or data vendor. You would need to obtain 
# an API key or authentication credentials to access the options data source.

# Once you have access to the options data source, you can use a function to retrieve the option prices for a given stock symbol and date range. Here is an example of a dynamic 
# function that retrieves option prices using the yfinance library:

def get_option_prices(symbol, start_date, end_date):
    start = datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=30)
    end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=30)
    data = yf.download(symbol, start=start, end=end, group_by='ticker', prepost=True)
    options_data = data['OPTIONS']
    return options_data
# This function takes in the stock symbol, start date, and end date as parameters, and returns a DataFrame containing the option prices for the given stock and date range.

# Note that the prepost parameter is set to True, which allows the function to retrieve option prices outside of regular trading hours. This may not be necessary for all use cases.

# Keep in mind that options prices can be quite volatile and may not always be available for all stocks and date ranges. It's important to carefully consider the quality and 
# availability of the data before using it for any analysis or trading decisions.

#here is a high-level overview of what the function might look like:

#The function would take in the following parameters:

    # ticker: the stock ticker symbol (e.g. "AAPL")
    # start_date: the start date for the data (e.g. "2020-01-01")
    # end_date: the end date for the data (e.g. "2021-12-31")

# The function would use the requests library to make an API call to the CBOE Options API.
# The API response would be in JSON format, so the function would use the json library to parse the response into a Python dictionary.
# The function would then extract the relevant data from the dictionary, such as the option prices, expiration dates, and strike prices.
# The function would return the data in a Pandas DataFrame for further analysis.

# Note that the specifics of the function would depend on the specific API being used, as well as the format of the API response. Additionally, there may be rate limits or other restrictions on API usage that would need to be taken into account.


#Black-Scholes Fair value comparison 
from scipy.stats import norm

def black_scholes_call(S, K, r, t, sigma):
    d1 = (np.log(S / K) + (r + sigma ** 2 / 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)
    return S * norm.cdf(d1) - K * np.exp(-r * t) * norm.cdf(d2)

def option_analysis(ticker, start_date, end_date, strike_price, expiry_date):
    # Download historical stock data
    stock_data = yf.download(ticker, start=start_date, end=end_date)
    stock_data = stock_data.reset_index()

    # Calculate time to expiry in years
    expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d")
    time_to_expiry = (expiry_date - stock_data['Date']).dt.days / 365.0

    # Calculate stock price and risk-free rate
    stock_price = stock_data['Close'].values[-1]
    risk_free_rate = 0.02

    # Calculate annualized volatility of the stock price
    log_returns = np.log(stock_data['Close'] / stock_data['Close'].shift(1))
    volatility = np.sqrt(252) * log_returns.std()

    # Calculate the fair value price of the call option
    fair_value_price = black_scholes_call(stock_price, strike_price, risk_free_rate, time_to_expiry, volatility)

    # Retrieve option data
    option_data = yf.Ticker(f"{ticker}{expiry_date.strftime('%y%m%d')}C{strike_price}").option_chain(expiry_date.strftime("%Y-%m-%d")).calls

    # Get the option price and calculate the percent difference from the fair value price
    option_price = option_data[option_data['inTheMoney'] == False]['lastPrice'].values[0]
    percent_diff = (option_price - fair_value_price) / fair_value_price

    # Return the fair value price, option price, and percent difference
    return fair_value_price, option_price, percent_diff

ticker = 'AAPL'
start_date = '2019-01-01'
end_date = '2021-01-01'
strike_price = 150
expiry_date = '2021-03-19'

fair_value_price, option_price, percent_diff = option_analysis(ticker, start_date, end_date, strike_price, expiry_date)
print(f"Fair value price: {fair_value_price}")
print(f"Option price: {option_price}")
print(f"Percent difference: {percent_diff}")

# Note that this script assumes that you have access to a Yahoo Finance API key in order to download the historical stock and option data. It also assumes that you have the 
# necessary permissions to access the CBOE Options API.

#Here's an example script that combines the output of the Black-Scholes pricing model with the Keras model to identify which indicator has high accuracy and is associated with 
# good stock option prices:
from keras.models import load_model
from black_scholes import black_scholes

# Load the Keras model
model = load_model('keras_model.h5')

# Load the accuracy and stock options data
accuracy_data = pd.read_csv('accuracy_features.csv')
options_data = pd.read_csv('stock_options_data.csv')

# Merge the accuracy and stock options data on the date column
data = pd.merge(accuracy_data, options_data, on='Date')

# Calculate the fair value price using the Black-Scholes pricing model
data['Fair Value'] = black_scholes(data['Spot Price'], data['Strike'], data['Risk-Free Rate'], data['Time to Maturity'], data['Volatility'])

# Use the Keras model to predict if the option is a good price
predictions = model.predict(data[['Indicator Accuracy', 'Fair Value']])

# Add the predictions to the dataframe
data['Good Price Prediction'] = predictions

# Print the top 10 rows of the dataframe
print(data.head(10))

#This script loads the Keras model, as well as the accuracy and stock options data. It merges the two datasets on the date column and calculates the fair value price using the 
# Black-Scholes pricing model. It then uses the Keras model to predict if the option is a good price, based on the indicator accuracy and the fair value price. 
# Finally, it adds the predictions to the dataframe and prints the top 10 rows.


# Yes, it is possible to create an Airflow DAG (Directed Acyclic Graph) to schedule and automate this script to run periodically. The DAG can then use the output of the script to 
# send an email notification when certain conditions are met, such as the appearance of a potential trade.

# To create this DAG, you would need to define the following components:
    # Operators: Airflow Operators are used to define the individual tasks in a DAG. For this workflow, you can use the BashOperator to execute the script that identifies potential 
    # trades, and the EmailOperator to send an email notification.

    # Tasks: Tasks are instances of operators with specific configurations. For this workflow, you can define a single task that executes the script.

    # Dependencies: DAGs consist of multiple tasks that have dependencies on one another. For this workflow, you can set up the task to depend on a specific time, such as running 
    # every morning at 9 am.

# Here is an example DAG that runs the script every day at 9 am, and sends an email notification if a potential trade is detected:
from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.email_operator import EmailOperator
from datetime import datetime

default_args = {
    'owner': 'you',
    'start_date': datetime(2023, 2, 20),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'stock_trading',
    default_args=default_args,
    schedule_interval='0 9 * * *',
)

run_analysis = BashOperator(
    task_id='run_analysis',
    bash_command='python /path/to/analysis_script.py',
    dag=dag,
)

send_notification = EmailOperator(
    task_id='send_notification',
    to='youremail@example.com',
    subject='Potential trade detected',
    html_content='A potential trade has been detected. Please review the analysis results.',
    trigger_rule='one_success',
    dag=dag,
)

run_analysis >> send_notification
#You can customize this example DAG to fit your specific use case by adjusting the BashOperator command to execute your script, setting the email address and content in the 
# EmailOperator, and configuring the time interval for the schedule_interval parameter.


#Airflow sensors are used to pause a DAG until a specific condition is met. In this case, we want to create a sensor that triggers when a potential trade appears. We can create 
# a PythonOperator that executes a function to check if there are any potential trades, and a CustomSensor that waits until the PythonOperator indicates that there is a 
# potential trade.

#Here is an example implementation:

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.sensors.base_sensor_operator import BaseSensorOperator
from airflow.utils.decorators import apply_defaults
from datetime import datetime, timedelta

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2021, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'trade_watcher',
    default_args=default_args,
    schedule_interval=timedelta(minutes=30)
)

def check_for_trades():
    # Check for potential trades
    # Return True if there are potential trades, False otherwise
    pass

check_for_trades_operator = PythonOperator(
    task_id='check_for_trades',
    python_callable=check_for_trades,
    dag=dag
)

class TradeSensor(BaseSensorOperator):
    @apply_defaults
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def poke(self, context):
        if check_for_trades():
            return True
        else:
            return False

trade_sensor = TradeSensor(
    task_id='trade_sensor',
    dag=dag
)

check_for_trades_operator >> trade_sensor

#This DAG has two tasks: check_for_trades_operator, which executes a Python function to check for potential trades, and trade_sensor, which waits until the check_for_trades_operator 
# indicates that there are potential trades. Once the trade_sensor detects that there are potential trades, it will unblock the DAG and allow downstream tasks to execute.



#We can create a neural network to analyze when a trend break is going to happen soon.

# The first step would be to define the inputs and outputs for the neural network. The inputs could include various technical indicators such as moving averages, relative strength 
# index, and other indicators that could potentially signal a trend break. The output of the neural network would be a binary classification, indicating whether a trend break is 
# likely to occur soon or not.

# We can then train the neural network using historical data to learn the patterns and relationships between the inputs and the output. Once the neural network is trained, we can 
# use it to make predictions on new data and identify potential trend breaks.

# It's important to note that creating an accurate neural network for predicting trend breaks is a complex task that requires careful consideration of the data and model 
# architecture. Additionally, no prediction model can perfectly predict future trends in the market, so it's important to carefully manage risk and not rely solely on a 
# prediction model for making investment decisions.

# To create a neural network that predicts when a trend break is going to happen soon, we can use a time series forecasting model like an LSTM (Long Short-Term Memory) network.

# Here's an example of how to create an LSTM network for this purpose:
from keras.models import Sequential
from keras.layers import LSTM, Dense

def create_lstm_model(input_shape):
    model = Sequential()
    model.add(LSTM(50, activation='relu', input_shape=input_shape))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mse')
    return model
# In this example, we create a function create_lstm_model that takes an input shape and returns a compiled LSTM model.

# The model architecture consists of a single LSTM layer with 50 units and a ReLU activation function, followed by a single dense layer with a single output neuron. We use the 
# mean squared error loss function and the Adam optimization algorithm to train the model.

# To train the model, we can use historical price data for the security we are interested in, along with any indicators that we have identified as useful for predicting trend 
# breaks. We can then use the trained model to make predictions on new data in real time.

# We can also incorporate the stock option pricing data and the Black-Scholes pricing model into the model by including the relevant data as additional features in the input 
# data.




# there are many ways to potentially improve the performance of a neural network for trend prediction. Some options include:

# Increasing the size of the neural network by adding more layers or nodes to the existing architecture.
# Using more advanced activation functions such as LeakyReLU or PReLU.
# Using more advanced optimization algorithms such as Adam or RMSProp.
# Increasing the amount of data used to train the model by using data from more securities or from a longer period of time.
# Adding additional features to the model such as news sentiment or macroeconomic data that could potentially impact the trend of a security.
# Using a more advanced model architecture such as a convolutional neural network (CNN) or long short-term memory (LSTM) network.
# These are just a few examples of potential ways to improve the performance of a neural network for trend prediction. Ultimately, the best approach will depend on the specific 
# problem being addressed and the available data.




# after training the models, we can package them up and create an API with an interface so that users can access the models and make predictions. This can be done using a web 
# framework like Flask or Django, which allow us to create endpoints that receive input data, run it through the models, and return predictions to the user.

# The API can be hosted on a cloud platform like Amazon Web Services or Google Cloud Platform, which can handle scaling and provide additional tools for deployment and management.

# The interface can be developed using HTML/CSS/JavaScript, which can be served by the same server that hosts the API, or as a standalone web application that communicates with 
# the API via HTTP requests.

# By packaging the models in this way, users can access the predictive power of the models without needing to be familiar with the underlying machine learning algorithms or 
# programming languages.

# here is an example of how you could use Flask, AWS and HTML/CSS/JS to create an interface for the models you've created:

# First, you'll need to create a Flask app that hosts your machine learning models. Here is a simple example:
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/predict', methods=['POST'])
def predict():
    # Your machine learning model logic goes here
    return jsonify({'prediction': 0.75})

if __name__ == '__main__':
    app.run(debug=True)
# This app has a single endpoint (/predict) that accepts HTTP POST requests with JSON data, and returns a JSON response with a prediction. You would replace the # Your 
# machine learning model logic goes here with your actual machine learning code.

# Next, you'll need to deploy your Flask app to AWS. One way to do this is by using Elastic Beanstalk. Here are the high-level steps:
# Create an Elastic Beanstalk application and environment.
# Create a requirements.txt file that lists all the Python packages required by your Flask app.
# Create a .ebextensions directory that contains a configuration file to set up the environment (e.g. install required system packages, set environment variables).
# Create a zip file that contains your Flask app, requirements.txt, and .ebextensions directory.
# Upload the zip file to your Elastic Beanstalk environment.
# There are many tutorials and resources available online that provide more details on how to deploy a Flask app to AWS.


# we can create a program that checks a list of stocks at regular intervals for potential trades. One way to implement this program is to use a combination of a Python script and 
# a task scheduler, such as cron or Windows Task Scheduler.

# The Python script would read in the list of stocks to monitor and their associated indicators, then periodically query the necessary data sources, calculate the indicators, 
# and analyze them to determine whether a potential trade exists. If a potential trade is identified, the script can send an alert to notify the user.

# The task scheduler can be used to run the Python script at regular intervals, such as every n hours. The scheduling parameters can be customized based on the user's preferences.

# Alternatively, this program can be implemented using a cloud-based service, such as AWS Lambda, which allows for serverless computing and automated scaling based on demand. The 
# function code can be written in Python, and the scheduling can be configured using the AWS EventBridge service. The program can also be integrated with other AWS services, 
# such as S3 for data storage and SNS for notification alerts.

# The user interface for this program can also be created using web-based technologies, such as HTML/CSS/JS. The interface can communicate with the Python script via HTTP requests 
# to retrieve the necessary data and display it to the user. The interface can also provide the user with the ability to configure the list of stocks to monitor and their 
# associated indicators.

# Here's an example program that checks a list of stocks every 24 hours for a potential trade:
import time
from datetime import datetime, timedelta

def check_stocks(stock_list):
    for stock in stock_list:
        # Check for potential trades for the current stock
        if is_potential_trade(stock):
            # Send notification or execute trade
            execute_trade(stock)
    print("Finished checking all stocks at " + str(datetime.now()))

def is_potential_trade(stock):
    # Implement algorithm to check for potential trades for the given stock
    return True  # Placeholder return value

def execute_trade(stock):
    # Implement algorithm to execute trade for the given stock
    print("Executing trade for " + stock)

if __name__ == '__main__':
    stock_list = ['AAPL', 'GOOG', 'AMZN']  # Replace with actual list of stocks
    while True:
        check_stocks(stock_list)
        time.sleep(24 * 60 * 60)  # Sleep for 24 hours before checking again

# This program defines a check_stocks() function that takes a list of stocks, iterates over the list, and calls the is_potential_trade() function to check for potential trades 
# for each stock. If a potential trade is found, the program calls the execute_trade() function to execute the trade. The program then sleeps for 24 hours before checking again.

# You can customize this program to use your own algorithm for checking potential trades, and modify the execute_trade() function to execute trades according to your own trading 
# strategy. You can also replace the print() statements with code to send notifications or interface with your brokerage account.


# I can provide a general outline of the steps you may take to create a Flask API:
# Define your API endpoints: You should determine what endpoints you need for your app to function, such as /login, /register, /trade, etc.
# Define the data models: You need to determine the data models you need for your app. These models may include user information, stock information, trade information, and so on.
# Create your Flask app: You can start your Flask app with the basic code structure, including routes, database connection, error handling, and middleware configuration.
# Define the database models: Using an ORM like SQLAlchemy, create models for your app.
# Create the API routes: For each of your API endpoints, create a Flask route that maps to the respective API endpoint.
# Add authentication: To protect your API routes, you should add an authentication mechanism, such as OAuth or JWT.
# Deploy your app: You can deploy your app to a hosting service such as AWS or Heroku.
# To plug the Flask API into a phone app, you can use a mobile app development framework like React Native, which allows you to create apps for both iOS and Android using 
# JavaScript. You can also use a platform like Firebase, which provides backend services, including authentication and real-time database.


#Theorizing potential profits. 

# Assuming a standard normal distribution, about 99.7% of the data lies within 3 standard deviations of the mean. If the median accuracy is 0.84, the standard deviation of the accuracy distribution would need to be estimated to compute the accuracy at 3 standard deviations.

# If the median accuracy is 0.84 and we assume a normal distribution, we can use the cumulative distribution function to find the percentage of trades with accuracy less than or equal to 2 standard deviations above the median.

# Assuming a normal distribution, 95% of the accuracy values lie within 2 standard deviations of the mean. Using a standard normal distribution table or a calculator, we can find that the z-score corresponding to the 97.5th percentile (i.e., 2 standard deviations above the mean) is approximately 1.96.

# Therefore, the percentage of trades with accuracy less than or equal to 2 standard deviations above the median is approximately:

# Copy code
# 0.5 + 0.4772 = 0.9772 or 97.72%
# So out of 100 trades, approximately 97 trades would be at or below 2 standard deviations above the median accuracy.


# Based on our calculation, we expect approximately 3 trades out of 100 to have an accuracy that is above 2 standard deviations from the median accuracy. However, it's important to note that this is an estimation based on a normal distribution assumption and other factors could affect the actual results.


# To calculate 2500 * 2^18, we can use the following steps:

# Calculate 2^18 = 262,144
# Multiply 2500 by 262,144 to get the result.
# So, the result is:

# 2500 * 262144 = 655360000

# Therefore, 2500 * 2^18 = 655,360,000.