"""
Polygon.io Historical Data Fetcher
===================================
Fetches historical stock data from Polygon.io API for production use.

Features:
- Full historical intraday data (years of 1-min bars)
- Real-time and delayed data options
- Options chain data (with appropriate subscription)
- Corporate actions and dividends
- Rate limiting and retry logic

Requirements:
- Polygon.io API key (set POLYGON_API_KEY environment variable)
- Subscription tier determines data access:
  - Basic ($29/mo): 2 years historical, 15-min delayed
  - Starter ($79/mo): 5 years, real-time
  - Developer ($199/mo): Full history, options

Usage:
    # Set API key
    export POLYGON_API_KEY=your_api_key_here

    # Fetch daily data
    python -m src.polygon_data_fetcher --tickers AAPL,MSFT --daily --start 2020-01-01

    # Fetch intraday data (1-min bars)
    python -m src.polygon_data_fetcher --tickers AAPL --intraday --interval 1min --start 2024-01-01

    # Fetch full S&P 500 with all data
    python -m src.polygon_data_fetcher --sp500 --all --start 2020-01-01
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Generator
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import logging
import requests
from urllib.parse import urljoin

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Polygon.io configuration
POLYGON_BASE_URL = "https://api.polygon.io"
POLYGON_API_KEY = os.environ.get('POLYGON_API_KEY', '')

# Rate limits by subscription tier
RATE_LIMITS = {
    'basic': 5,       # 5 requests per minute
    'starter': 100,   # Unlimited but we'll be conservative
    'developer': 100,
}

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('TIMESERIES_DB_HOST', 'localhost'),
    'port': int(os.environ.get('TIMESERIES_DB_PORT', 5433)),
    'database': os.environ.get('TIMESERIES_DB_NAME', 'trading_data'),
    'user': os.environ.get('TIMESERIES_DB_USER', 'trading'),
    'password': os.environ.get('TIMESERIES_DB_PASSWORD', 'change-this-timeseries-password'),
    'sslmode': os.environ.get('TIMESERIES_DB_SSLMODE', 'prefer'),
}

# Interval mappings for Polygon
POLYGON_INTERVALS = {
    '1min': ('minute', 1),
    '5min': ('minute', 5),
    '10min': ('minute', 10),
    '15min': ('minute', 15),
    '30min': ('minute', 30),
    '1hour': ('hour', 1),
    '1day': ('day', 1),
}


class PolygonRateLimiter:
    """Simple rate limiter for Polygon API."""

    def __init__(self, requests_per_minute: int = 5):
        self.requests_per_minute = requests_per_minute
        self.request_times = []

    def wait_if_needed(self):
        """Wait if we've exceeded our rate limit."""
        now = time.time()
        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]

        if len(self.request_times) >= self.requests_per_minute:
            # Wait until the oldest request is more than 1 minute old
            wait_time = 60 - (now - self.request_times[0]) + 0.1
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.1f}s...")
                time.sleep(wait_time)

        self.request_times.append(time.time())


