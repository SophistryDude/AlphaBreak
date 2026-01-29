"""
Database Connection Utilities

Provides connection pooling and utilities for interacting with PostgreSQL time series database.
"""

import os
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages PostgreSQL connection pool for time series data."""

    def __init__(self):
        self.connection_pool = None
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize connection pool."""
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=os.environ.get('TIMESERIES_DB_HOST', 'postgres-timeseries-service'),
                port=int(os.environ.get('TIMESERIES_DB_PORT', 5432)),
                database=os.environ.get('TIMESERIES_DB_NAME', 'trading_data'),
                user=os.environ.get('TIMESERIES_DB_USER', 'trading'),
                password=os.environ.get('TIMESERIES_DB_PASSWORD', 'change-this-timeseries-password'),
                sslmode=os.environ.get('TIMESERIES_DB_SSLMODE', 'prefer')
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        conn = None
        try:
            conn = self.connection_pool.getconn()
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    @contextmanager
    def get_cursor(self, commit=False):
        """Get a cursor with automatic connection management."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
                if commit:
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Database cursor error: {e}")
                raise
            finally:
                cursor.close()

    def execute_query(self, query, params=None, fetch=True):
        """Execute a query and optionally fetch results."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if fetch:
                return cursor.fetchall()
            return None

    def execute_many(self, query, data):
        """Execute query with multiple parameter sets."""
        with self.get_cursor(commit=True) as cursor:
            cursor.executemany(query, data)

    def close_pool(self):
        """Close all connections in the pool."""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Database connection pool closed")


# Global database manager instance
db_manager = DatabaseManager()


def store_stock_price(ticker, timestamp, open_price, high, low, close, volume, adjusted_close):
    """Store a single stock price record."""
    query = """
        INSERT INTO stock_prices
        (ticker, timestamp, open, high, low, close, volume, adjusted_close)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, timestamp) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            adjusted_close = EXCLUDED.adjusted_close
    """
    with db_manager.get_cursor(commit=True) as cursor:
        cursor.execute(query, (ticker, timestamp, open_price, high, low, close, volume, adjusted_close))


def get_recent_prices(ticker, hours=24):
    """Get recent price data for a ticker."""
    query = """
        SELECT timestamp, open, high, low, close, volume
        FROM stock_prices
        WHERE ticker = %s
          AND timestamp > NOW() - INTERVAL '%s hours'
        ORDER BY timestamp DESC
    """
    return db_manager.execute_query(query, (ticker, hours))


def store_indicator(ticker, timestamp, indicator_name, indicator_value):
    """Store a technical indicator value."""
    query = """
        INSERT INTO technical_indicators
        (ticker, timestamp, indicator_name, indicator_value)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (ticker, timestamp, indicator_name) DO UPDATE SET
            indicator_value = EXCLUDED.indicator_value
    """
    with db_manager.get_cursor(commit=True) as cursor:
        cursor.execute(query, (ticker, timestamp, indicator_name, indicator_value))


def get_indicator_values(ticker, indicator_name, hours=24):
    """Get recent indicator values."""
    query = """
        SELECT timestamp, indicator_value
        FROM technical_indicators
        WHERE ticker = %s
          AND indicator_name = %s
          AND timestamp > NOW() - INTERVAL '%s hours'
        ORDER BY timestamp DESC
    """
    return db_manager.execute_query(query, (ticker, indicator_name, hours))


