import pandas as pd
import numpy as np
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
