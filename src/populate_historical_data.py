"""
Historical Data Population Script - Full S&P 500 & DJIA
=========================================================
Fetches complete historical data for S&P 500 and DJIA constituents.

Supports:
- Daily OHLCV data (back to Yahoo Finance inception ~1962 for indices)
- Intraday data (1min, 5min, 10min, 1hour) - limited to recent data
- Corporate actions (dividends, splits)
- Index constituent tracking

Data Source Limitations:
- Yahoo Finance free tier: 7 days of 1-min data, 60 days of intraday
- Daily data: Available back to ~1962 for major stocks
- Options data: Current chain only (no historical)

Usage:
    # Full S&P 500 daily data (all history)
    python -m src.populate_historical_data --sp500 --daily

    # DJIA with intraday (last 60 days)
    python -m src.populate_historical_data --djia --intraday

    # Specific tickers with everything
    python -m src.populate_historical_data --tickers AAPL,MSFT --daily --intraday --actions

    # Estimate storage requirements
    python -m src.populate_historical_data --sp500 --estimate-only
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import logging

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

# Import yfinance directly
try:
    import yfinance as yf
except ImportError:
    logger.error("yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('TIMESERIES_DB_HOST', 'localhost'),
    'port': int(os.environ.get('TIMESERIES_DB_PORT', 5433)),  # Using 5433 for port-forward
    'database': os.environ.get('TIMESERIES_DB_NAME', 'trading_data'),
    'user': os.environ.get('TIMESERIES_DB_USER', 'trading'),
    'password': os.environ.get('TIMESERIES_DB_PASSWORD', 'change-this-timeseries-password'),
    'sslmode': os.environ.get('TIMESERIES_DB_SSLMODE', 'prefer'),
}

# S&P 500 tickers (current constituents as of 2024)
# In production, this would be fetched from Wikipedia or a data provider
SP500_TICKERS = [
    'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'GOOG', 'TSLA', 'BRK.B', 'UNH',
    'XOM', 'JNJ', 'JPM', 'V', 'PG', 'MA', 'AVGO', 'HD', 'CVX', 'MRK',
    'ABBV', 'LLY', 'PEP', 'COST', 'KO', 'WMT', 'MCD', 'CSCO', 'TMO', 'ACN',
    'ABT', 'DHR', 'CRM', 'BAC', 'NKE', 'ADBE', 'CMCSA', 'PFE', 'NFLX', 'DIS',
    'VZ', 'INTC', 'WFC', 'TXN', 'PM', 'COP', 'RTX', 'QCOM', 'NEE', 'UPS',
    # Add more... (truncated for brevity - full list would have ~500)
    'AMD', 'AMGN', 'AXP', 'BA', 'BMY', 'C', 'CAT', 'CVS', 'DE', 'DOW',
    'DUK', 'EMR', 'EXC', 'F', 'FDX', 'GE', 'GILD', 'GM', 'GS', 'HON',
    'IBM', 'ISRG', 'LIN', 'LMT', 'LOW', 'MDT', 'MMM', 'MO', 'MRK', 'MS',
    'ORCL', 'PYPL', 'SBUX', 'SCHW', 'SO', 'SPG', 'SYK', 'T', 'TGT', 'UNP',
    'USB', 'VLO', 'WBA', 'NOW', 'BLK', 'INTU', 'BKNG', 'MDLZ', 'ADP', 'CI',
]

# DJIA 30 components
DJIA_TICKERS = [
    'AAPL', 'AMGN', 'AXP', 'BA', 'CAT', 'CRM', 'CSCO', 'CVX', 'DIS', 'DOW',
    'GS', 'HD', 'HON', 'IBM', 'INTC', 'JNJ', 'JPM', 'KO', 'MCD', 'MMM',
    'MRK', 'MSFT', 'NKE', 'PG', 'TRV', 'UNH', 'V', 'VZ', 'WBA', 'WMT'
]

# Interval mappings for yfinance
INTERVAL_MAP = {
    '1min': '1m',
    '5min': '5m',
    '10min': '10m',   # Note: yfinance doesn't support 10min, we'll aggregate from 1min
    '15min': '15m',
    '30min': '30m',
    '1hour': '1h',
    '1day': '1d',
}


class HistoricalDataPopulator:
    """Handles population of historical stock data into TimescaleDB."""

    def __init__(self, db_config: dict = None, max_workers: int = 5):
        self.db_config = db_config or DB_CONFIG
        self.conn = None
        self.max_workers = max_workers
        self.stats = {
            'tickers_processed': 0,
            'tickers_failed': 0,
            'daily_records': 0,
            'intraday_records': 0,
            'actions_records': 0,
        }

    def connect(self) -> bool:
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            logger.info(f"Connected to database: {self.db_config['database']}@{self.db_config['host']}")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def ensure_schema(self):
        """Create tables if they don't exist."""
        schema_file = os.path.join(project_root, 'kubernetes', 'schema_v2_intraday.sql')
        if os.path.exists(schema_file):
            logger.info("Schema file found - ensure you've run it manually or via Kubernetes init")
        else:
            logger.warning("Schema file not found - tables may not exist")

    # =========================================================================
    # DAILY DATA FETCHING
    # =========================================================================

    def fetch_daily_data(self, ticker: str, start_date: str = '1960-01-01',
                        end_date: str = None) -> pd.DataFrame:
        """Fetch daily OHLCV data from Yahoo Finance."""
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date, interval='1d', auto_adjust=False)

            if df.empty:
                return pd.DataFrame()

            # Reset index to get Date as column
            df = df.reset_index()
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
                'Adj Close': 'adjusted_close'
            })

            # Keep only needed columns
            df = df[['date', 'open', 'high', 'low', 'close', 'volume', 'adjusted_close']]
            df['ticker'] = ticker
            df['date'] = pd.to_datetime(df['date']).dt.date

            return df

        except Exception as e:
            logger.warning(f"Failed to fetch daily data for {ticker}: {e}")
            return pd.DataFrame()

    def insert_daily_data(self, ticker: str, df: pd.DataFrame) -> int:
        """Insert daily data into stock_prices (existing table with timestamp column)."""
        if df.empty:
            return 0

        cursor = self.conn.cursor()

        rows = []
        for _, row in df.iterrows():
            # Convert date to timestamp for stock_prices table
            timestamp = pd.Timestamp(row['date']).to_pydatetime()
            rows.append((
                ticker,
                timestamp,
                float(row['open']) if pd.notna(row['open']) else None,
                float(row['high']) if pd.notna(row['high']) else None,
                float(row['low']) if pd.notna(row['low']) else None,
                float(row['close']) if pd.notna(row['close']) else None,
                int(row['volume']) if pd.notna(row['volume']) else None,
                float(row['adjusted_close']) if pd.notna(row['adjusted_close']) else None,
            ))

        insert_query = """
            INSERT INTO stock_prices
            (ticker, timestamp, open, high, low, close, volume, adjusted_close)
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
            logger.error(f"Error inserting daily data for {ticker}: {e}")
            return 0
        finally:
            cursor.close()

    # =========================================================================
    # INTRADAY DATA FETCHING
    # =========================================================================

    # Yahoo Finance max periods for each interval
    YAHOO_MAX_PERIODS = {
        '1min': '7d',      # ~4-7 days actual
        '5min': '60d',     # ~56 days actual
        '15min': '60d',    # ~56 days actual
        '30min': '60d',    # ~56 days actual
        '1hour': '730d',   # ~725 days (~2 years) actual
    }

    def fetch_intraday_data(self, ticker: str, interval: str = '1min',
                           period: str = None) -> pd.DataFrame:
        """
        Fetch intraday OHLCV data from Yahoo Finance.

        Uses maximum available period for each interval:
        - 1min data: max 7 days (~4 days actual)
        - 5min/15min/30min: max 60 days (~56 days actual)
        - 1hour: max 730 days (~2 years actual)

        Args:
            ticker: Stock symbol
            interval: '1min', '5min', '15min', '30min', '1hour'
            period: Override period (default: use max for interval)
        """
        yf_interval = INTERVAL_MAP.get(interval, interval)

        # Use max period if not specified
        if period is None:
            period = self.YAHOO_MAX_PERIODS.get(interval, '60d')

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=yf_interval)

            if df.empty:
                return pd.DataFrame()

            df = df.reset_index()
            df = df.rename(columns={
                'Datetime': 'timestamp',
                'Date': 'timestamp',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })

            df['ticker'] = ticker
            df['interval_type'] = interval
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            # Calculate VWAP if we have price and volume
            if 'close' in df.columns and 'volume' in df.columns:
                df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
            else:
                df['vwap'] = None

            df['trade_count'] = None  # Not available from Yahoo

            return df[['ticker', 'timestamp', 'interval_type', 'open', 'high',
                      'low', 'close', 'volume', 'vwap', 'trade_count']]

        except Exception as e:
            logger.warning(f"Failed to fetch {interval} data for {ticker}: {e}")
            return pd.DataFrame()

    def insert_intraday_data(self, ticker: str, df: pd.DataFrame) -> int:
        """Insert intraday data into stock_prices_intraday."""
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
                float(row['vwap']) if pd.notna(row['vwap']) else None,
                int(row['trade_count']) if pd.notna(row['trade_count']) else None,
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

    # =========================================================================
    # CORPORATE ACTIONS
    # =========================================================================

    def fetch_corporate_actions(self, ticker: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Fetch dividends and stock splits from Yahoo Finance."""
        try:
            stock = yf.Ticker(ticker)

            # Dividends
            dividends = stock.dividends
            if not dividends.empty:
                div_df = dividends.reset_index()
                div_df.columns = ['ex_date', 'value']
                div_df['ticker'] = ticker
                div_df['action_type'] = 'dividend'
                div_df['ex_date'] = pd.to_datetime(div_df['ex_date']).dt.date
            else:
                div_df = pd.DataFrame()

            # Splits
            splits = stock.splits
            if not splits.empty:
                split_df = splits.reset_index()
                split_df.columns = ['ex_date', 'value']
                split_df['ticker'] = ticker
                split_df['action_type'] = 'split'
                split_df['ex_date'] = pd.to_datetime(split_df['ex_date']).dt.date
            else:
                split_df = pd.DataFrame()

            return div_df, split_df

        except Exception as e:
            logger.warning(f"Failed to fetch corporate actions for {ticker}: {e}")
            return pd.DataFrame(), pd.DataFrame()

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
                    'yahoo'
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
    # TICKER METADATA
    # =========================================================================

    def fetch_ticker_metadata(self, ticker: str) -> dict:
        """Fetch company metadata from Yahoo Finance."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            return {
                'ticker': ticker,
                'company_name': info.get('longName') or info.get('shortName'),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'exchange': info.get('exchange'),
                'market_cap_category': self._categorize_market_cap(info.get('marketCap')),
            }
        except Exception as e:
            logger.warning(f"Failed to fetch metadata for {ticker}: {e}")
            return {'ticker': ticker}

    def _categorize_market_cap(self, market_cap: int) -> str:
        """Categorize market cap into size buckets."""
        if market_cap is None:
            return None
        if market_cap >= 200_000_000_000:  # $200B+
            return 'mega'
        elif market_cap >= 10_000_000_000:  # $10B+
            return 'large'
        elif market_cap >= 2_000_000_000:   # $2B+
            return 'mid'
        elif market_cap >= 300_000_000:     # $300M+
            return 'small'
        else:
            return 'micro'

    def insert_ticker_metadata(self, metadata: dict) -> bool:
        """Insert ticker metadata into database."""
        cursor = self.conn.cursor()

        query = """
            INSERT INTO ticker_metadata
            (ticker, company_name, sector, industry, exchange, market_cap_category, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (ticker) DO UPDATE SET
                company_name = EXCLUDED.company_name,
                sector = EXCLUDED.sector,
                industry = EXCLUDED.industry,
                exchange = EXCLUDED.exchange,
                market_cap_category = EXCLUDED.market_cap_category,
                last_updated = NOW()
        """

        try:
            cursor.execute(query, (
                metadata.get('ticker'),
                metadata.get('company_name'),
                metadata.get('sector'),
                metadata.get('industry'),
                metadata.get('exchange'),
                metadata.get('market_cap_category'),
            ))
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error inserting metadata for {metadata.get('ticker')}: {e}")
            return False
        finally:
            cursor.close()

    # =========================================================================
    # INDEX CONSTITUENTS
    # =========================================================================

    def insert_index_constituents(self, index_symbol: str, tickers: List[str]):
        """Insert current index constituents."""
        cursor = self.conn.cursor()

        today = datetime.now().date()

        for ticker in tickers:
            query = """
                INSERT INTO index_constituents (index_symbol, ticker, added_date)
                VALUES (%s, %s, %s)
                ON CONFLICT (index_symbol, ticker, added_date) DO NOTHING
            """
            try:
                cursor.execute(query, (index_symbol, ticker, today))
            except Exception as e:
                logger.warning(f"Error inserting constituent {ticker}: {e}")

        self.conn.commit()
        cursor.close()
        logger.info(f"Inserted {len(tickers)} constituents for {index_symbol}")

    # =========================================================================
    # MAIN POPULATION METHODS
    # =========================================================================

    def populate_ticker(self, ticker: str, fetch_daily: bool = True,
                       fetch_intraday: bool = False, fetch_actions: bool = True,
                       fetch_metadata: bool = True,
                       daily_start: str = '1960-01-01') -> dict:
        """
        Populate all data for a single ticker.

        Returns dict with stats.
        """
        result = {
            'ticker': ticker,
            'daily_records': 0,
            'intraday_records': 0,
            'actions_records': 0,
            'status': 'success',
            'error': None
        }

        try:
            # Metadata
            if fetch_metadata:
                metadata = self.fetch_ticker_metadata(ticker)
                self.insert_ticker_metadata(metadata)

            # Daily data
            if fetch_daily:
                logger.info(f"  Fetching daily data for {ticker}...")
                df = self.fetch_daily_data(ticker, start_date=daily_start)
                if not df.empty:
                    count = self.insert_daily_data(ticker, df)
                    result['daily_records'] = count
                    logger.info(f"  Inserted {count:,} daily records")

            # Intraday data - fetch max available for each interval
            if fetch_intraday:
                # Fetch all intervals with their max available periods
                intraday_intervals = [
                    ('1hour', None),   # ~2 years (730d)
                    ('5min', None),    # ~60 days
                    ('1min', None),    # ~7 days
                ]
                for interval, period in intraday_intervals:
                    max_period = self.YAHOO_MAX_PERIODS.get(interval, '60d')
                    logger.info(f"  Fetching {interval} data for {ticker} (max: {max_period})...")
                    df = self.fetch_intraday_data(ticker, interval=interval, period=period)
                    if not df.empty:
                        count = self.insert_intraday_data(ticker, df)
                        result['intraday_records'] += count
                        logger.info(f"  Inserted {count:,} {interval} records")

            # Corporate actions
            if fetch_actions:
                logger.info(f"  Fetching corporate actions for {ticker}...")
                dividends, splits = self.fetch_corporate_actions(ticker)
                count = self.insert_corporate_actions(ticker, dividends, splits)
                result['actions_records'] = count
                if count > 0:
                    logger.info(f"  Inserted {count} corporate actions")

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            logger.error(f"Error processing {ticker}: {e}")

        return result

    def populate_multiple(self, tickers: List[str], **kwargs) -> List[dict]:
        """
        Populate data for multiple tickers with progress tracking.
        """
        results = []
        total = len(tickers)

        logger.info("=" * 60)
        logger.info(f"Starting population for {total} tickers")
        logger.info(f"Options: daily={kwargs.get('fetch_daily', True)}, "
                   f"intraday={kwargs.get('fetch_intraday', False)}, "
                   f"actions={kwargs.get('fetch_actions', True)}")
        logger.info("=" * 60)

        for i, ticker in enumerate(tickers, 1):
            logger.info(f"[{i}/{total}] Processing {ticker}...")
            result = self.populate_ticker(ticker, **kwargs)
            results.append(result)

            # Rate limiting to avoid Yahoo blocks
            time.sleep(0.5)

            # Update stats
            self.stats['tickers_processed'] += 1
            if result['status'] == 'error':
                self.stats['tickers_failed'] += 1
            self.stats['daily_records'] += result['daily_records']
            self.stats['intraday_records'] += result['intraday_records']
            self.stats['actions_records'] += result['actions_records']

        self._print_summary(results)
        return results

    def _print_summary(self, results: List[dict]):
        """Print population summary."""
        logger.info("=" * 60)
        logger.info("POPULATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Tickers processed: {self.stats['tickers_processed']}")
        logger.info(f"Tickers failed: {self.stats['tickers_failed']}")
        logger.info(f"Daily records: {self.stats['daily_records']:,}")
        logger.info(f"Intraday records: {self.stats['intraday_records']:,}")
        logger.info(f"Corporate actions: {self.stats['actions_records']:,}")

        if self.stats['tickers_failed'] > 0:
            logger.info("\nFailed tickers:")
            for r in results:
                if r['status'] == 'error':
                    logger.info(f"  - {r['ticker']}: {r['error']}")

    def estimate_storage(self, tickers: List[str], fetch_daily: bool = True,
                        fetch_intraday: bool = False) -> dict:
        """Estimate storage requirements without fetching data."""
        num_tickers = len(tickers)

        # Assumptions
        trading_days_per_year = 252
        years_of_history = 64  # 1960-2024
        bytes_per_daily_row = 100
        bytes_per_intraday_row = 80
        minutes_per_day = 390  # 6.5 hours
        intraday_retention_days = 30

        estimates = {
            'num_tickers': num_tickers,
            'daily_rows': 0,
            'daily_bytes': 0,
            'intraday_rows': 0,
            'intraday_bytes': 0,
        }

        if fetch_daily:
            estimates['daily_rows'] = num_tickers * trading_days_per_year * years_of_history
            estimates['daily_bytes'] = estimates['daily_rows'] * bytes_per_daily_row

        if fetch_intraday:
            estimates['intraday_rows'] = num_tickers * minutes_per_day * intraday_retention_days
            estimates['intraday_bytes'] = estimates['intraday_rows'] * bytes_per_intraday_row

        estimates['total_bytes'] = estimates['daily_bytes'] + estimates['intraday_bytes']
        estimates['total_gb'] = estimates['total_bytes'] / (1024**3)
        estimates['compressed_gb'] = estimates['total_gb'] * 0.4  # ~60% compression

        return estimates


def get_sp500_tickers_live() -> List[str]:
    """Fetch current S&P 500 tickers from Wikipedia."""
    try:
        import requests
        from bs4 import BeautifulSoup

        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'id': 'constituents'})

        tickers = []
        for row in table.find_all('tr')[1:]:
            cols = row.find_all('td')
            if cols:
                ticker = cols[0].text.strip()
                # Clean up ticker symbols
                ticker = ticker.replace('.', '-')  # BRK.B -> BRK-B for Yahoo
                tickers.append(ticker)

        return tickers

    except Exception as e:
        logger.warning(f"Failed to fetch S&P 500 from Wikipedia: {e}")
        logger.info("Using hardcoded list")
        return SP500_TICKERS


def main():
    parser = argparse.ArgumentParser(
        description='Populate historical stock data into TimescaleDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Ticker selection
    ticker_group = parser.add_mutually_exclusive_group()
    ticker_group.add_argument('--tickers', '-t', type=str,
                             help='Comma-separated list of tickers')
    ticker_group.add_argument('--sp500', action='store_true',
                             help='Populate all S&P 500 stocks')
    ticker_group.add_argument('--djia', action='store_true',
                             help='Populate all DJIA stocks')
    ticker_group.add_argument('--both-indices', action='store_true',
                             help='Populate both S&P 500 and DJIA')

    # Data types
    parser.add_argument('--daily', action='store_true',
                       help='Fetch daily OHLCV data (all history)')
    parser.add_argument('--intraday', action='store_true',
                       help='Fetch intraday data (1min: 7d, 1hour: 60d)')
    parser.add_argument('--actions', action='store_true',
                       help='Fetch dividends and splits')
    parser.add_argument('--metadata', action='store_true',
                       help='Fetch company metadata')
    parser.add_argument('--all', action='store_true',
                       help='Fetch all data types')

    # Options
    parser.add_argument('--start-date', type=str, default='1960-01-01',
                       help='Start date for daily data (default: 1960-01-01)')
    parser.add_argument('--estimate-only', action='store_true',
                       help='Only estimate storage, don\'t fetch data')

    # Database
    parser.add_argument('--host', type=str, default=DB_CONFIG['host'])
    parser.add_argument('--port', type=int, default=DB_CONFIG['port'])
    parser.add_argument('--database', type=str, default=DB_CONFIG['database'])
    parser.add_argument('--user', type=str, default=DB_CONFIG['user'])
    parser.add_argument('--password', type=str, default=DB_CONFIG['password'])

    args = parser.parse_args()

    # Determine tickers
    if args.sp500:
        tickers = get_sp500_tickers_live()
        logger.info(f"Using {len(tickers)} S&P 500 tickers")
    elif args.djia:
        tickers = DJIA_TICKERS
        logger.info(f"Using {len(tickers)} DJIA tickers")
    elif args.both_indices:
        sp500 = get_sp500_tickers_live()
        tickers = list(set(sp500 + DJIA_TICKERS))
        logger.info(f"Using {len(tickers)} unique tickers from S&P 500 and DJIA")
    elif args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        tickers = DJIA_TICKERS[:5]  # Default to first 5 DJIA for testing
        logger.info(f"Using default test tickers: {tickers}")

    # Determine what to fetch
    if args.all:
        fetch_daily = fetch_intraday = fetch_actions = fetch_metadata = True
    else:
        fetch_daily = args.daily or (not args.intraday and not args.actions and not args.metadata)
        fetch_intraday = args.intraday
        fetch_actions = args.actions or args.all
        fetch_metadata = args.metadata or args.all

    # Database config
    db_config = {
        'host': args.host,
        'port': args.port,
        'database': args.database,
        'user': args.user,
        'password': args.password,
    }

    # Create populator
    populator = HistoricalDataPopulator(db_config)

    # Estimate only mode
    if args.estimate_only:
        estimates = populator.estimate_storage(tickers, fetch_daily, fetch_intraday)
        print("\n" + "=" * 60)
        print("STORAGE ESTIMATES")
        print("=" * 60)
        print(f"Tickers: {estimates['num_tickers']}")
        print(f"Daily rows: {estimates['daily_rows']:,}")
        print(f"Intraday rows: {estimates['intraday_rows']:,}")
        print(f"Total uncompressed: {estimates['total_gb']:.2f} GB")
        print(f"Estimated compressed: {estimates['compressed_gb']:.2f} GB")
        return

    # Connect and populate
    if not populator.connect():
        sys.exit(1)

    try:
        # Insert index constituents
        if args.sp500 or args.both_indices:
            populator.insert_index_constituents('SPY', get_sp500_tickers_live())
        if args.djia or args.both_indices:
            populator.insert_index_constituents('DIA', DJIA_TICKERS)

        # Populate data
        populator.populate_multiple(
            tickers,
            fetch_daily=fetch_daily,
            fetch_intraday=fetch_intraday,
            fetch_actions=fetch_actions,
            fetch_metadata=fetch_metadata,
            daily_start=args.start_date
        )

    finally:
        populator.close()


if __name__ == '__main__':
    main()
