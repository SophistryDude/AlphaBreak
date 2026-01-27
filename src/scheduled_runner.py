"""
Scheduled Runner Module
========================
Run analysis on a schedule with configurable time windows.

This script runs on execution and analyzes stocks for potential trades
based on the specified time window (24 hours, 1 hour, 15 mins, 5 mins).

Usage:
    # Run once with 24-hour window (daily analysis)
    python -m src.scheduled_runner --window 24h --tickers AAPL,MSFT,GOOGL

    # Run once with 15-minute window (intraday)
    python -m src.scheduled_runner --window 15m --tickers AAPL

    # Run continuously every hour
    python -m src.scheduled_runner --window 1h --tickers AAPL --continuous --interval 3600

    # Run with all S&P 500 stocks
    python -m src.scheduled_runner --window 24h --sp500
"""

import argparse
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import pandas as pd
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher import get_stock_data, get_stock_data_interval, get_sp500_tickers, get_crypto_tickers
from src.technical_indicators import calculate_all_indicators, calculate_rsi, calculate_macd
from src.trend_analysis import trend_break, analyze_indicator_accuracy


# ════════════════════════════════════════════════════════════════════════════
# TIME WINDOW CONFIGURATIONS
# ════════════════════════════════════════════════════════════════════════════

TIME_WINDOWS = {
    '5m': {'interval': '5m', 'period': '1d', 'lookback_days': 1},
    '15m': {'interval': '15m', 'period': '5d', 'lookback_days': 5},
    '30m': {'interval': '30m', 'period': '5d', 'lookback_days': 5},
    '1h': {'interval': '1h', 'period': '7d', 'lookback_days': 7},
    '4h': {'interval': '1h', 'period': '1mo', 'lookback_days': 30},  # 4h not directly supported, use 1h
    '24h': {'interval': '1d', 'period': '3mo', 'lookback_days': 90},
    '1d': {'interval': '1d', 'period': '3mo', 'lookback_days': 90},
    '1w': {'interval': '1d', 'period': '1y', 'lookback_days': 365},
}


