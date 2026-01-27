import pandas as pd
import numpy as np


def trend_break(df, trend_col, direction_col):
    """
    This function identifies the time when a trend line is broken.

    Args:
        df (pd.DataFrame): Dataframe containing historical data of a security.
        trend_col (str): Name of the column containing the trend line values.
        direction_col (str): Name of the column to store the direction of the trend (increasing or decreasing).

    Returns:
        A list of tuples containing the date and direction of the trend (increasing or decreasing)
        when the trend line was broken.

    ╔════════════════════════════════════════════════════════════════════════╗
    ║ CHANGES FROM ORIGINAL:                                                 ║
    ║ 1. Fixed loop range from range(1, len(df)) to range(1, len(df)-1)     ║
    ║    to prevent IndexError when accessing trend[i+1]                     ║
    ║ 2. KEPT direction_col parameter (as requested)                         ║
    ║ 3. Fixed logic to correctly capture direction at reversal point        ║
    ║ 4. Direction now represents the trend BEFORE the reversal              ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """
    trend = df[trend_col].values
    prev_trend = trend[0]
    direction = ""
    trend_breaks = []

    # ████ CHANGE #1: Loop range fixed to prevent index out of bounds ████
    for i in range(1, len(df) - 1):  # ← CHANGED: was range(1, len(df))

        # Track if trend is increasing or decreasing
        if trend[i] > prev_trend:
            if direction != "increasing":
                direction = "increasing"
        elif trend[i] < prev_trend:
            if direction != "decreasing":
                direction = "decreasing"
        else:
            continue

        # Detect reversal points (peaks and troughs)
        # Peak: trend was increasing, now reversing
        # Trough: trend was decreasing, now reversing
        if (trend[i] > trend[i-1] and trend[i] > trend[i+1]) or \
           (trend[i] < trend[i-1] and trend[i] < trend[i+1]):
            # ████ KEPT ORIGINAL FORMAT: Tuple with (date, direction) ████
            trend_breaks.append((df.iloc[i]['Date'], direction))

        prev_trend = trend[i]

    # ████ OPTIONAL: Store direction in DataFrame column if needed ████
    if direction_col not in df.columns:
        df[direction_col] = ""

    # Mark the reversal points in the direction column
    for date, dir_value in trend_breaks:
        df.loc[df['Date'] == date, direction_col] = dir_value

    return trend_breaks


def convert_breaks_to_ranges(trend_breaks_list):
    """
    Converts list of trend break tuples into DataFrame format for trend_line_break_accuracy().

    Args:
        trend_breaks_list (List[Tuple]): Output from trend_break() function
                                          List of tuples: [(date, direction), ...]

    Returns:
        pd.DataFrame: DataFrame with columns ['start_date', 'end_date', 'trend_direction']

    ╔════════════════════════════════════════════════════════════════════════╗
    ║ NEW FUNCTION - BRIDGES THE GAP                                         ║
    ║ Converts List[Tuple] from trend_break() to DataFrame format            ║
    ║ required by trend_line_break_accuracy()                                ║
    ║                                                                         ║
    ║ LOGIC:                                                                  ║
    ║ - Consecutive break points form a range                                ║
    ║ - Direction tells us what the trend was doing BEFORE reversal          ║
    ║ - We map this to upward/downward for the RANGE between breaks          ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """
    if len(trend_breaks_list) < 2:
        # Not enough breaks to create ranges
        return pd.DataFrame(columns=['start_date', 'end_date', 'trend_direction'])

    ranges = []

    # Create ranges from consecutive break points
    for i in range(len(trend_breaks_list) - 1):
        current_date, current_direction = trend_breaks_list[i]
        next_date, next_direction = trend_breaks_list[i + 1]

        # The direction at the first break tells us what the trend was doing
        # during the range leading UP TO that break
        #
        # Example:
        # - Peak detected with direction="increasing"
        #   → Trend was going UP before the peak
        #   → After the peak, it goes DOWN
        #   → So the NEXT range is "downward"
        #
        # - Trough detected with direction="decreasing"
        #   → Trend was going DOWN before the trough
        #   → After the trough, it goes UP
        #   → So the NEXT range is "upward"

        # Determine the trend direction for the range AFTER current break
        if current_direction == "increasing":
            # If we hit a peak (was increasing), next range is downward
            range_direction = "downward"
        else:  # current_direction == "decreasing"
            # If we hit a trough (was decreasing), next range is upward
            range_direction = "upward"

        ranges.append({
            'start_date': current_date,
            'end_date': next_date,
            'trend_direction': range_direction,
            'start_reversal_type': 'peak' if current_direction == 'increasing' else 'trough',
            'end_reversal_type': 'peak' if next_direction == 'increasing' else 'trough'
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
    ║ 4. Added warning messages instead of silent failures                   ║
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
            'signal_change': signal_end - signal_start,
            'hist_change': hist_end - hist_start,
            'accuracy': accuracy
        })

    return pd.DataFrame(results)