def store_prediction(ticker, timestamp, prediction_type, predicted_value,
                    confidence, model_version, features_used, metadata):
    """Store a model prediction."""
    query = """
        INSERT INTO predictions_log
        (ticker, prediction_timestamp, prediction_type, predicted_value,
         confidence, model_version, features_used, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    with db_manager.get_cursor(commit=True) as cursor:
        cursor.execute(query, (
            ticker, timestamp, prediction_type, predicted_value,
            confidence, model_version,
            psycopg2.extras.Json(features_used),
            psycopg2.extras.Json(metadata)
        ))
        return cursor.fetchone()[0]


def update_prediction_actual(prediction_id, actual_value, actual_timestamp):
    """Update prediction with actual outcome."""
    query = """
        UPDATE predictions_log
        SET actual_value = %s,
            actual_timestamp = %s
        WHERE id = %s
    """
    with db_manager.get_cursor(commit=True) as cursor:
        cursor.execute(query, (actual_value, actual_timestamp, prediction_id))


def get_prediction_accuracy(model_version, days=30):
    """Calculate prediction accuracy for a model version."""
    query = """
        SELECT
            COUNT(*) as total_predictions,
            AVG(ABS(predicted_value - actual_value)) as mae,
            STDDEV(predicted_value - actual_value) as std_error,
            AVG(confidence) as avg_confidence
        FROM predictions_log
        WHERE model_version = %s
          AND actual_value IS NOT NULL
          AND prediction_timestamp > NOW() - INTERVAL '%s days'
    """
    result = db_manager.execute_query(query, (model_version, days))
    if result and result[0]:
        return {
            'total_predictions': result[0][0],
            'mae': float(result[0][1]) if result[0][1] else None,
            'std_error': float(result[0][2]) if result[0][2] else None,
            'avg_confidence': float(result[0][3]) if result[0][3] else None
        }
    return None


def store_backtest_result(backtest_name, ticker, start_date, end_date,
                         initial_capital, final_capital, total_return,
                         sharpe_ratio, max_drawdown, win_rate, total_trades,
                         winning_trades, losing_trades, avg_profit, avg_loss, metadata):
    """Store backtest results."""
    query = """
        INSERT INTO backtest_results
        (backtest_name, ticker, start_date, end_date, initial_capital,
         final_capital, total_return, sharpe_ratio, max_drawdown, win_rate,
         total_trades, winning_trades, losing_trades, avg_profit, avg_loss, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    with db_manager.get_cursor(commit=True) as cursor:
        cursor.execute(query, (
            backtest_name, ticker, start_date, end_date, initial_capital,
            final_capital, total_return, sharpe_ratio, max_drawdown, win_rate,
            total_trades, winning_trades, losing_trades, avg_profit, avg_loss,
            psycopg2.extras.Json(metadata)
        ))
        return cursor.fetchone()[0]


def get_best_performing_strategies(days=90, limit=10):
    """Get best performing backtest strategies."""
    query = """
        SELECT
            backtest_name,
            ticker,
            AVG(total_return) as avg_return,
            AVG(sharpe_ratio) as avg_sharpe,
            AVG(win_rate) as avg_win_rate,
            SUM(total_trades) as total_trades
        FROM backtest_results
        WHERE created_at > NOW() - INTERVAL '%s days'
        GROUP BY backtest_name, ticker
        ORDER BY avg_return DESC
        LIMIT %s
    """
    return db_manager.execute_query(query, (days, limit))


def store_indicator_accuracy(ticker, timestamp, indicator_name, lookback_window,
                            lookahead_window, accuracy, precision_score,
                            recall_score, f1_score, samples_analyzed, metadata):
    """Store indicator accuracy metrics."""
    query = """
        INSERT INTO indicator_accuracy
        (ticker, timestamp, indicator_name, lookback_window, lookahead_window,
         accuracy, precision_score, recall_score, f1_score, samples_analyzed, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with db_manager.get_cursor(commit=True) as cursor:
        cursor.execute(query, (
            ticker, timestamp, indicator_name, lookback_window, lookahead_window,
            accuracy, precision_score, recall_score, f1_score, samples_analyzed,
            psycopg2.extras.Json(metadata)
        ))


def get_top_indicators(ticker, min_accuracy=0.7, days=30):
    """Get top performing indicators for a ticker."""
    query = """
        SELECT
            indicator_name,
            AVG(accuracy) as avg_accuracy,
            AVG(f1_score) as avg_f1,
            COUNT(*) as evaluations
        FROM indicator_accuracy
        WHERE ticker = %s
          AND timestamp > NOW() - INTERVAL '%s days'
          AND accuracy >= %s
        GROUP BY indicator_name
        ORDER BY avg_accuracy DESC
    """
    return db_manager.execute_query(query, (ticker, days, min_accuracy))


def get_stock_data_by_date_range(ticker, start_date, end_date):
    """
    Get stock price data for a ticker within a date range.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        List of tuples: (timestamp, open, high, low, close, volume, adjusted_close)
    """
    query = """
        SELECT timestamp, open, high, low, close, volume, adjusted_close
        FROM stock_prices
        WHERE ticker = %s
          AND timestamp >= %s::date
          AND timestamp <= %s::date
        ORDER BY timestamp ASC
    """
    return db_manager.execute_query(query, (ticker, start_date, end_date))


def get_stock_data_as_dataframe(ticker, start_date, end_date):
    """
    Get stock price data as a pandas DataFrame.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with Date, Open, High, Low, Close, Volume, Adj Close columns
    """
    import pandas as pd

    data = get_stock_data_by_date_range(ticker, start_date, end_date)

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Adj Close'])

    # Convert numeric columns
    for col in ['Open', 'High', 'Low', 'Close', 'Adj Close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce').astype('Int64')

    return df


def check_data_availability(ticker, start_date, end_date):
    """
    Check if data is available for a ticker in the specified date range.

    Returns:
        dict with 'available' (bool), 'record_count', 'first_date', 'last_date'
    """
    query = """
        SELECT
            COUNT(*) as record_count,
            MIN(timestamp)::date as first_date,
            MAX(timestamp)::date as last_date
        FROM stock_prices
        WHERE ticker = %s
          AND timestamp >= %s::date
          AND timestamp <= %s::date
    """
    result = db_manager.execute_query(query, (ticker, start_date, end_date))

    if result and result[0]:
        count, first, last = result[0]
        return {
            'available': count > 0,
            'record_count': count,
            'first_date': str(first) if first else None,
            'last_date': str(last) if last else None
        }
    return {'available': False, 'record_count': 0, 'first_date': None, 'last_date': None}


def get_all_tickers():
    """Get list of all tickers in the database."""
    query = """
        SELECT DISTINCT ticker
        FROM stock_prices
        ORDER BY ticker
    """
    result = db_manager.execute_query(query)
    return [row[0] for row in result] if result else []


def get_ticker_summary():
    """Get summary statistics for all tickers in the database."""
    query = """
        SELECT
            ticker,
            COUNT(*) as record_count,
            MIN(timestamp)::date as first_date,
            MAX(timestamp)::date as last_date
        FROM stock_prices
        GROUP BY ticker
        ORDER BY ticker
    """
    result = db_manager.execute_query(query)

    if not result:
        return []

    return [
        {
            'ticker': row[0],
            'record_count': row[1],
            'first_date': str(row[2]) if row[2] else None,
            'last_date': str(row[3]) if row[3] else None
        }
        for row in result
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Earnings cache helpers
# ──────────────────────────────────────────────────────────────────────────────

def ensure_earnings_tables():
    """Create earnings cache tables if they don't exist."""
    create_sql = """
    CREATE TABLE IF NOT EXISTS earnings_calendar (
        id              SERIAL PRIMARY KEY,
        ticker          VARCHAR(10)  NOT NULL,
        earnings_date   DATE         NOT NULL,
        eps_estimate    NUMERIC(10,2),
        eps_actual      NUMERIC(10,2),
        surprise_pct    NUMERIC(10,2),
        is_upcoming     BOOLEAN      DEFAULT TRUE,
        fetched_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_earnings_ticker_date UNIQUE (ticker, earnings_date)
    );

    CREATE TABLE IF NOT EXISTS earnings_cache_meta (
        ticker          VARCHAR(10)  PRIMARY KEY,
        last_fetched    TIMESTAMP    NOT NULL DEFAULT NOW()
    );
    """
    try:
        with db_manager.get_cursor(commit=True) as cursor:
            cursor.execute(create_sql)
        logger.info("Earnings cache tables ensured")
    except Exception as e:
        logger.warning(f"Could not create earnings tables: {e}")


def get_cached_earnings(ticker, stale_hours=6):
    """Fetch cached earnings for a ticker if data is fresh enough.

    Returns list of dicts or None if cache is stale/missing.
    """
    meta_query = """
        SELECT last_fetched FROM earnings_cache_meta
        WHERE ticker = %s AND last_fetched > NOW() - INTERVAL '%s hours'
    """
    try:
        rows = db_manager.execute_query(meta_query, (ticker, stale_hours))
        if not rows:
            return None

        data_query = """
            SELECT earnings_date, eps_estimate, eps_actual, surprise_pct, is_upcoming
            FROM earnings_calendar
            WHERE ticker = %s
            ORDER BY earnings_date ASC
        """
        rows = db_manager.execute_query(data_query, (ticker,))
        if not rows:
            return None

        return [
            {
                'date': str(row[0]),
                'eps_estimate': float(row[1]) if row[1] is not None else None,
                'eps_actual': float(row[2]) if row[2] is not None else None,
                'surprise_pct': float(row[3]) if row[3] is not None else None,
                'is_upcoming': bool(row[4]),
            }
            for row in rows
        ]
    except Exception as e:
        logger.debug(f"Earnings cache read failed for {ticker}: {e}")
        return None


def get_all_cached_earnings(stale_hours=6):
    """Fetch all cached earnings where the ticker data is still fresh.

    Returns dict keyed by ticker -> list of earnings entries.
    """
    query = """
        SELECT ec.ticker, ec.earnings_date, ec.eps_estimate, ec.eps_actual,
               ec.surprise_pct, ec.is_upcoming
        FROM earnings_calendar ec
        JOIN earnings_cache_meta ecm ON ec.ticker = ecm.ticker
        WHERE ecm.last_fetched > NOW() - INTERVAL '%s hours'
        ORDER BY ec.ticker, ec.earnings_date ASC
    """
    try:
        rows = db_manager.execute_query(query, (stale_hours,))
        if not rows:
            return {}

        result = {}
        for row in rows:
            ticker = row[0]
            if ticker not in result:
                result[ticker] = []
            result[ticker].append({
                'date': str(row[1]),
                'eps_estimate': float(row[2]) if row[2] is not None else None,
                'eps_actual': float(row[3]) if row[3] is not None else None,
                'surprise_pct': float(row[4]) if row[4] is not None else None,
                'is_upcoming': bool(row[5]),
            })
        return result
    except Exception as e:
        logger.debug(f"Bulk earnings cache read failed: {e}")
        return {}


def store_ticker_earnings(ticker, entries):
    """Cache earnings entries for a ticker. Upserts rows + updates meta timestamp.

    Args:
        ticker: Stock ticker symbol
        entries: List of dicts with keys: date, eps_estimate, eps_actual, surprise_pct, is_upcoming
    """
    upsert_query = """
        INSERT INTO earnings_calendar (ticker, earnings_date, eps_estimate, eps_actual, surprise_pct, is_upcoming, fetched_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (ticker, earnings_date) DO UPDATE SET
            eps_estimate  = EXCLUDED.eps_estimate,
            eps_actual    = EXCLUDED.eps_actual,
            surprise_pct  = EXCLUDED.surprise_pct,
            is_upcoming   = EXCLUDED.is_upcoming,
            fetched_at    = NOW()
    """
    meta_query = """
        INSERT INTO earnings_cache_meta (ticker, last_fetched)
        VALUES (%s, NOW())
        ON CONFLICT (ticker) DO UPDATE SET last_fetched = NOW()
    """
    try:
        with db_manager.get_cursor(commit=True) as cursor:
            for entry in entries:
                cursor.execute(upsert_query, (
                    ticker,
                    entry['date'],
                    entry.get('eps_estimate'),
                    entry.get('eps_actual'),
                    entry.get('surprise_pct'),
                    entry.get('is_upcoming', True),
                ))
            cursor.execute(meta_query, (ticker,))
    except Exception as e:
        logger.warning(f"Failed to cache earnings for {ticker}: {e}")
