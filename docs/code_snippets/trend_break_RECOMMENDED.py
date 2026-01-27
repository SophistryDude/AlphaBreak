import pandas as pd
import numpy as np

"""
RECOMMENDED IMPLEMENTATION - OPTION C (Hybrid Approach)
========================================================

This combines the best of both worlds:
- Captures peak/trough type (mathematically precise)
- Captures direction before/after (matches your original intent)
- Returns DataFrame (better for ML workflows)
- Includes extra features for model training
"""


def trend_break(df, trend_col, direction_col):
    """
    Identifies trend reversals (peaks and troughs) with complete directional information.

    Args:
        df (pd.DataFrame): Dataframe containing historical data of a security.
        trend_col (str): Name of the column containing the trend line values.
        direction_col (str): Name of the column to store the reversal information.

    Returns:
        pd.DataFrame: DataFrame with columns:
            - date: Date of reversal
            - reversal_type: 'peak' or 'trough'
            - direction_before: 'increasing' or 'decreasing'
            - direction_after: 'decreasing' or 'increasing'
            - trend_value: Value of trend at reversal point

    This captures BOTH your original intent (direction tracking) AND
    mathematical precision (peak/trough detection).
    """
    trend = df[trend_col].values
    trend_breaks = []

    # ████ FIX: Loop range prevents index out of bounds ████
    for i in range(1, len(df) - 1):

        # Detect PEAK (local maximum)
        if trend[i] > trend[i-1] and trend[i] > trend[i+1]:
            trend_breaks.append({
                'date': df.iloc[i]['Date'],
                'reversal_type': 'peak',
                'direction_before': 'increasing',  # Was going up
                'direction_after': 'decreasing',   # Now going down
                'trend_value': trend[i],
                'magnitude': min(trend[i] - trend[i-1], trend[i] - trend[i+1])  # Sharpness
            })

        # Detect TROUGH (local minimum)
        elif trend[i] < trend[i-1] and trend[i] < trend[i+1]:
            trend_breaks.append({
                'date': df.iloc[i]['Date'],
                'reversal_type': 'trough',
                'direction_before': 'decreasing',  # Was going down
                'direction_after': 'increasing',   # Now going up
                'trend_value': trend[i],
                'magnitude': min(trend[i-1] - trend[i], trend[i+1] - trend[i])  # Sharpness
            })

    # Convert to DataFrame
    breaks_df = pd.DataFrame(trend_breaks)

    # Store in the direction_col for reference
    if len(breaks_df) > 0:
        if direction_col not in df.columns:
            df[direction_col] = ""

        for _, row in breaks_df.iterrows():
            df.loc[df['Date'] == row['date'], direction_col] = row['reversal_type']

    return breaks_df


def convert_breaks_to_ranges(trend_breaks_df):
    """
    Converts trend break points into trend ranges for analysis.

    Args:
        trend_breaks_df (pd.DataFrame): Output from trend_break() function

    Returns:
        pd.DataFrame: DataFrame with columns:
            - start_date: Beginning of trend range
            - end_date: End of trend range
            - trend_direction: 'upward' or 'downward'
            - start_reversal_type: 'peak' or 'trough'
            - end_reversal_type: 'peak' or 'trough'
            - range_length: Number of periods in range (for ML features)
    """
    if len(trend_breaks_df) < 2:
        return pd.DataFrame(columns=['start_date', 'end_date', 'trend_direction',
                                     'start_reversal_type', 'end_reversal_type'])

    ranges = []

    for i in range(len(trend_breaks_df) - 1):
        current = trend_breaks_df.iloc[i]
        next_break = trend_breaks_df.iloc[i + 1]

        # Use direction_after from current break to determine range direction
        # This is more accurate than inferring from peak/trough sequence
        range_direction = 'upward' if current['direction_after'] == 'increasing' else 'downward'

        ranges.append({
            'start_date': current['date'],
            'end_date': next_break['date'],
            'trend_direction': range_direction,
            'start_reversal_type': current['reversal_type'],
            'end_reversal_type': next_break['reversal_type'],
            'start_magnitude': current['magnitude'],
            'end_magnitude': next_break['magnitude']
        })

    return pd.DataFrame(ranges)


