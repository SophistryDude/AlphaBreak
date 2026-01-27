"""
Trend Break Detection Module
============================
Detects trend breaks (peaks and troughs) at multiple timeframes from historical price data.
Populates the trend_breaks, trend_ranges, and trend_break_features tables.

Usage:
    # Detect breaks for all tickers at daily timeframe
    python -m src.detect_trend_breaks --timeframe daily --all

    # Detect breaks for specific ticker at all timeframes
    python -m src.detect_trend_breaks --ticker AAPL --all-timeframes

    # Detect breaks for all tickers at all available timeframes
    python -m src.detect_trend_breaks --all --all-timeframes

    # Estimate storage requirements
    python -m src.detect_trend_breaks --estimate-only
"""

import argparse
import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pandas as pd
import numpy as np
from decimal import Decimal
import psycopg2
from psycopg2.extras import execute_values

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Database connection configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5433')),  # Port-forwarded from k8s
    'database': os.getenv('DB_NAME', 'trading_data'),
    'user': os.getenv('DB_USER', 'trading'),
    'password': os.getenv('DB_PASSWORD', 'trading123')
}

# Timeframe configurations
# Maps timeframe name to (source_table, source_timeframe, typical_trend_periods)
TIMEFRAME_CONFIG = {
    'daily': {
        'source_table': 'stock_prices',  # Main daily price table
        'source_column': 'timestamp',
        'interval_filter': None,
        'typical_trend_min': 13,
        'typical_trend_max': 18,
        'trend_col': 'close',  # Use close price for trend detection
    },
    '1hour': {
        'source_table': 'stock_prices_intraday',
        'source_column': 'timestamp',
        'interval_filter': '1hour',
        'typical_trend_min': 13,
        'typical_trend_max': 18,
        'trend_col': 'close',
    },
    '5min': {
        'source_table': 'stock_prices_intraday',
        'source_column': 'timestamp',
        'interval_filter': '5min',
        'typical_trend_min': 13,
        'typical_trend_max': 18,
        'trend_col': 'close',
    },
    '1min': {
        'source_table': 'stock_prices_intraday',
        'source_column': 'timestamp',
        'interval_filter': '1min',
        'typical_trend_min': 13,
        'typical_trend_max': 18,
        'trend_col': 'close',
    }
}


def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_tickers_for_timeframe(conn, timeframe: str) -> List[str]:
    """Get list of tickers that have data for the given timeframe."""
    config = TIMEFRAME_CONFIG[timeframe]

    with conn.cursor() as cur:
        if config['interval_filter']:
            cur.execute(f"""
                SELECT DISTINCT ticker
                FROM {config['source_table']}
                WHERE interval_type = %s
                ORDER BY ticker
            """, (config['interval_filter'],))
        else:
            cur.execute(f"""
                SELECT DISTINCT ticker
                FROM {config['source_table']}
                ORDER BY ticker
            """)

        return [row[0] for row in cur.fetchall()]


def fetch_price_data(conn, ticker: str, timeframe: str) -> pd.DataFrame:
    """Fetch price data for a ticker at the specified timeframe."""
    config = TIMEFRAME_CONFIG[timeframe]

    with conn.cursor() as cur:
        if config['interval_filter']:
            cur.execute(f"""
                SELECT
                    {config['source_column']} as timestamp,
                    open, high, low, close, volume
                FROM {config['source_table']}
                WHERE ticker = %s AND interval_type = %s
                ORDER BY {config['source_column']}
            """, (ticker, config['interval_filter']))
        else:
            cur.execute(f"""
                SELECT
                    {config['source_column']} as timestamp,
                    open, high, low, close, volume
                FROM {config['source_table']}
                WHERE ticker = %s
                ORDER BY {config['source_column']}
            """, (ticker,))

        columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        data = cur.fetchall()

    if not data:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(data, columns=columns)
    # Convert Decimal to float for calculations
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)
    df['volume'] = df['volume'].astype(float)

    return df


