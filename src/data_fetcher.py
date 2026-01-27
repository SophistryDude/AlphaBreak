"""
Data Fetcher Module
====================
Pull historical data for specific tickers and store in database.

This module can be called ad-hoc to populate a database with security information.

Usage:
    # Command line (ad-hoc):
    python -m src.data_fetcher --ticker AAPL --start 2020-01-01 --end 2024-01-01

    # As module:
    from src.data_fetcher import get_stock_data, fetch_and_store
    data = get_stock_data('AAPL', '2020-01-01', '2024-01-01')
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Union
import argparse
import os


def get_stock_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Pull historical OHLCV data for a specific ticker.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'BTC-USD')
        start_date: Start date in format 'YYYY-MM-DD'
        end_date: End date in format 'YYYY-MM-DD'

    Returns:
        DataFrame with columns: Date, Open, High, Low, Close, Adj Close, Volume

    Example:
        >>> data = get_stock_data('AAPL', '2020-01-01', '2024-01-01')
        >>> print(data.head())
    """
    data = yf.download(ticker, start=start_date, end=end_date, progress=False)

    # Handle multi-level columns from yfinance (ticker, price type)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.reset_index()

    # Handle different column naming conventions in yfinance versions
    # Some versions use 'Adj Close', others just have 'Close'
    columns_to_select = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    if 'Adj Close' in data.columns:
        columns_to_select.insert(5, 'Adj Close')
    else:
        # Create Adj Close from Close if not present
        data['Adj Close'] = data['Close']
        columns_to_select.insert(5, 'Adj Close')

    data = data[columns_to_select]
    return data


def get_stock_data_interval(
    ticker: str,
    period: str = "1d",
    interval: str = "1h"
) -> pd.DataFrame:
    """
    Pull historical data with specific interval for intraday analysis.

    Args:
        ticker: Stock ticker symbol
        period: Data period - valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
        interval: Data interval - valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo

    Returns:
        DataFrame with OHLCV data at specified interval

    Note:
        Intraday data (< 1d intervals) is only available for last 60 days

    Example:
        >>> data = get_stock_data_interval('AAPL', period='5d', interval='15m')
    """
    stock = yf.Ticker(ticker)
    data = stock.history(period=period, interval=interval)
    data = data.reset_index()
    return data


def get_multiple_stocks(
    tickers: List[str],
    start_date: str,
    end_date: str
) -> dict:
    """
    Pull historical data for multiple tickers.

    Args:
        tickers: List of ticker symbols
        start_date: Start date in format 'YYYY-MM-DD'
        end_date: End date in format 'YYYY-MM-DD'

    Returns:
        Dictionary with ticker as key and DataFrame as value

    Example:
        >>> data = get_multiple_stocks(['AAPL', 'MSFT', 'GOOGL'], '2020-01-01', '2024-01-01')
        >>> print(data['AAPL'].head())
    """
    results = {}
    for ticker in tickers:
        try:
            results[ticker] = get_stock_data(ticker, start_date, end_date)
            print(f"✓ Downloaded {ticker}")
        except Exception as e:
            print(f"✗ Error downloading {ticker}: {e}")
            results[ticker] = None
    return results


def fetch_and_store(
    ticker: str,
    start_date: str,
    end_date: str,
    output_path: Optional[str] = None,
    db_connection: Optional[str] = None,
    table_name: str = "stock_data"
) -> pd.DataFrame:
    """
    Fetch stock data and store to file or database.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date in format 'YYYY-MM-DD'
        end_date: End date in format 'YYYY-MM-DD'
        output_path: Path to save CSV file (optional)
        db_connection: SQLAlchemy database connection string (optional)
        table_name: Table name for database storage

    Returns:
        DataFrame with the fetched data

    Example:
        # Save to CSV
        >>> fetch_and_store('AAPL', '2020-01-01', '2024-01-01', output_path='data/aapl.csv')

        # Save to PostgreSQL
        >>> fetch_and_store('AAPL', '2020-01-01', '2024-01-01',
        ...     db_connection='postgresql://user:pass@localhost/trading_db')
    """
    # Fetch data
    data = get_stock_data(ticker, start_date, end_date)
    data['ticker'] = ticker
    data['fetched_at'] = datetime.now()

    # Save to CSV if path provided
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        data.to_csv(output_path, index=False)
        print(f"✓ Saved to {output_path}")

    # Save to database if connection provided
    if db_connection:
        try:
            from sqlalchemy import create_engine
            engine = create_engine(db_connection)
            data.to_sql(table_name, engine, if_exists='append', index=False)
            print(f"✓ Saved to database table '{table_name}'")
        except ImportError:
            print("✗ SQLAlchemy not installed. Run: pip install sqlalchemy")
        except Exception as e:
            print(f"✗ Database error: {e}")

    return data


