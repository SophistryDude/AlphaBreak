"""
Trend Analysis Module
======================
Functions for detecting and analyzing trend breaks.

This module contains:
- Trend break detection
- Trend line break accuracy measurement
- Feature engineering for trend analysis
- Indicator accuracy analysis

Usage:
    from src.trend_analysis import trend_break, analyze_indicator_accuracy
    from src.data_fetcher import get_stock_data

    data = get_stock_data('AAPL', '2020-01-01', '2024-01-01')
    breaks = trend_break(data, 'Close')
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Optional, Any
from datetime import datetime


def trend_break(
    df: pd.DataFrame,
    trend_col: str,
    direction_col: str = 'trend_direction'
) -> List[Tuple[datetime, str]]:
    """
    Identify when a trend line is broken.

    Args:
        df: DataFrame containing historical data
        trend_col: Name of column containing trend line values
        direction_col: Name of column to store trend direction

    Returns:
        List of tuples (date, direction) for each trend break

    Example:
        >>> breaks = trend_break(data, 'Close')
        >>> for date, direction in breaks:
        ...     print(f"{date}: {direction}")
    """
    trend = df[trend_col].values
    dates = df['Date'].values if 'Date' in df.columns else df.index.values

    prev_trend = trend[0]
    direction = ""
    trend_breaks = []

    for i in range(1, len(df) - 1):
        if trend[i] > prev_trend:
            if direction != "increasing":
                direction = "increasing"
        elif trend[i] < prev_trend:
            if direction != "decreasing":
                direction = "decreasing"
        else:
            continue

        # Check for local peak or trough
        if (trend[i] > trend[i-1] and trend[i] > trend[i+1]) or \
           (trend[i] < trend[i-1] and trend[i] < trend[i+1]):
            trend_breaks.append((dates[i], direction))

        prev_trend = trend[i]

    return trend_breaks


def trend_line_break_accuracy(
    data: pd.DataFrame,
    trend_breaks: pd.DataFrame,
    signal_col: str,
    hist_col: str
) -> pd.DataFrame:
    """
    Calculate accuracy of an indicator at each trend line break.

    Args:
        data: DataFrame containing indicator data
        trend_breaks: DataFrame with start_date, end_date, trend_direction columns
        signal_col: Name of column containing signal line data
        hist_col: Name of column containing histogram data

    Returns:
        DataFrame with accuracy measurements for each trend break

    Example:
        >>> accuracy = trend_line_break_accuracy(data, breaks_df, 'MACD_signal', 'MACD_hist')
    """
    results = []

    for i, row in trend_breaks.iterrows():
        start_date = row['start_date']
        end_date = row['end_date']
        trend_direction = row['trend_direction']

        try:
            signal_start = data.loc[data['Date'] == start_date, signal_col].values[0]
            signal_end = data.loc[data['Date'] == end_date, signal_col].values[0]
            hist_start = data.loc[data['Date'] == start_date, hist_col].values[0]
            hist_end = data.loc[data['Date'] == end_date, hist_col].values[0]
        except (IndexError, KeyError):
            continue

        if trend_direction == 'upward':
            if signal_end > signal_start and hist_end > hist_start:
                accuracy = 1.0
            elif signal_end > signal_start or hist_end > hist_start:
                accuracy = 0.5
            else:
                accuracy = 0.0
        else:  # downward
            if signal_end < signal_start and hist_end < hist_start:
                accuracy = 1.0
            elif signal_end < signal_start or hist_end < hist_start:
                accuracy = 0.5
            else:
                accuracy = 0.0

        results.append({
            'start_date': start_date,
            'end_date': end_date,
            'trend_direction': trend_direction,
            'accuracy': accuracy
        })

    return pd.DataFrame(results)


def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add engineered features for trend analysis.

    Args:
        df: DataFrame with trend break data including:
            - start_date, end_date
            - start_price, end_price
            - start_signal, end_signal
            - start_hist, end_hist
            - accuracy

    Returns:
        DataFrame with additional engineered features

    Example:
        >>> df = feature_engineering(trend_df)
    """
    df = df.copy()

    # Trend length in days
    if 'start_date' in df.columns and 'end_date' in df.columns:
        df['trend_length'] = (pd.to_datetime(df['end_date']) - pd.to_datetime(df['start_date'])).dt.days

    # Price distance
    if 'start_price' in df.columns and 'end_price' in df.columns:
        df['price_distance'] = df['end_price'] - df['start_price']

    # Signal difference
    if 'start_signal' in df.columns and 'end_signal' in df.columns:
        df['signal_difference'] = df['end_signal'] - df['start_signal']

    # Histogram difference
    if 'start_hist' in df.columns and 'end_hist' in df.columns:
        df['hist_difference'] = df['end_hist'] - df['start_hist']

    # Accuracy as percentage
    if 'accuracy' in df.columns:
        df['accuracy_percentage'] = df['accuracy'] * 100

    # Trend strength
    if 'trend_length' in df.columns and 'price_distance' in df.columns:
        df['trend_strength'] = df['trend_length'] * df['price_distance']

    return df