def detect_trend_breaks(df: pd.DataFrame, trend_col: str = 'close') -> pd.DataFrame:
    """
    Detect trend breaks (peaks and troughs) in price data.

    Uses the local extrema detection method from trend_break_RECOMMENDED.py,
    adapted for multiple timeframes.

    Args:
        df: DataFrame with timestamp and price columns
        trend_col: Column to use for trend detection (default: 'close')

    Returns:
        DataFrame with detected trend breaks
    """
    if len(df) < 3:
        return pd.DataFrame()

    trend = df[trend_col].values
    timestamps = df['timestamp'].values
    volumes = df['volume'].values
    prices = df['close'].values

    breaks = []

    # Calculate average volume for volume ratio
    avg_volume = np.mean(volumes) if len(volumes) > 0 else 1

    for i in range(1, len(df) - 1):
        # Detect PEAK (local maximum)
        if trend[i] > trend[i-1] and trend[i] > trend[i+1]:
            magnitude = min(trend[i] - trend[i-1], trend[i] - trend[i+1])
            breaks.append({
                'timestamp': timestamps[i],
                'break_type': 'peak',
                'direction_before': 'increasing',
                'direction_after': 'decreasing',
                'price_at_break': float(prices[i]),
                'trend_value': float(trend[i]),
                'magnitude': float(magnitude),
                'volume_ratio': float(volumes[i] / avg_volume) if avg_volume > 0 else 1.0,
            })

        # Detect TROUGH (local minimum)
        elif trend[i] < trend[i-1] and trend[i] < trend[i+1]:
            magnitude = min(trend[i-1] - trend[i], trend[i+1] - trend[i])
            breaks.append({
                'timestamp': timestamps[i],
                'break_type': 'trough',
                'direction_before': 'decreasing',
                'direction_after': 'increasing',
                'price_at_break': float(prices[i]),
                'trend_value': float(trend[i]),
                'magnitude': float(magnitude),
                'volume_ratio': float(volumes[i] / avg_volume) if avg_volume > 0 else 1.0,
            })

    if not breaks:
        return pd.DataFrame()

    breaks_df = pd.DataFrame(breaks)

    # Convert timestamps to pandas datetime for consistent comparison
    breaks_df['timestamp'] = pd.to_datetime(breaks_df['timestamp'])

    # Calculate additional metrics
    # Price change % from previous break
    breaks_df['price_change_pct'] = breaks_df['price_at_break'].pct_change() * 100

    # Periods since last break - use index-based counting (simpler and faster)
    breaks_df['periods_since_last_break'] = 1  # Default
    # For each break, find its index in the original df and compute difference
    df_timestamps = pd.to_datetime(df['timestamp'])
    for i in range(1, len(breaks_df)):
        current_ts = breaks_df.iloc[i]['timestamp']
        prev_ts = breaks_df.iloc[i-1]['timestamp']

        # Find indices in original df
        try:
            current_idx = df_timestamps[df_timestamps == current_ts].index[0]
            prev_idx = df_timestamps[df_timestamps == prev_ts].index[0]
            breaks_df.loc[breaks_df.index[i], 'periods_since_last_break'] = current_idx - prev_idx
        except (IndexError, KeyError):
            breaks_df.loc[breaks_df.index[i], 'periods_since_last_break'] = 1

    return breaks_df