# ════════════════════════════════════════════════════════════════════════════
# ANALYSIS FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def analyze_ticker(
    ticker: str,
    window: str = '24h',
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Analyze a single ticker for potential trades.

    Args:
        ticker: Stock ticker symbol
        window: Time window ('5m', '15m', '30m', '1h', '4h', '24h', '1d', '1w')
        verbose: Print analysis progress

    Returns:
        Dictionary with analysis results

    Example:
        >>> result = analyze_ticker('AAPL', window='1h')
        >>> if result['signal']:
        ...     print(f"Signal: {result['signal_type']}")
    """
    config = TIME_WINDOWS.get(window, TIME_WINDOWS['24h'])

    if verbose:
        print(f"\n{'='*50}")
        print(f"Analyzing {ticker} ({window} window)")
        print(f"{'='*50}")

    try:
        # Fetch data based on window type
        if window in ['5m', '15m', '30m', '1h']:
            # Intraday data
            data = get_stock_data_interval(ticker, period=config['period'], interval=config['interval'])
        else:
            # Daily data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=config['lookback_days'])
            data = get_stock_data(ticker, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))

        if len(data) < 20:
            return {'ticker': ticker, 'error': 'Insufficient data', 'signal': False}

        # Rename columns if needed (intraday data has different column names)
        if 'Datetime' in data.columns:
            data = data.rename(columns={'Datetime': 'Date'})

        # Calculate indicators
        data = calculate_all_indicators(data)

        # Get latest values
        latest = data.iloc[-1]
        prev = data.iloc[-2] if len(data) > 1 else latest

        # Determine signals
        signals = []

        # RSI signals
        if 'RSI' in data.columns:
            rsi = latest['RSI']
            if rsi < 30:
                signals.append(('RSI', 'OVERSOLD', f'RSI={rsi:.1f}'))
            elif rsi > 70:
                signals.append(('RSI', 'OVERBOUGHT', f'RSI={rsi:.1f}'))

        # MACD signals
        if 'MACD' in data.columns and 'Signal_Line' in data.columns:
            macd = latest['MACD']
            signal_line = latest['Signal_Line']
            prev_macd = prev['MACD']
            prev_signal = prev['Signal_Line']

            # MACD crossover
            if prev_macd < prev_signal and macd > signal_line:
                signals.append(('MACD', 'BULLISH_CROSS', f'MACD crossed above signal'))
            elif prev_macd > prev_signal and macd < signal_line:
                signals.append(('MACD', 'BEARISH_CROSS', f'MACD crossed below signal'))

        # Stochastic signals
        if '%K' in data.columns and '%D' in data.columns:
            k = latest['%K']
            d = latest['%D']
            prev_k = prev['%K']
            prev_d = prev['%D']

            if k < 20 and prev_k < prev_d and k > d:
                signals.append(('Stochastic', 'BULLISH_CROSS', f'%K crossed above %D in oversold'))
            elif k > 80 and prev_k > prev_d and k < d:
                signals.append(('Stochastic', 'BEARISH_CROSS', f'%K crossed below %D in overbought'))

        # Bollinger Band signals
        if 'BB_Upper' in data.columns and 'BB_Lower' in data.columns:
            close = latest['Close']
            bb_upper = latest['BB_Upper']
            bb_lower = latest['BB_Lower']

            if close < bb_lower:
                signals.append(('BB', 'BELOW_LOWER', f'Price below lower band'))
            elif close > bb_upper:
                signals.append(('BB', 'ABOVE_UPPER', f'Price above upper band'))

        # Determine overall signal
        bullish_signals = sum(1 for s in signals if 'BULLISH' in s[1] or s[1] in ['OVERSOLD', 'BELOW_LOWER'])
        bearish_signals = sum(1 for s in signals if 'BEARISH' in s[1] or s[1] in ['OVERBOUGHT', 'ABOVE_UPPER'])

        if bullish_signals > bearish_signals and bullish_signals >= 2:
            overall_signal = 'BUY'
        elif bearish_signals > bullish_signals and bearish_signals >= 2:
            overall_signal = 'SELL'
        else:
            overall_signal = 'HOLD'

        result = {
            'ticker': ticker,
            'timestamp': datetime.now().isoformat(),
            'window': window,
            'current_price': float(latest['Close']),
            'signal': len(signals) > 0,
            'signal_type': overall_signal,
            'signals': signals,
            'bullish_count': bullish_signals,
            'bearish_count': bearish_signals,
            'indicators': {
                'rsi': float(latest['RSI']) if 'RSI' in data.columns else None,
                'macd': float(latest['MACD']) if 'MACD' in data.columns else None,
                'stochastic_k': float(latest['%K']) if '%K' in data.columns else None,
            },
            'error': None
        }

        if verbose:
            print(f"Current Price: ${result['current_price']:.2f}")
            print(f"RSI: {result['indicators']['rsi']:.1f}" if result['indicators']['rsi'] else "RSI: N/A")
            print(f"Signal: {result['signal_type']}")
            if signals:
                print(f"Active Signals:")
                for indicator, signal_type, detail in signals:
                    print(f"  - {indicator}: {signal_type} ({detail})")

        return result

    except Exception as e:
        if verbose:
            print(f"Error analyzing {ticker}: {e}")
        return {'ticker': ticker, 'error': str(e), 'signal': False}


def analyze_multiple_tickers(
    tickers: List[str],
    window: str = '24h',
    verbose: bool = True
) -> List[Dict[str, Any]]:
    """
    Analyze multiple tickers for potential trades.

    Args:
        tickers: List of ticker symbols
        window: Time window
        verbose: Print analysis progress

    Returns:
        List of analysis results

    Example:
        >>> results = analyze_multiple_tickers(['AAPL', 'MSFT'], window='1h')
    """
    results = []

    for ticker in tickers:
        result = analyze_ticker(ticker, window, verbose)
        results.append(result)

    return results


def filter_signals(results: List[Dict], signal_type: Optional[str] = None) -> List[Dict]:
    """
    Filter analysis results by signal type.

    Args:
        results: List of analysis results
        signal_type: 'BUY', 'SELL', or None for all signals

    Returns:
        Filtered list of results

    Example:
        >>> buy_signals = filter_signals(results, signal_type='BUY')
    """
    filtered = [r for r in results if r.get('signal', False) and not r.get('error')]

    if signal_type:
        filtered = [r for r in filtered if r.get('signal_type') == signal_type]

    return filtered


def generate_report(results: List[Dict], output_path: Optional[str] = None) -> str:
    """
    Generate a text report from analysis results.

    Args:
        results: List of analysis results
        output_path: Optional path to save report

    Returns:
        Report as string

    Example:
        >>> report = generate_report(results, output_path='./reports/daily.txt')
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    lines = [
        "=" * 60,
        f"TRADING ANALYSIS REPORT",
        f"Generated: {timestamp}",
        "=" * 60,
        ""
    ]

    # Summary
    total = len(results)
    errors = len([r for r in results if r.get('error')])
    buy_signals = filter_signals(results, 'BUY')
    sell_signals = filter_signals(results, 'SELL')

    lines.extend([
        "SUMMARY",
        "-" * 40,
        f"Total tickers analyzed: {total}",
        f"Errors: {errors}",
        f"Buy signals: {len(buy_signals)}",
        f"Sell signals: {len(sell_signals)}",
        ""
    ])

    # Buy signals
    if buy_signals:
        lines.extend([
            "BUY SIGNALS",
            "-" * 40
        ])
        for r in buy_signals:
            lines.append(f"  {r['ticker']}: ${r['current_price']:.2f}")
            for ind, sig, detail in r.get('signals', []):
                lines.append(f"    - {ind}: {detail}")
        lines.append("")

    # Sell signals
    if sell_signals:
        lines.extend([
            "SELL SIGNALS",
            "-" * 40
        ])
        for r in sell_signals:
            lines.append(f"  {r['ticker']}: ${r['current_price']:.2f}")
            for ind, sig, detail in r.get('signals', []):
                lines.append(f"    - {ind}: {detail}")
        lines.append("")

    # Errors
    if errors > 0:
        lines.extend([
            "ERRORS",
            "-" * 40
        ])
        for r in results:
            if r.get('error'):
                lines.append(f"  {r['ticker']}: {r['error']}")
        lines.append("")

    report = "\n".join(lines)

    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(report)
        print(f"\nReport saved to: {output_path}")

    return report