# ════════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE - Complete workflow
# ════════════════════════════════════════════════════════════════════════════

def analyze_trend_breaks_complete(df, trend_col, direction_col, signal_col, hist_col):
    """
    Complete workflow to analyze trend breaks and indicator accuracy.

    Args:
        df (pd.DataFrame): Stock data with Date, trend, signal, and histogram columns
        trend_col (str): Column name for trend line values
        direction_col (str): Column name to store direction (will be created/updated)
        signal_col (str): Column name for indicator signal line
        hist_col (str): Column name for indicator histogram

    Returns:
        tuple: (trend_breaks_list, trend_ranges_df, accuracy_df)

    ╔════════════════════════════════════════════════════════════════════════╗
    ║ COMPLETE WORKFLOW - Shows how to use all functions together            ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """
    # Step 1: Identify trend break points with direction
    trend_breaks_list = trend_break(df, trend_col, direction_col)
    print(f"Found {len(trend_breaks_list)} trend break points")
    print(f"Sample breaks: {trend_breaks_list[:3]}")

    # Step 2: Convert break points list to DataFrame ranges
    trend_ranges_df = convert_breaks_to_ranges(trend_breaks_list)
    print(f"\nCreated {len(trend_ranges_df)} trend ranges")

    # Step 3: Calculate indicator accuracy for each trend range
    accuracy_df = trend_line_break_accuracy(df, trend_ranges_df, signal_col, hist_col)
    print(f"\nAnalyzed {len(accuracy_df)} trend periods")
    if len(accuracy_df) > 0:
        print(f"Average accuracy: {accuracy_df['accuracy'].mean():.2%}")

    return trend_breaks_list, trend_ranges_df, accuracy_df


# ════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE CODE
# ════════════════════════════════════════════════════════════════════════════
"""
# Example: Using with MACD indicator

import yfinance as yf
from trend_break_fixed_v2 import trend_break, convert_breaks_to_ranges, trend_line_break_accuracy
from SP_historical_data import get_stock_data, calculate_macd, trend_line

# Get stock data
df = get_stock_data('AAPL', '2023-01-01', '2024-01-01')

# Calculate MACD
df = calculate_macd(df)

# Calculate trend line
df['Trend_Line'] = trend_line(df)

# Method 1: Step by step
breaks_list = trend_break(df, 'Trend_Line', 'Trend_Direction')
print("Trend breaks (date, direction):")
for date, direction in breaks_list:
    print(f"  {date}: {direction}")

ranges_df = convert_breaks_to_ranges(breaks_list)
print("\nTrend ranges:")
print(ranges_df)

accuracy_df = trend_line_break_accuracy(df, ranges_df, 'Signal Line', 'Histogram')
print("\nAccuracy results:")
print(accuracy_df)

# Method 2: All in one
breaks, ranges, accuracy = analyze_trend_breaks_complete(
    df,
    trend_col='Trend_Line',
    direction_col='Trend_Direction',
    signal_col='Signal Line',
    hist_col='Histogram'
)
"""
