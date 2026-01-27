import pandas as pd
import numpy as np


def trend_break(df, trend_col):
    """
    This function identifies the time when a trend line is broken by detecting local peaks and troughs.

    Args:
        df (pd.DataFrame): Dataframe containing historical data of a security.
        trend_col (str): Name of the column containing the trend line values.

    Returns:
        pd.DataFrame: DataFrame with columns ['date', 'break_type', 'trend_value']
                     where break_type is 'peak' or 'trough'

    ╔════════════════════════════════════════════════════════════════════════╗
    ║ CHANGES FROM ORIGINAL:                                                 ║
    ║ 1. Fixed loop range from range(1, len(df)) to range(1, len(df)-1)     ║
    ║    to prevent IndexError when accessing trend[i+1]                     ║
    ║ 2. Removed unused 'direction_col' parameter                            ║
    ║ 3. Changed return type from List[Tuple] to DataFrame                   ║
    ║ 4. Simplified logic to focus on peak/trough detection                  ║
    ║ 5. Returns 'peak' or 'trough' instead of 'increasing'/'decreasing'     ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """
    trend = df[trend_col].values
    trend_breaks = []

    # ████ CHANGE #1: Loop range fixed to prevent index out of bounds ████
    for i in range(1, len(df) - 1):  # ← CHANGED: was range(1, len(df))

        # Detect local maximum (peak)
        if trend[i] > trend[i-1] and trend[i] > trend[i+1]:
            trend_breaks.append({
                'date': df.iloc[i]['Date'],
                'break_type': 'peak',  # ← CHANGED: was 'increasing'
                'trend_value': trend[i]
            })

        # Detect local minimum (trough)
        elif trend[i] < trend[i-1] and trend[i] < trend[i+1]:
            trend_breaks.append({
                'date': df.iloc[i]['Date'],
                'break_type': 'trough',  # ← CHANGED: was 'decreasing'
                'trend_value': trend[i]
            })

    # ████ CHANGE #3: Return DataFrame instead of List[Tuple] ████
    return pd.DataFrame(trend_breaks)  # ← CHANGED: was returning list of tuples


def convert_breaks_to_ranges(trend_breaks_df):
    """
    Converts individual trend break points (peaks/troughs) into trend ranges.

    Args:
        trend_breaks_df (pd.DataFrame): Output from trend_break() function
                                        with columns ['date', 'break_type', 'trend_value']

    Returns:
        pd.DataFrame: DataFrame with columns ['start_date', 'end_date', 'trend_direction']
                     where trend_direction is 'upward' or 'downward'

    ╔════════════════════════════════════════════════════════════════════════╗
    ║ NEW FUNCTION - BRIDGES THE GAP                                         ║
    ║ This function was missing in the original implementation.              ║
    ║ It converts single points (peaks/troughs) into ranges (start→end)      ║
    ║ which is what trend_line_break_accuracy() expects.                     ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """
    if len(trend_breaks_df) < 2:
        # Not enough breaks to create ranges
        return pd.DataFrame(columns=['start_date', 'end_date', 'trend_direction'])

    ranges = []

    # Create ranges from consecutive break points
    for i in range(len(trend_breaks_df) - 1):
        current_break = trend_breaks_df.iloc[i]
        next_break = trend_breaks_df.iloc[i + 1]

        # Determine trend direction based on break types
        if current_break['break_type'] == 'trough' and next_break['break_type'] == 'peak':
            direction = 'upward'  # Going from trough to peak = upward trend
        elif current_break['break_type'] == 'peak' and next_break['break_type'] == 'trough':
            direction = 'downward'  # Going from peak to trough = downward trend
        else:
            # Two consecutive peaks or troughs - use trend values to determine
            if next_break['trend_value'] > current_break['trend_value']:
                direction = 'upward'
            else:
                direction = 'downward'

        ranges.append({
            'start_date': current_break['date'],
            'end_date': next_break['date'],
            'trend_direction': direction
        })

    return pd.DataFrame(ranges)