def convert_breaks_to_ranges(breaks_df: pd.DataFrame, price_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert trend break points into trend ranges.

    Args:
        breaks_df: DataFrame from detect_trend_breaks()
        price_df: Original price data

    Returns:
        DataFrame with trend ranges
    """
    if len(breaks_df) < 2:
        return pd.DataFrame()

    ranges = []

    # Convert timestamps to same type for comparison
    price_timestamps = pd.to_datetime(price_df['timestamp']).values

    for i in range(len(breaks_df) - 1):
        current = breaks_df.iloc[i]
        next_break = breaks_df.iloc[i + 1]

        # Convert break timestamps
        current_ts = pd.to_datetime(current['timestamp'])
        next_ts = pd.to_datetime(next_break['timestamp'])

        # Get price data within range using numpy comparison
        mask = (price_timestamps > current_ts) & (price_timestamps <= next_ts)
        range_data = price_df[mask]

        if len(range_data) == 0:
            continue

        # Determine trend direction
        trend_direction = 'upward' if current['direction_after'] == 'increasing' else 'downward'

        # Calculate volume trend
        if len(range_data) >= 3:
            vol_first_half = range_data.iloc[:len(range_data)//2]['volume'].mean()
            vol_second_half = range_data.iloc[len(range_data)//2:]['volume'].mean()
            if vol_second_half > vol_first_half * 1.1:
                volume_trend = 'increasing'
            elif vol_second_half < vol_first_half * 0.9:
                volume_trend = 'decreasing'
            else:
                volume_trend = 'flat'
        else:
            volume_trend = 'flat'

        ranges.append({
            'start_timestamp': current['timestamp'],
            'end_timestamp': next_break['timestamp'],
            'trend_direction': trend_direction,
            'start_break_type': current['break_type'],
            'end_break_type': next_break['break_type'],
            'range_periods': len(range_data),
            'start_price': float(current['price_at_break']),
            'end_price': float(next_break['price_at_break']),
            'price_change': float(next_break['price_at_break'] - current['price_at_break']),
            'price_change_pct': float((next_break['price_at_break'] - current['price_at_break']) /
                                     current['price_at_break'] * 100) if current['price_at_break'] != 0 else 0,
            'max_price': float(range_data['high'].max()),
            'min_price': float(range_data['low'].min()),
            'avg_volume': int(range_data['volume'].mean()),
            'total_volume': int(range_data['volume'].sum()),
            'volume_trend': volume_trend,
            'start_magnitude': float(current['magnitude']),
            'end_magnitude': float(next_break['magnitude']),
        })

    return pd.DataFrame(ranges)


def compute_trend_features(price_df: pd.DataFrame, breaks_df: pd.DataFrame,
                          timeframe: str) -> pd.DataFrame:
    """
    Compute ML features for each time point to predict upcoming breaks.

    Args:
        price_df: Original price data
        breaks_df: Detected trend breaks
        timeframe: Timeframe identifier

    Returns:
        DataFrame with features for each time point
    """
    if len(price_df) < 10 or len(breaks_df) < 2:
        return pd.DataFrame()

    config = TIMEFRAME_CONFIG[timeframe]
    typical_min = config['typical_trend_min']
    typical_max = config['typical_trend_max']
    typical_avg = (typical_min + typical_max) / 2

    features = []

    # Ensure timestamps are comparable - reset price_df index
    price_df = price_df.reset_index(drop=True)
    price_df['timestamp'] = pd.to_datetime(price_df['timestamp'])

    # Create a mapping of break timestamps to their index in price_df
    # This avoids repeated timestamp comparisons
    break_indices = []
    for _, brk in breaks_df.iterrows():
        # Find the index in price_df where this break occurred
        matches = price_df[price_df['timestamp'] == brk['timestamp']].index
        if len(matches) > 0:
            break_indices.append({
                'idx': matches[0],
                'timestamp': brk['timestamp'],
                'direction_after': brk['direction_after']
            })

    if len(break_indices) < 2:
        return pd.DataFrame()

    # Sort by index
    break_indices.sort(key=lambda x: x['idx'])

    for i in range(10, len(price_df)):
        row = price_df.iloc[i]
        ts = row['timestamp']

        # Find current trend state (last break before this index)
        prev_breaks = [b for b in break_indices if b['idx'] < i]
        if not prev_breaks:
            continue

        last_break = prev_breaks[-1]
        last_break_idx = last_break['idx']

        # Current trend direction
        current_direction = last_break['direction_after']
        current_direction_simple = 'upward' if current_direction == 'increasing' else 'downward'

        # Periods in current trend (index-based)
        periods_in_trend = i - last_break_idx

        # Trend age ratio (how "old" is this trend relative to typical)
        trend_age_ratio = periods_in_trend / typical_avg

        # Price momentum
        momentum_1 = (row['close'] - price_df.iloc[i-1]['close']) / price_df.iloc[i-1]['close'] * 100 if i > 0 else 0
        momentum_3 = (row['close'] - price_df.iloc[i-3]['close']) / price_df.iloc[i-3]['close'] * 100 if i > 2 else 0
        momentum_5 = (row['close'] - price_df.iloc[i-5]['close']) / price_df.iloc[i-5]['close'] * 100 if i > 4 else 0

        # Volume ratio
        avg_volume = price_df.iloc[max(0, i-20):i]['volume'].mean()
        volume_ratio = row['volume'] / avg_volume if avg_volume > 0 else 1

        # Volatility (using simple range-based measure)
        recent_data = price_df.iloc[max(0, i-20):i+1]
        volatility = recent_data['close'].std() / recent_data['close'].mean() * 100 if len(recent_data) > 1 else 0

        # ATR-like measure
        atr = (recent_data['high'] - recent_data['low']).mean()
        atr_ratio = atr / row['close'] * 100 if row['close'] > 0 else 0

        # Higher highs / lower lows count
        higher_highs = 0
        lower_lows = 0
        for j in range(max(0, i-10), i):
            if j > 0:
                if price_df.iloc[j]['high'] > price_df.iloc[j-1]['high']:
                    higher_highs += 1
                if price_df.iloc[j]['low'] < price_df.iloc[j-1]['low']:
                    lower_lows += 1

        # Future break detection using index-based lookup
        next_break_indices = [b['idx'] for b in break_indices if b['idx'] > i]
        future_breaks_1 = any(idx <= i + 1 for idx in next_break_indices)
        future_breaks_3 = any(idx <= i + 3 for idx in next_break_indices)
        future_breaks_5 = any(idx <= i + 5 for idx in next_break_indices)
        future_breaks_10 = any(idx <= i + 10 for idx in next_break_indices)

        # Periods until next break (index-based)
        if next_break_indices:
            next_break_idx = min(next_break_indices)
            periods_until_break = next_break_idx - i
        else:
            periods_until_break = None

        features.append({
            'timestamp': ts,
            'current_trend_direction': current_direction_simple,
            'periods_in_current_trend': periods_in_trend,
            'trend_age_ratio': round(trend_age_ratio, 4),
            'price_vs_trend': round(momentum_1, 4),  # Simplified
            'momentum_1': round(momentum_1, 4),
            'momentum_3': round(momentum_3, 4),
            'momentum_5': round(momentum_5, 4),
            'volume_ratio': round(volume_ratio, 4),
            'volume_momentum': round((row['volume'] - avg_volume) / avg_volume * 100 if avg_volume > 0 else 0, 4),
            'volatility_ratio': round(volatility, 4),
            'atr_ratio': round(atr_ratio, 4),
            'higher_highs': higher_highs,
            'lower_lows': lower_lows,
            'break_in_next_1': future_breaks_1,
            'break_in_next_3': future_breaks_3,
            'break_in_next_5': future_breaks_5,
            'break_in_next_10': future_breaks_10,
            'periods_until_break': periods_until_break,
        })

    return pd.DataFrame(features)


def insert_trend_breaks(conn, ticker: str, timeframe: str, breaks_df: pd.DataFrame) -> int:
    """Insert trend breaks into database."""
    if breaks_df.empty:
        return 0

    records = []
    for _, row in breaks_df.iterrows():
        records.append((
            ticker,
            row['timestamp'],
            timeframe,
            row['break_type'],
            row['direction_before'],
            row['direction_after'],
            row['price_at_break'],
            row['trend_value'],
            row['magnitude'],
            row.get('price_change_pct'),
            row.get('volume_ratio'),
            row.get('periods_since_last_break'),
            None,  # trend_strength
            'local_extrema'
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO trend_breaks (
                ticker, timestamp, timeframe, break_type, direction_before, direction_after,
                price_at_break, trend_value, magnitude, price_change_pct, volume_ratio,
                periods_since_last_break, trend_strength, detection_method
            ) VALUES %s
            ON CONFLICT (ticker, timestamp, timeframe) DO UPDATE SET
                break_type = EXCLUDED.break_type,
                direction_before = EXCLUDED.direction_before,
                direction_after = EXCLUDED.direction_after,
                price_at_break = EXCLUDED.price_at_break,
                trend_value = EXCLUDED.trend_value,
                magnitude = EXCLUDED.magnitude,
                price_change_pct = EXCLUDED.price_change_pct,
                volume_ratio = EXCLUDED.volume_ratio,
                periods_since_last_break = EXCLUDED.periods_since_last_break
            """,
            records
        )
        conn.commit()

    return len(records)