# ════════════════════════════════════════════════════════════════════════════
# CONTINUOUS RUNNING
# ════════════════════════════════════════════════════════════════════════════

def run_continuous(
    tickers: List[str],
    window: str = '24h',
    interval_seconds: int = 3600,
    output_dir: str = './reports'
):
    """
    Run analysis continuously at specified intervals.

    Args:
        tickers: List of ticker symbols
        window: Time window for analysis
        interval_seconds: Seconds between runs
        output_dir: Directory to save reports

    Example:
        >>> run_continuous(['AAPL', 'MSFT'], window='1h', interval_seconds=3600)
    """
    print(f"\nStarting continuous analysis")
    print(f"Tickers: {len(tickers)}")
    print(f"Window: {window}")
    print(f"Interval: {interval_seconds} seconds")
    print(f"Output: {output_dir}")
    print(f"\nPress Ctrl+C to stop\n")

    os.makedirs(output_dir, exist_ok=True)

    try:
        while True:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running analysis...")

            results = analyze_multiple_tickers(tickers, window, verbose=False)

            # Generate report
            report_path = os.path.join(output_dir, f"report_{timestamp}.txt")
            report = generate_report(results, report_path)

            # Print summary
            buy_signals = filter_signals(results, 'BUY')
            sell_signals = filter_signals(results, 'SELL')

            print(f"Buy signals: {len(buy_signals)}, Sell signals: {len(sell_signals)}")

            if buy_signals:
                print("  BUY: " + ", ".join([r['ticker'] for r in buy_signals]))
            if sell_signals:
                print("  SELL: " + ", ".join([r['ticker'] for r in sell_signals]))

            # Wait for next interval
            print(f"Next run in {interval_seconds} seconds...")
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n\nStopped by user")