def trend_line_break_accuracy(data, trend_breaks, signal_col, hist_col):
    """
    Calculate the accuracy of the given indicator at each trend line break.

    Args:
        data (pd.DataFrame): DataFrame containing the indicator data with 'Date' column
        trend_breaks (pd.DataFrame): DataFrame containing trend line breaks
                                     with columns ['start_date', 'end_date', 'trend_direction']
        signal_col (str): Name of the column containing the signal line data
        hist_col (str): Name of the column containing the histogram data

    Returns:
        pd.DataFrame: DataFrame containing information on each trend line break
                     with accuracy scores

    ╔════════════════════════════════════════════════════════════════════════╗
    ║ CHANGES FROM ORIGINAL:                                                 ║
    ║ 1. Added error handling for missing dates                              ║
    ║ 2. Added validation for required columns                               ║
    ║ 3. Added detailed comments for clarity                                 ║
    ║ 4. Added error messages for debugging                                  ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """
    # ████ CHANGE #1: Validate required columns exist ████
    required_cols = ['Date', signal_col, hist_col]
    missing_cols = [col for col in required_cols if col not in data.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in data: {missing_cols}")

    if not all(col in trend_breaks.columns for col in ['start_date', 'end_date', 'trend_direction']):
        raise ValueError("trend_breaks must have columns: ['start_date', 'end_date', 'trend_direction']")

    results = []

    for i, row in trend_breaks.iterrows():
        start_date = row['start_date']
        end_date = row['end_date']
        trend_direction = row['trend_direction']

        # ████ CHANGE #2: Add error handling for missing dates ████
        start_data = data.loc[data['Date'] == start_date, [signal_col, hist_col]]
        end_data = data.loc[data['Date'] == end_date, [signal_col, hist_col]]

        if start_data.empty:
            print(f"Warning: start_date {start_date} not found in data. Skipping this range.")
            continue

        if end_data.empty:
            print(f"Warning: end_date {end_date} not found in data. Skipping this range.")
            continue

        signal_start = start_data[signal_col].values[0]
        signal_end = end_data[signal_col].values[0]
        hist_start = start_data[hist_col].values[0]
        hist_end = end_data[hist_col].values[0]

        # Calculate accuracy based on whether indicators moved in expected direction
        if trend_direction == 'upward':
            # For upward trend, expect signal and histogram to increase
            if signal_end > signal_start and hist_end > hist_start:
                accuracy = 1.0  # Both correct
            elif signal_end > signal_start or hist_end > hist_start:
                accuracy = 0.5  # One correct
            else:
                accuracy = 0.0  # Both wrong
        else:  # downward trend
            # For downward trend, expect signal and histogram to decrease
            if signal_end < signal_start and hist_end < hist_start:
                accuracy = 1.0  # Both correct
            elif signal_end < signal_start or hist_end < hist_start:
                accuracy = 0.5  # One correct
            else:
                accuracy = 0.0  # Both wrong

        results.append({
            'start_date': start_date,
            'end_date': end_date,
            'trend_direction': trend_direction,
            'signal_change': signal_end - signal_start,  # ← ADDED: for analysis
            'hist_change': hist_end - hist_start,        # ← ADDED: for analysis
            'accuracy': accuracy
        })

    return pd.DataFrame(results)


# ════════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE - Complete workflow with all three functions
# ════════════════════════════════════════════════════════════════════════════

def analyze_trend_breaks_complete(df, trend_col, signal_col, hist_col):
    """
    Complete workflow to analyze trend breaks and indicator accuracy.

    Args:
        df (pd.DataFrame): Stock data with Date, trend, signal, and histogram columns
        trend_col (str): Column name for trend line values
        signal_col (str): Column name for indicator signal line
        hist_col (str): Column name for indicator histogram

    Returns:
        tuple: (trend_breaks_df, trend_ranges_df, accuracy_df)

    ╔════════════════════════════════════════════════════════════════════════╗
    ║ NEW FUNCTION - COMPLETE WORKFLOW                                       ║
    ║ Shows how to use all three functions together properly.                ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """
    # Step 1: Identify trend break points (peaks and troughs)
    trend_breaks = trend_break(df, trend_col)
    print(f"Found {len(trend_breaks)} trend break points")

    # Step 2: Convert break points to trend ranges
    trend_ranges = convert_breaks_to_ranges(trend_breaks)
    print(f"Created {len(trend_ranges)} trend ranges")

    # Step 3: Calculate indicator accuracy for each trend range
    accuracy_results = trend_line_break_accuracy(df, trend_ranges, signal_col, hist_col)
    print(f"Analyzed {len(accuracy_results)} trend periods")
    print(f"Average accuracy: {accuracy_results['accuracy'].mean():.2%}")

    return trend_breaks, trend_ranges, accuracy_results


# ════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE CODE
# ════════════════════════════════════════════════════════════════════════════
"""
# Example: Using with MACD indicator

import yfinance as yf
from trend_break_fixed import trend_break, convert_breaks_to_ranges, trend_line_break_accuracy
from SP_historical_data import get_stock_data, calculate_macd, trend_line

# Get stock data
df = get_stock_data('AAPL', '2023-01-01', '2024-01-01')

# Calculate MACD
df = calculate_macd(df)

# Calculate trend line
df['Trend_Line'] = trend_line(df)

# Run complete analysis
breaks, ranges, accuracy = analyze_trend_breaks_complete(
    df,
    trend_col='Trend_Line',
    signal_col='Signal Line',
    hist_col='Histogram'
)

# View results
print("\nTrend Breaks:")
print(breaks)

print("\nTrend Ranges:")
print(ranges)

print("\nAccuracy Results:")
print(accuracy)
"""
