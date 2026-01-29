"""
Database Population Script
===========================
Fetches historical securities data and populates the TimescaleDB database.

Usage:
    # Populate with default tickers (top tech stocks)
    python -m src.populate_database

    # Populate specific tickers
    python -m src.populate_database --tickers AAPL,MSFT,GOOGL

    # Populate S&P 500
    python -m src.populate_database --sp500

    # Specify date range
    python -m src.populate_database --tickers AAPL --start 2020-01-01 --end 2024-01-01

    # Include technical indicators
    python -m src.populate_database --tickers AAPL --indicators
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# Add project root to path for direct module imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import data_fetcher directly using importlib to avoid __init__.py
import importlib.util

def load_module_direct(module_path, module_name):
    """Load a module directly without triggering package __init__.py."""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Load data_fetcher directly
data_fetcher_path = os.path.join(project_root, 'src', 'data_fetcher.py')
data_fetcher = load_module_direct(data_fetcher_path, 'data_fetcher_direct')

get_stock_data = data_fetcher.get_stock_data
get_sp500_tickers = data_fetcher.get_sp500_tickers
get_crypto_tickers = data_fetcher.get_crypto_tickers

# Lazy import for technical indicators (may not be installed locally)
def get_indicator_calculator():
    """Lazy load indicator calculator to handle missing dependencies."""
    try:
        ti_path = os.path.join(project_root, 'src', 'technical_indicators.py')
        ti_module = load_module_direct(ti_path, 'technical_indicators_direct')
        return ti_module.calculate_all_indicators
    except Exception as e:
        print(f"Warning: Technical indicators not available: {e}")
        return None


# Default connection settings (for Kubernetes)
DB_CONFIG = {
    'host': os.environ.get('TIMESERIES_DB_HOST', 'localhost'),
    'port': int(os.environ.get('TIMESERIES_DB_PORT', 5432)),
    'database': os.environ.get('TIMESERIES_DB_NAME', 'trading_data'),
    'user': os.environ.get('TIMESERIES_DB_USER', 'trading'),
    'password': os.environ.get('TIMESERIES_DB_PASSWORD', 'change-this-timeseries-password'),
    'sslmode': os.environ.get('TIMESERIES_DB_SSLMODE', 'prefer'),
}

# Default tickers for quick testing
DEFAULT_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
    'META', 'TSLA', 'JPM', 'V', 'JNJ'
]


class DatabasePopulator:
    """Handles database population with historical securities data."""

    def __init__(self, db_config: dict = None):
        """Initialize with database configuration."""
        self.db_config = db_config or DB_CONFIG
        self.conn = None

    def connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            print(f"[OK] Connected to database: {self.db_config['database']}@{self.db_config['host']}")
            return True
        except Exception as e:
            print(f"[ERROR] Database connection failed: {e}")
            return False

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            print("[OK] Database connection closed")

    def insert_stock_prices(self, ticker: str, data: pd.DataFrame) -> int:
        """
        Insert stock price data into the database.

        Args:
            ticker: Stock ticker symbol
            data: DataFrame with Date, Open, High, Low, Close, Volume, Adj Close

        Returns:
            Number of rows inserted
        """
        if data.empty:
            return 0

        cursor = self.conn.cursor()

        # Prepare data for insertion
        rows = []
        for _, row in data.iterrows():
            timestamp = row['Date']
            if isinstance(timestamp, str):
                timestamp = pd.to_datetime(timestamp)

            rows.append((
                ticker,
                timestamp,
                float(row['Open']) if pd.notna(row['Open']) else None,
                float(row['High']) if pd.notna(row['High']) else None,
                float(row['Low']) if pd.notna(row['Low']) else None,
                float(row['Close']) if pd.notna(row['Close']) else None,
                int(row['Volume']) if pd.notna(row['Volume']) else None,
                float(row['Adj Close']) if pd.notna(row.get('Adj Close', row['Close'])) else None,
            ))

        # Use INSERT ... ON CONFLICT for upsert
        insert_query = """
            INSERT INTO stock_prices (ticker, timestamp, open, high, low, close, volume, adjusted_close)
            VALUES %s
            ON CONFLICT (ticker, timestamp) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                adjusted_close = EXCLUDED.adjusted_close
        """

        try:
            execute_values(cursor, insert_query, rows)
            self.conn.commit()
            return len(rows)
        except Exception as e:
            self.conn.rollback()
            print(f"  [ERROR] Error inserting prices for {ticker}: {e}")
            return 0
        finally:
            cursor.close()

    def insert_technical_indicators(self, ticker: str, data: pd.DataFrame) -> int:
        """
        Insert technical indicator values into the database.

        Args:
            ticker: Stock ticker symbol
            data: DataFrame with Date and indicator columns

        Returns:
            Number of rows inserted
        """
        if data.empty:
            return 0

        cursor = self.conn.cursor()

        # Get indicator columns (exclude OHLCV)
        exclude_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
        indicator_cols = [col for col in data.columns if col not in exclude_cols]

        rows = []
        for _, row in data.iterrows():
            timestamp = row['Date']
            if isinstance(timestamp, str):
                timestamp = pd.to_datetime(timestamp)

            for indicator in indicator_cols:
                value = row[indicator]
                if pd.notna(value):
                    rows.append((
                        ticker,
                        timestamp,
                        indicator,
                        float(value)
                    ))

        if not rows:
            return 0

        insert_query = """
            INSERT INTO technical_indicators (ticker, timestamp, indicator_name, indicator_value)
            VALUES %s
            ON CONFLICT (ticker, timestamp, indicator_name) DO UPDATE SET
                indicator_value = EXCLUDED.indicator_value
        """

        try:
            execute_values(cursor, insert_query, rows)
            self.conn.commit()
            return len(rows)
        except Exception as e:
            self.conn.rollback()
            print(f"  [ERROR] Error inserting indicators for {ticker}: {e}")
            return 0
        finally:
            cursor.close()

    def get_latest_timestamp(self, ticker: str) -> Optional[datetime]:
        """Get the latest timestamp for a ticker in the database."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT MAX(timestamp) FROM stock_prices WHERE ticker = %s",
                (ticker,)
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
        finally:
            cursor.close()

    def get_row_count(self, ticker: str) -> int:
        """Get the number of rows for a ticker."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM stock_prices WHERE ticker = %s",
                (ticker,)
            )
            return cursor.fetchone()[0]
        finally:
            cursor.close()

    def populate_ticker(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        include_indicators: bool = False,
        incremental: bool = True
    ) -> dict:
        """
        Populate database with data for a single ticker.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            include_indicators: Calculate and store technical indicators
            incremental: Only fetch data newer than latest in database

        Returns:
            Dictionary with population statistics
        """
        stats = {
            'ticker': ticker,
            'prices_inserted': 0,
            'indicators_inserted': 0,
            'status': 'success',
            'error': None
        }

        try:
            # Check for incremental update
            if incremental:
                latest = self.get_latest_timestamp(ticker)
                if latest:
                    # Fetch data from day after latest
                    start_date = (latest + timedelta(days=1)).strftime('%Y-%m-%d')
                    print(f"  Incremental update from {start_date}")

            # Fetch stock data
            print(f"  Fetching data for {ticker}...")
            data = get_stock_data(ticker, start_date, end_date)

            if data.empty:
                print(f"  [WARN] No data available for {ticker}")
                stats['status'] = 'no_data'
                return stats

            # Insert price data
            prices_count = self.insert_stock_prices(ticker, data)
            stats['prices_inserted'] = prices_count
            print(f"  [OK] Inserted {prices_count} price records")

            # Calculate and insert indicators
            if include_indicators:
                calculate_all_indicators = get_indicator_calculator()
                if calculate_all_indicators:
                    print(f"  Calculating indicators...")
                    data_with_indicators = calculate_all_indicators(data)
                    indicators_count = self.insert_technical_indicators(ticker, data_with_indicators)
                    stats['indicators_inserted'] = indicators_count
                    print(f"  [OK] Inserted {indicators_count} indicator records")
                else:
                    print(f"  [WARN] Skipping indicators (dependencies not installed)")

        except Exception as e:
            stats['status'] = 'error'
            stats['error'] = str(e)
            print(f"  [ERROR] Error: {e}")

        return stats

    def populate_multiple(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        include_indicators: bool = False,
        incremental: bool = True
    ) -> List[dict]:
        """
        Populate database with data for multiple tickers.

        Args:
            tickers: List of stock ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            include_indicators: Calculate and store technical indicators
            incremental: Only fetch data newer than latest in database

        Returns:
            List of population statistics for each ticker
        """
        results = []
        total = len(tickers)

        print(f"\n{'='*60}")
        print(f"Populating database with {total} tickers")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Indicators: {'Yes' if include_indicators else 'No'}")
        print(f"Mode: {'Incremental' if incremental else 'Full'}")
        print(f"{'='*60}\n")

        for i, ticker in enumerate(tickers, 1):
            print(f"[{i}/{total}] Processing {ticker}...")
            stats = self.populate_ticker(
                ticker, start_date, end_date,
                include_indicators, incremental
            )
            results.append(stats)
            print()

        # Summary
        print(f"{'='*60}")
        print("POPULATION COMPLETE")
        print(f"{'='*60}")

        success = sum(1 for r in results if r['status'] == 'success')
        no_data = sum(1 for r in results if r['status'] == 'no_data')
        errors = sum(1 for r in results if r['status'] == 'error')
        total_prices = sum(r['prices_inserted'] for r in results)
        total_indicators = sum(r['indicators_inserted'] for r in results)

        print(f"Successful: {success}/{total}")
        print(f"No data: {no_data}/{total}")
        print(f"Errors: {errors}/{total}")
        print(f"Total price records: {total_prices:,}")
        print(f"Total indicator records: {total_indicators:,}")

        if errors > 0:
            print("\nErrors:")
            for r in results:
                if r['status'] == 'error':
                    print(f"  - {r['ticker']}: {r['error']}")

        return results


def main():
    """Command line interface for database population."""
    parser = argparse.ArgumentParser(
        description='Populate database with historical securities data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Ticker selection
    ticker_group = parser.add_mutually_exclusive_group()
    ticker_group.add_argument(
        '--tickers', '-t',
        type=str,
        help='Comma-separated list of tickers (default: top 10 tech/finance)'
    )
    ticker_group.add_argument(
        '--sp500',
        action='store_true',
        help='Populate all S&P 500 stocks'
    )
    ticker_group.add_argument(
        '--crypto',
        action='store_true',
        help='Populate major cryptocurrencies'
    )

    # Date range
    parser.add_argument(
        '--start', '-s',
        type=str,
        default=(datetime.now() - timedelta(days=365*2)).strftime('%Y-%m-%d'),
        help='Start date (YYYY-MM-DD), default: 2 years ago'
    )
    parser.add_argument(
        '--end', '-e',
        type=str,
        default=datetime.now().strftime('%Y-%m-%d'),
        help='End date (YYYY-MM-DD), default: today'
    )

    # Options
    parser.add_argument(
        '--indicators', '-i',
        action='store_true',
        help='Calculate and store technical indicators'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Full refresh (not incremental)'
    )

    # Database connection
    parser.add_argument(
        '--host',
        type=str,
        default=DB_CONFIG['host'],
        help='Database host'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=DB_CONFIG['port'],
        help='Database port'
    )
    parser.add_argument(
        '--database',
        type=str,
        default=DB_CONFIG['database'],
        help='Database name'
    )
    parser.add_argument(
        '--user',
        type=str,
        default=DB_CONFIG['user'],
        help='Database user'
    )
    parser.add_argument(
        '--password',
        type=str,
        default=DB_CONFIG['password'],
        help='Database password'
    )

    args = parser.parse_args()

    # Determine tickers
    if args.sp500:
        print("Fetching S&P 500 ticker list...")
        tickers = get_sp500_tickers()
        print(f"Found {len(tickers)} tickers")
    elif args.crypto:
        tickers = get_crypto_tickers()
        print(f"Using {len(tickers)} cryptocurrency tickers")
    elif args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        tickers = DEFAULT_TICKERS
        print(f"Using default tickers: {', '.join(tickers)}")

    # Configure database connection
    db_config = {
        'host': args.host,
        'port': args.port,
        'database': args.database,
        'user': args.user,
        'password': args.password,
    }

    # Run population
    populator = DatabasePopulator(db_config)

    if not populator.connect():
        sys.exit(1)

    try:
        populator.populate_multiple(
            tickers=tickers,
            start_date=args.start,
            end_date=args.end,
            include_indicators=args.indicators,
            incremental=not args.full
        )
    finally:
        populator.close()


if __name__ == '__main__':
    main()
