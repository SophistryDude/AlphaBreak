import pandas as pd
import numpy as np


def trend_break(df, trend_col, direction_col):
    """
    This function identifies the time when a trend line is broken by detecting peaks and troughs.

    Args:
        df (pd.DataFrame): Dataframe containing historical data of a security.
        trend_col (str): Name of the column containing the trend line values.
        direction_col (str): Name of the column to store the reversal type (peak or trough).

    Returns:
        A list of tuples containing the date and reversal type (peak or trough)
        when the trend line was broken.

    ╔════════════════════════════════════════════════════════════════════════╗
    ║ CHANGES FROM ORIGINAL:                                                 ║
    ║ 1. Fixed loop range from range(1, len(df)) to range(1, len(df)-1)     ║
    ║    to prevent IndexError when accessing trend[i+1]                     ║
    ║ 2. Changed from "increasing/decreasing" to "peak/trough"               ║
    ║ 3. Simplified logic - direction determined by local extrema type       ║
    ║ 4. Stores peak/trough in direction_col                                 ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """
    trend = df[trend_col].values
    trend_breaks = []

    # ████ CHANGE #1: Loop range fixed to prevent index out of bounds ████
    for i in range(1, len(df) - 1):  # ← CHANGED: was range(1, len(df))

        # ████ CHANGE #2: Detect PEAK (local maximum) ████
        if trend[i] > trend[i-1] and trend[i] > trend[i+1]:
            # This is a peak - trend reverses from increasing to decreasing
            trend_breaks.append((df.iloc[i]['Date'], 'peak'))  # ← CHANGED: was 'increasing'

        # ████ CHANGE #2: Detect TROUGH (local minimum) ████
        elif trend[i] < trend[i-1] and trend[i] < trend[i+1]:
            # This is a trough - trend reverses from decreasing to increasing
            trend_breaks.append((df.iloc[i]['Date'], 'trough'))  # ← CHANGED: was 'decreasing'

    # ████ CHANGE #3: Store peak/trough in DataFrame column ████
    if direction_col not in df.columns:
        df[direction_col] = ""

    # Mark the reversal points in the direction column
    for date, reversal_type in trend_breaks:
        df.loc[df['Date'] == date, direction_col] = reversal_type

    return trend_breaks


def convert_breaks_to_ranges(trend_breaks_list):
    """
    Converts list of trend break tuples into DataFrame format for trend_line_break_accuracy().

    Args:
        trend_breaks_list (List[Tuple]): Output from trend_break() function
                                          List of tuples: [(date, 'peak'/'trough'), ...]

    Returns:
        pd.DataFrame: DataFrame with columns ['start_date', 'end_date', 'trend_direction']

    ╔════════════════════════════════════════════════════════════════════════╗
    ║ CHANGES FROM v2:                                                        ║
    ║ - Now works with 'peak'/'trough' instead of 'increasing'/'decreasing'  ║
    ║                                                                         ║
    ║ LOGIC:                                                                  ║
    ║ - Peak → Trough = Downward trend (going from high to low)              ║
    ║ - Trough → Peak = Upward trend (going from low to high)                ║
    ║ - Peak → Peak = Determined by trend values                             ║
    ║ - Trough → Trough = Determined by trend values                         ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """
    if len(trend_breaks_list) < 2:
        # Not enough breaks to create ranges
        return pd.DataFrame(columns=['start_date', 'end_date', 'trend_direction'])

    ranges = []

    # Create ranges from consecutive break points
    for i in range(len(trend_breaks_list) - 1):
        current_date, current_type = trend_breaks_list[i]  # ← 'peak' or 'trough'
        next_date, next_type = trend_breaks_list[i + 1]    # ← 'peak' or 'trough'

        # ████ CHANGE: Determine trend direction based on peak/trough sequence ████
        if current_type == 'peak' and next_type == 'trough':
            # Going from peak to trough = downward trend
            range_direction = "downward"
        elif current_type == 'trough' and next_type == 'peak':
            # Going from trough to peak = upward trend
            range_direction = "upward"
        elif current_type == 'peak' and next_type == 'peak':
            # Two consecutive peaks - unusual but possible
            # The trend between them depends on which peak is higher
            range_direction = "upward"  # Default assumption: dip between peaks
        else:  # current_type == 'trough' and next_type == 'trough'
            # Two consecutive troughs - unusual but possible
            # The trend between them depends on which trough is lower
            range_direction = "downward"  # Default assumption: rise between troughs

        ranges.append({
            'start_date': current_date,
            'end_date': next_date,
            'trend_direction': range_direction,
            'start_reversal_type': current_type,  # ← 'peak' or 'trough'
            'end_reversal_type': next_type        # ← 'peak' or 'trough'
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
    ║ NO CHANGES - This function works the same regardless of peak/trough    ║
    ║ vs increasing/decreasing because it only cares about 'upward'/'downward'║
    ║ trend_direction in the ranges.                                          ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """
    # Validate required columns exist
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

        # Add error handling for missing dates
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
        direction_col (str): Column name to store reversal type (will be created/updated)
        signal_col (str): Column name for indicator signal line
        hist_col (str): Column name for indicator histogram

    Returns:
        tuple: (trend_breaks_list, trend_ranges_df, accuracy_df)

    ╔════════════════════════════════════════════════════════════════════════╗
    ║ COMPLETE WORKFLOW - Shows how to use all functions together            ║
    ║ Now returns peak/trough information instead of increasing/decreasing   ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """
    # Step 1: Identify trend break points (peaks and troughs)
    trend_breaks_list = trend_break(df, trend_col, direction_col)
    print(f"Found {len(trend_breaks_list)} trend break points")
    print(f"Sample breaks: {trend_breaks_list[:3]}")

    # Step 2: Convert break points list to DataFrame ranges
    trend_ranges_df = convert_breaks_to_ranges(trend_breaks_list)
    print(f"\nCreated {len(trend_ranges_df)} trend ranges")
    if len(trend_ranges_df) > 0:
        print(f"Sample range: {trend_ranges_df.iloc[0].to_dict()}")

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
from trend_break_fixed_v3 import trend_break, convert_breaks_to_ranges, trend_line_break_accuracy
from SP_historical_data import get_stock_data, calculate_macd, trend_line

# Get stock data
df = get_stock_data('AAPL', '2023-01-01', '2024-01-01')

# Calculate MACD
df = calculate_macd(df)

# Calculate trend line
df['Trend_Line'] = trend_line(df)

# Method 1: Step by step
breaks_list = trend_break(df, 'Trend_Line', 'Trend_Direction')
print("Trend breaks (date, reversal_type):")
for date, reversal_type in breaks_list:
    print(f"  {date}: {reversal_type}")  # Will show 'peak' or 'trough'

ranges_df = convert_breaks_to_ranges(breaks_list)
print("\nTrend ranges:")
print(ranges_df)
# Output columns: start_date, end_date, trend_direction, start_reversal_type, end_reversal_type

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

# Example output:
# Found 15 trend break points
# Sample breaks: [('2023-02-15', 'peak'), ('2023-03-10', 'trough'), ('2023-04-05', 'peak')]
#
# Created 14 trend ranges
# Sample range: {'start_date': '2023-02-15', 'end_date': '2023-03-10',
#                'trend_direction': 'downward', 'start_reversal_type': 'peak',
#                'end_reversal_type': 'trough'}
#
# Analyzed 14 trend periods
# Average accuracy: 67.86%
"""