def insert_trend_ranges(conn, ticker: str, timeframe: str, ranges_df: pd.DataFrame) -> int:
    """Insert trend ranges into database."""
    if ranges_df.empty:
        return 0

    records = []
    for _, row in ranges_df.iterrows():
        records.append((
            ticker,
            timeframe,
            row['start_timestamp'],
            row['end_timestamp'],
            row['trend_direction'],
            row['start_break_type'],
            row['end_break_type'],
            row['range_periods'],
            row['start_price'],
            row['end_price'],
            row['price_change'],
            row['price_change_pct'],
            row['max_price'],
            row['min_price'],
            row['avg_volume'],
            row['total_volume'],
            row['volume_trend'],
            row['start_magnitude'],
            row['end_magnitude'],
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO trend_ranges (
                ticker, timeframe, start_timestamp, end_timestamp, trend_direction,
                start_break_type, end_break_type, range_periods, start_price, end_price,
                price_change, price_change_pct, max_price, min_price, avg_volume,
                total_volume, volume_trend, start_magnitude, end_magnitude
            ) VALUES %s
            ON CONFLICT (ticker, timeframe, start_timestamp) DO UPDATE SET
                end_timestamp = EXCLUDED.end_timestamp,
                trend_direction = EXCLUDED.trend_direction,
                range_periods = EXCLUDED.range_periods,
                price_change = EXCLUDED.price_change,
                price_change_pct = EXCLUDED.price_change_pct
            """,
            records
        )
        conn.commit()

    return len(records)


def insert_trend_features(conn, ticker: str, timeframe: str, features_df: pd.DataFrame) -> int:
    """Insert trend break features into database."""
    if features_df.empty:
        return 0

    records = []
    for _, row in features_df.iterrows():
        records.append((
            ticker,
            row['timestamp'],
            timeframe,
            row['current_trend_direction'],
            row['periods_in_current_trend'],
            row['trend_age_ratio'],
            row['price_vs_trend'],
            row['momentum_1'],
            row['momentum_3'],
            row['momentum_5'],
            row['volume_ratio'],
            row['volume_momentum'],
            row['volatility_ratio'],
            row['atr_ratio'],
            row['higher_highs'],
            row['lower_lows'],
            row['break_in_next_1'],
            row['break_in_next_3'],
            row['break_in_next_5'],
            row['break_in_next_10'],
            row['periods_until_break'],
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO trend_break_features (
                ticker, timestamp, timeframe, current_trend_direction, periods_in_current_trend,
                trend_age_ratio, price_vs_trend, momentum_1, momentum_3, momentum_5,
                volume_ratio, volume_momentum, volatility_ratio, atr_ratio,
                higher_highs, lower_lows, break_in_next_1, break_in_next_3,
                break_in_next_5, break_in_next_10, periods_until_break
            ) VALUES %s
            ON CONFLICT (ticker, timestamp, timeframe) DO UPDATE SET
                current_trend_direction = EXCLUDED.current_trend_direction,
                periods_in_current_trend = EXCLUDED.periods_in_current_trend,
                trend_age_ratio = EXCLUDED.trend_age_ratio,
                break_in_next_1 = EXCLUDED.break_in_next_1,
                break_in_next_3 = EXCLUDED.break_in_next_3,
                break_in_next_5 = EXCLUDED.break_in_next_5,
                break_in_next_10 = EXCLUDED.break_in_next_10,
                periods_until_break = EXCLUDED.periods_until_break
            """,
            records
        )
        conn.commit()

    return len(records)


def process_ticker(conn, ticker: str, timeframe: str,
                   compute_features: bool = True) -> Dict[str, int]:
    """
    Process a single ticker for trend break detection.

    Args:
        conn: Database connection
        ticker: Stock ticker symbol
        timeframe: Timeframe to process
        compute_features: Whether to compute ML features (slower)

    Returns:
        Dict with counts of inserted records
    """
    config = TIMEFRAME_CONFIG[timeframe]

    # Fetch price data
    price_df = fetch_price_data(conn, ticker, timeframe)

    if len(price_df) < 20:
        logger.debug(f"Insufficient data for {ticker} at {timeframe}: {len(price_df)} records")
        return {'breaks': 0, 'ranges': 0, 'features': 0}

    # Detect trend breaks
    breaks_df = detect_trend_breaks(price_df, config['trend_col'])

    if len(breaks_df) < 2:
        logger.debug(f"No trend breaks found for {ticker} at {timeframe}")
        return {'breaks': 0, 'ranges': 0, 'features': 0}

    # Convert to ranges
    ranges_df = convert_breaks_to_ranges(breaks_df, price_df)

    # Insert breaks and ranges
    breaks_inserted = insert_trend_breaks(conn, ticker, timeframe, breaks_df)
    ranges_inserted = insert_trend_ranges(conn, ticker, timeframe, ranges_df)

    # Compute and insert features if requested
    features_inserted = 0
    if compute_features:
        features_df = compute_trend_features(price_df, breaks_df, timeframe)
        if not features_df.empty:
            features_inserted = insert_trend_features(conn, ticker, timeframe, features_df)

    return {
        'breaks': breaks_inserted,
        'ranges': ranges_inserted,
        'features': features_inserted
    }


def estimate_storage(conn) -> Dict:
    """Estimate storage requirements for trend break tables."""
    estimates = {}

    for timeframe, config in TIMEFRAME_CONFIG.items():
        tickers = get_tickers_for_timeframe(conn, timeframe)

        with conn.cursor() as cur:
            if config['interval_filter']:
                cur.execute(f"""
                    SELECT COUNT(*)
                    FROM {config['source_table']}
                    WHERE interval_type = %s
                """, (config['interval_filter'],))
            else:
                cur.execute(f"SELECT COUNT(*) FROM {config['source_table']}")

            total_records = cur.fetchone()[0]

        # Estimate breaks (roughly 1 per 15 periods)
        est_breaks = total_records // 15
        est_ranges = est_breaks - len(tickers)

        estimates[timeframe] = {
            'tickers': len(tickers),
            'source_records': total_records,
            'estimated_breaks': est_breaks,
            'estimated_ranges': max(0, est_ranges),
            'estimated_features': total_records,  # One feature per period
            'estimated_size_mb': (est_breaks * 150 + est_ranges * 200 + total_records * 200) / 1_000_000
        }

    return estimates


def main():
    parser = argparse.ArgumentParser(description='Detect trend breaks at multiple timeframes')
    parser.add_argument('--ticker', type=str, help='Process specific ticker')
    parser.add_argument('--timeframe', type=str, choices=list(TIMEFRAME_CONFIG.keys()),
                       help='Process specific timeframe')
    parser.add_argument('--all', action='store_true', help='Process all tickers')
    parser.add_argument('--all-timeframes', action='store_true', help='Process all timeframes')
    parser.add_argument('--no-features', action='store_true',
                       help='Skip computing ML features (faster)')
    parser.add_argument('--estimate-only', action='store_true',
                       help='Only estimate storage requirements')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='Number of tickers to process before committing')

    args = parser.parse_args()

    # Connect to database
    logger.info("Connecting to database...")
    conn = get_db_connection()

    try:
        # Estimate only mode
        if args.estimate_only:
            estimates = estimate_storage(conn)
            print("\n" + "="*60)
            print("STORAGE ESTIMATES FOR TREND BREAK TABLES")
            print("="*60)

            total_size = 0
            for tf, est in estimates.items():
                print(f"\n{tf.upper()}:")
                print(f"  Tickers: {est['tickers']}")
                print(f"  Source records: {est['source_records']:,}")
                print(f"  Est. breaks: {est['estimated_breaks']:,}")
                print(f"  Est. ranges: {est['estimated_ranges']:,}")
                print(f"  Est. features: {est['estimated_features']:,}")
                print(f"  Est. size: {est['estimated_size_mb']:.1f} MB")
                total_size += est['estimated_size_mb']

            print(f"\n{'='*60}")
            print(f"TOTAL ESTIMATED SIZE: {total_size:.1f} MB ({total_size/1000:.2f} GB)")
            print("="*60)
            return

        # Determine timeframes to process
        if args.all_timeframes:
            timeframes = list(TIMEFRAME_CONFIG.keys())
        elif args.timeframe:
            timeframes = [args.timeframe]
        else:
            timeframes = ['daily']  # Default

        # Process each timeframe
        for timeframe in timeframes:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing timeframe: {timeframe}")
            logger.info("="*60)

            # Determine tickers to process
            if args.ticker:
                tickers = [args.ticker]
            elif args.all:
                tickers = get_tickers_for_timeframe(conn, timeframe)
            else:
                logger.error("Must specify --ticker or --all")
                return

            logger.info(f"Processing {len(tickers)} tickers for {timeframe}")

            total_breaks = 0
            total_ranges = 0
            total_features = 0

            for i, ticker in enumerate(tickers):
                try:
                    result = process_ticker(
                        conn, ticker, timeframe,
                        compute_features=not args.no_features
                    )

                    total_breaks += result['breaks']
                    total_ranges += result['ranges']
                    total_features += result['features']

                    if (i + 1) % 10 == 0:
                        logger.info(f"Progress: {i+1}/{len(tickers)} tickers "
                                  f"({total_breaks} breaks, {total_ranges} ranges)")

                except Exception as e:
                    logger.error(f"Error processing {ticker}: {e}")
                    continue

            logger.info(f"\nCompleted {timeframe}:")
            logger.info(f"  Total breaks inserted: {total_breaks:,}")
            logger.info(f"  Total ranges inserted: {total_ranges:,}")
            logger.info(f"  Total features inserted: {total_features:,}")

    finally:
        conn.close()

    logger.info("\nTrend break detection complete!")


if __name__ == '__main__':
    main()