def trend_line_break_accuracy(data, trend_breaks, signal_col, hist_col):
    """
    Calculate the accuracy of the given indicator at each trend line break.

    Args:
        data (pd.DataFrame): DataFrame containing the indicator data with 'Date' column
        trend_breaks (pd.DataFrame): DataFrame from convert_breaks_to_ranges()
        signal_col (str): Name of the column containing the signal line data
        hist_col (str): Name of the column containing the histogram data

    Returns:
        pd.DataFrame: DataFrame with accuracy metrics for each trend range
    """
    # Validate inputs
    required_data_cols = ['Date', signal_col, hist_col]
    missing_cols = [col for col in required_data_cols if col not in data.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in data: {missing_cols}")

    required_break_cols = ['start_date', 'end_date', 'trend_direction']
    if not all(col in trend_breaks.columns for col in required_break_cols):
        raise ValueError(f"trend_breaks must have columns: {required_break_cols}")

    results = []

    for i, row in trend_breaks.iterrows():
        start_date = row['start_date']
        end_date = row['end_date']
        trend_direction = row['trend_direction']

        # Get indicator values at start and end
        start_data = data.loc[data['Date'] == start_date, [signal_col, hist_col]]
        end_data = data.loc[data['Date'] == end_date, [signal_col, hist_col]]

        # Handle missing dates gracefully
        if start_data.empty:
            print(f"Warning: start_date {start_date} not found. Skipping.")
            continue
        if end_data.empty:
            print(f"Warning: end_date {end_date} not found. Skipping.")
            continue

        signal_start = start_data[signal_col].values[0]
        signal_end = end_data[signal_col].values[0]
        hist_start = start_data[hist_col].values[0]
        hist_end = end_data[hist_col].values[0]

        # Calculate changes
        signal_change = signal_end - signal_start
        hist_change = hist_end - hist_start

        # Score accuracy
        if trend_direction == 'upward':
            signal_correct = signal_change > 0
            hist_correct = hist_change > 0
        else:  # downward
            signal_correct = signal_change < 0
            hist_correct = hist_change < 0

        # Calculate accuracy score
        if signal_correct and hist_correct:
            accuracy = 1.0
        elif signal_correct or hist_correct:
            accuracy = 0.5
        else:
            accuracy = 0.0

        results.append({
            'start_date': start_date,
            'end_date': end_date,
            'trend_direction': trend_direction,
            'signal_change': signal_change,
            'hist_change': hist_change,
            'signal_correct': signal_correct,
            'hist_correct': hist_correct,
            'accuracy': accuracy,
            # Include reversal info for deeper analysis
            'start_reversal_type': row.get('start_reversal_type', None),
            'end_reversal_type': row.get('end_reversal_type', None)
        })

    return pd.DataFrame(results)


def analyze_trend_breaks_complete(df, trend_col, direction_col, signal_col, hist_col):
    """
    Complete workflow for trend break analysis with indicator validation.

    This is the main function you should use. It orchestrates all steps:
    1. Detect trend reversals
    2. Convert to ranges
    3. Calculate indicator accuracy

    Args:
        df (pd.DataFrame): Stock data with Date, trend, signal, and histogram columns
        trend_col (str): Column name for trend line values
        direction_col (str): Column name to store reversal info
        signal_col (str): Column name for indicator signal line
        hist_col (str): Column name for indicator histogram

    Returns:
        dict: Dictionary containing:
            - 'breaks': DataFrame of reversal points
            - 'ranges': DataFrame of trend ranges
            - 'accuracy': DataFrame of accuracy metrics
            - 'summary': Dictionary with summary statistics
    """
    # Step 1: Detect reversals
    breaks_df = trend_break(df, trend_col, direction_col)
    print(f"✓ Found {len(breaks_df)} trend reversals")

    if len(breaks_df) == 0:
        print("⚠ No reversals found. Cannot analyze.")
        return {
            'breaks': breaks_df,
            'ranges': pd.DataFrame(),
            'accuracy': pd.DataFrame(),
            'summary': {}
        }

    # Step 2: Convert to ranges
    ranges_df = convert_breaks_to_ranges(breaks_df)
    print(f"✓ Created {len(ranges_df)} trend ranges")

    if len(ranges_df) == 0:
        print("⚠ Not enough reversals to create ranges.")
        return {
            'breaks': breaks_df,
            'ranges': ranges_df,
            'accuracy': pd.DataFrame(),
            'summary': {}
        }

    # Step 3: Calculate accuracy
    accuracy_df = trend_line_break_accuracy(df, ranges_df, signal_col, hist_col)
    print(f"✓ Analyzed {len(accuracy_df)} trend periods")

    # Calculate summary statistics
    summary = {}
    if len(accuracy_df) > 0:
        summary = {
            'total_ranges': len(accuracy_df),
            'average_accuracy': accuracy_df['accuracy'].mean(),
            'perfect_predictions': (accuracy_df['accuracy'] == 1.0).sum(),
            'partial_predictions': (accuracy_df['accuracy'] == 0.5).sum(),
            'failed_predictions': (accuracy_df['accuracy'] == 0.0).sum(),
            'upward_ranges': (accuracy_df['trend_direction'] == 'upward').sum(),
            'downward_ranges': (accuracy_df['trend_direction'] == 'downward').sum(),
            'signal_accuracy': accuracy_df['signal_correct'].mean(),
            'histogram_accuracy': accuracy_df['hist_correct'].mean()
        }

        print(f"\n📊 SUMMARY:")
        print(f"   Average Accuracy: {summary['average_accuracy']:.1%}")
        print(f"   Perfect: {summary['perfect_predictions']} | "
              f"Partial: {summary['partial_predictions']} | "
              f"Failed: {summary['failed_predictions']}")
        print(f"   Signal Accuracy: {summary['signal_accuracy']:.1%}")
        print(f"   Histogram Accuracy: {summary['histogram_accuracy']:.1%}")

    return {
        'breaks': breaks_df,
        'ranges': ranges_df,
        'accuracy': accuracy_df,
        'summary': summary
    }


# ════════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ════════════════════════════════════════════════════════════════════════════
"""
from trend_break_RECOMMENDED import analyze_trend_breaks_complete
from SP_historical_data import get_stock_data, calculate_macd, trend_line

# Get data
df = get_stock_data('AAPL', '2023-01-01', '2024-01-01')
df = calculate_macd(df)
df['Trend_Line'] = trend_line(df)

# Run complete analysis
results = analyze_trend_breaks_complete(
    df,
    trend_col='Trend_Line',
    direction_col='Trend_Reversal',
    signal_col='Signal Line',
    hist_col='Histogram'
)

# Access results
print(results['breaks'])      # All reversal points
print(results['ranges'])      # All trend ranges
print(results['accuracy'])    # Accuracy metrics
print(results['summary'])     # Summary statistics

# Use for ML model training
features_df = results['accuracy'].copy()
features_df['label'] = features_df['accuracy'] > 0.5  # Binary classification
"""
