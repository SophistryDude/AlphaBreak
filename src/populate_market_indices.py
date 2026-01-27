"""
Populate market indices and macro ETFs data for prediction model features.

This script fetches historical data for:
- S&P 500 Index (^GSPC)
- Dow Jones Industrial Average (^DJI)
- CBOE Volatility Index (^VIX)
- Russell 2000 Index (^RUT)
- Invesco QQQ Trust / Nasdaq-100 ETF (QQQ)
- E-mini S&P 500 Futures (ES=F)
- Inverse ETFs: SH, PSQ, DOG
- Volatility ETF: VXX

Data is stored in:
- market_indices (daily data)
- market_indices_intraday (5min, 1hour data via Polygon)
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_values
import os
from typing import List, Dict, Optional
import time

# Database connection parameters
DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': int(os.environ.get('POSTGRES_PORT', 5433)),
    'database': os.environ.get('POSTGRES_DB', 'trading_data'),
    'user': os.environ.get('POSTGRES_USER', 'trading'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'trading123')
}

# Market indices and ETFs to track
MARKET_SYMBOLS = [
    '^GSPC',   # S&P 500 Index
    '^DJI',    # Dow Jones Industrial Average
    '^VIX',    # CBOE Volatility Index
    '^RUT',    # Russell 2000 Index
    'QQQ',     # Invesco QQQ Trust (Nasdaq-100 ETF)
    'ES=F',    # E-mini S&P 500 Futures
    'SH',      # ProShares Short S&P 500
    'PSQ',     # ProShares Short QQQ
    'DOG',     # ProShares Short Dow 30
    'VXX',     # iPath Series B S&P 500 VIX Short-Term Futures ETN
]


def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(**DB_CONFIG)


def fetch_daily_data(symbol: str, start_date: str, end_date: str = None) -> pd.DataFrame:
    """
    Fetch daily OHLCV data from yfinance.

    Args:
        symbol: Ticker symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD), defaults to today

    Returns:
        DataFrame with OHLCV data
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date, interval='1d')

        if df.empty:
            print(f"  Warning: No data returned for {symbol}")
            return pd.DataFrame()

        # Rename columns to match our schema
        df = df.reset_index()
        df = df.rename(columns={
            'Date': 'timestamp',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })

        # Add adjusted close if available
        if 'Adj Close' in df.columns:
            df['adjusted_close'] = df['Adj Close']
        else:
            df['adjusted_close'] = df['close']

        df['symbol'] = symbol

        # Select only needed columns
        columns = ['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'adjusted_close']
        df = df[[c for c in columns if c in df.columns]]

        # Ensure timestamp is timezone-aware
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize('America/New_York')

        return df

    except Exception as e:
        print(f"  Error fetching {symbol}: {e}")
        return pd.DataFrame()


def insert_daily_data(df: pd.DataFrame, conn) -> int:
    """
    Insert daily data into market_indices table.

    Args:
        df: DataFrame with market data
        conn: Database connection

    Returns:
        Number of rows inserted
    """
    if df.empty:
        return 0

    cursor = conn.cursor()

    # Prepare data for insertion
    columns = ['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'adjusted_close']
    available_cols = [c for c in columns if c in df.columns]

    values = df[available_cols].values.tolist()

    # Use upsert to handle duplicates
    insert_query = f"""
        INSERT INTO market_indices ({', '.join(available_cols)})
        VALUES %s
        ON CONFLICT (symbol, timestamp) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            adjusted_close = EXCLUDED.adjusted_close
    """

    try:
        execute_values(cursor, insert_query, values, page_size=1000)
        conn.commit()
        return len(values)
    except Exception as e:
        conn.rollback()
        print(f"  Error inserting data: {e}")
        return 0
    finally:
        cursor.close()


def get_existing_date_range(symbol: str, conn) -> tuple:
    """Get the date range of existing data for a symbol."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MIN(timestamp), MAX(timestamp)
        FROM market_indices
        WHERE symbol = %s
    """, (symbol,))
    result = cursor.fetchone()
    cursor.close()
    return result


def populate_daily_data(
    symbols: List[str] = None,
    start_date: str = '2020-01-01',
    end_date: str = None,
    update_existing: bool = True
) -> Dict[str, int]:
    """
    Populate daily market indices data.

    Args:
        symbols: List of symbols to fetch (defaults to MARKET_SYMBOLS)
        start_date: Start date for historical data
        end_date: End date (defaults to today)
        update_existing: If True, update data for symbols that already exist

    Returns:
        Dictionary mapping symbols to rows inserted
    """
    if symbols is None:
        symbols = MARKET_SYMBOLS

    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    conn = get_db_connection()
    results = {}

    print(f"\n{'='*60}")
    print("POPULATING MARKET INDICES - DAILY DATA")
    print(f"{'='*60}")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Date range: {start_date} to {end_date}")
    print()

    for symbol in symbols:
        print(f"Processing {symbol}...")

        # Check existing data
        min_date, max_date = get_existing_date_range(symbol, conn)

        if min_date and max_date and not update_existing:
            print(f"  Skipping - data exists from {min_date} to {max_date}")
            results[symbol] = 0
            continue

        # Determine fetch range
        fetch_start = start_date
        if max_date and update_existing:
            # Only fetch new data
            fetch_start = (max_date - timedelta(days=5)).strftime('%Y-%m-%d')
            print(f"  Updating from {fetch_start} (existing data: {min_date} to {max_date})")

        # Fetch and insert data
        df = fetch_daily_data(symbol, fetch_start, end_date)
        if not df.empty:
            rows = insert_daily_data(df, conn)
            results[symbol] = rows
            print(f"  Inserted/updated {rows} rows")
        else:
            results[symbol] = 0

        # Small delay to avoid rate limiting
        time.sleep(0.5)

    conn.close()

    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    total = sum(results.values())
    for symbol, count in results.items():
        print(f"  {symbol}: {count} rows")
    print(f"\nTotal rows: {total}")

    return results


def populate_intraday_data_polygon(
    symbols: List[str] = None,
    interval: str = '1hour',
    days_back: int = 30
) -> Dict[str, int]:
    """
    Populate intraday market indices data using Polygon.io.

    Args:
        symbols: List of symbols to fetch
        interval: '5min' or '1hour'
        days_back: Number of days of historical data

    Returns:
        Dictionary mapping symbols to rows inserted
    """
    try:
        from polygon_data_fetcher import PolygonDataFetcher
    except ImportError:
        print("Polygon data fetcher not available. Skipping intraday data.")
        return {}

    if symbols is None:
        # Only fetch intraday for ETFs and futures (indices don't have intraday on Polygon)
        symbols = ['SH', 'PSQ', 'DOG', 'VXX']

    api_key = os.environ.get('POLYGON_API_KEY')
    if not api_key:
        print("POLYGON_API_KEY not set. Skipping intraday data.")
        return {}

    fetcher = PolygonDataFetcher(api_key)
    conn = get_db_connection()
    results = {}

    print(f"\n{'='*60}")
    print(f"POPULATING MARKET INDICES - {interval.upper()} DATA")
    print(f"{'='*60}")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    # Map interval to Polygon timespan
    timespan_map = {'5min': 'minute', '1hour': 'hour'}
    multiplier_map = {'5min': 5, '1hour': 1}

    for symbol in symbols:
        print(f"Processing {symbol}...")

        try:
            df = fetcher.get_aggregates(
                symbol,
                multiplier=multiplier_map.get(interval, 1),
                timespan=timespan_map.get(interval, 'hour'),
                from_date=start_date.strftime('%Y-%m-%d'),
                to_date=end_date.strftime('%Y-%m-%d')
            )

            if df is not None and not df.empty:
                # Add interval_type and symbol columns
                df['interval_type'] = interval
                df['symbol'] = symbol

                # Insert into intraday table
                cursor = conn.cursor()
                columns = ['symbol', 'timestamp', 'interval_type', 'open', 'high', 'low', 'close', 'volume']
                values = df[columns].values.tolist()

                insert_query = f"""
                    INSERT INTO market_indices_intraday ({', '.join(columns)})
                    VALUES %s
                    ON CONFLICT (symbol, timestamp, interval_type) DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                """

                execute_values(cursor, insert_query, values, page_size=1000)
                conn.commit()
                cursor.close()

                results[symbol] = len(values)
                print(f"  Inserted {len(values)} rows")
            else:
                results[symbol] = 0
                print(f"  No data returned")

        except Exception as e:
            print(f"  Error: {e}")
            results[symbol] = 0

        time.sleep(0.5)

    conn.close()
    return results


def get_market_index_data(
    symbol: str,
    start_date: str,
    end_date: str = None,
    interval: str = 'daily'
) -> pd.DataFrame:
    """
    Retrieve market index data from database.

    Args:
        symbol: Market index symbol
        start_date: Start date
        end_date: End date (defaults to today)
        interval: 'daily', '1hour', or '5min'

    Returns:
        DataFrame with market data
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    conn = get_db_connection()

    if interval == 'daily':
        query = """
            SELECT timestamp, open, high, low, close, volume, adjusted_close
            FROM market_indices
            WHERE symbol = %s
            AND timestamp >= %s
            AND timestamp <= %s
            ORDER BY timestamp
        """
        df = pd.read_sql(query, conn, params=(symbol, start_date, end_date))
    else:
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM market_indices_intraday
            WHERE symbol = %s
            AND interval_type = %s
            AND timestamp >= %s
            AND timestamp <= %s
            ORDER BY timestamp
        """
        df = pd.read_sql(query, conn, params=(symbol, interval, start_date, end_date))

    conn.close()
    return df


def calculate_market_features(
    stock_timestamp: datetime,
    lookback_periods: int = 20
) -> Dict[str, float]:
    """
    Calculate market features at a specific timestamp for use in predictions.

    Features include:
    - S&P 500 return and trend
    - VIX level and change
    - Futures premium/discount
    - Inverse ETF flows (as sentiment indicator)

    Args:
        stock_timestamp: The timestamp to calculate features for
        lookback_periods: Number of periods for rolling calculations

    Returns:
        Dictionary of market features
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    features = {}

    # Get S&P 500 data
    cursor.execute("""
        SELECT close, volume
        FROM market_indices
        WHERE symbol = '^GSPC'
        AND timestamp <= %s
        ORDER BY timestamp DESC
        LIMIT %s
    """, (stock_timestamp, lookback_periods + 1))

    sp500_data = cursor.fetchall()
    if len(sp500_data) >= 2:
        sp500_closes = [row[0] for row in sp500_data]
        features['sp500_return_1d'] = (sp500_closes[0] - sp500_closes[1]) / sp500_closes[1] if sp500_closes[1] else 0
        if len(sp500_closes) >= lookback_periods:
            features['sp500_return_20d'] = (sp500_closes[0] - sp500_closes[-1]) / sp500_closes[-1] if sp500_closes[-1] else 0
            features['sp500_trend'] = 1 if features['sp500_return_20d'] > 0 else -1

    # Get VIX data
    cursor.execute("""
        SELECT close
        FROM market_indices
        WHERE symbol = '^VIX'
        AND timestamp <= %s
        ORDER BY timestamp DESC
        LIMIT %s
    """, (stock_timestamp, lookback_periods + 1))

    vix_data = cursor.fetchall()
    if len(vix_data) >= 2:
        vix_closes = [row[0] for row in vix_data]
        features['vix_level'] = float(vix_closes[0]) if vix_closes[0] else 0
        features['vix_change_1d'] = (vix_closes[0] - vix_closes[1]) / vix_closes[1] if vix_closes[1] else 0
        # High VIX (>25) indicates fear, low VIX (<15) indicates complacency
        features['vix_regime'] = 1 if features['vix_level'] > 25 else (-1 if features['vix_level'] < 15 else 0)

    # Get futures premium/discount (ES futures vs S&P 500)
    cursor.execute("""
        SELECT m1.close as futures, m2.close as index
        FROM market_indices m1
        JOIN market_indices m2 ON DATE(m1.timestamp) = DATE(m2.timestamp)
        WHERE m1.symbol = 'ES=F'
        AND m2.symbol = '^GSPC'
        AND m1.timestamp <= %s
        ORDER BY m1.timestamp DESC
        LIMIT 1
    """, (stock_timestamp,))

    futures_data = cursor.fetchone()
    if futures_data and futures_data[0] and futures_data[1]:
        features['futures_premium'] = (futures_data[0] - futures_data[1]) / futures_data[1]

    # Get inverse ETF volumes as sentiment indicator
    cursor.execute("""
        SELECT symbol, volume
        FROM market_indices
        WHERE symbol IN ('SH', 'PSQ', 'DOG')
        AND timestamp <= %s
        ORDER BY timestamp DESC
        LIMIT 3
    """, (stock_timestamp,))

    inverse_data = cursor.fetchall()
    if inverse_data:
        total_inverse_volume = sum(row[1] for row in inverse_data if row[1])
        features['inverse_etf_volume'] = total_inverse_volume

    cursor.close()
    conn.close()

    return features


# ════════════════════════════════════════════════════════════════════════════
# BATCH MARKET DATA LOADING FOR TREND BREAK ANALYSIS
# ════════════════════════════════════════════════════════════════════════════

def batch_load_market_data(
    start_date: str,
    end_date: str
) -> Dict[str, pd.DataFrame]:
    """
    Load daily OHLCV data for all market symbols from database in one batch query.

    Returns a dict keyed by symbol, each value a DataFrame indexed by date
    with columns: Open, High, Low, Close, Volume (capitalized for pandas_ta).

    This avoids per-break DB queries when processing 200K+ trend breaks.
    """
    conn = get_db_connection()

    query = """
        SELECT symbol, timestamp, open, high, low, close, volume
        FROM market_indices
        WHERE timestamp >= %s AND timestamp <= %s
        ORDER BY symbol, timestamp
    """
    df = pd.read_sql(query, conn, params=(start_date, end_date))
    conn.close()

    if df.empty:
        print("Warning: No market index data found in database.")
        return {}

    # Normalize timestamps to date-only for alignment with daily stock data
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.normalize()

    market_data = {}
    for symbol, group in df.groupby('symbol'):
        mdf = group.set_index('timestamp').sort_index()
        mdf = mdf.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low',
            'close': 'Close', 'volume': 'Volume'
        })
        mdf = mdf[['Open', 'High', 'Low', 'Close', 'Volume']]
        market_data[symbol] = mdf

    print(f"Loaded market data for {len(market_data)} symbols: {list(market_data.keys())}")
    for sym, mdf in market_data.items():
        print(f"  {sym}: {len(mdf)} rows ({mdf.index.min().date()} to {mdf.index.max().date()})")

    return market_data


def calculate_market_features_batch(
    market_data: Dict[str, pd.DataFrame],
    timestamps: pd.Series,
    lookback_periods: int = 20
) -> pd.DataFrame:
    """
    Vectorized calculation of market features for an array of break timestamps.

    Uses pd.merge_asof to align market data to break timestamps efficiently.

    Args:
        market_data: Dict from batch_load_market_data()
        timestamps: Series of break timestamps to calculate features for
        lookback_periods: Number of periods for rolling calculations

    Returns:
        DataFrame indexed by timestamp with market feature columns:
        sp500_return_1d, sp500_return_20d, sp500_trend, vix_level,
        vix_change_1d, vix_regime, futures_premium, inverse_etf_volume,
        vxx_level, vxx_change_1d
    """
    ts = pd.to_datetime(timestamps).sort_values().drop_duplicates()
    ts_df = pd.DataFrame({'timestamp': ts})

    features = pd.DataFrame(index=ts)

    # --- S&P 500 features ---
    if '^GSPC' in market_data:
        sp = market_data['^GSPC'][['Close', 'Volume']].copy()
        sp['sp500_return_1d'] = sp['Close'].pct_change(1)
        sp['sp500_return_20d'] = sp['Close'].pct_change(lookback_periods)
        sp['sp500_trend'] = np.where(sp['sp500_return_20d'] > 0, 1, -1)
        sp = sp.reset_index()

        merged = pd.merge_asof(
            ts_df, sp, on='timestamp', direction='backward'
        )
        merged = merged.set_index('timestamp')
        features['sp500_return_1d'] = merged['sp500_return_1d']
        features['sp500_return_20d'] = merged['sp500_return_20d']
        features['sp500_trend'] = merged['sp500_trend']

    # --- VIX features ---
    if '^VIX' in market_data:
        vix = market_data['^VIX'][['Close']].copy()
        vix['vix_level'] = vix['Close']
        vix['vix_change_1d'] = vix['Close'].pct_change(1)
        vix['vix_regime'] = np.where(
            vix['Close'] > 25, 1,
            np.where(vix['Close'] < 15, -1, 0)
        )
        vix = vix.reset_index()

        merged = pd.merge_asof(
            ts_df, vix, on='timestamp', direction='backward'
        )
        merged = merged.set_index('timestamp')
        features['vix_level'] = merged['vix_level']
        features['vix_change_1d'] = merged['vix_change_1d']
        features['vix_regime'] = merged['vix_regime']

    # --- Futures premium ---
    if 'ES=F' in market_data and '^GSPC' in market_data:
        futures = market_data['ES=F'][['Close']].rename(columns={'Close': 'futures_close'})
        sp_close = market_data['^GSPC'][['Close']].rename(columns={'Close': 'sp_close'})

        # Align futures and S&P by date
        combined = futures.join(sp_close, how='inner')
        combined['futures_premium'] = (combined['futures_close'] - combined['sp_close']) / combined['sp_close']
        combined = combined.reset_index()

        merged = pd.merge_asof(
            ts_df, combined[['timestamp', 'futures_premium']], on='timestamp', direction='backward'
        )
        merged = merged.set_index('timestamp')
        features['futures_premium'] = merged['futures_premium']

    # --- Inverse ETF total volume ---
    inverse_symbols = ['SH', 'PSQ', 'DOG']
    inverse_dfs = []
    for sym in inverse_symbols:
        if sym in market_data:
            vol = market_data[sym][['Volume']].rename(columns={'Volume': f'{sym}_volume'})
            inverse_dfs.append(vol)

    if inverse_dfs:
        inv_combined = inverse_dfs[0]
        for idf in inverse_dfs[1:]:
            inv_combined = inv_combined.join(idf, how='outer')
        inv_combined['inverse_etf_volume'] = inv_combined.sum(axis=1)
        inv_combined = inv_combined.reset_index()

        merged = pd.merge_asof(
            ts_df, inv_combined[['timestamp', 'inverse_etf_volume']], on='timestamp', direction='backward'
        )
        merged = merged.set_index('timestamp')
        features['inverse_etf_volume'] = merged['inverse_etf_volume']

    # --- VXX features ---
    if 'VXX' in market_data:
        vxx = market_data['VXX'][['Close']].copy()
        vxx['vxx_level'] = vxx['Close']
        vxx['vxx_change_1d'] = vxx['Close'].pct_change(1)
        vxx = vxx.reset_index()

        merged = pd.merge_asof(
            ts_df, vxx[['timestamp', 'vxx_level', 'vxx_change_1d']], on='timestamp', direction='backward'
        )
        merged = merged.set_index('timestamp')
        features['vxx_level'] = merged['vxx_level']
        features['vxx_change_1d'] = merged['vxx_change_1d']

    # Fill NaN with 0 for missing data
    features = features.fillna(0)
    return features


def calculate_market_instrument_indicators(
    market_data: Dict[str, pd.DataFrame]
) -> Dict[str, pd.DataFrame]:
    """
    Calculate technical indicators on market instruments themselves.

    Applies the same indicator calculations used for individual stocks
    to S&P 500, VIX, and ES=F futures, producing indicators like
    SP500_RSI, VIX_BB, FUTURES_MACD, etc.

    These become additional "indicators" to test against stock trend breaks,
    answering questions like: "Was the S&P RSI overbought before this stock reversed?"

    Args:
        market_data: Dict from batch_load_market_data()

    Returns:
        Dict keyed by prefixed instrument name (e.g., 'SP500', 'VIX', 'FUTURES'),
        each containing a DataFrame of indicator signals indexed by timestamp.
    """
    from .meta_learning_model import calculate_indicator_signals

    instrument_map = {
        '^GSPC': 'SP500',
        '^VIX': 'VIX',
        'ES=F': 'FUTURES',
    }

    results = {}

    for symbol, prefix in instrument_map.items():
        if symbol not in market_data:
            print(f"  Warning: {symbol} not in market data, skipping {prefix} indicators")
            continue

        mdf = market_data[symbol].copy()
        if len(mdf) < 50:
            print(f"  Warning: {symbol} has only {len(mdf)} rows, need 50+, skipping")
            continue

        try:
            indicator_df = calculate_indicator_signals(mdf)

            # Prefix all indicator columns with instrument name
            rename_map = {}
            skip_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in indicator_df.columns:
                if col not in skip_cols:
                    rename_map[col] = f'{prefix}_{col}'

            indicator_df = indicator_df.rename(columns=rename_map)
            # Drop raw OHLCV columns
            indicator_df = indicator_df.drop(columns=[c for c in skip_cols if c in indicator_df.columns])

            results[prefix] = indicator_df
            print(f"  Calculated {len(rename_map)} indicators for {prefix} ({symbol})")

        except Exception as e:
            print(f"  Error calculating indicators for {symbol}: {e}")

    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Populate market indices data')
    parser.add_argument('--start-date', default='2020-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', default=None, help='End date (YYYY-MM-DD)')
    parser.add_argument('--symbols', nargs='+', default=None, help='Symbols to fetch')
    parser.add_argument('--daily', action='store_true', default=True, help='Fetch daily data')
    parser.add_argument('--intraday', action='store_true', help='Fetch intraday data (requires Polygon)')
    parser.add_argument('--interval', default='1hour', choices=['5min', '1hour'], help='Intraday interval')

    args = parser.parse_args()

    if args.daily:
        populate_daily_data(
            symbols=args.symbols,
            start_date=args.start_date,
            end_date=args.end_date
        )

    if args.intraday:
        populate_intraday_data_polygon(
            symbols=args.symbols,
            interval=args.interval
        )