def analyze_indicator_accuracy(
    ticker: str,
    start_date: str,
    end_date: str,
    trend_col: str = 'Close',
    direction_col: str = 'trend_direction'
) -> Dict[str, Any]:
    """
    Analyze all technical indicators for a given stock and calculate accuracy.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date in format 'YYYY-MM-DD'
        end_date: End date in format 'YYYY-MM-DD'
        trend_col: Column name for trend analysis (default: 'Close')
        direction_col: Column name for trend direction (default: 'trend_direction')

    Returns:
        Dictionary containing:
            - 'all_data': DataFrame with all indicator data
            - 'trend_breaks': List of trend break tuples
            - 'accuracy_data': Dictionary of accuracy scores per indicator
            - 'accuracy_df': DataFrame with accuracy metrics and rankings
            - 'summary_stats': Dictionary with summary statistics

    Example:
        >>> results = analyze_indicator_accuracy('AAPL', '2020-01-01', '2024-01-01')
        >>> print(results['accuracy_df'])
    """
    from .data_fetcher import get_stock_data
    from .technical_indicators import calculate_all_indicators

    print(f"Analyzing {ticker} from {start_date} to {end_date}...")

    # Get data and calculate indicators
    data = get_stock_data(ticker, start_date, end_date)
    all_data = calculate_all_indicators(data)

    # Detect trend breaks
    print(f"Detecting trend breaks using '{trend_col}' column...")
    trend_breaks = trend_break(all_data, trend_col, direction_col)
    print(f"Found {len(trend_breaks)} trend breaks")

    # Calculate accuracy for each indicator
    accuracy_data = {}
    indicator_cols = ['RSI', 'MACD', '%K', '%D', 'ADX', 'OBV', 'CMF', 'MFI']

    for col in indicator_cols:
        if col in all_data.columns:
            # Simple accuracy: did indicator predict direction correctly?
            correct = 0
            total = 0

            for date, direction in trend_breaks:
                try:
                    idx = all_data[all_data['Date'] == date].index[0]
                    if idx > 0:
                        prev_val = all_data.loc[idx - 1, col]
                        curr_val = all_data.loc[idx, col]

                        if direction == 'increasing' and curr_val > prev_val:
                            correct += 1
                        elif direction == 'decreasing' and curr_val < prev_val:
                            correct += 1
                        total += 1
                except (IndexError, KeyError):
                    continue

            if total > 0:
                accuracy_data[col] = correct / total
                print(f"  ✓ {col}: {accuracy_data[col]:.2%}")

    # Create accuracy DataFrame
    accuracy_df = pd.DataFrame.from_dict(
        accuracy_data,
        orient='index',
        columns=['accuracy']
    )
    accuracy_df = accuracy_df.dropna()
    accuracy_df['above_mean'] = accuracy_df['accuracy'] > accuracy_df['accuracy'].mean()
    accuracy_df['rank'] = accuracy_df['accuracy'].rank(ascending=False)
    accuracy_df['percentile'] = accuracy_df['accuracy'].rank(pct=True) * 100
    accuracy_df = accuracy_df.sort_values('rank')

    # Summary statistics
    summary_stats = {
        'ticker': ticker,
        'date_range': f"{start_date} to {end_date}",
        'total_indicators': len(accuracy_df),
        'trend_breaks_detected': len(trend_breaks),
        'mean_accuracy': accuracy_df['accuracy'].mean() if len(accuracy_df) > 0 else 0,
        'median_accuracy': accuracy_df['accuracy'].median() if len(accuracy_df) > 0 else 0,
        'best_indicator': accuracy_df.index[0] if len(accuracy_df) > 0 else None,
        'best_accuracy': accuracy_df['accuracy'].iloc[0] if len(accuracy_df) > 0 else 0,
    }

    print(f"\nBest indicator: {summary_stats['best_indicator']} ({summary_stats['best_accuracy']:.2%})")

    return {
        'all_data': all_data,
        'trend_breaks': trend_breaks,
        'accuracy_data': accuracy_data,
        'accuracy_df': accuracy_df,
        'summary_stats': summary_stats
    }