class PolygonDataFetcher:
    """Fetches historical stock data from Polygon.io API."""

    def __init__(self, api_key: str = None, db_config: dict = None,
                 subscription_tier: str = 'basic'):
        self.api_key = api_key or POLYGON_API_KEY
        if not self.api_key:
            raise ValueError(
                "Polygon API key required. Set POLYGON_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.db_config = db_config or DB_CONFIG
        self.conn = None
        self.session = requests.Session()
        self.rate_limiter = PolygonRateLimiter(RATE_LIMITS.get(subscription_tier, 5))

        self.stats = {
            'tickers_processed': 0,
            'tickers_failed': 0,
            'daily_records': 0,
            'intraday_records': 0,
            'api_calls': 0,
        }

    def connect_db(self) -> bool:
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            logger.info(f"Connected to database: {self.db_config['database']}@{self.db_config['host']}")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def close(self):
        """Close connections."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
        self.session.close()

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated request to Polygon API with rate limiting."""
        self.rate_limiter.wait_if_needed()

        url = urljoin(POLYGON_BASE_URL, endpoint)
        params = params or {}
        params['apiKey'] = self.api_key

        try:
            response = self.session.get(url, params=params, timeout=30)
            self.stats['api_calls'] += 1

            if response.status_code == 429:
                # Rate limited - wait and retry
                logger.warning("Rate limited by Polygon, waiting 60s...")
                time.sleep(60)
                return self._make_request(endpoint, params)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    # =========================================================================
    # AGGREGATE BARS (OHLCV)
    # =========================================================================

    def fetch_aggregate_bars(self, ticker: str, multiplier: int, timespan: str,
                            start_date: str, end_date: str,
                            adjusted: bool = True) -> Generator[pd.DataFrame, None, None]:
        """
        Fetch aggregate bars from Polygon.io.

        Uses pagination to handle large date ranges.

        Args:
            ticker: Stock symbol
            multiplier: Size of the timespan multiplier (e.g., 1 for 1-minute)
            timespan: 'minute', 'hour', 'day', 'week', 'month', 'quarter', 'year'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            adjusted: Whether to adjust for splits

        Yields:
            DataFrame chunks of OHLCV data
        """
        endpoint = f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start_date}/{end_date}"

        params = {
            'adjusted': str(adjusted).lower(),
            'sort': 'asc',
            'limit': 50000,  # Max limit per request
        }

        while True:
            data = self._make_request(endpoint, params)

            if data.get('status') != 'OK' or not data.get('results'):
                break

            results = data['results']

            # Convert to DataFrame
            df = pd.DataFrame(results)
            df = df.rename(columns={
                't': 'timestamp',
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume',
                'vw': 'vwap',
                'n': 'trade_count'
            })

            # Convert timestamp from milliseconds
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['ticker'] = ticker

            yield df

            # Check for next page
            if data.get('next_url'):
                # Extract cursor from next_url and continue
                next_url = data['next_url']
                # Parse the cursor parameter
                if 'cursor=' in next_url:
                    cursor = next_url.split('cursor=')[1].split('&')[0]
                    params['cursor'] = cursor
                else:
                    break
            else:
                break

    def fetch_daily_data(self, ticker: str, start_date: str,
                        end_date: str = None) -> pd.DataFrame:
        """Fetch daily OHLCV data."""
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        logger.info(f"Fetching daily data for {ticker}: {start_date} to {end_date}")

        all_data = []
        for df in self.fetch_aggregate_bars(ticker, 1, 'day', start_date, end_date):
            all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)
        result['date'] = result['timestamp'].dt.date
        result['adjusted_close'] = result['close']  # Polygon returns adjusted by default

        return result

    def fetch_intraday_data(self, ticker: str, interval: str,
                           start_date: str, end_date: str = None) -> pd.DataFrame:
        """
        Fetch intraday OHLCV data.

        Args:
            ticker: Stock symbol
            interval: '1min', '5min', '10min', '15min', '30min', '1hour'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        if interval not in POLYGON_INTERVALS:
            raise ValueError(f"Invalid interval: {interval}. "
                           f"Valid options: {list(POLYGON_INTERVALS.keys())}")

        timespan, multiplier = POLYGON_INTERVALS[interval]

        logger.info(f"Fetching {interval} data for {ticker}: {start_date} to {end_date}")

        all_data = []
        for df in self.fetch_aggregate_bars(ticker, multiplier, timespan,
                                           start_date, end_date):
            df['interval_type'] = interval
            all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        return pd.concat(all_data, ignore_index=True)

    # =========================================================================
    # TICKER DETAILS
    # =========================================================================

    def fetch_ticker_details(self, ticker: str) -> dict:
        """Fetch company details from Polygon."""
        try:
            data = self._make_request(f"/v3/reference/tickers/{ticker}")

            if data.get('status') != 'OK' or not data.get('results'):
                return {'ticker': ticker}

            result = data['results']

            return {
                'ticker': ticker,
                'company_name': result.get('name'),
                'sector': result.get('sic_description'),
                'industry': result.get('sic_description'),
                'exchange': result.get('primary_exchange'),
                'market_cap_category': self._categorize_market_cap(
                    result.get('market_cap')
                ),
                'cik': result.get('cik'),
            }

        except Exception as e:
            logger.warning(f"Failed to fetch details for {ticker}: {e}")
            return {'ticker': ticker}

    def _categorize_market_cap(self, market_cap: int) -> str:
        """Categorize market cap into size buckets."""
        if market_cap is None:
            return None
        if market_cap >= 200_000_000_000:
            return 'mega'
        elif market_cap >= 10_000_000_000:
            return 'large'
        elif market_cap >= 2_000_000_000:
            return 'mid'
        elif market_cap >= 300_000_000:
            return 'small'
        else:
            return 'micro'

    # =========================================================================
    # DIVIDENDS AND SPLITS
    # =========================================================================

    def fetch_dividends(self, ticker: str, start_date: str = None) -> pd.DataFrame:
        """Fetch dividend history from Polygon."""
        params = {'ticker': ticker, 'limit': 1000}
        if start_date:
            params['ex_dividend_date.gte'] = start_date

        try:
            data = self._make_request("/v3/reference/dividends", params)

            if not data.get('results'):
                return pd.DataFrame()

            df = pd.DataFrame(data['results'])
            df = df.rename(columns={
                'ex_dividend_date': 'ex_date',
                'cash_amount': 'value',
            })
            df['ticker'] = ticker
            df['action_type'] = 'dividend'

            return df[['ticker', 'ex_date', 'action_type', 'value']]

        except Exception as e:
            logger.warning(f"Failed to fetch dividends for {ticker}: {e}")
            return pd.DataFrame()

    def fetch_splits(self, ticker: str, start_date: str = None) -> pd.DataFrame:
        """Fetch stock split history from Polygon."""
        params = {'ticker': ticker, 'limit': 1000}
        if start_date:
            params['execution_date.gte'] = start_date

        try:
            data = self._make_request("/v3/reference/splits", params)

            if not data.get('results'):
                return pd.DataFrame()

            df = pd.DataFrame(data['results'])
            df = df.rename(columns={
                'execution_date': 'ex_date',
                'split_to': 'split_to',
                'split_from': 'split_from',
            })
            df['ticker'] = ticker
            df['action_type'] = 'split'
            df['value'] = df['split_to'] / df['split_from']

            return df[['ticker', 'ex_date', 'action_type', 'value']]

        except Exception as e:
            logger.warning(f"Failed to fetch splits for {ticker}: {e}")
            return pd.DataFrame()

    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================

    def insert_daily_data(self, ticker: str, df: pd.DataFrame) -> int:
        """Insert daily data into database."""
        if df.empty:
            return 0

        cursor = self.conn.cursor()

        rows = []
        for _, row in df.iterrows():
            rows.append((
                ticker,
                row['date'],
                float(row['open']) if pd.notna(row['open']) else None,
                float(row['high']) if pd.notna(row['high']) else None,
                float(row['low']) if pd.notna(row['low']) else None,
                float(row['close']) if pd.notna(row['close']) else None,
                int(row['volume']) if pd.notna(row['volume']) else None,
                float(row['adjusted_close']) if pd.notna(row['adjusted_close']) else None,
                'polygon'
            ))

        insert_query = """
            INSERT INTO stock_prices_daily
            (ticker, date, open, high, low, close, volume, adjusted_close, data_source)
            VALUES %s
            ON CONFLICT (ticker, date) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                adjusted_close = EXCLUDED.adjusted_close,
                data_source = EXCLUDED.data_source
        """

        try:
            execute_values(cursor, insert_query, rows)
            self.conn.commit()
            return len(rows)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error inserting daily data for {ticker}: {e}")
            return 0
        finally:
            cursor.close()

    def insert_intraday_data(self, ticker: str, df: pd.DataFrame) -> int:
        """Insert intraday data into database."""
        if df.empty:
            return 0

        cursor = self.conn.cursor()

        rows = []
        for _, row in df.iterrows():
            rows.append((
                ticker,
                row['timestamp'],
                row['interval_type'],
                float(row['open']) if pd.notna(row['open']) else None,
                float(row['high']) if pd.notna(row['high']) else None,
                float(row['low']) if pd.notna(row['low']) else None,
                float(row['close']) if pd.notna(row['close']) else None,
                int(row['volume']) if pd.notna(row['volume']) else None,
                float(row['vwap']) if pd.notna(row.get('vwap')) else None,
                int(row['trade_count']) if pd.notna(row.get('trade_count')) else None,
            ))

        insert_query = """
            INSERT INTO stock_prices_intraday
            (ticker, timestamp, interval_type, open, high, low, close, volume, vwap, trade_count)
            VALUES %s
            ON CONFLICT (ticker, timestamp, interval_type) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                vwap = EXCLUDED.vwap,
                trade_count = EXCLUDED.trade_count
        """

        try:
            execute_values(cursor, insert_query, rows)
            self.conn.commit()
            return len(rows)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error inserting intraday data for {ticker}: {e}")
            return 0
        finally:
            cursor.close()

    def insert_corporate_actions(self, ticker: str, dividends: pd.DataFrame,
                                splits: pd.DataFrame) -> int:
        """Insert corporate actions into database."""
        cursor = self.conn.cursor()
        total_inserted = 0

        for df in [dividends, splits]:
            if df.empty:
                continue

            rows = []
            for _, row in df.iterrows():
                rows.append((
                    ticker,
                    row['ex_date'],
                    row['action_type'],
                    float(row['value']) if pd.notna(row['value']) else None,
                    'polygon'
                ))

            insert_query = """
                INSERT INTO corporate_actions
                (ticker, ex_date, action_type, value, data_source)
                VALUES %s
                ON CONFLICT (ticker, ex_date, action_type) DO UPDATE SET
                    value = EXCLUDED.value
            """

            try:
                execute_values(cursor, insert_query, rows)
                self.conn.commit()
                total_inserted += len(rows)
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error inserting corporate actions for {ticker}: {e}")

        cursor.close()
        return total_inserted

    # =========================================================================
    # MAIN POPULATION METHODS
    # =========================================================================

    def populate_ticker(self, ticker: str, start_date: str,
                       fetch_daily: bool = True, fetch_intraday: bool = False,
                       intraday_interval: str = '1min',
                       fetch_actions: bool = True) -> dict:
        """Populate all data for a single ticker."""
        result = {
            'ticker': ticker,
            'daily_records': 0,
            'intraday_records': 0,
            'actions_records': 0,
            'status': 'success',
            'error': None
        }

        try:
            # Daily data
            if fetch_daily:
                df = self.fetch_daily_data(ticker, start_date)
                if not df.empty:
                    count = self.insert_daily_data(ticker, df)
                    result['daily_records'] = count
                    logger.info(f"  Inserted {count:,} daily records")

            # Intraday data
            if fetch_intraday:
                df = self.fetch_intraday_data(ticker, intraday_interval, start_date)
                if not df.empty:
                    count = self.insert_intraday_data(ticker, df)
                    result['intraday_records'] = count
                    logger.info(f"  Inserted {count:,} {intraday_interval} records")

            # Corporate actions
            if fetch_actions:
                dividends = self.fetch_dividends(ticker, start_date)
                splits = self.fetch_splits(ticker, start_date)
                count = self.insert_corporate_actions(ticker, dividends, splits)
                result['actions_records'] = count
                if count > 0:
                    logger.info(f"  Inserted {count} corporate actions")

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            logger.error(f"Error processing {ticker}: {e}")

        return result

    def populate_multiple(self, tickers: List[str], start_date: str,
                         **kwargs) -> List[dict]:
        """Populate data for multiple tickers."""
        results = []
        total = len(tickers)

        logger.info("=" * 60)
        logger.info(f"Starting Polygon.io population for {total} tickers")
        logger.info(f"Start date: {start_date}")
        logger.info("=" * 60)

        for i, ticker in enumerate(tickers, 1):
            logger.info(f"[{i}/{total}] Processing {ticker}...")
            result = self.populate_ticker(ticker, start_date, **kwargs)
            results.append(result)

            # Update stats
            self.stats['tickers_processed'] += 1
            if result['status'] == 'error':
                self.stats['tickers_failed'] += 1
            self.stats['daily_records'] += result['daily_records']
            self.stats['intraday_records'] += result['intraday_records']

        self._print_summary(results)
        return results

    def _print_summary(self, results: List[dict]):
        """Print population summary."""
        logger.info("=" * 60)
        logger.info("POLYGON.IO POPULATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Tickers processed: {self.stats['tickers_processed']}")
        logger.info(f"Tickers failed: {self.stats['tickers_failed']}")
        logger.info(f"Daily records: {self.stats['daily_records']:,}")
        logger.info(f"Intraday records: {self.stats['intraday_records']:,}")
        logger.info(f"Total API calls: {self.stats['api_calls']}")

        if self.stats['tickers_failed'] > 0:
            logger.info("\nFailed tickers:")
            for r in results:
                if r['status'] == 'error':
                    logger.info(f"  - {r['ticker']}: {r['error']}")


def main():
    parser = argparse.ArgumentParser(
        description='Fetch historical data from Polygon.io',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Ticker selection
    ticker_group = parser.add_mutually_exclusive_group()
    ticker_group.add_argument('--tickers', '-t', type=str,
                             help='Comma-separated list of tickers')
    ticker_group.add_argument('--sp500', action='store_true',
                             help='Fetch all S&P 500 stocks')
    ticker_group.add_argument('--djia', action='store_true',
                             help='Fetch all DJIA stocks')

    # Data types
    parser.add_argument('--daily', action='store_true',
                       help='Fetch daily OHLCV data')
    parser.add_argument('--intraday', action='store_true',
                       help='Fetch intraday data')
    parser.add_argument('--interval', type=str, default='1min',
                       choices=['1min', '5min', '10min', '15min', '30min', '1hour'],
                       help='Intraday interval (default: 1min)')
    parser.add_argument('--actions', action='store_true',
                       help='Fetch dividends and splits')
    parser.add_argument('--all', action='store_true',
                       help='Fetch all data types')

    # Date range
    parser.add_argument('--start', '-s', type=str, required=True,
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', '-e', type=str,
                       default=datetime.now().strftime('%Y-%m-%d'),
                       help='End date (YYYY-MM-DD, default: today)')

    # API configuration
    parser.add_argument('--api-key', type=str,
                       help='Polygon.io API key (or set POLYGON_API_KEY env var)')
    parser.add_argument('--tier', type=str, default='basic',
                       choices=['basic', 'starter', 'developer'],
                       help='Subscription tier for rate limiting (default: basic)')

    # Database
    parser.add_argument('--host', type=str, default=DB_CONFIG['host'])
    parser.add_argument('--port', type=int, default=DB_CONFIG['port'])
    parser.add_argument('--database', type=str, default=DB_CONFIG['database'])
    parser.add_argument('--user', type=str, default=DB_CONFIG['user'])
    parser.add_argument('--password', type=str, default=DB_CONFIG['password'])

    args = parser.parse_args()

    # Determine tickers
    if args.sp500:
        # Import from the other module
        from src.populate_historical_data import get_sp500_tickers_live
        tickers = get_sp500_tickers_live()
        logger.info(f"Using {len(tickers)} S&P 500 tickers")
    elif args.djia:
        from src.populate_historical_data import DJIA_TICKERS
        tickers = DJIA_TICKERS
        logger.info(f"Using {len(tickers)} DJIA tickers")
    elif args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        tickers = ['AAPL', 'MSFT', 'GOOGL']  # Default test tickers
        logger.info(f"Using default test tickers: {tickers}")

    # Determine what to fetch
    if args.all:
        fetch_daily = fetch_intraday = fetch_actions = True
    else:
        fetch_daily = args.daily or (not args.intraday and not args.actions)
        fetch_intraday = args.intraday
        fetch_actions = args.actions

    # Database config
    db_config = {
        'host': args.host,
        'port': args.port,
        'database': args.database,
        'user': args.user,
        'password': args.password,
    }

    # Create fetcher
    try:
        fetcher = PolygonDataFetcher(
            api_key=args.api_key,
            db_config=db_config,
            subscription_tier=args.tier
        )
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    # Connect and populate
    if not fetcher.connect_db():
        sys.exit(1)

    try:
        fetcher.populate_multiple(
            tickers,
            start_date=args.start,
            fetch_daily=fetch_daily,
            fetch_intraday=fetch_intraday,
            intraday_interval=args.interval,
            fetch_actions=fetch_actions
        )

    finally:
        fetcher.close()


if __name__ == '__main__':
    main()