# ════════════════════════════════════════════════════════════════════════════
# COMMAND LINE INTERFACE
# ════════════════════════════════════════════════════════════════════════════

def main():
    """
    Command line interface for scheduled runner.

    Examples:
        # Analyze single ticker
        python -m src.scheduled_runner --ticker AAPL --window 1h

        # Analyze multiple tickers
        python -m src.scheduled_runner --tickers AAPL,MSFT,GOOGL --window 24h

        # Analyze S&P 500
        python -m src.scheduled_runner --sp500 --window 24h --output ./reports/sp500.txt

        # Run continuously
        python -m src.scheduled_runner --tickers AAPL,MSFT --window 1h --continuous --interval 3600
    """
    parser = argparse.ArgumentParser(
        description='Run trading analysis on schedule',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=main.__doc__
    )

    # Ticker selection
    ticker_group = parser.add_mutually_exclusive_group(required=True)
    ticker_group.add_argument('--ticker', '-t', type=str, help='Single ticker symbol')
    ticker_group.add_argument('--tickers', type=str, help='Comma-separated list of tickers')
    ticker_group.add_argument('--sp500', action='store_true', help='Analyze all S&P 500 stocks')
    ticker_group.add_argument('--crypto', action='store_true', help='Analyze major cryptocurrencies')

    # Time window
    parser.add_argument(
        '--window', '-w',
        type=str,
        default='24h',
        choices=['5m', '15m', '30m', '1h', '4h', '24h', '1d', '1w'],
        help='Time window for analysis (default: 24h)'
    )

    # Output
    parser.add_argument('--output', '-o', type=str, help='Output file path for report')
    parser.add_argument('--output-dir', type=str, default='./reports', help='Output directory for continuous mode')

    # Continuous mode
    parser.add_argument('--continuous', '-c', action='store_true', help='Run continuously')
    parser.add_argument('--interval', '-i', type=int, default=3600, help='Interval in seconds for continuous mode')

    # Verbosity
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress output')

    args = parser.parse_args()

    # Determine tickers
    if args.ticker:
        tickers = [args.ticker]
    elif args.tickers:
        tickers = [t.strip() for t in args.tickers.split(',')]
    elif args.sp500:
        print("Fetching S&P 500 ticker list...")
        tickers = get_sp500_tickers()
        print(f"Found {len(tickers)} tickers")
    elif args.crypto:
        tickers = get_crypto_tickers()
        print(f"Analyzing {len(tickers)} cryptocurrencies")

    # Run mode
    if args.continuous:
        run_continuous(
            tickers=tickers,
            window=args.window,
            interval_seconds=args.interval,
            output_dir=args.output_dir
        )
    else:
        # Single run
        results = analyze_multiple_tickers(tickers, args.window, verbose=not args.quiet)

        # Generate report
        report = generate_report(results, args.output)

        if not args.output and not args.quiet:
            print("\n" + report)

        # Print summary
        buy_signals = filter_signals(results, 'BUY')
        sell_signals = filter_signals(results, 'SELL')

        print(f"\n{'='*50}")
        print(f"FINAL SUMMARY")
        print(f"{'='*50}")
        print(f"Total analyzed: {len(results)}")
        print(f"Buy signals: {len(buy_signals)}")
        print(f"Sell signals: {len(sell_signals)}")

        if buy_signals:
            print(f"\nBUY: {', '.join([r['ticker'] for r in buy_signals])}")
        if sell_signals:
            print(f"SELL: {', '.join([r['ticker'] for r in sell_signals])}")


if __name__ == '__main__':
    main()