def filter_best_indicators(
    results: Dict[str, Any],
    min_accuracy: float = 0.80,
    max_accuracy: float = 0.90
) -> Dict[str, Any]:
    """
    Filter indicators based on accuracy thresholds.

    Args:
        results: Results from analyze_indicator_accuracy()
        min_accuracy: Minimum accuracy threshold (default: 0.80)
        max_accuracy: Maximum accuracy threshold (default: 0.90)

    Returns:
        Dictionary containing:
            - 'best_indicators_df': DataFrame with filtered indicators
            - 'indicator_names': List of indicator names meeting criteria
            - 'count': Number of indicators meeting criteria
            - 'mean_accuracy': Mean accuracy of filtered indicators

    Example:
        >>> best = filter_best_indicators(results, min_accuracy=0.75)
        >>> print(best['indicator_names'])
    """
    accuracy_df = results['accuracy_df']

    filtered_df = accuracy_df[
        (accuracy_df['accuracy'] >= min_accuracy) &
        (accuracy_df['accuracy'] <= max_accuracy)
    ].copy()

    indicator_names = filtered_df.index.tolist()
    count = len(filtered_df)
    mean_acc = filtered_df['accuracy'].mean() if count > 0 else 0

    print(f"\nFiltered indicators ({min_accuracy:.0%} - {max_accuracy:.0%}):")
    print(f"Found {count} indicators")
    for name in indicator_names:
        acc = filtered_df.loc[name, 'accuracy']
        print(f"  - {name}: {acc:.2%}")

    return {
        'best_indicators_df': filtered_df,
        'indicator_names': indicator_names,
        'count': count,
        'mean_accuracy': mean_acc,
        'accuracy_range': (min_accuracy, max_accuracy)
    }


def compare_multiple_stocks(
    tickers: List[str],
    start_date: str,
    end_date: str,
    trend_col: str = 'Close'
) -> Dict[str, Any]:
    """
    Analyze indicator accuracy across multiple stocks.

    Args:
        tickers: List of ticker symbols
        start_date: Start date in format 'YYYY-MM-DD'
        end_date: End date in format 'YYYY-MM-DD'
        trend_col: Column name for trend analysis

    Returns:
        Dictionary with ticker as key and analysis results as value

    Example:
        >>> results = compare_multiple_stocks(['AAPL', 'MSFT'], '2020-01-01', '2024-01-01')
    """
    results = {}

    for ticker in tickers:
        print(f"\n{'='*60}")
        print(f"Analyzing {ticker}...")
        print('='*60)

        try:
            results[ticker] = analyze_indicator_accuracy(
                ticker, start_date, end_date, trend_col
            )
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            results[ticker] = None

    return results


def export_results(
    results: Dict[str, Any],
    output_dir: str = '.'
) -> Dict[str, str]:
    """
    Export analysis results to CSV files.

    Args:
        results: Results from analyze_indicator_accuracy()
        output_dir: Directory to save output files

    Returns:
        Dictionary with paths to exported files

    Example:
        >>> files = export_results(results, output_dir='./output')
    """
    import os

    ticker = results['summary_stats']['ticker']
    timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')

    os.makedirs(output_dir, exist_ok=True)

    # Export accuracy DataFrame
    accuracy_file = os.path.join(output_dir, f"{ticker}_indicator_accuracy_{timestamp}.csv")
    results['accuracy_df'].to_csv(accuracy_file)

    # Export summary stats
    summary_file = os.path.join(output_dir, f"{ticker}_summary_{timestamp}.txt")
    with open(summary_file, 'w') as f:
        for key, value in results['summary_stats'].items():
            f.write(f"{key}: {value}\n")

    print(f"\nExported:")
    print(f"  - Accuracy: {accuracy_file}")
    print(f"  - Summary: {summary_file}")

    return {
        'accuracy_file': accuracy_file,
        'summary_file': summary_file
    }