def get_sp500_tickers() -> List[str]:
    """
    Get list of current S&P 500 ticker symbols.

    Returns:
        List of ticker symbols

    Example:
        >>> tickers = get_sp500_tickers()
        >>> print(f"Found {len(tickers)} tickers")
    """
    try:
        table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = table[0]
        return df['Symbol'].str.replace('.', '-').tolist()
    except Exception as e:
        print(f"Error fetching S&P 500 list: {e}")
        # Return a subset if wiki fails
        return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'JPM', 'V', 'JNJ']


def get_crypto_tickers() -> List[str]:
    """
    Get list of major cryptocurrency ticker symbols for Yahoo Finance.

    Returns:
        List of crypto ticker symbols
    """
    return [
        'BTC-USD',   # Bitcoin
        'ETH-USD',   # Ethereum
        'BNB-USD',   # Binance Coin
        'XRP-USD',   # Ripple
        'ADA-USD',   # Cardano
        'SOL-USD',   # Solana
        'DOGE-USD',  # Dogecoin
        'DOT-USD',   # Polkadot
        'MATIC-USD', # Polygon
        'LTC-USD',   # Litecoin
    ]


# ════════════════════════════════════════════════════════════════════════════
# Command Line Interface
# ════════════════════════════════════════════════════════════════════════════

def main():
    """
    Command line interface for ad-hoc data fetching.

    Examples:
        # Fetch single ticker to CSV
        python -m src.data_fetcher --ticker AAPL --start 2020-01-01 --end 2024-01-01 --output data/aapl.csv

        # Fetch multiple tickers
        python -m src.data_fetcher --tickers AAPL,MSFT,GOOGL --start 2020-01-01 --end 2024-01-01

        # Fetch to database
        python -m src.data_fetcher --ticker AAPL --start 2020-01-01 --end 2024-01-01 --db postgresql://user:pass@localhost/db

        # Fetch S&P 500
        python -m src.data_fetcher --sp500 --start 2020-01-01 --end 2024-01-01 --output data/

        # Fetch crypto
        python -m src.data_fetcher --crypto --start 2020-01-01 --end 2024-01-01
    """
    parser = argparse.ArgumentParser(
        description='Fetch historical stock/crypto data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=main.__doc__
    )

    # Ticker selection (mutually exclusive)
    ticker_group = parser.add_mutually_exclusive_group(required=True)
    ticker_group.add_argument('--ticker', '-t', type=str, help='Single ticker symbol')
    ticker_group.add_argument('--tickers', type=str, help='Comma-separated list of tickers')
    ticker_group.add_argument('--sp500', action='store_true', help='Fetch all S&P 500 stocks')
    ticker_group.add_argument('--crypto', action='store_true', help='Fetch major cryptocurrencies')

    # Date range
    parser.add_argument('--start', '-s', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', '-e', type=str, required=True, help='End date (YYYY-MM-DD)')

    # Output options
    parser.add_argument('--output', '-o', type=str, help='Output path (file or directory)')
    parser.add_argument('--db', type=str, help='Database connection string')
    parser.add_argument('--table', type=str, default='stock_data', help='Database table name')

    args = parser.parse_args()

    # Determine tickers to fetch
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
        print(f"Fetching {len(tickers)} cryptocurrencies")

    # Fetch data for each ticker
    print(f"\nFetching data from {args.start} to {args.end}...")
    print("=" * 60)

    for ticker in tickers:
        # Determine output path
        if args.output:
            if os.path.isdir(args.output) or args.output.endswith('/'):
                output_path = os.path.join(args.output, f"{ticker}.csv")
            elif len(tickers) == 1:
                output_path = args.output
            else:
                # Multiple tickers, create directory
                os.makedirs(args.output, exist_ok=True)
                output_path = os.path.join(args.output, f"{ticker}.csv")
        else:
            output_path = None

        try:
            data = fetch_and_store(
                ticker=ticker,
                start_date=args.start,
                end_date=args.end,
                output_path=output_path,
                db_connection=args.db,
                table_name=args.table
            )
            print(f"✓ {ticker}: {len(data)} rows")
        except Exception as e:
            print(f"✗ {ticker}: Error - {e}")

    print("=" * 60)
    print("Done!")


if __name__ == '__main__':
    main()
